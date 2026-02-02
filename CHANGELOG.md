# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-02

### Added
- Initial release of kafka-performance-test-wrapper
- Python CLI with subcommands (run, check, render, serve)
- Support for Apache Kafka performance testing tools
- MSK IAM authentication support with auto assume-role
- YAML configuration files
- Human-readable text reports
- Interactive HTML reports with Tailwind CSS
- Built-in HTTP server for viewing reports
- **Auto-generate HTML reports after every test run**
- Support for local Kafka and remote clusters
- Docker-based CLI execution with `--network=host` for localhost
- Configurable test parameters (TPS, payload, duration, etc)
- Producer and consumer performance metrics
- Latency percentiles (P50, P95, P99, P99.9)
- Smart `check` command (validates connection + topic status)
- **JSON payload support** (file-based with auto-minification)
- Smart number formatting (remove unnecessary decimals)

### Features
- Zero external dependencies (only pyyaml)
- Works with any Kafka cluster
- Clean, maintainable Python codebase
- Professional CLI interface
- Automatic report directory creation (`reports/`)
- User-friendly completion messages with next steps
- Corporate-style HTML reports with Tailwind CSS
- MIT License
