"""
test_cleaning.py

Tests for src.transformation.cleaning — verifies duplicate removal,
placeholder-to-NULL conversion for dirty numeric strings, and correct
numeric casting (including comma-formatted values).
"""

from pyspark.sql.types import DoubleType, LongType

from config.schema_config import RawColumns
from src.transformation.cleaning import (
    clean_numeric_string_column,
    deduplicate_rows,
    impute_missing_warehouse_id,
    run_cleaning_pipeline,
)


class TestCleanNumericStringColumn:
    def test_converts_placeholder_values_to_null(self, spark):
        placeholders = ["-", "--", "---", "", " ", "NA", "N/A", "NULL", "null", "None", "none"]
        df = spark.createDataFrame([(v,) for v in placeholders], schema=["value"])
        cleaned, invalid_count = clean_numeric_string_column(df, "value", DoubleType())

        results = [row["value"] for row in cleaned.collect()]
        assert all(v is None for v in results)
        assert invalid_count == len(placeholders)

    def test_preserves_valid_numeric_values(self, spark):
        df = spark.createDataFrame([("500",), ("1234.5",), ("-10",)], schema=["value"])
        cleaned, invalid_count = clean_numeric_string_column(df, "value", DoubleType())

        results = sorted(row["value"] for row in cleaned.collect())
        assert results == [-10.0, 500.0, 1234.5]
        assert invalid_count == 0

    def test_handles_comma_formatted_numbers(self, spark):
        # Indian-style comma formatting, e.g. "8,17,935" -> 817935
        df = spark.createDataFrame([("8,17,935",)], schema=["value"])
        cleaned, invalid_count = clean_numeric_string_column(df, "value", LongType())

        assert cleaned.collect()[0]["value"] == 817935
        assert invalid_count == 0

    def test_never_raises_on_dirty_input(self, spark):
        # This is the regression test for the original SparkNumberFormatException.
        df = spark.createDataFrame([("-",), ("garbage$%",), ("100",)], schema=["value"])
        cleaned, _ = clean_numeric_string_column(df, "value", DoubleType())
        cleaned.collect()  # must not raise


class TestDeduplicateRows:
    def test_removes_exact_duplicates(self, spark):
        df = spark.createDataFrame([(1, "a"), (1, "a"), (2, "b")], schema=["id", "value"])
        deduped = deduplicate_rows(df)
        assert deduped.count() == 2

    def test_keeps_distinct_rows_intact(self, spark):
        df = spark.createDataFrame([(1, "a"), (2, "b"), (3, "c")], schema=["id", "value"])
        deduped = deduplicate_rows(df)
        assert deduped.count() == 3


class TestImputeMissingWarehouseId:
    def test_fills_nulls_with_sentinel(self, spark):
        df = spark.createDataFrame(
            [("WH1",), (None,), ("WH2",)], schema=[RawColumns.WAREHOUSE_ID]
        )
        filled, null_count = impute_missing_warehouse_id(df, fill_value="UNKNOWN")

        values = [row[RawColumns.WAREHOUSE_ID] for row in filled.collect()]
        assert None not in values
        assert "UNKNOWN" in values
        assert null_count == 1


class TestRunCleaningPipeline:
    def test_returns_metrics_dict_with_expected_keys(self, spark):
        rows = [
            (1, "Jan", 2022, "Retail", "Cat A", "Seg 1", "Reckitt", "Brand X", 1, 100, "ML",
             "1000", "50", "North", "State1", "City1", "S001", "P001", "SUP1", "DC1",
             "Modern Trade", "B1", "L1", 5, "WH1", "In Stock", "Completed", "POS", "2024-01-01"),
        ]
        columns = [
            RawColumns.MONTH_NUM, RawColumns.MONTH, RawColumns.YEAR, RawColumns.STORE_TYPE,
            RawColumns.CATEGORY, RawColumns.SEGMENT, RawColumns.MANUFACTURER, RawColumns.BRAND,
            RawColumns.BARCODE, RawColumns.PACK_SIZE, RawColumns.PACK_UNIT,
            RawColumns.VALUE_SALES, RawColumns.UNITS_SALES, RawColumns.REGION,
            RawColumns.STATE, RawColumns.CITY, RawColumns.STORE_ID, RawColumns.PRODUCT_ID,
            RawColumns.SUPPLIER_ID, RawColumns.DISTRIBUTION_CENTER, RawColumns.SALES_CHANNEL,
            RawColumns.BATCH_NUMBER, RawColumns.LOT_NUMBER, RawColumns.SUPPLIER_LEAD_TIME_DAYS,
            RawColumns.WAREHOUSE_ID, RawColumns.INVENTORY_STATUS, RawColumns.ORDER_STATUS,
            RawColumns.DATA_SOURCE, RawColumns.INGESTION_TIMESTAMP,
        ]
        df = spark.createDataFrame(rows, schema=columns)

        cleaned_df, metrics = run_cleaning_pipeline(df)

        for key in ("rows_before", "rows_after", "duplicates_removed",
                    "rows_dropped", "invalid_numeric", "nulls_filled"):
            assert key in metrics

        assert cleaned_df.count() == 1
