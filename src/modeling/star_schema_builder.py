"""
star_schema_builder.py

Builds the curated star schema (1 fact table + 6 dimension tables) from
the cleaned, feature-engineered staging DataFrame.

DESIGN DECISIONS (see docs/architecture.md for full rationale):
- Surrogate keys via monotonically_increasing_id() — insulates the model
  from source-system natural key changes.
- Every dimension is guaranteed to contain EXACTLY ONE row per natural
  key before it is used in any join (see _build_dimension and
  validate_dimension_uniqueness below). This is what prevents fact-table
  row explosion: a dimension with duplicate natural keys turns what
  should be a one-to-many join into a many-to-many join, multiplying
  every matching fact row.
- Fact table joins back to each dimension on the natural key to attach
  the surrogate FK, then drops the natural key + descriptive attributes
  that now live only in the dimension (avoids duplicate storage of
  descriptive text at fact grain).
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from config.schema_config import RawColumns
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Natural key(s) that uniquely identify one row in each dimension.
# Single source of truth, reused by both the builders below and by
# validate_dimension_uniqueness() so validation always checks the same
# keys the builders were designed around.
DIMENSION_NATURAL_KEYS = {
    "dim_date": [RawColumns.YEAR, RawColumns.MONTH_NUM],
    "dim_geography": [RawColumns.CITY],
    "dim_store": [RawColumns.STORE_ID],
    "dim_product": [RawColumns.PRODUCT_ID],
    "dim_supplier": [RawColumns.SUPPLIER_ID],
    "dim_warehouse": [RawColumns.WAREHOUSE_ID],
}


def _build_dimension(df: DataFrame, natural_key_cols: list, key_name: str,
                      extra_cols: list = None) -> DataFrame:
    """
    Generic dimension builder that guarantees exactly one output row per
    natural key. Shared by every dim_* build function to avoid duplicating
    this logic six times.

    Two cases, handled explicitly:

    1. No descriptive attributes (extra_cols is None/empty) — e.g.
       dim_warehouse, which is just the natural key itself. A plain
       groupBy().agg() with zero aggregate expressions is invalid in
       Spark ("AssertionError: exprs should not be empty"), so this case
       uses dropDuplicates(natural_key_cols) instead.

    2. Descriptive attributes present — e.g. dim_product. Uses
       groupBy(natural_key_cols).agg(F.first(col, ignorenulls=True) ...)
       rather than .select(...).distinct(). distinct() would keep a
       separate row for every distinct (key + attribute) COMBINATION,
       so if the same natural key ever appears with even slightly
       inconsistent attribute values across source rows, distinct()
       silently produces multiple dimension rows for one real-world
       entity — which is exactly what caused the fact table row
       explosion. groupBy + first() collapses to one authoritative row
       per key regardless of attribute-level inconsistency.

    Args:
        df: Source DataFrame (staging fact-grain data).
        natural_key_cols: Column(s) that uniquely identify one dimension row.
        key_name: Name of the surrogate key column to generate.
        extra_cols: Additional descriptive attribute columns to carry along.

    Returns:
        Dimension DataFrame with exactly one row per natural key and the
        surrogate key as the first column.
    """
    if not extra_cols:
        dim = df.select(*natural_key_cols).dropDuplicates(natural_key_cols)
    else:
        agg_exprs = [F.first(F.col(c), ignorenulls=True).alias(c) for c in extra_cols]
        dim = df.groupBy(*natural_key_cols).agg(*agg_exprs)

    dim = dim.withColumn(key_name, F.monotonically_increasing_id())
    ordered_cols = [key_name] + natural_key_cols + (extra_cols or [])
    return dim.select(*ordered_cols)


def build_dim_date(df: DataFrame) -> DataFrame:
    """dim_date: one row per (Year, Month#) — grain matches source data (monthly)."""
    return _build_dimension(
        df,
        natural_key_cols=DIMENSION_NATURAL_KEYS["dim_date"],
        key_name="date_key",
        extra_cols=[RawColumns.MONTH, "Quarter", "YearMonthKey"],
    )


def build_dim_geography(df: DataFrame) -> DataFrame:
    """dim_geography: Region -> State -> City hierarchy for map/drill-down visuals."""
    return _build_dimension(
        df,
        natural_key_cols=DIMENSION_NATURAL_KEYS["dim_geography"],
        key_name="geography_key",
        extra_cols=[RawColumns.STATE, RawColumns.REGION],
    )


def build_dim_store(df: DataFrame) -> DataFrame:
    """dim_store: one row per physical store."""
    return _build_dimension(
        df,
        natural_key_cols=DIMENSION_NATURAL_KEYS["dim_store"],
        key_name="store_key",
        extra_cols=[RawColumns.STORE_TYPE, RawColumns.SALES_CHANNEL],
    )


def build_dim_product(df: DataFrame) -> DataFrame:
    """dim_product: one row per product (Category/Segment/Brand/Manufacturer hierarchy)."""
    return _build_dimension(
        df,
        natural_key_cols=DIMENSION_NATURAL_KEYS["dim_product"],
        key_name="product_key",
        extra_cols=[
            RawColumns.BARCODE, RawColumns.CATEGORY, RawColumns.SEGMENT,
            RawColumns.MANUFACTURER, RawColumns.BRAND,
            RawColumns.PACK_SIZE, RawColumns.PACK_UNIT,
        ],
    )


def build_dim_supplier(df: DataFrame) -> DataFrame:
    """dim_supplier: one row per supplier."""
    return _build_dimension(
        df,
        natural_key_cols=DIMENSION_NATURAL_KEYS["dim_supplier"],
        key_name="supplier_key",
        extra_cols=[RawColumns.DISTRIBUTION_CENTER],
    )


def build_dim_warehouse(df: DataFrame) -> DataFrame:
    """dim_warehouse: one row per warehouse, including the 'UNKNOWN' sentinel member."""
    return _build_dimension(
        df,
        natural_key_cols=DIMENSION_NATURAL_KEYS["dim_warehouse"],
        key_name="warehouse_key",
    )


def validate_dimension_uniqueness(dimensions: dict) -> list:
    """
    Verifies every dimension has exactly one row per natural key BEFORE
    any dimension is used in a fact-table join. This is the single check
    that prevents silent row-explosion: a duplicate natural key in any
    dimension turns a one-to-many join into a many-to-many join.

    Prints a PASS/FAIL line per dimension (in the format requested for
    the pipeline's production log). On any FAIL, raises immediately with
    the offending duplicate keys rather than allowing the pipeline to
    continue into the fact join — never silently multiply rows.

    Args:
        dimensions: Dict of {dim_table_name: DataFrame}.

    Returns:
        List of (dim_name, row_count) tuples for tables that passed —
        used by the caller for the star-schema log section.

    Raises:
        ValueError: If any dimension contains duplicate natural keys.
    """
    print("=" * 50)
    print("CHECKING DIMENSION UNIQUENESS")
    print("=" * 50)

    results = []
    failures = []

    for dim_name, dim_df in dimensions.items():
        natural_key_cols = DIMENSION_NATURAL_KEYS[dim_name]
        total_rows = dim_df.count()
        distinct_keys = dim_df.select(*natural_key_cols).distinct().count()

        label = "/".join(natural_key_cols)

        if total_rows == distinct_keys:
            print(f"{label:.<40} PASS")
            results.append((dim_name, total_rows))
        else:
            print(f"{label:.<40} FAIL")
            offending = (
                dim_df.groupBy(*natural_key_cols)
                .count()
                .filter(F.col("count") > 1)
                .limit(20)
                .collect()
            )
            failures.append((dim_name, natural_key_cols, offending))

    print("=" * 50)

    if failures:
        error_lines = ["Duplicate natural keys detected — aborting before fact join:"]
        for dim_name, natural_key_cols, offending_rows in failures:
            error_lines.append(f"  {dim_name} (key: {', '.join(natural_key_cols)}):")
            for row in offending_rows:
                key_vals = {c: row[c] for c in natural_key_cols}
                error_lines.append(f"    {key_vals} -> {row['count']} rows")
        raise ValueError("\n".join(error_lines))

    return results


def build_fact_sales(df: DataFrame, dim_date: DataFrame, dim_geography: DataFrame,
                      dim_store: DataFrame, dim_product: DataFrame,
                      dim_supplier: DataFrame, dim_warehouse: DataFrame) -> DataFrame:
    """
    Builds fact_sales by joining staging data to each dimension on its
    natural key, attaching the surrogate FK, and dropping descriptive
    attributes that now live only in the dimension tables.

    Safe by construction: validate_dimension_uniqueness() is required to
    pass (called in build_star_schema, below) before this function ever
    runs, so every join here is guaranteed one-to-many on the fact side —
    no Cartesian or many-to-many joins are possible.

    Join strategy: broadcast joins are appropriate here — every dimension
    is small (<12K rows, well under Spark's default 10MB broadcast
    threshold after column pruning) — so Spark's cost-based optimizer
    will auto-broadcast without needing an explicit hint.
    """
    fact = (
        df
        .join(dim_date.select(RawColumns.YEAR, RawColumns.MONTH_NUM, "date_key"),
              on=[RawColumns.YEAR, RawColumns.MONTH_NUM], how="left")
        .join(dim_geography.select(RawColumns.CITY, "geography_key"),
              on=RawColumns.CITY, how="left")
        .join(dim_store.select(RawColumns.STORE_ID, "store_key"),
              on=RawColumns.STORE_ID, how="left")
        .join(dim_product.select(RawColumns.PRODUCT_ID, "product_key"),
              on=RawColumns.PRODUCT_ID, how="left")
        .join(dim_supplier.select(RawColumns.SUPPLIER_ID, "supplier_key"),
              on=RawColumns.SUPPLIER_ID, how="left")
        .join(dim_warehouse.select(RawColumns.WAREHOUSE_ID, "warehouse_key"),
              on=RawColumns.WAREHOUSE_ID, how="left")
    )

    fact = fact.select(
        F.monotonically_increasing_id().alias("sale_key"),
        "date_key", "geography_key", "store_key", "product_key",
        "supplier_key", "warehouse_key",
        F.col(RawColumns.VALUE_SALES).alias("value_sales"),
        F.col(RawColumns.UNITS_SALES).alias("units_sales"),
        F.col(RawColumns.SUPPLIER_LEAD_TIME_DAYS).alias("supplier_lead_time_days"),
        F.col(RawColumns.INVENTORY_STATUS).alias("inventory_status"),
        F.col(RawColumns.ORDER_STATUS).alias("order_status"),
        "PricePerUnit", "CategorySalesRank", "InventoryRiskFlag",
        F.col(RawColumns.BATCH_NUMBER).alias("batch_number"),
        F.col(RawColumns.LOT_NUMBER).alias("lot_number"),
    )

    return fact


def build_star_schema(df: DataFrame) -> dict:
    """
    Orchestrates the full star schema build:
    build dimensions -> validate uniqueness (fail fast) -> build fact.

    Args:
        df: Cleaned + feature-engineered staging DataFrame.

    Returns:
        Dict of {table_name: DataFrame} for fact + all dimension tables,
        ready to be written to the curated zone.

    Raises:
        ValueError: If any dimension fails the uniqueness check — the
        fact table is never built on top of an unsafe dimension.
    """
    logger.info("Building star schema...")

    dimensions = {
        "dim_date": build_dim_date(df),
        "dim_geography": build_dim_geography(df),
        "dim_store": build_dim_store(df),
        "dim_product": build_dim_product(df),
        "dim_supplier": build_dim_supplier(df),
        "dim_warehouse": build_dim_warehouse(df),
    }

    # Fail fast, before any join, if a dimension has duplicate natural keys.
    validate_dimension_uniqueness(dimensions)

    fact_sales = build_fact_sales(
        df,
        dimensions["dim_date"], dimensions["dim_geography"], dimensions["dim_store"],
        dimensions["dim_product"], dimensions["dim_supplier"], dimensions["dim_warehouse"],
    )

    tables = {"fact_sales": fact_sales, **dimensions}

    for name, table_df in tables.items():
        logger.info(f"  {name}: {table_df.count():,} rows, {len(table_df.columns)} columns")

    logger.info("Star schema build complete.")
    return tables
