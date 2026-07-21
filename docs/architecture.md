# Architecture

## System Overview

This pipeline is a single-node, batch ETL system built on PySpark that converts a raw monthly FMCG sales export into a curated star schema for Power BI. It runs locally (no cluster, no cloud dependency) and is organized into clearly separated layers so each stage can be tested, replaced, or scaled independently.

## Components

| Component | Responsibility |
|---|---|
| `config/` | Externalized configuration — paths, thresholds, schema contract. No pipeline logic reads hardcoded paths or magic thresholds directly. |
| `src/ingestion` | Reads the raw CSV with an explicit schema, normalizes column names. |
| `src/validation` | Read-only data quality checks (nulls, duplicates). Never mutates data. |
| `src/transformation` | Cleaning (fixes known issues) and feature engineering (adds derived columns). |
| `src/modeling` | Builds the star schema: 6 dimensions + 1 fact table, with a uniqueness gate before any join. |
| `src/utils` | Cross-cutting concerns: logging, SparkSession factory, console report formatting. |
| `main.py` | Orchestrates the stages in order. Contains no transformation logic itself. |

## Data Flow

```
data/raw/*.csv
      │
      ▼
 Ingestion (explicit schema, column-name normalization)
      │
      ▼
 Validation (null %, duplicate count, threshold check — read-only)
      │
      ▼
 Cleaning (dedup, numeric placeholder → NULL, WAREHOUSE_ID imputation)
      │
      ▼
 Feature Engineering (Quarter, PricePerUnit, CategorySalesRank, InventoryRiskFlag)
      │
      ▼
 Star Schema Build
   ├─ Build 6 dimensions (one row per natural key, guaranteed)
   ├─ Validate dimension uniqueness (fail fast before any join)
   └─ Build fact_sales (join dimensions, attach surrogate keys)
      │
      ▼
 Export (pandas → CSV, one flat file per table)
      │
      ▼
 data/curated/*.csv → Power BI
```

## Design Decisions

### Why layers instead of one script
Each stage (ingestion, validation, cleaning, feature engineering, modeling) is a separate module with pure functions that take a DataFrame and return a DataFrame (or a DataFrame + metrics tuple). This means:
- Each stage is independently unit-testable against small in-memory DataFrames — no disk I/O needed in tests.
- A stage can be swapped without touching the others (e.g., replacing the CSV source with a JDBC source only changes `data_loader.py`).

### Why explicit schema over `inferSchema`
`inferSchema=True` forces an extra full read pass and is unreliable on this dataset specifically — `Value Sales` / `Units Sales` contain comma-formatted numbers that Spark would infer as `StringType` anyway, hiding the need for explicit cleaning.

### Why validation is separate from cleaning
Validation *observes and reports*; cleaning *fixes*. Conflating them makes it impossible to answer "how bad was the raw data, before we touched it?" — which matters both for debugging and for demonstrating due diligence in a portfolio review.

### Why dimension uniqueness is validated before the fact join
A duplicate natural key in any dimension turns what should be a one-to-many join into a many-to-many join, silently multiplying every matching fact row. This pipeline treats that as a hard stop: `validate_dimension_uniqueness()` runs before `build_fact_sales()` and raises with the offending keys rather than allowing a corrupted fact table to be produced.

### Why pandas for the final export, not Spark's native writer
Spark's native `.write.csv()` / `.write.parquet()` route through Hadoop's `NativeIO` layer, which requires `winutils.exe` on Windows. To keep the project runnable on a bare Windows dev machine without that setup, each curated DataFrame is collected via `.toPandas()` and written with `pandas.DataFrame.to_csv()`. This is a deliberate, documented tradeoff — see [technical_design.md](technical_design.md#export-layer) for the scale limitation this introduces.
