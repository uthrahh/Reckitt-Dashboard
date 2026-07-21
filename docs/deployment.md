# Deployment Guide

## Setup

### Prerequisites
- Python 3.10+
- Java 11 or 17 (PySpark requires a JVM; verify with `java -version`)
- Git

### Install

```bash
git clone <this-repo-url>
cd reckitt-fmcg-analytics
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate      # macOS/Linux
pip install -r requirements.txt
```

For running tests, also install dev dependencies:

```bash
pip install -r requirements-dev.txt
```

## Configuration

All configurable values live in `config/config.yaml`:

| Key | Purpose |
|---|---|
| `paths.raw_data` | Path to the source CSV |
| `paths.curated_dir` | Output directory for curated CSVs |
| `paths.logs_dir` | Log file directory |
| `spark.shuffle_partitions` | Tuned low (8) for local/small-data workloads — raise for larger datasets |
| `spark.master` | Spark master URL (`local[*]` for local dev) |
| `data_quality.max_allowed_null_pct` | Null percentage threshold that triggers a validation warning |
| `cleaning.warehouse_id_fill_value` | Sentinel value used to impute missing `WAREHOUSE_ID` |

Place your raw source file at the path configured in `paths.raw_data` (default: `data/raw/reckitt_sales.csv`) before running.

## Execution

```bash
python main.py
python main.py --config config/config.yaml   # explicit config path
```

Expected output: a formatted execution log in the terminal (ingestion → validation → cleaning → feature engineering → star schema → export → timing → data quality report), plus 7 CSV files in `data/curated/`.

## Running Tests

```bash
pytest
```

39 tests across 6 modules (`test_data_loader.py`, `test_validation.py`, `test_cleaning.py`, `test_feature_engineering.py`, `test_star_schema.py`, `test_pipeline.py`). Runtime: ~60–90 seconds (dominated by SparkSession/JVM startup, not test logic).

## Troubleshooting

### `SparkNumberFormatException: The value '-' cannot be cast to BIGINT`
Already handled — `clean_numeric_string_column()` in `cleaning.py` converts any non-numeric placeholder to `NULL` before casting. If you see this error, confirm you're running the current `cleaning.py` and not an older cached `.pyc`.

### `AssertionError: exprs should not be empty`
Already handled — `_build_dimension()` in `star_schema_builder.py` branches explicitly for dimensions with no descriptive attributes (e.g. `dim_warehouse`), using `dropDuplicates()` instead of an empty `groupBy().agg()`.

### `java.lang.UnsatisfiedLinkError: org.apache.hadoop.io.nativeio.NativeIO$Windows.access0`
This occurs when Spark's *native* CSV/Parquet writer is used on Windows without `winutils.exe` configured. This project avoids the issue entirely — `main.write_curated_tables()` uses `pandas.DataFrame.to_csv()` instead of `df.write.csv()`. If you see this error, you're likely running a modified version of `main.py` that reintroduced a native Spark writer.

### `Duplicate natural keys detected — aborting before fact join`
This is the pipeline's uniqueness guard working as intended — it means a dimension has more than one row for the same natural key. The error message lists the offending keys and their row counts. Check the source data for the listed key(s); this should not occur with the current cleaning/modeling logic on well-formed input, but the guard exists specifically to catch it if it ever does.

### Java not found / `JAVA_HOME` errors
Install a JDK (11 or 17) and ensure `JAVA_HOME` is set and `java` is on `PATH`. PySpark will not start without a JVM.

### Tests fail with `'NoneType' object has no attribute 'sc'`
This means a SparkSession was stopped mid-test-run. The test suite's `tests/test_pipeline.py` monkeypatches `SparkSession.stop()` to a no-op specifically to prevent this (since the pipeline's own `spark.stop()` would otherwise tear down the shared session-scoped fixture used by other test modules). If you see this outside the test suite, ensure you're not calling `spark.stop()` and then reusing the same session object elsewhere in your own scripts.
