"""
test_star_schema.py

Tests for src.modeling.star_schema_builder — verifies dimensions contain
unique natural keys, the fact table preserves transactional grain (this
is the regression test for the row-explosion bug), and surrogate keys
are unique.
"""

import pytest

from config.schema_config import RawColumns
from src.modeling.star_schema_builder import (
    build_dim_product,
    build_star_schema,
    validate_dimension_uniqueness,
)


def _staging_row(product_id="P001", category="Cat A", store_id="S001", supplier_id="SUP1",
                  warehouse_id="WH1", city="City1", month_num=1, year=2022,
                  value_sales=1000.0, units_sales=50):
    return (
        month_num, "Jan", year, "Retail", category, "Seg 1", "Reckitt", "Brand X",
        1234567890, 100, "ML", value_sales, units_sales, "North", "State1", city,
        store_id, product_id, supplier_id, "DC1", "Modern Trade", "B1", "L1", 5,
        warehouse_id, "In Stock", "Completed", "POS", "2024-01-01T00:00:00",
        # feature-engineered columns expected by build_fact_sales:
        1, 202201, 20.0, 1, "Normal",
    )


_STAGING_COLUMNS = [
    RawColumns.MONTH_NUM, RawColumns.MONTH, RawColumns.YEAR, RawColumns.STORE_TYPE,
    RawColumns.CATEGORY, RawColumns.SEGMENT, RawColumns.MANUFACTURER, RawColumns.BRAND,
    RawColumns.BARCODE, RawColumns.PACK_SIZE, RawColumns.PACK_UNIT,
    RawColumns.VALUE_SALES, RawColumns.UNITS_SALES, RawColumns.REGION,
    RawColumns.STATE, RawColumns.CITY, RawColumns.STORE_ID, RawColumns.PRODUCT_ID,
    RawColumns.SUPPLIER_ID, RawColumns.DISTRIBUTION_CENTER, RawColumns.SALES_CHANNEL,
    RawColumns.BATCH_NUMBER, RawColumns.LOT_NUMBER, RawColumns.SUPPLIER_LEAD_TIME_DAYS,
    RawColumns.WAREHOUSE_ID, RawColumns.INVENTORY_STATUS, RawColumns.ORDER_STATUS,
    RawColumns.DATA_SOURCE, RawColumns.INGESTION_TIMESTAMP,
    "Quarter", "YearMonthKey", "PricePerUnit", "CategorySalesRank", "InventoryRiskFlag",
]


class TestBuildDimProduct:
    def test_one_row_per_product_id_even_with_inconsistent_attributes(self, spark):
        # Regression test: same PRODUCT_ID appearing with two different
        # CATEGORY values across source rows (dirty data) must still
        # collapse to exactly one dim_product row — this is what caused
        # the original 742,760-row fact table explosion.
        rows = [
            _staging_row(product_id="P001", category="Cat A"),
            _staging_row(product_id="P001", category="Cat B"),
        ]
        df = spark.createDataFrame(rows, schema=_STAGING_COLUMNS)
        dim_product = build_dim_product(df)

        assert dim_product.filter(dim_product[RawColumns.PRODUCT_ID] == "P001").count() == 1

    def test_dimension_has_no_duplicate_natural_keys(self, spark):
        rows = [_staging_row(product_id=f"P00{i}") for i in range(1, 4)]
        df = spark.createDataFrame(rows, schema=_STAGING_COLUMNS)
        dim_product = build_dim_product(df)

        total = dim_product.count()
        distinct = dim_product.select(RawColumns.PRODUCT_ID).distinct().count()
        assert total == distinct


class TestValidateDimensionUniqueness:
    def test_raises_on_duplicate_natural_key(self, spark):
        # Manually construct a dimension with a genuine duplicate natural
        # key (bypassing the builder) to confirm the guard actually fires.
        bad_dim_warehouse = spark.createDataFrame(
            [(1, "WH1"), (2, "WH1")], schema=["warehouse_key", RawColumns.WAREHOUSE_ID]
        )
        dimensions = {"dim_warehouse": bad_dim_warehouse}
        # Restrict the check to just this one dimension for the test.
        from src.modeling.star_schema_builder import DIMENSION_NATURAL_KEYS
        assert RawColumns.WAREHOUSE_ID in DIMENSION_NATURAL_KEYS["dim_warehouse"]

        with pytest.raises(ValueError):
            validate_dimension_uniqueness(dimensions)

    def test_passes_on_unique_natural_keys(self, spark):
        good_dim_warehouse = spark.createDataFrame(
            [(1, "WH1"), (2, "WH2")], schema=["warehouse_key", RawColumns.WAREHOUSE_ID]
        )
        results = validate_dimension_uniqueness({"dim_warehouse": good_dim_warehouse})
        assert results == [("dim_warehouse", 2)]


class TestBuildStarSchema:
    def test_fact_table_preserves_transactional_grain(self, spark):
        # This is the core regression test for the row-explosion bug:
        # N input rows must produce exactly N fact rows, never more.
        rows = [
            _staging_row(product_id="P001", category="Cat A"),
            _staging_row(product_id="P001", category="Cat B"),  # dirty duplicate attribute
            _staging_row(product_id="P002", store_id="S002"),
        ]
        df = spark.createDataFrame(rows, schema=_STAGING_COLUMNS)

        tables = build_star_schema(df)

        assert tables["fact_sales"].count() == len(rows)

    def test_no_duplicate_surrogate_keys_in_fact_table(self, spark):
        rows = [_staging_row(product_id=f"P00{i}", store_id=f"S00{i}") for i in range(1, 4)]
        df = spark.createDataFrame(rows, schema=_STAGING_COLUMNS)

        tables = build_star_schema(df)
        fact = tables["fact_sales"]

        assert fact.select("sale_key").distinct().count() == fact.count()

    def test_all_expected_tables_created(self, spark):
        rows = [_staging_row()]
        df = spark.createDataFrame(rows, schema=_STAGING_COLUMNS)

        tables = build_star_schema(df)

        expected = {
            "fact_sales", "dim_date", "dim_geography", "dim_store",
            "dim_product", "dim_supplier", "dim_warehouse",
        }
        assert set(tables.keys()) == expected
