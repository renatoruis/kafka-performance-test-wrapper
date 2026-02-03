#!/usr/bin/env python3 -u
"""
Kafka Performance Test Wrapper
A CLI wrapper for Apache Kafka performance testing tools
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

from lib import (
    ConfigLoader,
    DockerRunner,
    PayloadManager,
    ResultParser,
    TextReporter,
    HTMLGenerator,
    ReportServer,
    MSKIAMManager,
    format_bytes
)


class KafkaPerfWrapper:
    """Main wrapper class for Kafka performance testing"""
    
    def __init__(self, config_path: str = None):
        self.script_dir = Path(__file__).parent.resolve()
        config_file = config_path or self.script_dir / "configs" / "default.yaml"
        
        # Load configuration
        self.config_loader = ConfigLoader(str(config_file))
        self.config = self.config_loader.config
        
        # Initialize components
        kafka_image = self.config.get('docker', {}).get('kafka_image', 'confluentinc/cp-kafka:7.6.0')
        self.docker_runner = DockerRunner(kafka_image)
        self.payload_manager = PayloadManager(self.script_dir)
        self.parser = ResultParser()
        self.text_reporter = TextReporter()
        self.html_generator = HTMLGenerator()
        self.msk_iam_manager = MSKIAMManager(self.config, self.script_dir)
    
    def check(self):
        """Check Docker and connectivity"""
        print("🔍 Checking environment...")
        
        bootstrap_servers = self.config['kafka']['bootstrap_servers']
        
        # Check Docker
        result = self.docker_runner.run_kafka_cmd(
            ['kafka-topics', '--version'],
            bootstrap_servers=bootstrap_servers
        )
        
        if result.returncode == 0:
            print("✅ Docker OK")
        else:
            print("❌ Docker check failed")
            print(result.stderr)
            sys.exit(1)
        
        # Check Kafka connectivity
        result = self.docker_runner.run_kafka_cmd(
            ['kafka-broker-api-versions', '--bootstrap-server', bootstrap_servers],
            bootstrap_servers=bootstrap_servers
        )
        
        if result.returncode == 0:
            print(f"✅ Kafka connectivity OK ({bootstrap_servers})")
        else:
            print(f"❌ Cannot connect to Kafka ({bootstrap_servers})")
            print(result.stderr)
            sys.exit(1)
        
        print("\n✨ All checks passed!")
    
    def run(self):
        """Run performance test"""
        print("🚀 Starting performance test...")
        
        bootstrap_servers = self.config['kafka']['bootstrap_servers']
        topic = self.config['test']['topic']
        producer_config = self.config['test']['producer']
        test_params = self.config['test']
        
        # Create report directory
        report_dir_str = self.config.get('report', {}).get('dir', '')
        if not report_dir_str:
            report_dir = self.script_dir / 'reports'
        else:
            report_dir = Path(report_dir_str)
            if not report_dir.is_absolute():
                report_dir = self.script_dir / report_dir
        
        report_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test-specific directory
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        test_name = self.config.get('test', {}).get('name', 'performance-test')
        test_dir = report_dir / f"{timestamp}-{test_name}"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup outputs
        producer_out = test_dir / 'producer.out'
        consumer_out = test_dir / 'consumer.out'
        summary_out = test_dir / 'summary.txt'
        
        # Setup MSK IAM if needed
        jar_path = None
        aws_config = None
        producer_config_file = None
        consumer_config_file = None
        
        if self.msk_iam_manager.is_enabled():
            print("🔐 Setting up MSK IAM authentication...")
            jar_path, producer_config_file, consumer_config_file = self.msk_iam_manager.setup(
                bootstrap_servers, producer_config
            )
            aws_config = self.msk_iam_manager.get_aws_config()
        
        # Handle custom JSON payload
        payload_file = test_params.get('payload_file')
        temp_payload_file = None
        actual_payload_size = test_params.get('payload_bytes', 1024)
        
        try:
            if payload_file:
                print(f"📦 Loading JSON payload from: {payload_file}")
                temp_payload_file, payload_size = self.payload_manager.create_payload_file(payload_file)
                if temp_payload_file:
                    actual_payload_size = payload_size
                    print(f"   Payload size: {format_bytes(payload_size)}")
            
            # Build summary header
            payload_size_str = format_bytes(actual_payload_size)
            duration = test_params.get('duration_sec', 60)
            target_tps = test_params.get('target_tps', 1000)
            
            # Auto-calculate num_records if not specified: target_tps × duration_sec
            num_records = test_params.get('num_records')
            if num_records is None:
                num_records = target_tps * duration
            
            summary_header = f"""Kafka Performance Test Report
================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Topic: {topic}
Bootstrap: {bootstrap_servers}
Records: {num_records} records | TPS: {target_tps} | Payload: {payload_size_str} | Duration: {duration}s
Producer: acks={producer_config['acks']}, compression={producer_config['compression']}, linger={producer_config['linger_ms']}ms, batch={producer_config['batch_size']}
"""
            
            with open(summary_out, 'w') as f:
                f.write(summary_header)
            
            print(f"\n📊 Test Configuration:")
            print(f"   Topic: {topic}")
            print(f"   Bootstrap: {bootstrap_servers}")
            if test_params.get('num_records') is None:
                print(f"   Records: {num_records:,} (auto: {target_tps} × {duration}s)")
            else:
                print(f"   Records: {num_records:,}")
            print(f"   Target TPS: {target_tps}")
            print(f"   Payload: {payload_size_str}")
            print(f"   Duration: {duration}s")
            
            # Producer test
            print(f"\n🔥 Running producer test...")
            
            producer_cmd = [
                'kafka-producer-perf-test',
                '--topic', topic,
                '--num-records', str(num_records),
                '--throughput', str(target_tps),
                '--producer.config', '/tmp/producer.properties' if producer_config_file else '/dev/null',
                '--print-metrics'
            ]
            
            # Add payload option
            if temp_payload_file:
                producer_cmd.extend(['--payload-file', temp_payload_file])
            else:
                producer_cmd.extend(['--record-size', str(test_params.get('payload_bytes', 1024))])
            
            # Add producer properties if not using MSK IAM
            if not producer_config_file:
                producer_cmd.extend([
                    '--producer-props',
                    f'bootstrap.servers={bootstrap_servers}',
                    f'acks={producer_config["acks"]}',
                    f'compression.type={producer_config["compression"]}',
                    f'linger.ms={producer_config["linger_ms"]}',
                    f'batch.size={producer_config["batch_size"]}',
                    f'client.id={producer_config.get("client_id", "perf-cli")}'
                ])
            
            result = self.docker_runner.run_kafka_cmd(
                producer_cmd,
                bootstrap_servers=bootstrap_servers,
                jar_path=jar_path,
                payload_file=temp_payload_file,
                aws_config=aws_config
            )
            
            # Save producer output
            with open(producer_out, 'w') as f:
                f.write(result.stdout)
                if result.stderr:
                    f.write(f"\n=== STDERR ===\n{result.stderr}")
            
            if result.returncode != 0:
                print(f"❌ Producer test failed!")
                print(result.stderr)
                sys.exit(1)
            
            # Extract producer summary - get the FINAL summary line (has percentiles)
            producer_lines = result.stdout.split('\n')
            producer_summary = ''
            for line in reversed(producer_lines):
                if 'records sent' in line and 'records/sec' in line:
                    producer_summary = line
                    with open(summary_out, 'a') as f:
                        f.write(f"\nProducer Summary:\n{producer_summary}\n")
                    break
            
            print("✅ Producer test completed")
            
            # Consumer test
            print(f"\n📥 Running consumer test...")
            
            # Use unique consumer group for each test to avoid offset issues
            consumer_group = f"perf-consumer-{timestamp}"
            
            # Create consumer config to read from beginning
            temp_consumer_config_path = None
            if not consumer_config_file:
                # Create consumer config with auto.offset.reset=earliest in /tmp
                temp_consumer_config_path = f'/tmp/consumer-perf-{timestamp}.properties'
                with open(temp_consumer_config_path, 'w') as f:
                    f.write('auto.offset.reset=earliest\n')
                # Set readable permissions for Docker container
                os.chmod(temp_consumer_config_path, 0o644)
            
            # Build consumer command
            # NOTE: Not using --show-detailed-stats to get final aggregate metrics
            consumer_cmd = [
                'kafka-consumer-perf-test',
                '--topic', topic,
                '--bootstrap-server', bootstrap_servers,
                '--messages', str(num_records),
                '--timeout', str(test_params.get('consumer_timeout_ms', 60000)),
                '--group', consumer_group
            ]
            
            # Add consumer config file
            if consumer_config_file:
                # Using MSK IAM config
                consumer_cmd.extend(['--consumer.config', '/tmp/consumer.properties'])
            elif temp_consumer_config_path:
                # Using temp config with auto.offset.reset=earliest
                consumer_cmd.extend(['--consumer.config', temp_consumer_config_path])
            
            result = self.docker_runner.run_kafka_cmd(
                consumer_cmd,
                bootstrap_servers=bootstrap_servers,
                jar_path=jar_path,
                consumer_config=temp_consumer_config_path,
                aws_config=aws_config
            )
            
            # Save consumer output
            with open(consumer_out, 'w') as f:
                f.write(result.stdout)
                if result.stderr:
                    f.write(f"\n=== STDERR ===\n{result.stderr}")
            
            if result.returncode != 0:
                print(f"⚠️  Consumer test failed with exit code: {result.returncode}")
                print(f"💡 Check logs at: {consumer_out}")
                if result.stderr and 'is not a recognized option' not in result.stderr:
                    print(f"❌ Error: {result.stderr[:200]}")
            
            if result.returncode == 0:
                # Extract consumer summary - get last data line (most complete metrics)
                consumer_lines = result.stdout.strip().split('\n')
                consumer_summary = None
                
                for line in reversed(consumer_lines):
                    line = line.strip()
                    if not line or not ',' in line:
                        continue
                    
                    # Skip header line (contains column names)
                    if 'time' in line.lower() and ('threadId' in line or 'start.time' in line or 'data.consumed' in line):
                        continue
                    
                    # Check if it's a valid data line (has numbers)
                    parts = line.split(',')
                    if len(parts) > 5:
                        try:
                            # Try to parse as float to confirm it's data, not header
                            float(parts[2].strip())
                            consumer_summary = line
                            break
                        except (ValueError, IndexError):
                            continue
                
                if consumer_summary:
                    with open(summary_out, 'a') as f:
                        f.write(f"\nConsumer Summary:\n{consumer_summary}\n")
                    print("✅ Consumer test completed")
                else:
                    print("⚠️  Could not extract consumer metrics from output")
            
            print(f"\n📄 Reports saved to: {test_dir}")
            
            # Generate HTML report automatically
            print(f"\n🎨 Generating HTML report...")
            self.render(str(summary_out))
            
            # Final message
            print(f"\n{'='*60}")
            print(f"✅ Test completed successfully!")
            print(f"{'='*60}")
            print(f"\n📁 Reports location: {test_dir}")
            print(f"\n📊 To view the HTML report, run:")
            print(f"   ./kafka_perf.py serve")
            print(f"\n   or open directly:")
            print(f"   {test_dir / 'report.html'}")
            print(f"\n{'='*60}\n")
        
        finally:
            # Cleanup temporary files
            if temp_payload_file and Path(temp_payload_file).exists():
                Path(temp_payload_file).unlink()
            if 'temp_consumer_config_path' in locals() and temp_consumer_config_path and Path(temp_consumer_config_path).exists():
                Path(temp_consumer_config_path).unlink()
            if producer_config_file and Path(producer_config_file).exists():
                Path(producer_config_file).unlink()
            if consumer_config_file and Path(consumer_config_file).exists():
                Path(consumer_config_file).unlink()
    
    def render(self, summary_file: str):
        """Render HTML report from summary file"""
        summary_path = Path(summary_file)
        
        if not summary_path.exists():
            print(f"Summary file not found: {summary_file}")
            sys.exit(1)
        
        # Read and parse summary
        content = summary_path.read_text()
        metrics = self.parser.parse_summary(content)
        
        # Generate reports
        text_report = self.text_reporter.generate(metrics)
        html_report = self.html_generator.generate(metrics)
        
        # Save HTML
        html_path = summary_path.parent / 'report.html'
        self.html_generator.save(html_report, html_path)
        
        print(f"✅ HTML report generated: {html_path}")
    
    def serve(self):
        """Start HTTP server to view reports"""
        report_dir_str = self.config.get('report', {}).get('dir', '')
        if not report_dir_str:
            report_dir = self.script_dir / 'reports'
        else:
            report_dir = Path(report_dir_str)
            if not report_dir.is_absolute():
                report_dir = self.script_dir / report_dir
        
        port = self.config.get('report', {}).get('http_port', 8000)
        server = ReportServer(report_dir, port)
        server.serve()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Kafka Performance Test Wrapper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check environment
  ./kafka_perf.py check
  
  # Run test with default config
  ./kafka_perf.py run
  
  # Run test with custom config
  ./kafka_perf.py run --config configs/msk-iam.yaml
  
  # Generate HTML report from summary
  ./kafka_perf.py render reports/20240101-120000-test/summary.txt
  
  # Start HTTP server to view reports
  ./kafka_perf.py serve
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check Docker and Kafka connectivity')
    check_parser.add_argument('--config', '-c', 
                             help='Path to configuration file (default: configs/default.yaml)')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run performance test')
    run_parser.add_argument('--config', '-c',
                           help='Path to configuration file (default: configs/default.yaml)')
    
    # Render command
    render_parser = subparsers.add_parser('render', help='Generate HTML report from summary file')
    render_parser.add_argument('summary_file', help='Path to summary.txt file')
    
    # Serve command
    serve_parser = subparsers.add_parser('serve', help='Start HTTP server to view reports')
    serve_parser.add_argument('--config', '-c',
                             help='Path to configuration file (default: configs/default.yaml)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Get config from args if available
    config_file = getattr(args, 'config', None)
    
    # Initialize wrapper
    wrapper = KafkaPerfWrapper(config_file)
    
    # Execute command
    if args.command == 'check':
        wrapper.check()
    elif args.command == 'run':
        wrapper.run()
    elif args.command == 'render':
        wrapper.render(args.summary_file)
    elif args.command == 'serve':
        wrapper.serve()


if __name__ == '__main__':
    main()
