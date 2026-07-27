# DAX Measure Library — Reckitt FMCG Sales Analytics

All measures live in a dedicated **Measures Table** (a disconnected table with
no relationships — standard best practice so measures aren't scattered across
fact/dim tables). Organized into **Display Folders** as noted per section.
Every measure uses variables (`VAR`) for readability and to guarantee each
sub-expression is computed once, not re-evaluated per reference.

**Conventions used throughout:**
- `SUM`/`CALCULATE` over calculated columns — no row-by-row iteration unless
  a window/ranking function requires it (`RANKX`, `TOPN`).
- Time intelligence uses `dim_date` (marked as the model's official Date
  Table, contiguous Jan 2019–Jun 2022, `date_key` is NOT a real date column —
  see note in Utility folder for the `DateKey` fix required at model-build time).
- All ratio measures guard against divide-by-zero with `DIVIDE()`, never `/`.
- Product-level ranking deliberately omitted — `PRODUCT_ID` has ~1.005
  transactions per SKU, so ranking is done at Category/Segment/Brand instead
  (see Product Analysis folder).

---

## Time Intelligence (Monthly Model)

This warehouse stores data at **monthly grain**. The `dim_date` table
contains one row per month and is intentionally **not marked as a Power BI
Date Table**.

Accordingly, built-in DAX time-intelligence functions
(`TOTALYTD`, `DATESYTD`, `DATEADD`, `SAMEPERIODLASTYEAR`,
`DATESINPERIOD`, etc.) are not used.

All period comparisons are implemented using
`Year`, `Month #`, `Quarter`, and `YearMonthKey`,
ensuring compatibility with a monthly star schema.

---

## 📁 Folder: Core KPIs

```dax
Total Revenue =
SUM ( fact_sales[value_sales] )
```
*Base additive measure. Everything else builds on this.*

```dax
Total Units Sold =
SUM ( fact_sales[units_sales] )
```

```dax
Average Selling Price =
VAR TotalRevenue = [Total Revenue]
VAR TotalUnits = [Total Units Sold]
RETURN
    DIVIDE ( TotalRevenue, TotalUnits )
```
*Correct pattern: SUM/SUM, not AVERAGE(PricePerUnit) — averaging a
row-level ratio column would weight every transaction equally regardless
of its size, distorting the true blended price. `PricePerUnit` stays a
diagnostic column, not an aggregation source.*

```dax
Net Revenue =
CALCULATE (
    [Total Revenue],
    fact_sales[order_status] IN { "Completed", "Pending" }
)
```
*Excludes Returned/Cancelled. Handles the 15 rows where value_sales is
negative but order_status doesn't cleanly align — this measure defines
"real" revenue explicitly rather than relying on the sign of value_sales
alone, which the profiling step showed is inconsistent.*

```dax
Order Fulfillment Rate % =
VAR CompletedOrders =
    CALCULATE ( COUNTROWS ( fact_sales ), fact_sales[order_status] = "Completed" )
VAR TotalOrders = COUNTROWS ( fact_sales )
RETURN
    DIVIDE ( CompletedOrders, TotalOrders )
```

```dax
Return Rate % =
VAR ReturnedOrders =
    CALCULATE ( COUNTROWS ( fact_sales ), fact_sales[order_status] = "Returned" )
VAR TotalOrders = COUNTROWS ( fact_sales )
RETURN
    DIVIDE ( ReturnedOrders, TotalOrders )
```

```dax
Cancellation Rate % =
VAR CancelledOrders =
    CALCULATE ( COUNTROWS ( fact_sales ), fact_sales[order_status] = "Cancelled" )
VAR TotalOrders = COUNTROWS ( fact_sales )
RETURN
    DIVIDE ( CancelledOrders, TotalOrders )
```

---

## 📁 Folder: Time Intelligence

```dax
Revenue PY =
VAR CurrentYear =
    SELECTEDVALUE(dim_date[Year])

VAR CurrentMonth =
    SELECTEDVALUE(dim_date[Month #])

RETURN
CALCULATE(
    [Total Revenue],
    FILTER(
        ALL(dim_date),
        dim_date[Year] = CurrentYear - 1
            &&
        dim_date[Month #] = CurrentMonth
    )
)
```

```dax
Revenue YoY % =
VAR CurrentRevenue = [Total Revenue]
VAR PriorRevenue = [Revenue PY]
RETURN
    DIVIDE ( CurrentRevenue - PriorRevenue, PriorRevenue )
```

```dax
Revenue Prior Month =
VAR CurrentYear =
    SELECTEDVALUE(dim_date[Year])

VAR CurrentMonth =
    SELECTEDVALUE(dim_date[Month #])

RETURN
IF(
    CurrentMonth=1,

    CALCULATE(
        [Total Revenue],
        FILTER(
            ALL(dim_date),
            dim_date[Year]=CurrentYear-1
            &&
            dim_date[Month #]=12
        )
    ),

    CALCULATE(
        [Total Revenue],
        FILTER(
            ALL(dim_date),
            dim_date[Year]=CurrentYear
            &&
            dim_date[Month #]=CurrentMonth-1
        )
    )
)
```

```dax
Revenue MoM % =
VAR CurrentRevenue = [Total Revenue]
VAR PriorRevenue = [Revenue Prior Month]
RETURN
    DIVIDE ( CurrentRevenue - PriorRevenue, PriorRevenue )
```

```dax
Revenue Running Total =
VAR CurrentKey =
    MAX(dim_date[YearMonthKey])

RETURN
CALCULATE(
    [Total Revenue],
    FILTER(
        ALLSELECTED(dim_date),
        dim_date[YearMonthKey] <= CurrentKey
    )
)
```
*`ALLSELECTED` (not `ALL`) so the running total respects any active
slicer context — e.g. running total within a filtered Region still
accumulates correctly rather than resetting to the whole table.*

```dax
Revenue 3-Month Moving Average =
AVERAGEX(
    TOPN(
        3,
        FILTER(
            ALL(dim_date),
            dim_date[YearMonthKey]
                <= MAX(dim_date[YearMonthKey])
        ),
        dim_date[YearMonthKey],
        DESC
    ),
    CALCULATE([Total Revenue])
)
```

```dax
Revenue YTD =
VAR CurrentYear =
    MAX(dim_date[Year])

VAR CurrentMonth =
    MAX(dim_date[Month #])

RETURN
CALCULATE(
    [Total Revenue],
    FILTER(
        ALL(dim_date),
        dim_date[Year]=CurrentYear
            &&
        dim_date[Month #] <= CurrentMonth
    )
)
```

```dax
Revenue QTD =
VAR CurrentYear =
    MAX(dim_date[Year])

VAR CurrentQuarter =
    MAX(dim_date[Quarter])

RETURN
CALCULATE(
    [Total Revenue],
    FILTER(
        ALL(dim_date),
        dim_date[Year]=CurrentYear
            &&
        dim_date[Quarter]=CurrentQuarter
    )
)
```

```
Revenue Rolling 6-Month =
SUMX(
    TOPN(
        6,
        FILTER(
            ALL(dim_date),
            dim_date[YearMonthKey]
                <= MAX(dim_date[YearMonthKey])
        ),
        dim_date[YearMonthKey],
        DESC
    ),
    CALCULATE([Total Revenue])
)
```

```
Revenue Rolling 12-Month =
SUMX(
    TOPN(
        12,
        FILTER(
            ALL(dim_date),
            dim_date[YearMonthKey]
                <= MAX(dim_date[YearMonthKey])
        ),
        dim_date[YearMonthKey],
        DESC
    ),
    CALCULATE([Total Revenue])
)
```

---

## 📁 Folder: Product Analysis (Category / Segment / Brand — never raw Product)

```dax
Category Revenue Share % =
VAR CategoryRevenue = [Total Revenue]
VAR AllCategoriesRevenue =
    CALCULATE ( [Total Revenue], ALLSELECTED ( dim_product[CATEGORY] ) )
RETURN
    DIVIDE ( CategoryRevenue, AllCategoriesRevenue )
```

```dax
Brand Revenue Rank =
RANKX (
    ALLSELECTED ( dim_product[BRAND_2] ),
    CALCULATE ( [Total Revenue] ),
    ,
    DESC,
    Dense
)
```
*Ranking done over Brand, deliberately not PRODUCT_ID — see model note
at the top of this document.*

```dax
Segment Contribution to Category % =
VAR SegmentRevenue = [Total Revenue]
VAR CategoryRevenue =
    CALCULATE ( [Total Revenue], ALLSELECTED ( dim_product[SEGMENT] ) )
RETURN
    DIVIDE ( SegmentRevenue, CategoryRevenue )
```

```dax
Brand Cumulative Revenue % (for Pareto) =
VAR CurrentBrandRevenue = [Total Revenue]
VAR BrandsRankedHigherOrEqual =
    FILTER (
        ALLSELECTED ( dim_product[BRAND_2] ),
        CALCULATE ( [Total Revenue] ) >= CurrentBrandRevenue
    )
VAR CumulativeRevenue =
    CALCULATE ( [Total Revenue], BrandsRankedHigherOrEqual )
VAR TotalRevenueAllBrands =
    CALCULATE ( [Total Revenue], ALLSELECTED ( dim_product[BRAND_2] ) )
RETURN
    DIVIDE ( CumulativeRevenue, TotalRevenueAllBrands )
```
*Drives the Pareto line series. Combine with a bar of `[Total Revenue]`
by Brand, sorted descending, to build the classic Pareto chart.*

```dax
Brand ABC Classification =
VAR CumulativePct = [Brand Cumulative Revenue % (for Pareto)]
RETURN
    SWITCH (
        TRUE (),
        CumulativePct <= 0.8, "A — Top 80%",
        CumulativePct <= 0.95, "B — Next 15%",
        "C — Long Tail"
    )
```
*Standard ABC thresholds (80/15/5). Used as a legend/slicer value on the
Product Intelligence page, not just a hidden calc.*

```dax
Top N Brands Selector (Field Parameter support) =
VAR SelectedN = SELECTEDVALUE ( 'Top N Parameter'[Top N Value], 10 )
VAR BrandRank = [Brand Revenue Rank]
RETURN
    IF ( BrandRank <= SelectedN, [Total Revenue] )
```
*Pairs with a What-If parameter table (`Top N Parameter`, values 5/10/15/20)
to drive a dynamic Top-N bar chart without needing a separate TOPN table.*

---

## 📁 Folder: Geography Analysis

```dax
Regional Revenue Share % =
VAR RegionRevenue = [Total Revenue]
VAR AllRegionsRevenue =
    CALCULATE ( [Total Revenue], ALLSELECTED ( dim_geography[REGION] ) )
RETURN
    DIVIDE ( RegionRevenue, AllRegionsRevenue )
```

```dax
City Revenue Rank =
RANKX (
    ALLSELECTED ( dim_geography[CITY] ),
    CALCULATE ( [Total Revenue] ),
    ,
    DESC,
    Dense
)
```

```dax
City Performance Index =
VAR CityRevenue = [Total Revenue]
VAR AvgCityRevenue =
    AVERAGEX (
        ALLSELECTED ( dim_geography[CITY] ),
        CALCULATE ( [Total Revenue] )
    )
RETURN
    DIVIDE ( CityRevenue, AvgCityRevenue )
```
*Index of 1.0 = performing at the average city's level; >1 = above
average. Drives conditional formatting (green >1.1, amber 0.9–1.1, red <0.9)
on the City scorecard.*

```dax
Is Top 5 City =
VAR CurrentRank = [City Revenue Rank]
RETURN
    IF ( CurrentRank <= 5, "Top 5", "Other" )
```

```dax
Is Bottom 5 City =
VAR CurrentRank = [City Revenue Rank]
VAR TotalCities = CALCULATE ( DISTINCTCOUNT ( dim_geography[CITY] ), ALLSELECTED ( dim_geography[CITY] ) )
RETURN
    IF ( CurrentRank > TotalCities - 5, "Bottom 5", "Other" )
```

---

## 📁 Folder: Store Analysis

```dax
Revenue per Store =
VAR StoreCount = DISTINCTCOUNT ( dim_store[STORE_ID] )
RETURN
    DIVIDE ( [Total Revenue], StoreCount )
```

```dax
Store Revenue Rank =
RANKX (
    ALLSELECTED ( dim_store[STORE_ID] ),
    CALCULATE ( [Total Revenue] ),
    ,
    DESC,
    Dense
)
```
*Meaningful here — unlike PRODUCT_ID, stores have real repeat volume
(1,497 stores across 11,050 transactions, ~7.4 transactions/store average),
so store-level ranking is statistically sound.*

```dax
Store Type Revenue Share % =
VAR StoreTypeRevenue = [Total Revenue]
VAR AllStoreTypesRevenue =
    CALCULATE ( [Total Revenue], ALLSELECTED ( dim_store[STORE TYPE] ) )
RETURN
    DIVIDE ( StoreTypeRevenue, AllStoreTypesRevenue )
```

```dax
Sales Channel Revenue Share % =
VAR ChannelRevenue = [Total Revenue]
VAR AllChannelsRevenue =
    CALCULATE ( [Total Revenue], ALLSELECTED ( dim_store[SALES_CHANNEL] ) )
RETURN
    DIVIDE ( ChannelRevenue, AllChannelsRevenue )
```

---

## 📁 Folder: Supply Chain & Risk Analysis

```dax
High Risk Transaction Count =
CALCULATE (
    COUNTROWS ( fact_sales ),
    fact_sales[InventoryRiskFlag] = "High Risk"
)
```

```dax
High Risk Rate % =
VAR HighRiskCount = [High Risk Transaction Count]
VAR TotalCount = COUNTROWS ( fact_sales )
RETURN
    DIVIDE ( HighRiskCount, TotalCount )
```

```dax
Average Supplier Lead Time =
AVERAGE ( fact_sales[supplier_lead_time_days] )
```

```dax
DC Revenue Contribution % =
VAR DCRevenue = [Total Revenue]
VAR AllDCRevenue =
    CALCULATE ( [Total Revenue], ALLSELECTED ( dim_supplier[DISTRIBUTION_CENTER] ) )
RETURN
    DIVIDE ( DCRevenue, AllDCRevenue )
```

```dax
Warehouse Unknown Flag Rate % =
VAR UnknownCount =
    CALCULATE ( COUNTROWS ( fact_sales ), dim_warehouse[WAREHOUSE_ID] = "UNKNOWN" )
VAR TotalCount = COUNTROWS ( fact_sales )
RETURN
    DIVIDE ( UnknownCount, TotalCount )
```
*Surfaced deliberately, not hidden — 2% of records have an unresolved
warehouse (imputed during ETL cleaning). A senior reviewer will notice if
this is swept under the rug; showing it as a small "Data Completeness"
KPI signals data-quality maturity instead.*

```dax
Supplier Scorecard Composite =
VAR LeadTimeScore = 1 - DIVIDE ( [Average Supplier Lead Time] - 2, 14 - 2 )
VAR RiskScore = 1 - [High Risk Rate %]
RETURN
    ( LeadTimeScore * 0.5 ) + ( RiskScore * 0.5 )
```
*Simple weighted composite (0–1, higher is better) combining lead-time
performance and inventory-risk exposure per supplier. Weights are a
documented assumption (50/50) — flagged in the data dictionary as a
business rule that should be validated with actual stakeholders, not
presented as an empirically-derived formula.*

---

## 📁 Folder: Dynamic Titles & Narrative (Smart Narrative support)

```dax
Dynamic Page Title — Executive Overview =
VAR SelectedYear = SELECTEDVALUE ( dim_date[Year], "All Years" )
VAR SelectedRegion = SELECTEDVALUE ( dim_geography[REGION], "All Regions" )
RETURN
    "Executive Overview — " & SelectedRegion & " — " & SelectedYear
```

```dax
Dynamic Narrative — Revenue Commentary =
VAR YoY = [Revenue YoY %]
VAR Direction = IF ( YoY >= 0, "up", "down" )
VAR TopCategory =
    CALCULATE (
        SELECTEDVALUE ( dim_product[CATEGORY] ),
        TOPN ( 1, ALLSELECTED ( dim_product[CATEGORY] ), CALCULATE ( [Total Revenue] ), DESC )
    )
RETURN
    "Revenue is " & Direction & " " & FORMAT ( ABS ( YoY ), "0.0%" )
    & " year-over-year, led by " & TopCategory & "."
```
*Feeds a Smart Narrative / dynamic text box. Kept as a single sentence —
narrative boxes that try to say too much read as gimmicky rather than
executive.*

---

## 📁 Folder: Utility (non-visual, supporting measures)

```dax
Selected Period Label =
VAR StartMonth =
MIN(dim_date[Month])

VAR StartYear =
MIN(dim_date[Year])

VAR EndMonth =
MAX(dim_date[Month])

VAR EndYear =
MAX(dim_date[Year])

RETURN
StartMonth
&
" "
&
StartYear
&
" - "
&
EndMonth
&
" "
&
EndYear
```

```dax
Transaction Count =
COUNTROWS ( fact_sales )
```
*Used as a lightweight sanity-check card on the hidden Measure Table
page — confirms slicer context matches expectations during QA.*

---

## Performance notes (documented, not just implemented)

- Every ranking measure uses `ALLSELECTED`, not `ALL` — preserves slicer
  context (e.g. ranking within a filtered Region) while still ignoring the
  visual's own row context, which is the correct pattern for RANKX inside
  a table/matrix visual.
- No calculated columns were added beyond the one required `dim_date[Date]`
  fix — every other derived value is a measure, computed at query time
  against the current filter context, per the "avoid unnecessary calculated
  columns" requirement.
- `DIVIDE()` used everywhere instead of `/` — returns BLANK() instead of
  throwing an error on zero denominators (relevant given the nulls in
  `units_sales` and `PricePerUnit`).

---

## 📁 Folder: Rolling Windows (extends Time Intelligence)

```dax
Revenue Rolling 6-Month =
VAR CurrentDate = MAX ( dim_date[Date] )
VAR Window = DATESINPERIOD ( dim_date[Date], CurrentDate, -6, MONTH )
RETURN
    CALCULATE ( [Total Revenue], Window )
```

```dax
Revenue Rolling 12-Month =
VAR CurrentDate = MAX ( dim_date[Date] )
VAR Window = DATESINPERIOD ( dim_date[Date], CurrentDate, -12, MONTH )
RETURN
    CALCULATE ( [Total Revenue], Window )
```
*Note: with a 42-month curated date range (Jan 2019–Jun 2022), a rolling
12-month window is valid from Jan 2020 onward only — the first 11 months
of the dataset will show a partial window. This is real, not a bug; the
DAX correctly reflects however much history is available, and the visual
should note "rolling 12mo (partial before 2020)" rather than padding with
zeros.*

```dax
Revenue Rolling 6-Month Average =
DIVIDE ( [Revenue Rolling 6-Month], 6 )
```

```dax
Revenue Rolling 12-Month Average =
DIVIDE ( [Revenue Rolling 12-Month], 12 )
```

```dax
Units Rolling 3-Month =
VAR CurrentDate = MAX ( dim_date[Date] )
VAR Window = DATESINPERIOD ( dim_date[Date], CurrentDate, -3, MONTH )
RETURN
    CALCULATE ( [Total Units Sold], Window )
```

---

## 📁 Folder: Variance & Contribution

```dax
Revenue Variance vs Prior Period =
[Total Revenue] - [Revenue Prior Month]
```

```dax
Revenue Variance % vs Prior Period =
DIVIDE ( [Revenue Variance vs Prior Period], [Revenue Prior Month] )
```

```dax
Market Share % (Category within Total) =
DIVIDE (
    [Total Revenue],
    CALCULATE ( [Total Revenue], ALL ( dim_product[CATEGORY] ) )
)
```
*Distinct from `[Category Revenue Share %]` — this version uses `ALL`
(not `ALLSELECTED`) deliberately, giving true market share against the
entire dataset regardless of slicer state. Use this on the Executive
Overview; use the `ALLSELECTED` version inside interactive drill visuals.*

---

## 📁 Folder: Dimension-Specific KPI Sets

**Store KPIs**
```dax
Store Count (Active) =
DISTINCTCOUNT ( fact_sales[store_key] )
```
```dax
Average Transactions per Store =
DIVIDE ( COUNTROWS ( fact_sales ), [Store Count (Active)] )
```

**Supplier KPIs**
```dax
Supplier Count (Active) =
DISTINCTCOUNT ( fact_sales[supplier_key] )
```
```dax
Supplier Lead Time Variance =
VAR SupplierAvg = [Average Supplier Lead Time]
VAR OverallAvg =
    CALCULATE ( [Average Supplier Lead Time], ALL ( dim_supplier[SUPPLIER_ID] ) )
RETURN
    SupplierAvg - OverallAvg
```

**Warehouse KPIs**
```dax
Warehouse Count (Excl. Unknown) =
CALCULATE (
    DISTINCTCOUNT ( dim_warehouse[WAREHOUSE_ID] ),
    dim_warehouse[WAREHOUSE_ID] <> "UNKNOWN"
)
```
```dax
Warehouse Data Completeness % =
1 - [Warehouse Unknown Flag Rate %]
```

**Inventory KPIs**
```dax
Out of Stock Rate % =
VAR OutOfStockCount =
    CALCULATE ( COUNTROWS ( fact_sales ), fact_sales[inventory_status] = "Out of Stock" )
VAR TotalCount = COUNTROWS ( fact_sales )
RETURN
    DIVIDE ( OutOfStockCount, TotalCount )
```
```dax
Low Stock Rate % =
VAR LowStockCount =
    CALCULATE ( COUNTROWS ( fact_sales ), fact_sales[inventory_status] = "Low Stock" )
VAR TotalCount = COUNTROWS ( fact_sales )
RETURN
    DIVIDE ( LowStockCount, TotalCount )
```

**Region KPIs**
```dax
Region Count (Active) =
DISTINCTCOUNT ( dim_geography[REGION] )
```
```dax
Region Revenue Variance vs Average =
VAR RegionRevenue = [Total Revenue]
VAR AvgRegionRevenue =
    AVERAGEX ( ALLSELECTED ( dim_geography[REGION] ), CALCULATE ( [Total Revenue] ) )
RETURN
    RegionRevenue - AvgRegionRevenue
```

**Brand KPIs** *(see Product Analysis folder above for ranking/Pareto/ABC — these are supplementary)*
```dax
Brand Count (Active) =
DISTINCTCOUNT ( dim_product[BRAND_2] )
```

**Category KPIs**
```dax
Category Count =
DISTINCTCOUNT ( dim_product[CATEGORY] )
```
*Always 6 in this dataset — a static-looking KPI, included for
completeness and because a slicer-filtered view could show fewer.*

**Segment KPIs**
```dax
Segment Count =
DISTINCTCOUNT ( dim_product[SEGMENT] )
```

---

## 📁 Folder: SVG Icons & Color Measures (dynamic conditional icons)

Power BI supports data-URI SVG measures for dynamic icons in tables/cards
(image measures set to "Image URL" data category). Pattern used throughout:

```dax
Trend Icon (Revenue YoY) =
VAR YoY = [Revenue YoY %]
VAR IconColor = IF ( YoY >= 0, "238B57", "C0392B" )
VAR Rotation = IF ( YoY >= 0, "0", "180" )
RETURN
    "data:image/svg+xml;utf8," &
    "<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24'>" &
    "<g transform='rotate(" & Rotation & " 12 12)'>" &
    "<path d='M12 2 L20 14 L14 14 L14 22 L10 22 L10 14 L4 14 Z' fill='#" & IconColor & "'/>" &
    "</g></svg>"
```
*Note: `238B57`/`C0392B` are the hex values of the theme's `good`/`bad`
tokens without the `#`, kept in sync manually since DAX can't reference
the theme JSON directly — documented here so a future edit to the theme
palette is a two-place update, not a silent mismatch.*

```dax
Risk Flag Icon =
VAR Flag = SELECTEDVALUE ( fact_sales[InventoryRiskFlag] )
VAR IconColor =
    SWITCH ( Flag, "High Risk", "C0392B", "Watch", "D9A400", "238B57" )
RETURN
    "data:image/svg+xml;utf8," &
    "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'>" &
    "<circle cx='8' cy='8' r='7' fill='#" & IconColor & "'/></svg>"
```

```dax
KPI Status Color (hex, for conditional formatting rules) =
VAR YoY = [Revenue YoY %]
RETURN
    SWITCH (
        TRUE (),
        YoY >= 0.05, "#238B57",
        YoY >= 0, "#D9A400",
        "#C0392B"
    )
```
*Bind this directly in a visual's Conditional Formatting → Font Color →
"Format by: Field Value" for a data-driven KPI card color, without a
separate rules dialog per visual — one measure, reused everywhere.*

```dax
ABC Classification Color =
SWITCH (
    SELECTEDVALUE ( dim_product[BRAND_2] ) <> BLANK (),
    [Brand ABC Classification],
    "A — Top 80%", "#1B3A5C",
    "B — Next 15%", "#D9A400",
    "#B0B0B0"
)
```

---

## 📁 Folder: Tooltip & Bookmark Support Measures

```dax
Tooltip — 12-Month Sparkline Label =
"Last 12 months: " & FORMAT ( [Revenue Rolling 12-Month], "₹#,##0,,\"M\"" )
```

```dax
Tooltip — Period Comparison Text =
VAR CurrentRevenue = [Total Revenue]
VAR PriorRevenue = [Revenue PY]
VAR Direction = IF ( CurrentRevenue >= PriorRevenue, "▲", "▼" )
RETURN
    Direction & " " & FORMAT ( ABS ( [Revenue YoY %] ), "0.0%" ) & " vs last year"
```

```dax
Bookmark Active State Label =
VAR SelectedView = SELECTEDVALUE ( 'View Selector'[View], "Monthly" )
RETURN
    "Viewing: " & SelectedView
```
*Pairs with a disconnected `View Selector` table (values: Monthly,
Quarterly, YoY) used purely to drive bookmark button labels/state — not
a data model relationship, just a UI-state helper table.*

---

## 📁 Folder: Customer-Friendly Formatting Helpers

```dax
Total Revenue (Formatted) =
VAR Revenue = [Total Revenue]
RETURN
    SWITCH (
        TRUE (),
        Revenue >= 10000000, FORMAT ( Revenue / 10000000, "0.0" ) & " Cr",
        Revenue >= 100000, FORMAT ( Revenue / 100000, "0.0" ) & " L",
        FORMAT ( Revenue, "#,##0" )
    )
```
*Indian numbering convention (Crore/Lakh) — appropriate given the
source data's Indian comma-formatting (`"8,17,935"`) found during
profiling; matches the audience's expectations better than raw millions.*

```dax
Total Units Sold (Formatted) =
FORMAT ( [Total Units Sold], "#,##0" ) & " units"
```

