#!/usr/bin/env python3
"""
Kafka Performance Test Wrapper
A CLI wrapper for Apache Kafka performance testing tools
"""

import argparse
import os
import subprocess
import sys
import tempfile
import yaml
import json
import re
import http.server
import socketserver
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class KafkaPerfWrapper:
    """Main wrapper class for Kafka performance testing"""
    
    def __init__(self, config_path: str = None):
        self.script_dir = Path(__file__).parent.resolve()
        self.config_path = config_path or self.script_dir / "configs" / "default.yaml"
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not Path(self.config_path).exists():
            print(f"Config file not found: {self.config_path}")
            sys.exit(1)
            
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _get_bootstrap_servers(self) -> str:
        """Get bootstrap servers - when using localhost, we use --network=host"""
        return self.config['kafka']['bootstrap_servers']
    
    def _setup_msk_iam(self) -> tuple[Optional[str], Optional[str]]:
        """Setup MSK IAM authentication if enabled"""
        if not self.config.get('msk_iam', {}).get('enabled', False):
            return None, None
        
        msk_config = self.config['msk_iam']
        aws_region = msk_config.get('region')
        role_arn = msk_config.get('role_arn')
        
        if not aws_region:
            print("MSK IAM requires aws_region")
            sys.exit(1)
        
        # Assume role if ARN provided
        if role_arn:
            try:
                session_name = msk_config.get('session_name', 'kafka-perf')
                cmd = [
                    'aws', 'sts', 'assume-role',
                    '--role-arn', role_arn,
                    '--role-session-name', session_name,
                    '--query', 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]',
                    '--output', 'text'
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                creds = result.stdout.strip().split()
                os.environ['AWS_ACCESS_KEY_ID'] = creds[0]
                os.environ['AWS_SECRET_ACCESS_KEY'] = creds[1]
                os.environ['AWS_SESSION_TOKEN'] = creds[2]
            except subprocess.CalledProcessError as e:
                print(f"Failed to assume role: {e}")
                sys.exit(1)
        
        # Check credentials
        if not os.environ.get('AWS_ACCESS_KEY_ID') or not os.environ.get('AWS_SECRET_ACCESS_KEY'):
            print("MSK IAM requires AWS credentials")
            sys.exit(1)
        
        # Download MSK IAM JAR if needed
        jar_version = msk_config.get('jar_version', '2.3.5')
        cache_dir = self.script_dir / '.cache'
        cache_dir.mkdir(exist_ok=True)
        jar_path = cache_dir / f'aws-msk-iam-auth-{jar_version}.jar'
        
        if not jar_path.exists():
            jar_url = f'https://repo1.maven.org/maven2/software/amazon/msk/aws-msk-iam-auth/{jar_version}/aws-msk-iam-auth-{jar_version}.jar'
            print(f"Downloading MSK IAM auth jar: {jar_url}")
            subprocess.run(['curl', '-fsSL', jar_url, '-o', str(jar_path)], check=True)
        
        # Create producer config
        producer_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.properties')
        producer_config.write(f"""bootstrap.servers={self._get_bootstrap_servers()}
acks={self.config['producer']['acks']}
compression.type={self.config['producer']['compression']}
linger.ms={self.config['producer']['linger_ms']}
batch.size={self.config['producer']['batch_size']}
client.id={self.config['producer'].get('client_id', 'perf-cli')}
security.protocol=SASL_SSL
sasl.mechanism=AWS_MSK_IAM
sasl.jaas.config=software.amazon.msk.auth.iam.IAMLoginModule required;
sasl.client.callback.handler.class=software.amazon.msk.auth.iam.IAMClientCallbackHandler
""")
        producer_config.close()
        
        # Create consumer config
        consumer_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.properties')
        consumer_config.write(f"""bootstrap.servers={self._get_bootstrap_servers()}
security.protocol=SASL_SSL
sasl.mechanism=AWS_MSK_IAM
sasl.jaas.config=software.amazon.msk.auth.iam.IAMLoginModule required;
sasl.client.callback.handler.class=software.amazon.msk.auth.iam.IAMClientCallbackHandler
""")
        consumer_config.close()
        
        return str(jar_path), producer_config.name, consumer_config.name
    
    def _run_kafka_cmd(self, cmd: list, jar_path: str = None, payload_file: str = None) -> subprocess.CompletedProcess:
        """Run Kafka CLI command via Docker"""
        kafka_image = self.config.get('kafka_image', 'confluentinc/cp-kafka:7.6.0')
        
        docker_cmd = ['docker', 'run', '--rm']
        
        # Use host network if connecting to localhost/127.0.0.1
        bootstrap = self.config['kafka']['bootstrap_servers']
        if 'localhost' in bootstrap or '127.0.0.1' in bootstrap:
            docker_cmd.append('--network=host')
        
        # MSK IAM setup
        if jar_path:
            docker_cmd.extend([
                '-v', f'{jar_path}:/opt/msk-iam-auth.jar:ro',
                '-e', 'CLASSPATH=/opt/msk-iam-auth.jar',
                '-e', f'AWS_REGION={self.config["msk_iam"]["region"]}',
                '-e', f'AWS_ACCESS_KEY_ID={os.environ.get("AWS_ACCESS_KEY_ID")}',
                '-e', f'AWS_SECRET_ACCESS_KEY={os.environ.get("AWS_SECRET_ACCESS_KEY")}',
            ])
            if os.environ.get('AWS_SESSION_TOKEN'):
                docker_cmd.extend(['-e', f'AWS_SESSION_TOKEN={os.environ.get("AWS_SESSION_TOKEN")}'])
        
        # Mount payload file if provided
        if payload_file:
            docker_payload_path = '/tmp/payload.json'
            docker_cmd.extend(['-v', f'{payload_file}:{docker_payload_path}:ro'])
            # Update command to use Docker path
            cmd = [docker_payload_path if arg == payload_file else arg for arg in cmd]
        
        docker_cmd.append(kafka_image)
        docker_cmd.extend(cmd)
        
        return subprocess.run(docker_cmd, capture_output=True, text=True)
    
    def _create_payload_file(self, test_config: Dict[str, Any]) -> tuple[Optional[str], int]:
        """Create payload file for producer test - converts JSON to single line
        Returns: (temp_file_path, payload_size_bytes)
        """
        payload_file = test_config.get('payload_file', '')
        
        if not payload_file:
            return None, 0
        
        # Check if path is relative, make it relative to script dir
        payload_path = Path(payload_file)
        if not payload_path.is_absolute():
            payload_path = self.script_dir / payload_file
        
        if not payload_path.exists():
            print(f"⚠️  Payload file not found: {payload_file}")
            print(f"   Looked in: {payload_path}")
            return None, 0
        
        # Read JSON and convert to single line
        # kafka-producer-perf-test reads line by line, so we need to minify the JSON
        try:
            with open(payload_path, 'r') as f:
                json_data = json.load(f)
            
            # Minify JSON
            minified_json = json.dumps(json_data, separators=(',', ':'))
            payload_size = len(minified_json.encode('utf-8'))
            
            # Create temp file with minified JSON (single line)
            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
            temp_file.write(minified_json)
            temp_file.close()
            
            return temp_file.name, payload_size
            
        except json.JSONDecodeError as e:
            print(f"⚠️  Invalid JSON in payload file: {e}")
            return None, 0
        except Exception as e:
            print(f"⚠️  Error reading payload file: {e}")
            return None, 0
    
    def check(self):
        """Validate cluster connection and topic"""
        print("🔍 Validating cluster connection...")
        
        bootstrap = self._get_bootstrap_servers()
        bootstrap_orig = self.config['kafka']['bootstrap_servers']
        topic = self.config['test']['topic']
        
        jar_path = None
        producer_config = None
        consumer_config = None
        
        if self.config.get('msk_iam', {}).get('enabled'):
            jar_path, producer_config, consumer_config = self._setup_msk_iam()
        
        try:
            # Step 1: Test connection by listing topics
            print(f"   → Connecting to {bootstrap_orig}...")
            cmd = ['kafka-topics', '--bootstrap-server', bootstrap, '--list']
            
            if producer_config:
                cmd.extend(['--command-config', producer_config])
            
            result = self._run_kafka_cmd(cmd, jar_path)
            
            if result.returncode != 0:
                print(f"❌ Failed to connect to Kafka cluster:")
                print(result.stderr)
                sys.exit(1)
            
            # Connection successful
            topics = result.stdout.strip().split('\n')
            topics = [t.strip() for t in topics if t.strip()]
            print(f"✅ Connected successfully! Found {len(topics)} topic(s)")
            
            # Step 2: Check if target topic exists
            print(f"\n🔍 Checking topic: {topic}...")
            if topic in topics:
                # Get topic details
                cmd = ['kafka-topics', '--bootstrap-server', bootstrap, '--describe', '--topic', topic]
                if producer_config:
                    cmd.extend(['--command-config', producer_config])
                
                result = self._run_kafka_cmd(cmd, jar_path)
                if result.returncode == 0:
                    print(f"✅ Topic '{topic}' exists")
                    # Show topic details
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            print(f"   {line}")
            else:
                print(f"⚠️  Topic '{topic}' does not exist")
                print(f"   💡 Tip: Run './kafka_perf.py run' to create it automatically")
                print(f"   Or create manually with:")
                print(f"      docker run --rm --network=host confluentinc/cp-kafka:7.6.0 \\")
                print(f"        kafka-topics --bootstrap-server {bootstrap} \\")
                print(f"        --create --topic {topic} \\")
                print(f"        --partitions {self.config['test'].get('partitions', 3)} \\")
                print(f"        --replication-factor {self.config['test'].get('replication_factor', 1)}")
            
        finally:
            if producer_config:
                Path(producer_config).unlink(missing_ok=True)
            if consumer_config:
                Path(consumer_config).unlink(missing_ok=True)
    
    def run(self):
        """Execute performance test"""
        test_config = self.config['test']
        producer_config_obj = self.config['producer']
        consumer_config_obj = self.config.get('consumer', {})
        
        # Calculate num_records
        num_records = test_config.get('num_records', 0)
        if num_records <= 0:
            num_records = test_config['tps'] * test_config['duration_sec']
        
        # Setup report directory
        report_dir = self.config.get('report_dir', '')
        if not report_dir:  # Empty string or None
            reports_dir = self.script_dir / 'reports'
        else:
            reports_dir = Path(report_dir)
        reports_dir.mkdir(exist_ok=True, parents=True)
        
        topic = test_config['topic']
        if test_config.get('topic_prefix'):
            topic = f"{test_config['topic_prefix']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        run_id = datetime.now().strftime('%Y%m%d-%H%M%S')
        run_dir = reports_dir / f'{run_id}-{topic}'
        run_dir.mkdir(exist_ok=True)
        
        producer_out = run_dir / 'producer.out'
        consumer_out = run_dir / 'consumer.out'
        summary_out = run_dir / 'summary.txt'
        
        # Setup MSK IAM
        jar_path = None
        producer_config_file = None
        consumer_config_file = None
        
        if self.config.get('msk_iam', {}).get('enabled'):
            jar_path, producer_config_file, consumer_config_file = self._setup_msk_iam()
        
        # Setup custom payload
        payload_file_path, payload_size = self._create_payload_file(test_config)
        use_custom_payload = payload_file_path is not None
        
        # Use actual payload size if JSON file is used, otherwise use config value
        actual_payload_size = payload_size if use_custom_payload else test_config['payload_bytes']
        
        if use_custom_payload:
            print(f"📝 Using custom JSON payload: {payload_size} bytes")
        
        try:
            bootstrap = self._get_bootstrap_servers()
            bootstrap_orig = self.config['kafka']['bootstrap_servers']
            
            # Print summary
            summary_header = f"""=== Kafka Performance Test ===
Topic: {topic}
Bootstrap: {bootstrap_orig}
Records: {num_records} | TPS: {test_config['tps']} | Payload: {actual_payload_size} bytes | Duration: {test_config['duration_sec']}s
Producer: acks={producer_config_obj['acks']} compression={producer_config_obj['compression']} linger_ms={producer_config_obj['linger_ms']} batch_size={producer_config_obj['batch_size']}
"""
            
            print(summary_header)
            summary_out.write_text(summary_header)
            
            # Create topic if needed
            if test_config.get('create_topic', True):
                cmd = [
                    'kafka-topics',
                    '--bootstrap-server', bootstrap,
                    '--create',
                    '--if-not-exists',
                    '--topic', topic,
                    '--partitions', str(test_config.get('partitions', 3)),
                    '--replication-factor', str(test_config.get('replication_factor', 1))
                ]
                self._run_kafka_cmd(cmd, jar_path)
            
            # Run producer test
            print("[1/2] Running producer perf test...")
            
            # Build producer command
            if producer_config_file:
                producer_cmd = [
                    'kafka-producer-perf-test',
                    '--topic', topic,
                    '--num-records', str(num_records),
                    '--throughput', str(test_config['tps']),
                    '--producer.config', producer_config_file,
                    '--print-metrics'
                ]
            else:
                producer_cmd = [
                    'kafka-producer-perf-test',
                    '--topic', topic,
                    '--num-records', str(num_records),
                    '--throughput', str(test_config['tps']),
                    '--producer-props',
                    f'bootstrap.servers={bootstrap}',
                    f'acks={producer_config_obj["acks"]}',
                    f'compression.type={producer_config_obj["compression"]}',
                    f'linger.ms={producer_config_obj["linger_ms"]}',
                    f'batch.size={producer_config_obj["batch_size"]}',
                    f'client.id={producer_config_obj.get("client_id", "perf-cli")}',
                    '--print-metrics'
                ]
            
            # Add payload file or record size
            if use_custom_payload:
                producer_cmd.extend(['--payload-file', payload_file_path])
            else:
                producer_cmd.extend(['--record-size', str(test_config['payload_bytes'])])
            
            result = self._run_kafka_cmd(producer_cmd, jar_path, payload_file_path if use_custom_payload else None)
            producer_out.write_text(result.stdout + result.stderr)
            
            # Extract producer summary
            producer_summary = None
            for line in result.stdout.split('\n'):
                if 'records sent' in line:
                    producer_summary = line
            
            if producer_summary:
                with open(summary_out, 'a') as f:
                    f.write(f"\nProducer Summary:\n{producer_summary}\n")
            
            # Run consumer test if enabled
            if consumer_config_obj.get('enabled', True):
                print("[2/2] Running consumer perf test...")
                
                consumer_cmd = [
                    'kafka-consumer-perf-test',
                    '--topic', topic,
                    '--messages', str(num_records),
                    '--timeout', str(consumer_config_obj.get('timeout_ms', 120000)),
                    '--group', consumer_config_obj.get('group', 'perf-cli-group'),
                    '--reporting-interval', str(consumer_config_obj.get('reporting_interval_ms', 5000))
                ]
                
                if consumer_config_file:
                    consumer_cmd.extend(['--consumer.config', consumer_config_file])
                else:
                    consumer_cmd.extend(['--bootstrap-server', bootstrap])
                
                if consumer_config_obj.get('from_latest', False):
                    consumer_cmd.append('--from-latest')
                
                result = self._run_kafka_cmd(consumer_cmd, jar_path)
                consumer_out.write_text(result.stdout + result.stderr)
                
                # Extract consumer summary
                consumer_lines = result.stdout.split('\n')
                for line in consumer_lines:
                    if ',' in line and len(line.split(',')) > 5:
                        consumer_summary = line
                        with open(summary_out, 'a') as f:
                            f.write(f"\nConsumer Summary:\n{consumer_summary}\n")
                        break
            
            # Final report location
            report_msg = f"\n\n📄 Report saved to: {run_dir}\n"
            report_msg += f" - Producer output: {producer_out}\n"
            if consumer_config_obj.get('enabled', True):
                report_msg += f" - Consumer output: {consumer_out}\n"
            report_msg += f" - Summary: {summary_out}\n"
            
            print(report_msg)
            
            with open(summary_out, 'a') as f:
                f.write(report_msg)
            
            # Auto-render text report
            print("\n📊 Rendering report...")
            self._render_report(str(summary_out))
            
            # Auto-generate HTML report
            html_path = run_dir / 'report.html'
            print(f"\n🌐 Generating HTML report...")
            self._render_report(str(summary_out), str(html_path))
            
            # Final message with instructions
            print("\n" + "="*60)
            print("✅ Test completed successfully!")
            print("="*60)
            print(f"\n📁 Reports location: {run_dir}")
            print(f"   • Text summary:   {summary_out.name}")
            print(f"   • HTML report:    {html_path.name}")
            print(f"   • Producer logs:  {producer_out.name}")
            if consumer_config_obj.get('enabled', True):
                print(f"   • Consumer logs:  {consumer_out.name}")
            
            print(f"\n💡 View reports in browser:")
            print(f"   ./kafka_perf.py serve")
            print(f"\n   Or open directly:")
            print(f"   open {html_path}")
            print()
            
        finally:
            if producer_config_file:
                Path(producer_config_file).unlink(missing_ok=True)
            if consumer_config_file:
                Path(consumer_config_file).unlink(missing_ok=True)
            if use_custom_payload and payload_file_path:
                # Always delete temp file (it's a minified copy)
                Path(payload_file_path).unlink(missing_ok=True)
    
    def _render_report(self, summary_path: str, html_output: str = None):
        """Render human-readable report from summary"""
        summary_file = Path(summary_path)
        
        if summary_file.is_dir():
            summary_file = summary_file / 'summary.txt'
        
        if not summary_file.exists():
            print(f"Summary file not found: {summary_file}")
            return
        
        content = summary_file.read_text()
        
        # Parse summary
        topic = self._extract_value(content, r'Topic:\s*(.+)')
        bootstrap = self._extract_value(content, r'Bootstrap:\s*(.+)')
        records_line = self._extract_value(content, r'Records:\s*(.+)')
        producer_config_line = self._extract_value(content, r'Producer:\s*(.+)')
        
        producer_line = self._extract_section(content, 'Producer Summary:')
        consumer_line = self._extract_section(content, 'Consumer Summary:')
        
        # Parse test parameters from records_line
        # Format: "60000 | TPS: 1000 | Payload: 1024 bytes | Duration: 60s"
        num_records = self._extract_value(records_line, r'^(\d+)')
        target_tps = self._extract_value(records_line, r'TPS:\s*(\d+)')
        payload_size = self._extract_value(records_line, r'Payload:\s*(\d+)\s*bytes')
        duration = self._extract_value(records_line, r'Duration:\s*(\d+)s')
        
        # Parse producer metrics
        if producer_line:
            parts = producer_line.split(',')
            records = parts[0].strip().replace(' records sent', '')
            
            # Round TPS to integer (no decimal places)
            tps_raw = parts[1].strip().split()[0] if len(parts) > 1 else 'N/A'
            if tps_raw != 'N/A':
                try:
                    tps = f"{int(float(tps_raw))}"
                except:
                    tps = tps_raw
            else:
                tps = 'N/A'
            
            mbps_match = re.search(r'\((.+?)\)', producer_line)
            mbps = mbps_match.group(1) if mbps_match else 'N/A'
            
            # Format latencies: remove .00 if integer, keep decimals if significant
            avg_ms = parts[2].strip().replace(' ms avg latency', '') if len(parts) > 2 else 'N/A'
            if avg_ms != 'N/A':
                try:
                    val = float(avg_ms)
                    # If it's an integer value (7.00), show as integer
                    if val == int(val):
                        avg_ms = f"{int(val)}"
                    else:
                        # Keep decimals (7.97)
                        avg_ms = f"{val:.2f}"
                except:
                    pass
            
            max_ms = parts[3].strip().replace(' ms max latency', '') if len(parts) > 3 else 'N/A'
            if max_ms != 'N/A':
                try:
                    val = float(max_ms)
                    # If it's an integer value (356.00), show as integer
                    if val == int(val):
                        max_ms = f"{int(val)}"
                    else:
                        # Keep decimals (356.45)
                        max_ms = f"{val:.2f}"
                except:
                    pass
            
            p50 = parts[4].strip().replace(' ms 50th', '') if len(parts) > 4 else 'N/A'
            p95 = parts[5].strip().replace(' ms 95th', '') if len(parts) > 5 else 'N/A'
            p99 = parts[6].strip().replace(' ms 99th', '') if len(parts) > 6 else 'N/A'
            p999 = parts[7].strip().replace(' ms 99.9th', '').replace('.', '') if len(parts) > 7 else 'N/A'
        else:
            records = tps = mbps = avg_ms = max_ms = p50 = p95 = p99 = p999 = 'N/A'
        
        # Parse consumer metrics
        if consumer_line:
            parts = consumer_line.split(',')
            consumer_start = parts[0].strip() if len(parts) > 0 else 'N/A'
            consumer_end = parts[1].strip() if len(parts) > 1 else 'N/A'
            consumer_mb = parts[2].strip() if len(parts) > 2 else 'N/A'
            consumer_mbps = parts[3].strip() if len(parts) > 3 else 'N/A'
            consumer_msgs = parts[4].strip() if len(parts) > 4 else 'N/A'
            consumer_msgps = parts[5].strip() if len(parts) > 5 else 'N/A'
        else:
            consumer_start = consumer_end = consumer_mb = consumer_mbps = consumer_msgs = consumer_msgps = 'N/A'
        
        # Generate human-readable report
        report = f"""
╔══════════════════════════════════════════════════════════╗
║       Kafka Performance Report (CLI)                     ║
╚══════════════════════════════════════════════════════════╝

📊 Test Configuration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Topic:        {topic}
Bootstrap:    {bootstrap}
Records:      {records_line}

🚀 Producer Results (TPS is most important)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TPS:          {tps} msg/s ⭐
Throughput:   {mbps}
Records Sent: {records}
Latency Avg:  {avg_ms} ms
Latency Max:  {max_ms} ms
P50/P95/P99:  {p50} / {p95} / {p99} ms
P99.9:        {p999} ms

📥 Consumer Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Window:       {consumer_start} → {consumer_end}
Consumed:     {consumer_msgs} msgs ({consumer_mb} MB)
TPS:          {consumer_msgps} msg/s
Throughput:   {consumer_mbps} MB/s
"""
        
        print(report)
        
        # Generate HTML if requested
        if html_output:
            self._generate_html(html_output, topic, bootstrap, records_line, 
                              tps, mbps, records, avg_ms, max_ms, p50, p95, p99, p999,
                              consumer_start, consumer_end, consumer_msgs, consumer_mb,
                              consumer_msgps, consumer_mbps,
                              producer_config_line, num_records, target_tps, payload_size, duration)
    
    def _extract_value(self, content: str, pattern: str) -> str:
        """Extract value using regex"""
        match = re.search(pattern, content)
        return match.group(1).strip() if match else 'N/A'
    
    def _extract_section(self, content: str, header: str) -> str:
        """Extract section after header"""
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if header in line and i + 1 < len(lines):
                return lines[i + 1].strip()
        return ''
    
    def _generate_html(self, output_path: str, topic, bootstrap, records_line,
                      tps, mbps, records_sent, avg_ms, max_ms, p50, p95, p99, p999,
                      consumer_start, consumer_end, consumer_msgs, consumer_mb,
                      consumer_msgps, consumer_mbps,
                      producer_config='', num_records='N/A', target_tps='N/A', 
                      payload_size='N/A', duration='N/A'):
        """Generate HTML report"""
        # Get current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kafka Performance Report</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        body {{ font-family: 'Inter', sans-serif; }}
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-6 py-6">
            <div class="flex items-center justify-between">
                <div>
                    <h1 class="text-2xl font-bold text-gray-900">Kafka Performance Report</h1>
                    <p class="text-sm text-gray-500 mt-1">Generated on {timestamp}</p>
                </div>
                <div class="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg">
                    <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    <span class="text-sm font-medium text-gray-700">CLI Test</span>
                </div>
            </div>
        </div>
    </div>

    <div class="max-w-7xl mx-auto px-6 py-8">
        
        <!-- Executive Summary -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <div class="text-xs font-medium text-gray-500 uppercase mb-1">Target TPS</div>
                <div class="text-2xl font-bold text-gray-900">{target_tps}</div>
                <div class="text-xs text-gray-500 mt-1">msg/s</div>
            </div>
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <div class="text-xs font-medium text-gray-500 uppercase mb-1">Payload Size</div>
                <div class="text-2xl font-bold text-gray-900">{payload_size}</div>
                <div class="text-xs text-gray-500 mt-1">bytes</div>
            </div>
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <div class="text-xs font-medium text-gray-500 uppercase mb-1">Duration</div>
                <div class="text-2xl font-bold text-gray-900">{duration}</div>
                <div class="text-xs text-gray-500 mt-1">seconds</div>
            </div>
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <div class="text-xs font-medium text-gray-500 uppercase mb-1">Total Records</div>
                <div class="text-2xl font-bold text-gray-900">{num_records}</div>
                <div class="text-xs text-gray-500 mt-1">messages</div>
            </div>
        </div>
        
        <!-- Test Configuration -->
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
            <div class="px-6 py-4 border-b border-gray-200">
                <h2 class="text-lg font-semibold text-gray-900">Test Configuration</h2>
            </div>
            <div class="px-6 py-4">
                <dl class="grid grid-cols-1 gap-4">
                    <div class="flex justify-between py-3 border-b border-gray-100">
                        <dt class="text-sm font-medium text-gray-600">Topic</dt>
                        <dd class="text-sm text-gray-900 font-mono">{topic}</dd>
                    </div>
                    <div class="flex justify-between py-3 border-b border-gray-100">
                        <dt class="text-sm font-medium text-gray-600">Bootstrap Servers</dt>
                        <dd class="text-sm text-gray-900 font-mono">{bootstrap}</dd>
                    </div>
                    <div class="flex justify-between py-3">
                        <dt class="text-sm font-medium text-gray-600">Producer Configuration</dt>
                        <dd class="text-sm text-gray-900 font-mono">{producer_config}</dd>
                    </div>
                </dl>
            </div>
        </div>

        <!-- Producer Metrics -->
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
            <div class="px-6 py-4 border-b border-gray-200">
                <h2 class="text-lg font-semibold text-gray-900">Producer Performance</h2>
            </div>
            
            <!-- Key Metrics Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 p-6">
                <!-- TPS -->
                <div class="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-5 border border-blue-200">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-medium text-blue-800 uppercase tracking-wide">Throughput (TPS)</span>
                        <svg class="w-4 h-4 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path>
                        </svg>
                    </div>
                    <div class="text-3xl font-bold text-blue-900">{tps}</div>
                    <div class="text-xs text-blue-700 mt-1">msg/s · target {target_tps}</div>
                </div>

                <!-- Throughput -->
                <div class="bg-gradient-to-br from-slate-50 to-slate-100 rounded-lg p-5 border border-slate-200">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-medium text-slate-800 uppercase tracking-wide">Data Rate</span>
                    </div>
                    <div class="text-3xl font-bold text-slate-900">{mbps}</div>
                    <div class="text-xs text-slate-700 mt-1">throughput</div>
                </div>

                <!-- Avg Latency -->
                <div class="bg-gradient-to-br from-emerald-50 to-emerald-100 rounded-lg p-5 border border-emerald-200">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-medium text-emerald-800 uppercase tracking-wide">Avg Latency</span>
                    </div>
                    <div class="text-3xl font-bold text-emerald-900">{avg_ms}</div>
                    <div class="text-xs text-emerald-700 mt-1">milliseconds</div>
                </div>

                <!-- Max Latency -->
                <div class="bg-gradient-to-br from-amber-50 to-amber-100 rounded-lg p-5 border border-amber-200">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-medium text-amber-800 uppercase tracking-wide">Max Latency</span>
                    </div>
                    <div class="text-3xl font-bold text-amber-900">{max_ms}</div>
                    <div class="text-xs text-amber-700 mt-1">milliseconds</div>
                </div>
            </div>

            <!-- Latency Percentiles -->
            <div class="px-6 pb-6">
                <h3 class="text-sm font-semibold text-gray-900 mb-4">Latency Distribution</h3>
                <div class="space-y-3">
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <span class="font-medium text-gray-700">P50 (Median)</span>
                            <span class="font-mono text-gray-900">{p50} ms</span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-2">
                            <div class="bg-emerald-500 h-2 rounded-full" style="width: 50%"></div>
                        </div>
                    </div>
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <span class="font-medium text-gray-700">P95</span>
                            <span class="font-mono text-gray-900">{p95} ms</span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-2">
                            <div class="bg-blue-500 h-2 rounded-full" style="width: 75%"></div>
                        </div>
                    </div>
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <span class="font-medium text-gray-700">P99</span>
                            <span class="font-mono text-gray-900">{p99} ms</span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-2">
                            <div class="bg-amber-500 h-2 rounded-full" style="width: 90%"></div>
                        </div>
                    </div>
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <span class="font-medium text-gray-700">P99.9</span>
                            <span class="font-mono text-gray-900">{p999} ms</span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-2">
                            <div class="bg-red-500 h-2 rounded-full" style="width: 95%"></div>
                        </div>
                    </div>
                </div>
                <div class="mt-4 pt-4 border-t border-gray-200">
                    <div class="flex justify-between text-sm">
                        <span class="font-medium text-gray-700">Total Records Sent</span>
                        <span class="font-mono text-gray-900">{records_sent}</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Consumer Metrics -->
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
            <div class="px-6 py-4 border-b border-gray-200">
                <h2 class="text-lg font-semibold text-gray-900">Consumer Performance</h2>
            </div>
            <div class="px-6 py-6">
                <div class="border border-gray-200 rounded-lg overflow-hidden">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Metric</th>
                                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Value</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            <tr>
                                <td class="px-6 py-4 text-sm font-medium text-gray-900">Time Window</td>
                                <td class="px-6 py-4 text-sm text-gray-900 text-right font-mono">{consumer_start} → {consumer_end}</td>
                            </tr>
                            <tr>
                                <td class="px-6 py-4 text-sm font-medium text-gray-900">Messages Consumed</td>
                                <td class="px-6 py-4 text-sm text-gray-900 text-right font-mono">{consumer_msgs}</td>
                            </tr>
                            <tr>
                                <td class="px-6 py-4 text-sm font-medium text-gray-900">Data Consumed</td>
                                <td class="px-6 py-4 text-sm text-gray-900 text-right font-mono">{consumer_mb} MB</td>
                            </tr>
                            <tr>
                                <td class="px-6 py-4 text-sm font-medium text-gray-900">Throughput (TPS)</td>
                                <td class="px-6 py-4 text-sm text-gray-900 text-right font-mono">{consumer_msgps} msg/s</td>
                            </tr>
                            <tr>
                                <td class="px-6 py-4 text-sm font-medium text-gray-900">Data Rate</td>
                                <td class="px-6 py-4 text-sm text-gray-900 text-right font-mono">{consumer_mbps} MB/s</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

    </div>

    <!-- Footer -->
    <div class="bg-white border-t border-gray-200 mt-12">
        <div class="max-w-7xl mx-auto px-6 py-6">
            <div class="flex items-center justify-between text-sm text-gray-500">
                <p>Generated by <span class="font-medium text-gray-700">kafka-performance-test-wrapper</span></p>
                <p>{timestamp}</p>
            </div>
        </div>
    </div>

</body>
</html>
"""
        
        Path(output_path).write_text(html)
        # Silent generation during run, message shown later
    
    def render(self, report_path: str, html: bool = False, output: str = None):
        """Render report from summary file"""
        html_path = None
        if html:
            html_path = output or str(Path(report_path).parent / 'report.html')
        
        self._render_report(report_path, html_path)
        
        if html and html_path:
            print(f"\n🌐 Open in browser: file://{Path(html_path).absolute()}")
    
    def serve(self, port: int = 8000):
        """Start HTTP server to view reports"""
        report_dir = self.config.get('report_dir', '')
        if not report_dir:  # Empty string or None
            reports_dir = self.script_dir / 'reports'
        else:
            reports_dir = Path(report_dir)
        
        if not reports_dir.exists():
            print(f"Reports directory not found: {reports_dir}")
            print("Run a test first to generate reports.")
            sys.exit(1)
        
        os.chdir(reports_dir)
        
        handler = http.server.SimpleHTTPRequestHandler
        
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"🌐 Serving reports at http://localhost:{port}")
            print(f"📁 Directory: {reports_dir}")
            print("Press Ctrl+C to stop")
            
            # Try to open browser
            try:
                webbrowser.open(f'http://localhost:{port}')
            except:
                pass
            
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n\n👋 Server stopped")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Kafka Performance Test Wrapper - CLI tool for Kafka performance testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s run                              # Run with default config
  %(prog)s run --config configs/msk.yaml    # Run with custom config
  %(prog)s check                            # Validate cluster connection
  %(prog)s render reports/<run>             # Render text report
  %(prog)s render reports/<run> --html      # Generate HTML report
  %(prog)s serve                            # Start HTTP server for reports
  %(prog)s serve --port 9000                # Serve on custom port

Repository: https://github.com/renatoruis/kafka-performance-test-wrapper
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # run command
    run_parser = subparsers.add_parser('run', help='Run performance test')
    run_parser.add_argument('--config', '-c', 
                           default='configs/default.yaml',
                           help='Config file path (default: configs/default.yaml)')
    
    # check command
    check_parser = subparsers.add_parser('check', help='Validate cluster connection and topic')
    check_parser.add_argument('--config', '-c',
                             default='configs/default.yaml',
                             help='Config file path')
    
    # render command
    render_parser = subparsers.add_parser('render', help='Render report from summary')
    render_parser.add_argument('report_path', help='Path to summary.txt or report directory')
    render_parser.add_argument('--html', action='store_true', help='Generate HTML report')
    render_parser.add_argument('--output', '-o', help='Output file path')
    
    # serve command
    serve_parser = subparsers.add_parser('serve', help='Start HTTP server to view reports')
    serve_parser.add_argument('--port', '-p', type=int, default=8000, help='Port (default: 8000)')
    serve_parser.add_argument('--config', '-c',
                             default='configs/default.yaml',
                             help='Config file for report_dir location')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'run':
            wrapper = KafkaPerfWrapper(args.config)
            wrapper.run()
        elif args.command == 'check':
            wrapper = KafkaPerfWrapper(args.config)
            wrapper.check()
        elif args.command == 'render':
            wrapper = KafkaPerfWrapper()
            wrapper.render(args.report_path, args.html, args.output)
        elif args.command == 'serve':
            wrapper = KafkaPerfWrapper(args.config)
            wrapper.serve(args.port)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
