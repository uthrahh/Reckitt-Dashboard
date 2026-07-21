# Pipeline Flow

Detailed description of each stage executed by `main.run_pipeline()`, in order.

## 1. Ingestion (`src/ingestion/data_loader.py`)

- Reads `config.paths.raw_data` using the explicit schema in `config/schema_config.RAW_SCHEMA`
- `mode="PERMISSIVE"` with `columnNameOfCorruptRecord` set — malformed rows are captured, never silently dropped
- Column names are normalized immediately (whitespace trimmed/collapsed) so no downstream stage needs to defend against header inconsistencies
- Raises `ValueError` if zero rows are loaded (fails fast rather than silently proceeding with an empty dataset)

**Output:** raw, schema-enforced DataFrame.

## 2. Validation (`src/validation/data_quality.py`)

- Computes null count/percentage per column in a single aggregation pass
- Computes duplicate row count
- Flags any column exceeding `config.data_quality.max_allowed_null_pct`
- Read-only — does not modify the DataFrame

**Output:** `DataQualityReport` (structured, not just log lines). Pipeline logs a warning if a known-and-handled column (`WAREHOUSE_ID`) exceeds the threshold, but does not hard-fail.

## 3. Cleaning (`src/transformation/cleaning.py`)

In order:
1. Deduplicate (full-row match)
2. Clean & cast `Value Sales` (→ double) and `Units Sales` (→ long) — placeholder tokens become NULL, comma-formatted numbers are parsed correctly
3. Impute missing `WAREHOUSE_ID` with a configurable sentinel value
4. Trim whitespace on categorical columns

**Output:** cleaned DataFrame + metrics dict (`rows_before`, `rows_after`, `duplicates_removed`, `invalid_numeric` per column, `nulls_filled` per column, `rows_dropped`).

## 4. Feature Engineering (`src/transformation/feature_engineering.py`)

Adds 5 derived columns: `Quarter`, `YearMonthKey`, `PricePerUnit`, `CategorySalesRank`, `InventoryRiskFlag`. See [data_dictionary.md](data_dictionary.md) for formulas.

**Output:** enriched DataFrame + feature metadata list (name + formula, used for logging).

## 5. Star Schema Build (`src/modeling/star_schema_builder.py`)

1. Build 6 dimension tables (`dim_date`, `dim_geography`, `dim_store`, `dim_product`, `dim_supplier`, `dim_warehouse`) — each guaranteed exactly one row per natural key
2. **Validate dimension uniqueness** — prints a PASS/FAIL line per dimension; raises with offending keys if any dimension has duplicates. This runs *before* the fact table is built.
3. Build `fact_sales` by joining the staging DataFrame to each dimension on its natural key and attaching the surrogate FK

**Output:** dict of `{table_name: DataFrame}` — 1 fact + 6 dimensions.

## 6. Export (`main.write_curated_tables`)

- Creates `data/curated/` if it doesn't exist
- For each table: `.toPandas()` → `pandas.DataFrame.to_csv(..., index=False, header=True)`
- Logs rows written, file size, and absolute path per table

**Output:** `data/curated/fact_sales.csv` + 6 `dim_*.csv` files.

## Execution Log

Every run prints a formatted section per stage (Ingestion, Validation, Cleaning, Feature Engineering, Star Schema, Export), a per-stage execution timing summary, and a final Data Quality Report — see the terminal output for the exact format, or run `python main.py` to see it live.
