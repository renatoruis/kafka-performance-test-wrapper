"""Parse Kafka performance test results"""

import re
from typing import Dict, Optional


class ResultParser:
    """Parse summary files and extract metrics"""
    
    @staticmethod
    def extract_value(content: str, pattern: str) -> str:
        """Extract value using regex"""
        match = re.search(pattern, content)
        return match.group(1).strip() if match else 'N/A'
    
    @staticmethod
    def extract_section(content: str, header: str) -> str:
        """Extract section after header"""
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if header in line and i + 1 < len(lines):
                return lines[i + 1].strip()
        return ''
    
    def parse_summary(self, content: str) -> Dict[str, str]:
        """Parse complete summary file"""
        # Basic info
        topic = self.extract_value(content, r'Topic:\s*(.+)')
        bootstrap = self.extract_value(content, r'Bootstrap:\s*(.+)')
        records_line = self.extract_value(content, r'Records:\s*(.+)')
        producer_config = self.extract_value(content, r'Producer:\s*(.+)')
        
        # Test parameters
        num_records = self.extract_value(records_line, r'^(\d+)')
        target_tps = self.extract_value(records_line, r'TPS:\s*(\d+)')
        payload_size = self.extract_value(records_line, r'Payload:\s*([0-9.]+\s*(?:bytes|KB|MB))')
        duration = self.extract_value(records_line, r'Duration:\s*(\d+)s')
        
        # Producer metrics
        producer_line = self.extract_section(content, 'Producer Summary:')
        producer_metrics = self._parse_producer_metrics(producer_line)
        
        # Consumer metrics
        consumer_line = self.extract_section(content, 'Consumer Summary:')
        consumer_metrics = self._parse_consumer_metrics(consumer_line)
        
        return {
            'topic': topic,
            'bootstrap': bootstrap,
            'records_line': records_line,
            'producer_config': producer_config,
            'num_records': num_records,
            'target_tps': target_tps,
            'payload_size': payload_size,
            'duration': duration,
            **producer_metrics,
            **consumer_metrics
        }
    
    def _parse_producer_metrics(self, producer_line: str) -> Dict[str, str]:
        """Parse producer metrics line"""
        if not producer_line:
            return {
                'records': 'N/A', 'tps': 'N/A', 'mbps': 'N/A',
                'avg_ms': 'N/A', 'max_ms': 'N/A',
                'p50': 'N/A', 'p95': 'N/A', 'p99': 'N/A', 'p999': 'N/A'
            }
        
        parts = producer_line.split(',')
        
        # Records sent
        records = parts[0].strip().replace(' records sent', '')
        
        # TPS (rounded to integer)
        tps_raw = parts[1].strip().split()[0] if len(parts) > 1 else 'N/A'
        tps = str(int(float(tps_raw))) if tps_raw != 'N/A' else 'N/A'
        
        # Throughput
        mbps_match = re.search(r'\((.+?)\)', producer_line)
        mbps = mbps_match.group(1) if mbps_match else 'N/A'
        
        # Latencies (smart formatting)
        avg_ms = self._format_latency(parts[2].strip().replace(' ms avg latency', '')) if len(parts) > 2 else 'N/A'
        max_ms = self._format_latency(parts[3].strip().replace(' ms max latency', '')) if len(parts) > 3 else 'N/A'
        
        # Percentiles
        p50 = parts[4].strip().replace(' ms 50th', '') if len(parts) > 4 else 'N/A'
        p95 = parts[5].strip().replace(' ms 95th', '') if len(parts) > 5 else 'N/A'
        p99 = parts[6].strip().replace(' ms 99th', '') if len(parts) > 6 else 'N/A'
        p999 = parts[7].strip().replace(' ms 99.9th', '').replace('.', '') if len(parts) > 7 else 'N/A'
        
        return {
            'records': records,
            'tps': tps,
            'mbps': mbps,
            'avg_ms': avg_ms,
            'max_ms': max_ms,
            'p50': p50,
            'p95': p95,
            'p99': p99,
            'p999': p999
        }
    
    @staticmethod
    def _format_latency(value: str) -> str:
        """Format latency: remove .00 if integer, keep decimals if significant"""
        if value == 'N/A':
            return value
        try:
            val = float(value)
            if val == int(val):
                return str(int(val))
            else:
                return f"{val:.2f}"
        except:
            return value
    
    def _parse_consumer_metrics(self, consumer_line: str) -> Dict[str, str]:
        """Parse consumer metrics line"""
        if not consumer_line:
            return {
                'consumer_start': 'N/A',
                'consumer_end': 'N/A',
                'consumer_duration': 'N/A',
                'consumer_mb': 'N/A',
                'consumer_mbps': 'N/A',
                'consumer_msgs': 'N/A',
                'consumer_msgps': 'N/A',
                'consumer_rebalance_ms': 'N/A',
                'consumer_fetch_ms': 'N/A',
                'consumer_fetch_mbps': 'N/A',
                'consumer_fetch_msgps': 'N/A'
            }
        
        parts = consumer_line.split(',')
        
        # Format: start.time, end.time, data.consumed.in.MB, MB.sec, data.consumed.in.nMsg, nMsg.sec, rebalance.time.ms, fetch.time.ms, fetch.MB.sec, fetch.nMsg.sec
        # Indices:  0           1          2                   3         4                      5           6                7             8               9
        
        # Parse timestamps and calculate duration
        start_time = parts[0].strip() if len(parts) > 0 else 'N/A'
        end_time = parts[1].strip() if len(parts) > 1 else 'N/A'
        duration = self._calculate_duration(start_time, end_time)
        
        # Format numbers for better readability
        # Data Volume - convert MB to appropriate unit (GB if large, KB/bytes if small)
        consumer_mb_raw = parts[2].strip() if len(parts) > 2 else 'N/A'
        if consumer_mb_raw != 'N/A':
            try:
                mb_val = float(consumer_mb_raw)
                if mb_val < 0.001:  # Less than 1 KB
                    consumer_mb = f"{mb_val * 1024 * 1024:.0f} bytes"
                elif mb_val < 1:  # Less than 1 MB, show in KB
                    consumer_mb = f"{mb_val * 1024:.2f} KB"
                else:
                    consumer_mb = self._format_mb_size(consumer_mb_raw)
            except ValueError:
                consumer_mb = consumer_mb_raw
        else:
            consumer_mb = 'N/A'
        
        # MB/sec throughput - show KB/sec if very small
        mbps_raw = parts[3].strip() if len(parts) > 3 else 'N/A'
        if mbps_raw != 'N/A':
            try:
                mbps_val = float(mbps_raw)
                if mbps_val < 0.01:  # Less than 0.01 MB/s, show in KB/s
                    consumer_mbps = f"{mbps_val * 1024:.2f} KB/s"
                else:
                    consumer_mbps = self._format_number(mbps_raw)
            except ValueError:
                consumer_mbps = mbps_raw
        else:
            consumer_mbps = 'N/A'
        
        # Message count
        consumer_msgs = self._format_number(parts[4].strip() if len(parts) > 4 else 'N/A')
        
        # TPS (nMsg.sec) - show decimals if < 1, otherwise round to integer
        msgps_raw = parts[5].strip() if len(parts) > 5 else 'N/A'
        try:
            if msgps_raw != 'N/A':
                msgps_val = float(msgps_raw)
                if msgps_val < 1:
                    msgps = f"{msgps_val:.2f}"
                else:
                    msgps = str(int(msgps_val))
            else:
                msgps = 'N/A'
        except ValueError:
            msgps = 'N/A'
        
        # Rebalance time
        rebalance_ms = self._format_number(parts[6].strip() if len(parts) > 6 else 'N/A')
        
        # Fetch metrics
        fetch_ms = self._format_number(parts[7].strip() if len(parts) > 7 else 'N/A')
        
        # Fetch MB/sec - show KB/sec if very small
        fetch_mbps_raw = parts[8].strip() if len(parts) > 8 else 'N/A'
        if fetch_mbps_raw != 'N/A':
            try:
                fetch_mbps_val = float(fetch_mbps_raw)
                if fetch_mbps_val < 0.01:  # Less than 0.01 MB/s, show in KB/s
                    fetch_mbps = f"{fetch_mbps_val * 1024:.2f} KB/s"
                else:
                    fetch_mbps = self._format_number(fetch_mbps_raw)
            except ValueError:
                fetch_mbps = fetch_mbps_raw
        else:
            fetch_mbps = 'N/A'
        
        # Fetch msg/sec - show decimals if < 1, otherwise round to integer
        fetch_msgps_raw = parts[9].strip() if len(parts) > 9 else 'N/A'
        try:
            if fetch_msgps_raw != 'N/A':
                fetch_msgps_val = float(fetch_msgps_raw)
                if fetch_msgps_val < 1:
                    fetch_msgps = f"{fetch_msgps_val:.2f}"
                else:
                    fetch_msgps = str(int(fetch_msgps_val))
            else:
                fetch_msgps = 'N/A'
        except ValueError:
            fetch_msgps = 'N/A'
        
        return {
            'consumer_start': start_time,
            'consumer_end': end_time,
            'consumer_duration': duration,
            'consumer_mb': consumer_mb,
            'consumer_mbps': consumer_mbps,
            'consumer_msgs': consumer_msgs,
            'consumer_msgps': msgps,
            'consumer_rebalance_ms': rebalance_ms,
            'consumer_fetch_ms': fetch_ms,
            'consumer_fetch_mbps': fetch_mbps,
            'consumer_fetch_msgps': fetch_msgps
        }
    
    @staticmethod
    def _format_number(value: str) -> str:
        """Format number with thousands separator and proper decimals"""
        if value == 'N/A':
            return value
        try:
            num = float(value)
            if num == int(num):
                # Integer - add thousands separator
                return f"{int(num):,}"
            else:
                # Float - round to 2 decimals and add separator
                return f"{num:,.2f}"
        except:
            return value
    
    @staticmethod
    def _format_mb_size(value: str) -> str:
        """Format MB value to appropriate unit (MB, GB, TB)"""
        if value == 'N/A':
            return value
        try:
            mb = float(value)
            if mb < 1024:
                return f"{mb:,.2f} MB"
            elif mb < 1024 * 1024:
                return f"{mb / 1024:.2f} GB"
            else:
                return f"{mb / (1024 * 1024):.2f} TB"
        except:
            return value
    
    @staticmethod
    def _calculate_duration(start_str: str, end_str: str) -> str:
        """Calculate duration between two timestamps in seconds"""
        if start_str == 'N/A' or end_str == 'N/A':
            return 'N/A'
        
        try:
            from datetime import datetime
            # Format: 2026-02-03 15:01:02:575
            fmt = '%Y-%m-%d %H:%M:%S:%f'
            start = datetime.strptime(start_str, fmt)
            end = datetime.strptime(end_str, fmt)
            duration_sec = (end - start).total_seconds()
            return f"{duration_sec:.2f}"
        except:
            return 'N/A'
