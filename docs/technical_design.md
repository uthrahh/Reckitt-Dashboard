# Technical Design

## ETL Architecture

The pipeline follows a linear stage pipeline pattern: each stage is a pure function `DataFrame -> DataFrame` (or `DataFrame -> (DataFrame, metrics)`), orchestrated by `main.run_pipeline()`. No stage reaches into another stage's internals; all cross-stage communication is via the DataFrame (data) and plain dicts/dataclasses (metrics).

## Spark Components Used

| Component | Where | Why |
|---|---|---|
| Explicit `StructType` schema | `config/schema_config.py` | Avoids `inferSchema` read overhead and unreliable type inference on comma-formatted numeric strings |
| `regexp_replace` + `rlike` | `cleaning.py` | Whitelist-pattern validation of numeric strings before casting — never lets an invalid cast reach `.cast()` |
| `Window` + `dense_rank()` | `feature_engineering.py` | Per-category sales ranking, computed once in the data layer instead of at BI-render time |
| `groupBy().agg(F.first(..., ignorenulls=True))` | `star_schema_builder.py` | Collapses a dimension to exactly one row per natural key even when descriptive attributes are inconsistent across source rows |
| `monotonically_increasing_id()` | `star_schema_builder.py` | Surrogate key generation, decoupled from natural/source keys |
| Broadcast joins (auto) | `star_schema_builder.py` | Every dimension is small enough (<12K rows) that Spark's cost-based optimizer auto-broadcasts without an explicit hint |

## Validation Logic

`src/validation/data_quality.py` computes, in a single aggregation pass per check (not N sequential `.filter().count()` calls):
- **Null counts per column** — via `F.sum(F.when(col.isNull(), 1).otherwise(0))` across all columns in one `.agg()` call
- **Duplicate row count** — `df.count() - df.distinct().count()`
- **Threshold breach detection** — any column whose null percentage exceeds `config.data_quality.max_allowed_null_pct` is flagged; the pipeline logs a warning but does not hard-fail, since the one known breaching column (`WAREHOUSE_ID`) has an explicit, documented handling path in cleaning.

Result is a `DataQualityReport` dataclass — structured, not just log lines — so `main.py` can make decisions (and the test suite can assert) on the actual values.

## Cleaning Logic

`src/transformation/cleaning.py`, in order:
1. **Deduplication** — `dropDuplicates()` across all columns (full-row match only; profiling confirmed known duplicates were exact re-ingestion artifacts, not legitimate repeat transactions)
2. **Numeric string cleaning** — for `Value Sales` / `Units Sales`: strip comma thousand-separators, then validate against `^-?\d+(\.\d+)?$`. Anything that doesn't match (`-`, `--`, `---`, blank, whitespace, `NA`, `N/A`, `NULL`, `null`, `None`, `none`, or any other placeholder) becomes `NULL` *before* the cast — this is what prevents `SparkNumberFormatException`. The pattern is a **whitelist**, not a blacklist of known-bad tokens, so it generalizes to placeholder styles not seen during development.
3. **WAREHOUSE_ID imputation** — nulls filled with a sentinel (`"UNKNOWN"`, configurable) rather than dropping rows, preserving otherwise-valid sales records. `dim_warehouse` gets a corresponding `UNKNOWN` member.
4. **Categorical string trimming** — prevents `"Retail"` and `"Retail "` being treated as distinct values in a `GROUP BY`.

Every step returns metrics (counts) alongside the DataFrame, consumed by `main.py`'s structured logging and the Data Quality Report.

## Feature Engineering

`src/transformation/feature_engineering.py` adds only row-level, non-aggregating features (they belong in the data layer because they're reusable as Power BI slicers/attributes, not because they're aggregations):

| Feature | Formula |
|---|---|
| `Quarter` | `CEIL(Month# / 3)` |
| `YearMonthKey` | `Year * 100 + Month#` |
| `PricePerUnit` | `Value Sales / Units Sales` (NULL when Units Sales = 0) |
| `CategorySalesRank` | `DENSE_RANK() OVER (PARTITION BY Category ORDER BY Value Sales DESC)` |
| `InventoryRiskFlag` | `CASE` on `Inventory Status` + `Supplier Lead Time Days` |

True aggregations (SUM, AVG across many rows) are deliberately left to Power BI DAX measures, not computed here — baking them into the data layer would fix a grain that Power BI should be free to re-aggregate.

## Star Schema

See [data_dictionary.md](data_dictionary.md) for full field-level detail. Design highlights:
- 6 dimensions, 1 fact, Type 1 SCD (overwrite — no history tracking; documented upgrade path to Type 2 if source data adds change timestamps)
- Every dimension is built via a shared `_build_dimension()` helper with two explicit code paths (natural-key-only vs. natural-key-plus-attributes) to avoid the `AssertionError: exprs should not be empty` failure mode and guarantee exactly one row per natural key
- `validate_dimension_uniqueness()` runs before `build_fact_sales()` and raises (with offending keys printed) if any dimension fails

## Export Layer

`main.write_curated_tables()` converts each curated Spark DataFrame to pandas via `.toPandas()` and writes with `pandas.DataFrame.to_csv()`, one flat file per table under `data/curated/`.

**Tradeoff, explicitly noted:** `.toPandas()` collects the full table to the driver. This is safe for this dataset (every curated table is well under 1M rows) but is **not** the right approach at genuine big-data scale — at that point, Spark's native writer with a properly configured Hadoop/winutils environment (or a Linux/cluster deployment target) is the correct choice.
