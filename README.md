# Reckitt FMCG Sales Analytics Pipeline

A production-style data engineering pipeline that transforms raw FMCG retail sales data into a Power BI–ready star schema — built with PySpark, validated with automated tests, and designed to run reliably on Windows without a Hadoop/winutils dependency.

> **Portfolio project** built during a Data Engineering internship. Demonstrates ETL design, data quality validation, dimensional modeling, and production-grade Python/PySpark engineering practices.

---

## Business Problem

Reckitt's FMCG sales data is spread across geography, product, store, supplier, and inventory dimensions in a single flat export. Business users (sales managers, category managers, supply chain managers, regional heads, executives) need a centralized, trustworthy dataset to power a BI dashboard — without manually cleaning or reconciling raw exports every reporting cycle.

## Objectives

- Ingest raw monthly sales data with an explicit, versioned schema contract
- Validate data quality automatically and fail fast on critical issues
- Clean known data quality problems (dirty numeric placeholders, duplicate rows, missing warehouse IDs) without silently dropping valid records
- Model the data as a star schema optimized for Power BI (VertiPaq-friendly, one-to-many joins only)
- Produce a fully reproducible, tested pipeline suitable for a portfolio review

## Features

- ✅ Explicit PySpark schema (no `inferSchema` — see [technical_design.md](docs/technical_design.md))
- ✅ Automated data quality validation with configurable thresholds
- ✅ Robust cleaning: comma-formatted numbers, placeholder tokens (`-`, `NA`, `N/A`, `NULL`, blank, whitespace), exact-duplicate removal
- ✅ Feature engineering: calendar attributes, price-per-unit, category sales rank (window function), inventory risk flag
- ✅ Star schema with **guaranteed unique dimension natural keys** — dimensions are validated before every fact join, preventing row explosion
- ✅ Windows-safe CSV export (no Hadoop NativeIO / winutils dependency)
- ✅ Structured, professional execution log with per-stage timing
- ✅ 39 automated pytest tests covering ingestion, validation, cleaning, feature engineering, star schema, and full pipeline integration

## Architecture

```
Raw CSV → PySpark Ingestion → Validation → Cleaning → Feature Engineering
        → Star Schema Build (with uniqueness validation) → Curated CSV Export
        → Power BI Dashboard
```

See [docs/diagrams/system_architecture.md](docs/diagrams/system_architecture.md) for the full Mermaid diagram and [docs/architecture.md](docs/architecture.md) for the written design rationale.

## Technology Stack

| Layer | Technology |
|---|---|
| Processing | PySpark 3.5 |
| Language | Python 3.12 |
| Configuration | YAML |
| Testing | pytest |
| Visualization | Power BI |
| Source Control | Git |
| Development | VS Code |
| OS Target | Windows (Hadoop-free), portable to Linux/Mac |

## Project Structure

```
reckitt-fmcg-analytics/
├── config/
│   ├── config.yaml              # paths, thresholds, environment settings
│   └── schema_config.py         # explicit PySpark schema + column constants
├── src/
│   ├── ingestion/                data_loader.py
│   ├── validation/                data_quality.py
│   ├── transformation/            cleaning.py, feature_engineering.py
│   ├── modeling/                  star_schema_builder.py
│   └── utils/                     logger.py, spark_session.py, report.py
├── data/
│   ├── raw/                     # source CSV (not committed — see .gitignore)
│   ├── staging/
│   └── curated/                 # fact_sales.csv + 6 dim_*.csv
├── tests/                        pytest suite (39 tests)
├── docs/                          architecture, technical design, data dictionary, pipeline flow, deployment
│   └── diagrams/                  Mermaid architecture diagrams
├── main.py                       pipeline entrypoint/orchestrator
├── requirements.txt
├── requirements-dev.txt
└── pytest.ini
```

## ETL Workflow / Data Pipeline

1. **Ingestion** — reads the raw CSV with an explicit schema, normalizes column-name whitespace
2. **Validation** — computes null percentages, duplicate row counts, and flags columns exceeding a configurable null threshold
3. **Cleaning** — removes exact duplicates, converts placeholder tokens (`-`, `NA`, blank, etc.) to `NULL` before casting, imputes missing `WAREHOUSE_ID`
4. **Feature Engineering** — adds `Quarter`, `YearMonthKey`, `PricePerUnit`, `CategorySalesRank` (window function), `InventoryRiskFlag`
5. **Star Schema Build** — builds 6 dimension tables + 1 fact table; **validates every dimension has unique natural keys before any join**
6. **Export** — writes each curated table to a flat CSV (`data/curated/*.csv`) via pandas, avoiding the Windows Hadoop NativeIO dependency

Full detail: [docs/pipeline_flow.md](docs/pipeline_flow.md).

## Star Schema

```
fact_sales
 ├─→ dim_date
 ├─→ dim_geography
 ├─→ dim_store
 ├─→ dim_product
 ├─→ dim_supplier
 └─→ dim_warehouse
```

Grain: one `fact_sales` row = one product sold at one store in one month. Full field-level documentation: [docs/data_dictionary.md](docs/data_dictionary.md). Diagram: [docs/diagrams/star_schema.md](docs/diagrams/star_schema.md).

## Power BI Dashboard

The curated CSVs in `data/curated/` are designed to be imported directly into Power BI as a star schema (import mode). Recommended relationships: single-direction, one-to-many, `fact_sales` on the many side. *(Dashboard screenshots to be added after Power BI build phase.)*

`[Screenshot placeholder: Executive Overview page]`
`[Screenshot placeholder: Regional Performance drill-through]`
`[Screenshot placeholder: Inventory & Supply Chain page]`

## How to Run

### Requirements

- Python 3.10+
- Java 11 or 17 (required by PySpark)
- ~500 MB free disk space

### Installation

```bash
git clone <this-repo-url>
cd reckitt-fmcg-analytics
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### Run the pipeline

```bash
python main.py
# or with a custom config:
python main.py --config config/config.yaml
```

Output: `data/curated/fact_sales.csv` + 6 `dim_*.csv` files, plus a full formatted execution log in the terminal.

### Run the tests

```bash
pip install -r requirements-dev.txt
pytest
```

See [docs/deployment.md](docs/deployment.md) for troubleshooting (including the Windows Hadoop NativeIO issue this project's export layer was specifically designed to avoid).

## Future Improvements

- Migrate curated export from pandas-CSV back to Spark-native Parquet once running in a proper Hadoop-configured environment (better compression, preserves types for Power BI)
- Add Slowly Changing Dimension (Type 2) support for `dim_product` if source data begins including change timestamps
- Incremental/append-mode ingestion instead of full reload
- CI pipeline (GitHub Actions) running `pytest` on every push
- Data quality metrics tracked over time (trend dashboard, not just point-in-time)

## Lessons Learned

- **`distinct()` is not a safe deduplication strategy for dimension tables** — it dedupes on the full row, so any attribute-level inconsistency for the same natural key produces multiple dimension rows and silently explodes fact-table joins. `groupBy(natural_key).agg(F.first(...))` is the correct pattern.
- **Validate before you join, not after.** Catching duplicate natural keys after a row explosion means debugging a 700K-row table; catching it before the join means reading a 6-line PASS/FAIL report.
- **Native Parquet/CSV writers assume a properly configured Hadoop environment.** For a local Windows dev setup, `pandas.to_csv()` is a pragmatic, dependency-free alternative — with the explicit tradeoff that it collects data to the driver, which only works at small-to-medium scale.

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgements

- Built as part of a Data Engineering internship project.
- Star schema and dimensional modeling approach informed by Kimball Group methodology.
