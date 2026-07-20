"""
cleaning.py

Cleaning layer: converts raw, schema-enforced data into an analysis-ready
staging DataFrame. Each function performs exactly one transformation and
is independently testable — no monolithic "clean_everything()" function.

Findings addressed here (from Step 2 profiling):
  1. 'Value Sales' / 'Units Sales' are comma-formatted strings -> numeric cast
  2. 221 fully duplicate rows -> removed
  3. WAREHOUSE_ID has 1.99% nulls -> imputed as 'UNKNOWN' (kept as its own
     dimension member rather than dropping rows — dropping would silently
     lose otherwise-valid sales records)
  4. BARCODE / PACK SIZE IQR "outliers" are NOT cleaned here — they are
     valid identifiers/measures once segmented correctly; see docs/data_dictionary.md
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, LongType

from config.schema_config import RawColumns
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Matches a clean integer or decimal string (optional leading '-' for true
# negatives), AFTER comma-stripping. Anything that doesn't match — '-',
# '', 'NA', 'N/A', 'null', whitespace, or any other placeholder token —
# is treated as missing rather than passed to .cast(), which is what was
# throwing SparkNumberFormatException.
_VALID_NUMERIC_PATTERN = r"^-?\d+(\.\d+)?$"


def clean_numeric_string_column(df: DataFrame, column: str, target_type=DoubleType()) -> tuple:
    """
    Strips comma thousand-separators and casts a numeric-looking string
    column to a proper numeric type, treating any non-numeric placeholder
    ('-', '', 'NA', 'N/A', 'null', whitespace, etc.) as NULL instead of
    letting Spark raise SparkNumberFormatException on cast.

    Handles the Indian numbering format found in 'Value Sales'
    (e.g. "8,17,935" -> 817935.0), which a naive .cast() would silently
    turn into NULL, while also guarding against placeholder tokens that
    would otherwise crash the cast entirely.

    Args:
        df: Input DataFrame.
        column: Name of the string column to clean.
        target_type: Spark numeric type to cast to.

    Returns:
        Tuple of (cleaned DataFrame, invalid_value_count). Invalid values
        become NULL; the count is returned for structured pipeline logging
        (previously logged as a side-effect only).
    """
    normalized = F.regexp_replace(F.trim(F.col(column)), ",", "")
    is_valid_numeric = normalized.rlike(_VALID_NUMERIC_PATTERN)

    invalid_count = df.filter(F.col(column).isNotNull() & ~is_valid_numeric).count()
    if invalid_count > 0:
        logger.warning(
            f"{column}: {invalid_count:,} non-numeric placeholder value(s) "
            f"(e.g. '-', 'NA', blank) found and set to NULL."
        )

    cleaned = df.withColumn(
        column,
        F.when(is_valid_numeric, normalized.cast(target_type)).otherwise(F.lit(None).cast(target_type))
    )
    return cleaned, invalid_count


def deduplicate_rows(df: DataFrame) -> DataFrame:
    """
    Removes fully duplicate rows.

    WHY dropDuplicates() over all columns (not a subset): the profiling
    step confirmed the 221 duplicates are exact full-row repeats
    (re-ingestion artifacts), not legitimate repeat transactions. Using a
    business key subset here would risk dropping valid records.
    """
    before = df.count()
    deduped = df.dropDuplicates()
    after = deduped.count()

    removed = before - after
    logger.info(f"Deduplication removed {removed:,} duplicate rows ({before:,} -> {after:,}).")

    return deduped


def impute_missing_warehouse_id(df: DataFrame, fill_value: str = "UNKNOWN") -> tuple:
    """
    Imputes null WAREHOUSE_ID values with a sentinel 'UNKNOWN' member
    rather than dropping rows. Preserves otherwise-valid sales records;
    the dim_warehouse table gets a corresponding 'UNKNOWN' row.

    Returns:
        Tuple of (DataFrame, count of nulls filled).
    """
    null_count = df.filter(F.col(RawColumns.WAREHOUSE_ID).isNull()).count()
    filled = df.fillna({RawColumns.WAREHOUSE_ID: fill_value})
    return filled, null_count


def standardize_string_columns(df: DataFrame, columns: list) -> DataFrame:
    """
    Trims whitespace on categorical string columns to prevent silent
    grouping errors downstream (e.g. "Retail" vs "Retail " being treated
    as distinct categories in a GROUP BY).
    """
    for c in columns:
        df = df.withColumn(c, F.trim(F.col(c)))
    return df


def run_cleaning_pipeline(df: DataFrame, warehouse_fill_value: str = "UNKNOWN") -> tuple:
    """
    Orchestrates the full cleaning sequence in the correct order:
    dedup -> numeric casts -> null imputation -> string standardization.

    Order matters: deduplication must happen before any derived columns
    are added, and numeric casting must happen before any aggregation or
    KPI logic relies on those columns.

    Args:
        df: Raw, schema-enforced DataFrame from the ingestion layer.
        warehouse_fill_value: Sentinel value for missing WAREHOUSE_ID.

    Returns:
        Tuple of (cleaned DataFrame, metrics dict). The metrics dict
        drives the pipeline's structured cleaning log and the final
        data quality report — it is not just informational logging,
        it's the single source of truth other stages/main.py read from.
    """
    logger.info("Starting cleaning pipeline...")

    rows_before = df.count()

    df = deduplicate_rows(df)
    rows_after_dedup = df.count()
    duplicates_removed = rows_before - rows_after_dedup

    df, invalid_value_sales = clean_numeric_string_column(df, RawColumns.VALUE_SALES, DoubleType())
    df, invalid_units_sales = clean_numeric_string_column(df, RawColumns.UNITS_SALES, LongType())

    df, warehouse_nulls_filled = impute_missing_warehouse_id(df, warehouse_fill_value)

    categorical_cols = [
        RawColumns.STORE_TYPE, RawColumns.CATEGORY, RawColumns.SEGMENT,
        RawColumns.MANUFACTURER, RawColumns.BRAND, RawColumns.REGION,
        RawColumns.STATE, RawColumns.CITY, RawColumns.SALES_CHANNEL,
        RawColumns.INVENTORY_STATUS, RawColumns.ORDER_STATUS,
    ]
    df = standardize_string_columns(df, categorical_cols)

    metrics = {
        "rows_before": rows_before,
        "rows_after": rows_after_dedup,
        "duplicates_removed": duplicates_removed,
        "rows_dropped": 0,  # no rows are ever dropped in this pipeline — invalid values are nulled, not removed
        "invalid_numeric": {
            RawColumns.VALUE_SALES: invalid_value_sales,
            RawColumns.UNITS_SALES: invalid_units_sales,
        },
        "nulls_filled": {
            RawColumns.WAREHOUSE_ID: warehouse_nulls_filled,
        },
    }

    logger.info("Cleaning pipeline complete.")
    return df, metrics
