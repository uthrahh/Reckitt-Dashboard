# Changelog

All notable changes to this project are documented in this file.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — Final production-readiness pass

### Added
- pytest test suite (39 tests) covering ingestion, validation, cleaning, feature engineering, star schema, and end-to-end pipeline integration
- `src/utils/report.py` — shared console log formatting helpers
- Full documentation set (`docs/architecture.md`, `technical_design.md`, `data_dictionary.md`, `pipeline_flow.md`, `deployment.md`)
- Mermaid architecture diagrams (`docs/diagrams/`)
- Repository metadata files (LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG)
- Structured, timed, per-stage execution logging in `main.py`
- `validate_dimension_uniqueness()` — fail-fast guard before any fact-table join

### Fixed
- **Row explosion bug**: dimension builder used `.select().distinct()`, which produced multiple dimension rows for the same natural key whenever descriptive attributes were inconsistent across source rows — silently turning one-to-many joins into many-to-many joins (742,760-row fact table from an ~11,050-row source). Replaced with `groupBy(natural_key).agg(F.first(..., ignorenulls=True))`.
- **`AssertionError: exprs should not be empty`**: dimensions with no descriptive attributes (e.g. `dim_warehouse`) now use `dropDuplicates()` instead of an empty `groupBy().agg()`.
- **`SparkNumberFormatException`** on numeric placeholder values (`-`, `NA`, `N/A`, `NULL`, blank, whitespace, etc.): numeric string columns are now validated against a whitelist regex before casting; anything that doesn't match becomes `NULL` instead of crashing the cast.
- **Windows `UnsatisfiedLinkError` (Hadoop NativeIO)**: replaced Spark's native `.write.csv()` / `.write.parquet()` with `pandas.DataFrame.to_csv()` for the curated export layer, removing the winutils dependency entirely.
- CSV header whitespace inconsistencies now normalized immediately after ingestion.

### Changed
- `run_cleaning_pipeline()`, `run_feature_engineering()`, and dimension/validation functions now return structured metrics alongside their DataFrames, enabling the professional execution log and making pipeline behavior assertable in tests (rather than only visible in log lines).

## [0.3.0]
- Switched curated output from Spark-native CSV/Parquet writers to CSV (still Spark-native at this point — the Hadoop dependency was resolved in 1.0.0).

## [0.2.0]
- Hardened numeric cleaning against dirty placeholder values.

## [0.1.0]
- Initial PySpark ETL pipeline: ingestion, validation, cleaning, feature engineering, star schema build, Parquet export.
