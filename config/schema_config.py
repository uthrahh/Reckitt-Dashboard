"""
schema_config.py

Defines the explicit PySpark schema for the raw Reckitt FMCG sales dataset,
plus centralized column-name constants used across the pipeline.

WHY EXPLICIT SCHEMA OVER INFERSCHEMA:
- inferSchema=True forces Spark to perform an extra full read pass over the
  data purely to sample types — wasted I/O at any real scale.
- Type inference is unreliable on this dataset specifically: 'Value Sales'
  and 'Units Sales' contain comma-formatted numbers (e.g. "8,17,935") which
  Spark would infer as StringType anyway, silently hiding a cleaning step
  that must happen explicitly.
- Explicit schemas make the contract with upstream data producers visible
  and version-controlled — a schema change is a code review, not a surprise.
"""

from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    LongType,
)

# -----------------------------------------------------------------------------
# Column name constants — single source of truth. Never hardcode raw column
# strings inside transformation logic; import from here instead.
# -----------------------------------------------------------------------------
class RawColumns:
    MONTH_NUM = "Month #"
    MONTH = "Month"
    YEAR = "Year"
    STORE_TYPE = "STORE TYPE"
    CATEGORY = "CATEGORY"
    SEGMENT = "SEGMENT"
    MANUFACTURER = "MANUFACTURER_1"
    BRAND = "BRAND_2"
    BARCODE = "BARCODE"
    PACK_SIZE = "PACK SIZE"
    PACK_UNIT = "PACK unit"
    VALUE_SALES = "Value Sales"
    UNITS_SALES = "Units Sales"
    REGION = "REGION"
    STATE = "STATE"
    CITY = "CITY"
    STORE_ID = "STORE_ID"
    PRODUCT_ID = "PRODUCT_ID"
    SUPPLIER_ID = "SUPPLIER_ID"
    DISTRIBUTION_CENTER = "DISTRIBUTION_CENTER"
    SALES_CHANNEL = "SALES_CHANNEL"
    BATCH_NUMBER = "BATCH_NUMBER"
    LOT_NUMBER = "LOT_NUMBER"
    SUPPLIER_LEAD_TIME_DAYS = "SUPPLIER_LEAD_TIME_DAYS"
    WAREHOUSE_ID = "WAREHOUSE_ID"
    INVENTORY_STATUS = "INVENTORY_STATUS"
    ORDER_STATUS = "ORDER_STATUS"
    DATA_SOURCE = "DATA_SOURCE"
    INGESTION_TIMESTAMP = "INGESTION_TIMESTAMP"


# -----------------------------------------------------------------------------
# Raw ingestion schema
# NOTE: Value Sales / Units Sales are intentionally typed as StringType here.
# They are comma-formatted (Indian numbering system) and must be cleaned via
# regex + cast in the transformation layer — casting at read time would
# silently null out every row.
# -----------------------------------------------------------------------------
RAW_SCHEMA = StructType([
    StructField(RawColumns.MONTH_NUM, IntegerType(), nullable=False),
    StructField(RawColumns.MONTH, StringType(), nullable=False),
    StructField(RawColumns.YEAR, IntegerType(), nullable=False),
    StructField(RawColumns.STORE_TYPE, StringType(), nullable=False),
    StructField(RawColumns.CATEGORY, StringType(), nullable=False),
    StructField(RawColumns.SEGMENT, StringType(), nullable=False),
    StructField(RawColumns.MANUFACTURER, StringType(), nullable=False),
    StructField(RawColumns.BRAND, StringType(), nullable=False),
    StructField(RawColumns.BARCODE, LongType(), nullable=False),
    StructField(RawColumns.PACK_SIZE, IntegerType(), nullable=False),
    StructField(RawColumns.PACK_UNIT, StringType(), nullable=False),
    StructField(RawColumns.VALUE_SALES, StringType(), nullable=False),
    StructField(RawColumns.UNITS_SALES, StringType(), nullable=False),
    StructField(RawColumns.REGION, StringType(), nullable=False),
    StructField(RawColumns.STATE, StringType(), nullable=False),
    StructField(RawColumns.CITY, StringType(), nullable=False),
    StructField(RawColumns.STORE_ID, StringType(), nullable=False),
    StructField(RawColumns.PRODUCT_ID, StringType(), nullable=False),
    StructField(RawColumns.SUPPLIER_ID, StringType(), nullable=False),
    StructField(RawColumns.DISTRIBUTION_CENTER, StringType(), nullable=False),
    StructField(RawColumns.SALES_CHANNEL, StringType(), nullable=False),
    StructField(RawColumns.BATCH_NUMBER, StringType(), nullable=False),
    StructField(RawColumns.LOT_NUMBER, StringType(), nullable=False),
    StructField(RawColumns.SUPPLIER_LEAD_TIME_DAYS, IntegerType(), nullable=False),
    StructField(RawColumns.WAREHOUSE_ID, StringType(), nullable=True),   # known 1.99% nulls
    StructField(RawColumns.INVENTORY_STATUS, StringType(), nullable=False),
    StructField(RawColumns.ORDER_STATUS, StringType(), nullable=False),
    StructField(RawColumns.DATA_SOURCE, StringType(), nullable=False),
    StructField(RawColumns.INGESTION_TIMESTAMP, StringType(), nullable=False),
])
