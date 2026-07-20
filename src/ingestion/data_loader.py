"""
data_loader.py

Ingestion layer: reads raw CSV into a DataFrame using the explicit schema
contract defined in config/schema_config.py.

WHY A DEDICATED INGESTION MODULE (vs inline spark.read in main.py):
Isolating I/O means the rest of the pipeline (validation, cleaning,
modeling) can be unit-tested against an in-memory DataFrame without ever
touching disk — a standard testability pattern in production data
engineering.
"""

from pyspark.sql import DataFrame, SparkSession

from config.schema_config import RAW_SCHEMA
from src.utils.logger import get_logger

logger = get_logger(__name__)


def normalize_column_names(df: DataFrame) -> DataFrame:
    """
    Trims leading/trailing whitespace from every column name and collapses
    repeated internal spaces to a single space (e.g. " Value  Sales " ->
    "Value Sales"). Guards against header-whitespace variants breaking
    downstream column references (RawColumns constants, joins, schema
    comparisons) — a common issue with source systems that export CSVs
    inconsistently.
    """
    renamed = df
    for original in df.columns:
        normalized = " ".join(original.split())  # trims + collapses internal whitespace
        if normalized != original:
            renamed = renamed.withColumnRenamed(original, normalized)
    return renamed


def load_raw_sales_data(spark: SparkSession, file_path: str) -> DataFrame:
    """
    Loads the raw Reckitt FMCG sales CSV using an explicit schema.

    Args:
        spark: Active SparkSession.
        file_path: Path to the raw CSV file.

    Returns:
        Raw DataFrame, schema-enforced, column names normalized, but not
        yet cleaned.

    Raises:
        FileNotFoundError: If the source file does not exist at file_path.
    """
    logger.info(f"Loading raw data from: {file_path}")

    df = (
        spark.read
        .option("header", True)
        .option("mode", "PERMISSIVE")       # never silently drop malformed rows
        .option("columnNameOfCorruptRecord", "_corrupt_record")
        .schema(RAW_SCHEMA)
        .csv(file_path)
    )

    df = normalize_column_names(df)

    row_count = df.count()
    logger.info(f"Loaded {row_count:,} rows, {len(df.columns)} columns.")

    if row_count == 0:
        raise ValueError(f"No rows loaded from {file_path} — check path and file format.")

    return df
