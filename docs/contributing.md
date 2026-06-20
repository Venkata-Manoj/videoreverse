# Contributing to VideoReverse

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/Venkata-Manoj/videoreverse.git
cd videoreverse
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows
```

### 3. Install dependencies

```bash
pip install -e ".[dev,web]"
```

### 4. Set up pre-commit hooks

```bash
pre-commit install
```

## Development Workflow

### Making Changes

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Run the linter: `python scripts/lint.py`
4. Run tests: `python -m pytest tests/unit/ -q`
5. Commit your changes
6. Push and create a pull request

### Code Style

- **Ruff** is used for linting and formatting
- **mypy** is used for type checking (strict mode enabled)
- Follow existing patterns in the codebase
- Add docstrings to public functions

### Running Tests

```bash
# Run all unit tests
python -m pytest tests/unit/ -q

# Run with coverage
python -m pytest tests/unit/ --cov=src --cov=utils -q

# Run specific test file
python -m pytest tests/unit/test_compile.py -v
```

### Pre-commit Hooks

The following hooks run automatically on commit:

- `ruff` — Linting and formatting
- `mypy` — Type checking
- `gitleaks` — Secret detection
- `trailing-whitespace` — Fix trailing whitespace
- `end-of-file-fixer` — Ensure files end with newline
- `check-yaml` — Validate YAML files
- `check-json` — Validate JSON files

## Project Structure

```
src/           — Core pipeline modules
utils/         — Utility functions
config/        — Configuration files
tests/         — Test suite
web/           — Web UI
scripts/       — Development scripts
docs/          — Documentation
```

## Adding a New Model

1. Add template to `config/prompt_templates.json`
2. Add model to `SUPPORTED_MODELS` in `utils/cli.py`
3. Add limits to `config/model_limits.json` if applicable
4. Test with: `python -m src.main ./video.mp4 -m new_model_key`

## Reporting Issues

- Use GitHub Issues for bug reports
- Include video file info, error messages, and steps to reproduce
- For security issues, see [SECURITY.md](../SECURITY.md)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
