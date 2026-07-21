"""
test_feature_engineering.py

Tests for src.transformation.feature_engineering — verifies each
engineered feature is added and computes the expected value.
"""

from config.schema_config import RawColumns
from src.transformation.feature_engineering import (
    add_calendar_features,
    add_inventory_risk_flag,
    add_price_per_unit,
    run_feature_engineering,
)


def _base_df(spark, month_num=4, value_sales=1000.0, units_sales=50,
             inventory_status="Low Stock", lead_time=15, category="Cat A"):
    row = (month_num, 2022, value_sales, units_sales, inventory_status, lead_time, category)
    columns = [
        RawColumns.MONTH_NUM, RawColumns.YEAR, RawColumns.VALUE_SALES, RawColumns.UNITS_SALES,
        RawColumns.INVENTORY_STATUS, RawColumns.SUPPLIER_LEAD_TIME_DAYS, RawColumns.CATEGORY,
    ]
    return spark.createDataFrame([row], schema=columns)


class TestAddCalendarFeatures:
    def test_quarter_calculated_correctly(self, spark):
        df = _base_df(spark, month_num=4)  # April -> Q2
        result = add_calendar_features(df).collect()[0]
        assert result["Quarter"] == 2

    def test_year_month_key_calculated_correctly(self, spark):
        df = _base_df(spark, month_num=4)
        result = add_calendar_features(df).collect()[0]
        assert result["YearMonthKey"] == 202204


class TestAddPricePerUnit:
    def test_computes_ratio_correctly(self, spark):
        df = _base_df(spark, value_sales=1000.0, units_sales=50)
        result = add_price_per_unit(df).collect()[0]
        assert result["PricePerUnit"] == 20.0

    def test_handles_zero_units_without_error(self, spark):
        df = _base_df(spark, value_sales=1000.0, units_sales=0)
        result = add_price_per_unit(df).collect()[0]
        assert result["PricePerUnit"] is None


class TestAddInventoryRiskFlag:
    def test_flags_high_risk_when_low_stock_and_long_lead_time(self, spark):
        df = _base_df(spark, inventory_status="Low Stock", lead_time=15)
        result = add_inventory_risk_flag(df).collect()[0]
        assert result["InventoryRiskFlag"] == "High Risk"

    def test_flags_watch_when_low_stock_but_short_lead_time(self, spark):
        df = _base_df(spark, inventory_status="Low Stock", lead_time=3)
        result = add_inventory_risk_flag(df).collect()[0]
        assert result["InventoryRiskFlag"] == "Watch"

    def test_flags_normal_when_in_stock(self, spark):
        df = _base_df(spark, inventory_status="In Stock", lead_time=15)
        result = add_inventory_risk_flag(df).collect()[0]
        assert result["InventoryRiskFlag"] == "Normal"


class TestRunFeatureEngineering:
    def test_all_expected_columns_added(self, spark):
        df = _base_df(spark)
        enriched, features_added = run_feature_engineering(df)

        expected_columns = {f["name"] for f in features_added}
        assert expected_columns.issubset(set(enriched.columns))

    def test_returns_feature_metadata_with_formulas(self, spark):
        df = _base_df(spark)
        _, features_added = run_feature_engineering(df)

        assert len(features_added) == 5
        for feature in features_added:
            assert "name" in feature
            assert "formula" in feature
