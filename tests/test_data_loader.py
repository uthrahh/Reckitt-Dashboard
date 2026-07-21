"""
test_data_loader.py

Tests for src.ingestion.data_loader — verifies the CSV loads with the
explicit schema, column names are normalized, and empty files are
handled with a clear error rather than a silent empty DataFrame.
"""

import pytest

from config.schema_config import RAW_SCHEMA, RawColumns
from src.ingestion.data_loader import load_raw_sales_data, normalize_column_names

# One minimal, valid CSV row matching RAW_SCHEMA column order exactly.
_HEADER = ",".join(f.name for f in RAW_SCHEMA.fields)
_VALID_ROW = (
    "1,Jan,2022,Retail,Category A,Segment 1,Reckitt,Brand X,1234567890,100,ML,"
    "1000,50,North,State1,City1,S001,P001,SUP1,DC1,Modern Trade,B1,L1,5,"
    "WH1,In Stock,Completed,POS,2024-01-01T00:00:00"
)


def _write_csv(tmp_path, content: str) -> str:
    path = tmp_path / "sales.csv"
    path.write_text(content)
    return str(path)


class TestLoadRawSalesData:
    def test_csv_loads_successfully(self, spark, tmp_path):
        csv_path = _write_csv(tmp_path, f"{_HEADER}\n{_VALID_ROW}\n")
        df = load_raw_sales_data(spark, csv_path)
        assert df.count() == 1

    def test_schema_matches_expected_columns(self, spark, tmp_path):
        csv_path = _write_csv(tmp_path, f"{_HEADER}\n{_VALID_ROW}\n")
        df = load_raw_sales_data(spark, csv_path)
        expected_columns = [f.name for f in RAW_SCHEMA.fields]
        assert df.columns == expected_columns

    def test_empty_file_raises_value_error(self, spark, tmp_path):
        # Header only, zero data rows -> should raise, not return silently.
        csv_path = _write_csv(tmp_path, f"{_HEADER}\n")
        with pytest.raises(ValueError):
            load_raw_sales_data(spark, csv_path)

    def test_missing_file_raises(self, spark, tmp_path):
        missing_path = str(tmp_path / "does_not_exist.csv")
        with pytest.raises(Exception):
            load_raw_sales_data(spark, missing_path)


class TestNormalizeColumnNames:
    def test_trims_leading_and_trailing_whitespace(self, spark):
        df = spark.createDataFrame([(1, 2)], schema=[" Value Sales ", "Units Sales"])
        normalized = normalize_column_names(df)
        assert "Value Sales" in normalized.columns
        assert " Value Sales " not in normalized.columns

    def test_collapses_internal_whitespace(self, spark):
        df = spark.createDataFrame([(1,)], schema=["Value   Sales"])
        normalized = normalize_column_names(df)
        assert normalized.columns == ["Value Sales"]

    def test_leaves_clean_names_unchanged(self, spark):
        df = spark.createDataFrame([(1,)], schema=[RawColumns.PRODUCT_ID])
        normalized = normalize_column_names(df)
        assert normalized.columns == [RawColumns.PRODUCT_ID]
