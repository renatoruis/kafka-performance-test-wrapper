# Changelog

All notable changes to the Kafka Performance Test Wrapper will be documented in this file.

## [1.0.0] - 2024-02-03

### Initial Release

#### Features
- ✅ **CLI Interface** - Simple command-line interface with `check`, `run`, `render`, and `serve` commands
- ✅ **Producer Testing** - Full support for `kafka-producer-perf-test` with configurable parameters
- ✅ **Consumer Testing** - Consumer performance validation with `kafka-consumer-perf-test`
- ✅ **HTML Reports** - Professional HTML reports with Tailwind CSS and responsive design
- ✅ **MSK IAM Authentication** - Built-in AWS MSK IAM authentication with automatic role assumption
- ✅ **JSON Payloads** - Support for custom JSON message payloads with automatic minification
- ✅ **Docker Integration** - Runs Kafka CLI tools via Docker, no local installation needed
- ✅ **HTTP Server** - Built-in HTTP server to view reports with automatic browser opening
- ✅ **Modular Architecture** - Clean codebase with separated concerns across 10 modules

#### Producer Metrics
- TPS (Transactions Per Second) with actual vs target comparison
- Throughput (MB/sec)
- Latency metrics (avg, max)
- Percentile latencies (P50, P95, P99, P99.9)
- Total records sent

#### Consumer Metrics
- Consumer TPS (messages/sec)
- Data rate (MB/sec)
- Total messages consumed
- Data volume consumed (MB)
- Time window tracking

#### HTML Report Features
- Executive summary with key metrics cards
- Producer performance section with gradient cards
- Consumer performance section with gradient cards
- Latency distribution visualization
- Test configuration details
- Responsive design for mobile/desktop
- Corporate-style color scheme

#### Configuration
- YAML-based configuration
- Support for multiple config profiles
- Configurable producer settings (acks, compression, batching)
- Flexible test parameters (TPS, duration, payload size)
- Custom report directory and HTTP port

#### Developer Features
- Modular library structure (`lib/` directory)
- Clean separation of responsibilities
- Type hints throughout codebase
- Comprehensive documentation
- Example configurations included

#### Files Included
- `kafka_perf.py` - Main CLI script
- `lib/` - Modular library with 10 focused modules
- `configs/` - Example configurations (default, MSK IAM, JSON)
- `payloads/` - Example JSON payload
- `requirements.txt` - Python dependencies
- `README.md` - Complete documentation
- `CHANGELOG.md` - This file
- `LICENSE` - MIT License

---

## Future Enhancements (Planned)

### Metrics & Reporting
- [ ] Additional producer metrics (batch size avg, compression rate, request latency)
- [ ] Export reports to JSON/CSV format
- [ ] Historical comparison between test runs
- [ ] Alert thresholds for metrics

### Testing Features
- [ ] Multi-topic testing
- [ ] Sustained load testing with time-based duration
- [ ] Ramp-up testing (gradual TPS increase)
- [ ] Stress testing mode

### Integration
- [ ] Prometheus metrics export
- [ ] Grafana dashboard templates
- [ ] CI/CD integration examples
- [ ] Kubernetes deployment configs

### Developer Experience
- [ ] Unit tests with pytest
- [ ] Integration tests
- [ ] GitHub Actions CI/CD pipeline
- [ ] Pre-commit hooks
- [ ] Code coverage reports

---

**Version Format:** [Major].[Minor].[Patch]
- **Major**: Breaking changes
- **Minor**: New features (backward compatible)
- **Patch**: Bug fixes and minor improvements
