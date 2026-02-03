# Kafka Performance Test Wrapper

🚀 Modern CLI wrapper for Apache Kafka performance testing with professional HTML reports and MSK IAM authentication.

## Features

- ✅ **Simple CLI interface** - Run tests with a single command
- ✅ **Professional HTML reports** - Beautiful reports with Tailwind CSS and metrics cards
- ✅ **Producer & Consumer tests** - Complete end-to-end performance validation
- ✅ **MSK IAM authentication** - Built-in support for AWS MSK with IAM
- ✅ **Docker-based** - No local Kafka CLI installation needed
- ✅ **JSON payload support** - Test with real-world message formats
- ✅ **HTTP server** - Built-in web server to view reports
- ✅ **Modular architecture** - Clean, maintainable codebase
- ✅ **Zero external dependencies** - Only requires `pyyaml`

## Quick Start

### 1. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Run Performance Test

```bash
# Local Kafka
./kafka_perf.py run

# MSK with IAM
./kafka_perf.py run --config configs/msk-iam.yaml

# With JSON payload
./kafka_perf.py run --config configs/json-file.yaml
```

### 3. View Reports

After running a test, HTML reports are **automatically generated**. View them with:

```bash
# Start HTTP server (opens browser at http://localhost:8000)
./kafka_perf.py serve

# Or open HTML directly
open reports/20260203-120000-performance-test/report.html
```

## Requirements

- **Docker** - Used to run Kafka CLI tools
- **Python 3.7+** - For the wrapper script
- **pyyaml** - For configuration files

### Network Configuration

When connecting to localhost Kafka (e.g., `localhost:9094`), the tool automatically uses `--network=host` for Docker containers. This allows the container to access the host's network stack.

For remote Kafka clusters (MSK, Confluent Cloud, etc), standard Docker networking is used.

## Commands

### `check` - Verify Environment

Checks Docker installation and Kafka connectivity:

```bash
./kafka_perf.py check
```

### `run` - Execute Performance Test

Runs producer and consumer performance tests:

```bash
# Default config
./kafka_perf.py run

# Custom config
./kafka_perf.py run --config configs/msk-iam.yaml
```

**What it does:**
1. Runs producer test with specified TPS and payload
2. Runs consumer test to validate message consumption
3. Generates summary report with metrics
4. Automatically creates HTML report
5. Saves all outputs to timestamped directory

**Output:**
```
reports/20260203-120000-performance-test/
├── producer.out       # Raw producer output
├── consumer.out       # Raw consumer output
├── summary.txt        # Parsed metrics
└── report.html        # Beautiful HTML report ⭐
```

### `render` - Generate HTML Report

Regenerate HTML report from an existing summary file:

```bash
./kafka_perf.py render reports/20260203-120000-test/summary.txt
```

### `serve` - Start HTTP Server

Start a local HTTP server to view reports:

```bash
./kafka_perf.py serve
```

Opens browser automatically at `http://localhost:8000` showing all test reports.

## Configuration

Configuration is done via YAML files in the `configs/` directory.

### Default Configuration

```yaml
# configs/default.yaml
kafka:
  bootstrap_servers: "localhost:9094"

test:
  name: "performance-test"
  topic: "test-perf"
  num_records: 1000000
  target_tps: 1000
  payload_bytes: 1024
  duration_sec: 60
  consumer_timeout_ms: 60000
  
  producer:
    acks: "all"
    compression: "lz4"
    linger_ms: 10
    batch_size: 32768
    client_id: "perf-producer"

report:
  dir: ""  # Empty = use ./reports
  http_port: 8000
```

### MSK IAM Configuration

For AWS MSK with IAM authentication:

```yaml
# configs/msk-iam.yaml
kafka:
  bootstrap_servers: "b-1.msk.us-east-1.amazonaws.com:9098"

msk_iam:
  enabled: true
  region: "us-east-1"
  role_arn: "arn:aws:iam::123456789:role/KafkaClientRole"
  session_name: "kafka-perf"
  jar_version: "2.3.5"

test:
  name: "msk-performance-test"
  topic: "test-perf"
  # ... rest of test config
```

### JSON Payload Configuration

To test with custom JSON payloads:

```yaml
# configs/json-file.yaml
test:
  name: "json-file-performance-test"
  topic: "test-json"
  num_records: 100000
  target_tps: 1000
  payload_file: "payloads/sample-event.json"  # Path to JSON file
  # ... rest of config
```

**Example payload file:**

```json
{
  "event_id": "evt-12345",
  "timestamp": "2024-01-15T10:30:00Z",
  "user_id": 67890,
  "event_type": "page_view",
  "properties": {
    "page": "/products/laptop",
    "referrer": "https://google.com",
    "device": "desktop"
  },
  "metadata": {
    "ip": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
  }
}
```

**Notes:**
- JSON is automatically minified to a single line (required by `kafka-producer-perf-test`)
- Payload size is calculated from the minified JSON
- Reports show the actual payload size used

## HTML Reports

The tool generates professional HTML reports with:

### Executive Summary
- Target TPS, Payload Size, Duration, Total Records

### Producer Performance
- **Key Metrics Cards:**
  - Throughput (TPS) - Messages per second
  - Data Rate - MB/s throughput
  - Average Latency - Mean response time
  - Max Latency - Peak response time
  
- **Latency Distribution:**
  - P50 (Median)
  - P95
  - P99
  - P99.9

### Consumer Performance
- **Key Metrics Cards:**
  - Throughput (TPS) - Messages consumed per second
  - Data Rate - MB/s consumption rate
  - Messages - Total messages consumed
  - Data Volume - Total MB consumed
  
- **Time Window** - Start and end timestamps

### Test Configuration
- Topic name
- Bootstrap servers
- Producer settings

## Project Structure

```
performance/
├── kafka_perf.py           # Main CLI script (416 lines)
├── lib/                    # Modular library
│   ├── __init__.py        # Library exports
│   ├── config.py          # Configuration loader
│   ├── docker.py          # Docker command executor
│   ├── payload.py         # JSON payload manager
│   ├── parser.py          # Result parser
│   ├── reporter.py        # Text reporter
│   ├── html_generator.py  # HTML report generator
│   ├── server.py          # HTTP server
│   ├── msk_iam.py         # AWS MSK IAM authenticator
│   └── utils.py           # Utility functions
├── configs/               # Configuration files
│   ├── default.yaml       # Default config
│   ├── msk-iam.yaml       # MSK IAM example
│   └── json-file.yaml     # JSON payload example
├── payloads/              # JSON payload files
│   └── sample-event.json  # Example payload
├── reports/               # Generated reports (gitignored)
├── requirements.txt       # Python dependencies
├── LICENSE                # MIT License
├── CHANGELOG.md           # Version history
└── README.md              # This file
```

## Understanding the Metrics

### Producer Metrics

**TPS (Transactions Per Second)**
- Most important metric for producer performance
- Shows actual throughput vs target
- Higher is better (up to cluster limits)

**Latency (ms)**
- Time from sending to acknowledgment
- `avg_ms`: Mean latency across all messages
- `max_ms`: Worst-case latency
- `p50/p95/p99/p99.9`: Percentile latencies

**Throughput (MB/sec)**
- Data rate in megabytes per second
- Depends on message size and TPS

### Consumer Metrics

**TPS (Messages/sec)**
- Consumer throughput
- Should match or exceed producer TPS for real-time processing

**Data Rate (MB/sec)**
- Consumer data consumption rate

**Time Window**
- Actual time taken to consume messages
- Used to calculate TPS

## Troubleshooting

### Docker Connection Issues

**Error:** `Cannot connect to Docker daemon`

**Solution:**
```bash
# Start Docker Desktop (macOS/Windows)
# Or start Docker service (Linux)
sudo systemctl start docker
```

### Kafka Connection Issues

**Error:** `Cannot connect to Kafka`

**Solution:**
1. Verify Kafka is running:
   ```bash
   docker ps | grep kafka
   ```

2. Check bootstrap servers in config:
   ```yaml
   kafka:
     bootstrap_servers: "localhost:9094"  # Correct port?
   ```

3. For localhost, ensure port is accessible

### MSK IAM Issues

**Error:** `MSK IAM requires AWS credentials`

**Solution:**
```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=xxx
export AWS_SECRET_ACCESS_KEY=yyy

# Or configure AWS CLI
aws configure
```

### Permission Issues

**Error:** `Permission denied: ./kafka_perf.py`

**Solution:**
```bash
chmod +x kafka_perf.py
```

## Performance Tips

### Producer Optimization

1. **Batch Size** - Increase for higher throughput:
   ```yaml
   producer:
     batch_size: 65536  # Default: 32768
   ```

2. **Linger Time** - Allow more time for batching:
   ```yaml
   producer:
     linger_ms: 20  # Default: 10
   ```

3. **Compression** - Enable for better network utilization:
   ```yaml
   producer:
     compression: "lz4"  # or snappy, gzip, zstd
   ```

4. **Acknowledgments** - Trade durability for speed:
   ```yaml
   producer:
     acks: "1"  # Instead of "all" for higher throughput
   ```

### Test Design

1. **Warm-up** - Run a small test first to warm up the cluster
2. **Duration** - Longer tests (60s+) give more stable results
3. **Payload Size** - Test with realistic message sizes
4. **TPS Targets** - Start conservative, increase gradually

## Examples

### Basic Local Test

```bash
# 1. Start local Kafka
docker-compose up -d

# 2. Run test
./kafka_perf.py run

# 3. View results
./kafka_perf.py serve
```

### High Throughput Test

```yaml
# configs/high-throughput.yaml
test:
  num_records: 10000000
  target_tps: 100000
  payload_bytes: 512
  
  producer:
    acks: "1"
    compression: "lz4"
    linger_ms: 20
    batch_size: 131072
```

```bash
./kafka_perf.py run --config configs/high-throughput.yaml
```

### JSON Payload Test

```bash
# Create custom payload
cat > payloads/my-event.json <<EOF
{
  "timestamp": "2024-01-15T10:00:00Z",
  "event": "user_action",
  "data": { "action": "click", "target": "button" }
}
EOF

# Update config to use it
./kafka_perf.py run --config configs/json-file.yaml
```

### MSK Production Test

```bash
# Assume AWS role
aws sts assume-role --role-arn arn:aws:iam::xxx:role/KafkaClient

# Run test
./kafka_perf.py run --config configs/msk-iam.yaml
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Support

For issues, questions, or contributions, please use the project's issue tracker.

---

**Made with ❤️ for Kafka performance testing**
