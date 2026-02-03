"""Text report generation"""

from pathlib import Path
from typing import Dict


class TextReporter:
    """Generate human-readable text reports"""
    
    def generate(self, metrics: Dict[str, str]) -> str:
        """Generate text report from metrics"""
        report = f"""
╔══════════════════════════════════════════════════════════╗
║       Kafka Performance Report (CLI)                     ║
╚══════════════════════════════════════════════════════════╝

📊 Test Configuration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Topic:        {metrics.get('topic', 'N/A')}
Bootstrap:    {metrics.get('bootstrap', 'N/A')}
Records:      {metrics.get('records_line', 'N/A')}

🚀 Producer Results (TPS is most important)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TPS:          {metrics.get('tps', 'N/A')} msg/s ⭐
Throughput:   {metrics.get('mbps', 'N/A')}
Records Sent: {metrics.get('records', 'N/A')}
Latency Avg:  {metrics.get('avg_ms', 'N/A')} ms
Latency Max:  {metrics.get('max_ms', 'N/A')} ms
P50/P95/P99:  {metrics.get('p50', 'N/A')} / {metrics.get('p95', 'N/A')} / {metrics.get('p99', 'N/A')} ms
P99.9:        {metrics.get('p999', 'N/A')} ms
"""
        
        # Add consumer results if available
        if metrics.get('consumer_msgs') != 'N/A':
            report += f"""
📥 Consumer Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Window:       {metrics.get('consumer_start', 'N/A')} → {metrics.get('consumer_end', 'N/A')}
Duration:     {metrics.get('consumer_duration', 'N/A')}s ⏱️
Consumed:     {metrics.get('consumer_msgs', 'N/A')} msgs ({metrics.get('consumer_mb', 'N/A')} MB)
TPS:          {metrics.get('consumer_msgps', 'N/A')} msg/s ⭐
Throughput:   {metrics.get('consumer_mbps', 'N/A')} MB/s

Fetch Stats:
  Time:       {metrics.get('consumer_fetch_ms', 'N/A')} ms
  Rate:       {metrics.get('consumer_fetch_mbps', 'N/A')} MB/s | {metrics.get('consumer_fetch_msgps', 'N/A')} msg/s
  Rebalance:  {metrics.get('consumer_rebalance_ms', 'N/A')} ms
"""
        
        return report
    
    def save(self, report: str, output_path: Path):
        """Save report to file"""
        output_path.write_text(report)
    
    def print(self, report: str):
        """Print report to console"""
        print(report)
