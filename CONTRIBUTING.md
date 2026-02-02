# Contributing to kafka-performance-test-wrapper

Thanks for your interest in contributing! 🎉

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test your changes
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Development Setup

```bash
git clone git@github.com:renatoruis/kafka-performance-test-wrapper.git
cd kafka-performance-test-wrapper
pip3 install -r requirements.txt
```

## Testing Changes

```bash
# Test with local Kafka
./kafka_perf.py run --config configs/default.yaml

# Test check command
./kafka_perf.py check

# Test report rendering
./kafka_perf.py render reports/<latest>/

# Test server
./kafka_perf.py serve
```

## Code Style

- Follow PEP 8
- Use type hints where appropriate
- Add docstrings to functions
- Keep functions focused and small

## Reporting Issues

When reporting issues, please include:

- Python version (`python3 --version`)
- Docker version (`docker --version`)
- Config file used
- Full error message
- Steps to reproduce

## Feature Requests

Open an issue with:

- Clear description of the feature
- Use case / motivation
- Example of how it would work

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
