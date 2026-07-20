"""
feature_engineering.py

Derives analytics-ready features on top of the cleaned staging DataFrame.
WHY THESE ARE COLUMNS, NOT DAX MEASURES: attributes that describe a *row's
static context* (quarter, price-per-unit, fiscal grouping) belong in the
data layer so they can be reused as dimension attributes / slicers in
Power BI. True aggregations (SUM, AVG across many rows) are deliberately
left to DAX measures — computing them here would bake a fixed grain into
the model and block flexible BI-side aggregation.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from config.schema_config import RawColumns
from src.utils.logger import get_logger

logger = get_logger(__name__)


def add_calendar_features(df: DataFrame) -> DataFrame:
    """Adds Quarter and a sortable YearMonth key for time-intelligence in Power BI."""
    return df.withColumn(
        "Quarter", F.ceil(F.col(RawColumns.MONTH_NUM) / 3).cast("int")
    ).withColumn(
        "YearMonthKey",
        (F.col(RawColumns.YEAR) * 100 + F.col(RawColumns.MONTH_NUM)).cast("int")
    )


def add_price_per_unit(df: DataFrame) -> DataFrame:
    """
    Derives average selling price per unit (Value Sales / Units Sales).
    Guarded against divide-by-zero with NULLIF-equivalent (F.when).

    This is a row-level ratio (not a simple additive measure), so it is
    appropriate as a precomputed column — a naive DAX AVERAGE(price_column)
    would be mathematically wrong for a ratio like this; the correct DAX
    approach is SUM(Value)/SUM(Units), which we still compute at BI time.
    This column exists for row-level analysis and outlier detection only.
    """
    return df.withColumn(
        "PricePerUnit",
        F.when(F.col(RawColumns.UNITS_SALES) > 0,
               F.col(RawColumns.VALUE_SALES) / F.col(RawColumns.UNITS_SALES))
        .otherwise(None)
    )


def add_rank_features(df: DataFrame) -> DataFrame:
    """
    Adds a per-category sales rank using a window function — demonstrates
    window function usage for "top N product per category" style analysis,
    and gives Power BI a precomputed rank to avoid expensive RANKX at
    report-render time for a high-cardinality PRODUCT_ID dimension.
    """
    window_spec = Window.partitionBy(RawColumns.CATEGORY).orderBy(F.desc(RawColumns.VALUE_SALES))
    return df.withColumn("CategorySalesRank", F.dense_rank().over(window_spec))


def add_inventory_risk_flag(df: DataFrame) -> DataFrame:
    """
    Flags supply-chain risk rows: low/out-of-stock combined with a
    long supplier lead time. Encodes a business rule once, in code,
    rather than replicating it in every downstream DAX measure.
    """
    return df.withColumn(
        "InventoryRiskFlag",
        F.when(
            (F.col(RawColumns.INVENTORY_STATUS).isin("Out of Stock", "Low Stock")) &
            (F.col(RawColumns.SUPPLIER_LEAD_TIME_DAYS) >= 10),
            F.lit("High Risk")
        ).when(
            F.col(RawColumns.INVENTORY_STATUS).isin("Out of Stock", "Low Stock"),
            F.lit("Watch")
        ).otherwise(F.lit("Normal"))
    )


FEATURES_ADDED = [
    {"name": "Quarter", "formula": "CEIL(Month# / 3)"},
    {"name": "YearMonthKey", "formula": "Year * 100 + Month#"},
    {"name": "PricePerUnit", "formula": "Value Sales / Units Sales (NULL when Units Sales = 0)"},
    {"name": "CategorySalesRank", "formula": "DENSE_RANK() OVER (PARTITION BY Category ORDER BY Value Sales DESC)"},
    {"name": "InventoryRiskFlag", "formula": "CASE on Inventory Status + Supplier Lead Time Days"},
]


def run_feature_engineering(df: DataFrame) -> tuple:
    """
    Orchestrates all feature engineering steps in sequence.

    Returns:
        Tuple of (enriched DataFrame, FEATURES_ADDED metadata list) — the
        metadata drives the pipeline's structured feature-engineering log.
    """
    logger.info("Running feature engineering...")

    df = add_calendar_features(df)
    df = add_price_per_unit(df)
    df = add_rank_features(df)
    df = add_inventory_risk_flag(df)

    logger.info("Feature engineering complete.")
    return df, FEATURES_ADDED
