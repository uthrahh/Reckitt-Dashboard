# Contributing

Thanks for your interest in this project. This started as an internship portfolio project but is structured to accept contributions like any standard open-source repository.

## Getting Started

1. Fork the repository and clone your fork
2. Create a virtual environment and install dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Create a feature branch: `git checkout -b feature/your-change`

## Development Guidelines

- **Preserve module boundaries.** Each stage (`ingestion`, `validation`, `transformation`, `modeling`) should remain independently testable — avoid reaching into another module's internals.
- **Type hints and docstrings are expected** on all public functions.
- **No magic numbers/strings** in transformation logic — add them to `config/config.yaml` or a named constant instead.
- **Every behavioral change needs a test.** See `tests/` for existing patterns (small in-memory DataFrames via the shared `spark` fixture in `tests/conftest.py`).
- **Don't reintroduce Spark-native writers** (`.write.csv()`, `.write.parquet()`) for the curated export layer without also solving the Windows Hadoop NativeIO dependency — see `docs/deployment.md` for context.

## Running Tests

```bash
pytest
```

All 39 tests should pass before submitting a pull request. If you add a new module or function, add corresponding tests in the matching `tests/test_*.py` file.

## Pull Request Process

1. Ensure `pytest` passes locally
2. Update `CHANGELOG.md` under an "Unreleased" section
3. Update relevant docs in `docs/` if you changed pipeline behavior
4. Open a PR with a clear description of what changed and why

## Code Style

- Follow PEP 8
- Prefer small, single-purpose functions over long ones
- Comment *why*, not *what* — the code should already say what it does
