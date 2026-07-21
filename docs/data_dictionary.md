# Data Dictionary

Field-level documentation for every table in `data/curated/`.

## fact_sales

Grain: one row = one product sold at one store in one month.

| Column | Type | Description |
|---|---|---|
| `sale_key` | long | Surrogate primary key |
| `date_key` | long | FK → `dim_date` |
| `geography_key` | long | FK → `dim_geography` |
| `store_key` | long | FK → `dim_store` |
| `product_key` | long | FK → `dim_product` |
| `supplier_key` | long | FK → `dim_supplier` |
| `warehouse_key` | long | FK → `dim_warehouse` |
| `value_sales` | double | Sales value, cleaned/cast from raw comma-formatted string |
| `units_sales` | long | Units sold, cleaned/cast from raw comma-formatted string |
| `supplier_lead_time_days` | int | Days between order and fulfillment for this supplier |
| `inventory_status` | string | Raw inventory status at time of record (e.g. In Stock, Low Stock, Out of Stock) |
| `order_status` | string | Raw order status (e.g. Completed, Pending) |
| `PricePerUnit` | double | `value_sales / units_sales`; NULL if units_sales = 0 |
| `CategorySalesRank` | int | Dense rank of this row's `value_sales` within its `CATEGORY` |
| `InventoryRiskFlag` | string | `High Risk` / `Watch` / `Normal` — derived from inventory status + lead time |
| `batch_number` | string | Degenerate dimension — traceability only, not intended for BI aggregation |
| `lot_number` | string | Degenerate dimension — traceability only, not intended for BI aggregation |

## dim_date

Grain: one row per (Year, Month#).

| Column | Type | Description |
|---|---|---|
| `date_key` | long | Surrogate primary key |
| `Year` | int | Calendar year |
| `Month #` | int | Month number (1–12) |
| `Month` | string | Month name |
| `Quarter` | int | Calendar quarter (1–4), derived from Month # |
| `YearMonthKey` | int | Sortable `YYYYMM` integer key, useful for time-intelligence slicers |

## dim_geography

Grain: one row per City.

| Column | Type | Description |
|---|---|---|
| `geography_key` | long | Surrogate primary key |
| `CITY` | string | City name (natural key) |
| `STATE` | string | State containing the city |
| `REGION` | string | Region containing the state |

## dim_store

Grain: one row per STORE_ID.

| Column | Type | Description |
|---|---|---|
| `store_key` | long | Surrogate primary key |
| `STORE_ID` | string | Natural key from source system |
| `STORE TYPE` | string | e.g. Retail, Wholesale, Online |
| `SALES_CHANNEL` | string | e.g. Modern Trade, General Trade |

## dim_product

Grain: one row per PRODUCT_ID.

| Column | Type | Description |
|---|---|---|
| `product_key` | long | Surrogate primary key |
| `PRODUCT_ID` | string | Natural key from source system |
| `BARCODE` | long | Product barcode/identifier — never used in numeric aggregation |
| `CATEGORY` | string | Top-level product category |
| `SEGMENT` | string | Sub-category segment |
| `MANUFACTURER_1` | string | Manufacturer name |
| `BRAND_2` | string | Brand name |
| `PACK SIZE` | int | Pack size value |
| `PACK unit` | string | Unit for pack size (e.g. ML, GR, EACH) — required context for interpreting PACK SIZE |

## dim_supplier

Grain: one row per SUPPLIER_ID.

| Column | Type | Description |
|---|---|---|
| `supplier_key` | long | Surrogate primary key |
| `SUPPLIER_ID` | string | Natural key from source system |
| `DISTRIBUTION_CENTER` | string | Associated distribution center |

## dim_warehouse

Grain: one row per WAREHOUSE_ID.

| Column | Type | Description |
|---|---|---|
| `warehouse_key` | long | Surrogate primary key |
| `WAREHOUSE_ID` | string | Natural key from source system. Includes an `"UNKNOWN"` sentinel member for records where the source data had a missing warehouse ID. |

## Notes

- All surrogate keys are generated via `monotonically_increasing_id()` and are stable only within a single pipeline run — they are **not** guaranteed stable across re-runs. Power BI relationships should be rebuilt on each full refresh, not incrementally patched.
- `INGESTION_TIMESTAMP` from the raw source is intentionally **not** carried into the curated tables — it is a load-time metadata field, not a business date, and was a known source of confusion during profiling (its 2024 values did not match the 2019–2022 transaction years).
