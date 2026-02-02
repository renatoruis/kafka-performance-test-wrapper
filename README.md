# kafka-performance-test-wrapper

🚀 CLI wrapper for Apache Kafka performance testing with support for MSK IAM authentication.

## Features

- ✅ Uses official Kafka CLI tools (`kafka-producer-perf-test`, `kafka-consumer-perf-test`)
- ✅ MSK IAM authentication support (auto assume-role)
- ✅ YAML configuration
- ✅ Human-readable and HTML reports
- ✅ Built-in HTTP server to view reports
- ✅ Zero external dependencies (only pyyaml)
- ✅ Works with any Kafka cluster (local, MSK, Confluent Cloud, etc)

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

# Custom config
./kafka_perf.py run --config my-config.yaml
```

### 3. View Reports

After running a test, HTML reports are **automatically generated**. View them with:

```bash
# Start HTTP server (opens browser at http://localhost:8000)
./kafka_perf.py serve

# Or open HTML directly
open reports/20260202-175030-performance-test/report.html
```

## Commands

### `run` - Execute Performance Test

Runs the complete performance test and automatically generates both text and HTML reports.

```bash
# Default config
./kafka_perf.py run

# Custom config
./kafka_perf.py run --config configs/msk-iam.yaml
```

**What it does:**
1. Creates topic (if `create_topic: true`)
2. Runs producer performance test
3. Runs consumer performance test (if enabled)
4. Generates text summary report
5. **Automatically generates HTML report**
6. Shows command to view reports in browser

**Output:**
```
✅ Test completed successfully!

📁 Reports location: reports/20260202-175030-performance-test
   • Text summary:   summary.txt
   • HTML report:    report.html
   • Producer logs:  producer.out
   • Consumer logs:  consumer.out

💡 View reports in browser:
   ./kafka_perf.py serve
```

### `check` - Validate Connection

Validates cluster connectivity and checks if the target topic exists.

```bash
# Check cluster and topic
./kafka_perf.py check

# Check with custom config
./kafka_perf.py check --config configs/msk-iam.yaml
```

**What it does:**
1. Tests connection to Kafka cluster
2. Lists available topics
3. Checks if configured topic exists
4. Shows topic details if it exists
5. Suggests how to create topic if it doesn't exist

**Note:** `check` does not fail if topic doesn't exist - it just warns you.

### `render` - Regenerate Reports

Re-renders reports from existing test results. **Note:** HTML reports are already auto-generated after each `run`.

```bash
# Text report (terminal)
./kafka_perf.py render reports/20260202-161526-perf-cli/

# Regenerate HTML report
./kafka_perf.py render reports/20260202-161526-perf-cli/ --html

# Custom output location
./kafka_perf.py render reports/20260202-161526-perf-cli/ --html --output my-report.html
```

**Use cases:**
- Re-format existing reports
- Generate custom HTML output location
- View old test results in terminal

### `serve` - HTTP Server for Reports

```bash
# Default port 8000
./kafka_perf.py serve

# Custom port
./kafka_perf.py serve --port 9000
```

## Configuration

### Default Config (`configs/default.yaml`)

```yaml
# Note: When using localhost/127.0.0.1, Docker automatically uses --network=host
kafka:
  bootstrap_servers: "localhost:9094"

use_docker_cli: true
kafka_image: "confluentinc/cp-kafka:7.6.0"

test:
  topic: "performance-test"
  tps: 1000
  duration_sec: 60
  payload_bytes: 1024
  
producer:
  acks: "all"
  compression: "snappy"
  linger_ms: 10
  batch_size: 16384

consumer:
  enabled: true
  group: "perf-cli-group"
  from_latest: false
```

### MSK IAM Config (`configs/msk-iam.yaml`)

```yaml
kafka:
  bootstrap_servers: "b-1.xxx.amazonaws.com:9098,b-2.xxx.amazonaws.com:9098"

msk_iam:
  enabled: true
  region: "us-east-1"
  role_arn: "arn:aws:iam::123456789012:role/MyKafkaRole"
  session_name: "perf-cli"

test:
  topic: "my-performance-test"
  tps: 1000
  duration_sec: 60
  payload_bytes: 1024
```

## Configuration Parameters

### Kafka

| Parameter | Description | Default |
|-----------|-------------|---------|
| `bootstrap_servers` | Kafka brokers | `localhost:9094` |

### JSON Payloads

| Parameter | Description | Example |
|-----------|-------------|---------|
| `payload_file` | Path to JSON file (auto-minified) | `payloads/event.json` |

**Note:** When using `payload_file`, the `payload_bytes` parameter is ignored. The JSON file will be automatically minified to a single line.

### MSK IAM

| Parameter | Description | Required |
|-----------|-------------|----------|
| `enabled` | Enable IAM auth | No |
| `region` | AWS region | Yes (if IAM) |
| `role_arn` | IAM role ARN | No* |
| `session_name` | Session name | No |
| `profile` | AWS profile | No |

*If `role_arn` not provided, uses existing AWS credentials from environment.

### Test

| Parameter | Description | Default |
|-----------|-------------|---------|
| `topic` | Topic name | `performance-test` |
| `topic_prefix` | Generate unique topic | `` |
| `tps` | Target TPS | `1000` |
| `duration_sec` | Test duration | `60` |
| `payload_bytes` | Message size | `1024` |
| `partitions` | Topic partitions | `3` |
| `replication_factor` | Replication factor | `1` |

### Producer

| Parameter | Description | Default |
|-----------|-------------|---------|
| `acks` | Ack mode | `all` |
| `compression` | Compression | `snappy` |
| `linger_ms` | Linger time | `10` |
| `batch_size` | Batch size | `16384` |

### Consumer

| Parameter | Description | Default |
|-----------|-------------|---------|
| `enabled` | Run consumer test | `true` |
| `group` | Consumer group | `perf-cli-group` |
| `from_latest` | Start from latest | `false` |

## Report Output

Each test run **automatically generates**:

```
reports/20260202-161526-performance-test/
├── producer.out         # Raw producer output
├── consumer.out         # Raw consumer output
├── summary.txt          # Text summary report
└── report.html          # HTML report (auto-generated) ✨
```

The HTML report is **always generated** after each test run. No need to run `render` manually!

### Example Report

```
╔══════════════════════════════════════════════════════════╗
║       Kafka Performance Report (CLI)                     ║
╚══════════════════════════════════════════════════════════╝

📊 Test Configuration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Topic:        performance-test
Bootstrap:    localhost:9094
Records:      60000 | TPS: 1000 | Payload: 1024 bytes

🚀 Producer Results (TPS is most important)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TPS:          999.70 msg/s  ⭐
Throughput:   0.98 MB/s
Records Sent: 60000
Latency Avg:  7.90 ms
Latency Max:  307.00 ms
P50/P95/P99:  8 / 14 / 19 ms
P99.9:        44 ms
```

## Use Cases

### 1. Local Kafka Testing

```yaml
# configs/local.yaml
kafka:
  bootstrap_servers: "localhost:9094"

test:
  topic: "test-local"
  tps: 1000
  duration_sec: 30
```

```bash
./kafka_perf.py run --config configs/local.yaml
```

### 2. AWS MSK with IAM

```yaml
# configs/msk-prod.yaml
kafka:
  bootstrap_servers: "b-1.xxx.amazonaws.com:9098,b-2.xxx.amazonaws.com:9098"

msk_iam:
  enabled: true
  region: "us-east-1"
  role_arn: "arn:aws:iam::123456789012:role/KafkaRole"

test:
  topic: "production-test"
  tps: 5000
  duration_sec: 120
  payload_bytes: 2048
```

```bash
./kafka_perf.py run --config configs/msk-prod.yaml
```

### 3. High Volume Test

```yaml
test:
  tps: 10000
  duration_sec: 300
  payload_bytes: 512

producer:
  acks: "1"
  compression: "lz4"
  batch_size: 32768
```

### 4. Large Payload Test

```yaml
test:
  tps: 100
  payload_bytes: 131072  # 128 KB
  
producer:
  compression: "snappy"
  batch_size: 262144  # 256 KB
```

### 5. JSON Payload Test

```yaml
# configs/json-file.yaml
test:
  topic: "json-file-test"
  tps: 1000
  
  # Use external JSON file
  payload_file: "payloads/sample-event.json"
```

```bash
./kafka_perf.py run --config configs/json-file.yaml
```

**How it works:**
- JSON file is automatically minified to a single line
- Each test message uses the same JSON payload
- Perfect for realistic load testing

**Benefits of JSON payloads:**
- ✅ More realistic testing (mimics production data)
- ✅ Better compression ratios (JSON patterns compress well)
- ✅ Test with actual message structure
- ✅ Validate real payload sizes

## Viewing Reports

### Option 1: HTTP Server (Recommended)

```bash
./kafka_perf.py serve
```

- Opens browser at http://localhost:8000
- Lists all report directories
- Click to view HTML reports
- Live refresh as new tests complete

### Option 2: Direct Render

```bash
# Terminal output
./kafka_perf.py render reports/20260202-161526-perf-cli/

# Generate/regenerate HTML
./kafka_perf.py render reports/20260202-161526-perf-cli/ --html
```

### Option 3: Open HTML Directly

```bash
open reports/20260202-161526-perf-cli/report.html
```

## Performance Tuning

### Increase TPS

```yaml
test:
  tps: 10000

producer:
  acks: "1"
  compression: "lz4"
  linger_ms: 5
  batch_size: 32768
```

### Reduce Latency

```yaml
producer:
  acks: "1"
  compression: "none"
  linger_ms: 0
  batch_size: 1024
```

### Large Payloads

```yaml
test:
  payload_bytes: 131072  # 128 KB
  
producer:
  compression: "snappy"
  batch_size: 262144
  linger_ms: 20
```

## Troubleshooting

### Connection Refused

```bash
# Check if Kafka is running
docker ps | grep kafka

# Test connection
./kafka_perf.py check
```

### MSK IAM Issues

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check role
aws iam get-role --role-name MyKafkaRole

# Test assume-role
aws sts assume-role --role-arn arn:aws:iam::123456789012:role/MyKafkaRole --role-session-name test
```

### Permission Denied (JAR download)

```bash
# Manually download
mkdir -p .cache
curl -fsSL https://repo1.maven.org/maven2/software/amazon/msk/aws-msk-iam-auth/2.3.5/aws-msk-iam-auth-2.3.5.jar \
  -o .cache/aws-msk-iam-auth-2.3.5.jar
```

## Requirements

- Python 3.8+
- Docker (for running Kafka CLI tools)
- AWS CLI (for MSK IAM with role assumption)

### Docker Network Mode

When testing with **local Kafka** (localhost/127.0.0.1), the tool automatically uses `--network=host` to allow Docker containers to access the host network. This means:

- ✅ No need to manually configure Docker networking
- ✅ Works seamlessly with `localhost:9094` or `127.0.0.1:9094`
- ✅ Kafka running on host machine is directly accessible

For **remote clusters** (MSK, Confluent Cloud, etc), standard Docker networking is used.

## Installation

```bash
git clone git@github.com:renatoruis/kafka-performance-test-wrapper.git
cd kafka-performance-test-wrapper
pip3 install -r requirements.txt
```

## Project Structure

```
kafka-performance-test-wrapper/
├── kafka_perf.py              # Main CLI
├── requirements.txt           # Python dependencies (pyyaml)
├── configs/
│   ├── default.yaml          # Local Kafka config
│   └── msk-iam.yaml          # MSK IAM config
├── .gitignore
├── LICENSE                    # MIT License
├── CHANGELOG.md
├── CONTRIBUTING.md
└── README.md                  # This file
```

## Repository

- **GitHub**: https://github.com/renatoruis/kafka-performance-test-wrapper
- **License**: MIT

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Author

Renato Ruis
