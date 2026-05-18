# Contributing to VideoReverse

Thank you for your interest in contributing!

## Development Setup

### Prerequisites

- Node.js 22+
- peepshow (`npm i -g peepshow`)
- GEMINI_API_KEY in `.env`

### Quick Start

```bash
# Clone the repository
git clone <your-fork-url>
cd vidrev

# Install dependencies
npm install

# Copy environment template
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Run the pipeline
npm run pipeline -- ./test1.mp4

# Run tests
npm test
```

## Project Structure

```
vidrev/
├── src/           # Source code
├── config/        # Configuration files
├── utils/         # Shared utilities
├── tests/         # Test suite
├── scripts/       # Dev automation
└── docs/          # Documentation
```

## Coding Standards

- Use ESM modules (`import`/`export`)
- No Zod — use lightweight custom validators
- 4-space indentation, UTF-8 charset
- See `.editorconfig` for formatting rules

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests (`npm test`)
5. Commit with clear message
6. Push to your fork
7. Open a Pull Request

## Commit Message Format

```
type(scope): description

[optional body]
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

## Testing

- Unit tests in `tests/unit/`
- Integration tests in `tests/integration/`
- Run all tests: `npm test`

## Code Review Process

- All PRs require review
- Tests must pass
- Lint must pass
- Follow existing code style