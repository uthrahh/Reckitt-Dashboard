# Power BI Build Guide — Reckitt FMCG Executive Analytics

Canvas standard: **1280 × 720px** (16:9, Power BI default). All positions
given as `(x, y, width, height)` in px from top-left. Import
`executive_theme.json` before placing any visuals — apply it first so every
default visual inherits the correct palette/typography rather than retrofitting.

**Global elements on every report page (not repeated per-page below):**
- Left nav rail: `(0, 0, 64, 720)` — background `#1B3A5C`, 7 custom SVG icon
  buttons (Home, Sales, Geo, Product, Store, Supply Chain, Data Engineering),
  each `(12, y, 40, 40)`
  stacked with 20px gaps starting at y=40. Active page icon gets a 3px
  `#5FA8D3` left-border indicator.
- Top filter bar: `(64, 0, 1216, 48)` — background `#FAFBFC`, bottom
  1px border `#E5E7EA`. Contains: Year slicer (dropdown, `(80,8,140,32)`),
  Region slicer (`(230,8,140,32)`), Category slicer (`(380,8,160,32)`), all
  **synced via Sync Slicers** across every page. Dynamic page title
  (measure-driven textbox) right-aligned at `(700,8,560,32)`.
- Content area: `(64, 48, 1216, 672)` — this is where each page's unique
  layout below is placed.

---

## Page 1 — Executive Overview

**Business question answered:** What happened, and is it good or bad — at a glance?

**Layout (content area 1216×672):**

Row 1 — KPI card strip, `y=64`, 6 cards, each `192×110`, 8px gaps:
| Card | Position x | Measure |
|---|---|---|
| Total Revenue | 64 | `[Total Revenue]` + `[Revenue YoY %]` trend arrow |
| Total Units Sold | 264 | `[Total Units Sold]` |
| Average Selling Price | 464 | `[Average Selling Price]` |
| Order Fulfillment Rate | 664 | `[Order Fulfillment Rate %]` |
| High Risk Rate | 864 | `[High Risk Rate %]`, red if >10% (conditional format) |
| Net Revenue | 1064 | `[Net Revenue]` |

Each KPI card: uses the **KPI visual** (not plain Card) with a sparkline
trendline against `dim_date[Date]` and a small YoY delta indicator —
satisfies "trend indicators + sparklines" without needing 6 separate charts.

Row 2, `y=190`:
- **Revenue Trend (line chart)** `(64,190,600,220)` — monthly `Total Revenue`
  with `Revenue 3-Month Moving Average` as a secondary dashed line.
- **Top Category / Top Brand / Top Region (3 stacked callout cards)**
  `(680,190,536,220)` — each uses `TOPN(1, ...)` measures, large number +
  category label, arranged in a 3-column mini-grid.

Row 3, `y=430`:
- **Dynamic Narrative textbox** `(64,430,600,90)` — bound to
  `[Dynamic Narrative — Revenue Commentary]`, styled as a quote/callout
  block with a left accent bar.
- **Inventory Risk donut** `(680,430,260,220)` — `InventoryRiskFlag`
  breakdown (Normal/Watch/High Risk), colors from `good`/`neutral`/`bad`
  theme tokens.
- **Region contribution bar** `(956,430,260,220)` — horizontal bar,
  `Regional Revenue Share %` by Region.

Row 4, `y=540` (only if space allows after Row 3 — otherwise this becomes
a scrollable footer): comparison toggle bookmark buttons ("This Year" /
"Last Year" / "All Time") `(64,650,300,30)`.

**Bookmark: Executive Story (guided sequence)** — 4-step bookmark group
that progressively highlights: (1) headline KPIs → (2) trend → (3) risk
callout → (4) full page. Used for live presentation walkthroughs.

---

## Page 2 — Sales Intelligence

**Business question:** Why did revenue move, and where is it heading?

Layout:
- **KPI strip** (same pattern as Page 1 but smaller): Revenue, MoM%, YoY%,
  Running Total — `(64,64,1216,90)`.
- **Waterfall chart** `(64,170,600,260)` — revenue bridge by Category
  showing period-over-period contribution to the change (this *is* the
  visual Power BI's native Waterfall is built for — category-level
  contribution to a variance, not raw category totals).
- **Ribbon chart** `(680,170,536,260)` — Category rank-shift over months,
  shows which category is #1 by revenue each period and how ranks swap.
- **Moving average + running total combo (line + area)** `(64,450,600,220)`.
- **Small multiples** `(680,450,536,220)` — one mini line chart per Region
  (5 small multiples), same y-axis scale, revenue trend — lets an
  executive compare regional trajectories at a glance without a legend
  clutter.

**Bookmarks:** "Monthly View" ↔ "Quarterly View" ↔ "YoY View" — three
bookmarks that swap the primary line chart's date hierarchy level via
bookmark-captured drill state, plus toggle visibility of the ribbon chart
(only relevant in Monthly/Quarterly, hidden in YoY).

---

## Page 3 — Geographic Intelligence

**Business question:** Where did it happen, and where should we focus next?

Layout:
- **Filled/Shape map of India** `(64,64,600,380)` — Region or State level
  (Power BI's Shape Map, using a State-level TopoJSON — City-level lat/long
  isn't reliably geocoded from city names alone at this scale, so State is
  the map's grain; City remains available via the drilldown hierarchy in
  the table beside it, not by pushing the map itself to city pins).
- **Region → State → City drilldown bar chart** `(680,64,536,380)` —
  standard Power BI drill hierarchy (right-click drill down / use the
  drill arrows in the visual header).
- **Top 5 / Bottom 5 Cities table** `(64,460,600,210)` — two-column
  layout inside one table using `[Is Top 5 City]` / `[Is Bottom 5 City]`
  as a slicer-driven toggle (bookmark swap, not two separate visuals).
- **City Performance Index heatmap (matrix with conditional formatting)**
  `(680,460,536,210)` — Cities as rows, `[City Performance Index]` as a
  background-color-scaled value (red–amber–green via theme `minimum`/
  `center`/`maximum` tokens).

**Drillthrough target:** right-click any City → **City Profile** page.

---

## Page 4 — Product Intelligence

**Business question:** Which categories/brands drive the business, and
where's the long tail? *(Built at Category/Segment/Brand grain per the
agreed design decision — Product-level ranking is not used.)*

Layout:
- **Treemap** `(64,64,600,300)` — Category → Segment, sized by
  `[Total Revenue]`, colored by `[Category Revenue Share %]`.
- **Pareto chart (combo: bar + line)** `(680,64,536,300)` — Brand revenue
  bars (descending) + `[Brand Cumulative Revenue % (for Pareto)]` line on
  a secondary axis with an 80% reference line.
- **ABC Classification matrix** `(64,380,600,180)` — Brand rows grouped
  by `[Brand ABC Classification]`, revenue and share % columns,
  conditional formatting (A=green, B=amber, C=grey).
- **Top N Brand selector (Field Parameter + What-if)** `(680,380,536,180)`
  — a slicer bound to the `Top N Parameter` table (5/10/15/20) driving a
  dynamic bar chart via `[Top N Brands Selector (Field Parameter support)]`.
- **Decomposition Tree** `(64,575,1152,105)` — full-width, analyze
  `[Total Revenue]`, explore by Category → Segment → Brand → Region
  (AI-splits enabled). Placed at the bottom as the "explore freely" tool
  after the guided visuals above.

**Drillthrough target:** right-click any Brand → **Brand Profile** page.

---

## Page 5 — Store Intelligence

**Business question:** Which stores/channels are winning or lagging?
*(Store-level ranking IS statistically meaningful — 1,497 stores across
11,050 transactions, ~7.4 avg transactions/store.)*

Layout:
- **KPI strip:** Revenue per Store, Store Count, Top Store Type share —
  `(64,64,1216,90)`.
- **Store Type × Sales Channel heatmap (matrix)** `(64,170,600,260)` —
  rows=Store Type, columns=Sales Channel, values=`[Total Revenue]`,
  background color scale.
- **Top 10 / Worst 10 Store scorecard (table)** `(680,170,536,260)` —
  toggle via bookmark (Top ↔ Worst), `[Store Revenue Rank]` +
  `[Revenue per Store]`, conditional formatting data bars.
- **Store Type revenue share (donut)** `(64,450,300,220)`.
- **Sales Channel revenue share (donut)** `(380,450,300,220)`.
- **Store performance distribution (histogram-style column chart)**
  `(696,450,520,220)` — revenue-per-store distribution to visually show
  the spread, not just top/bottom extremes.

**Drillthrough target:** right-click any Store → **Store Profile** page.

---

## Page 6 — Supply Chain Intelligence

**Business question:** Who's creating risk, and where?

Layout:
- **KPI strip:** Avg Supplier Lead Time, High Risk Rate, DC Count,
  Warehouse Data Completeness (`1 - [Warehouse Unknown Flag Rate %]`) —
  `(64,64,1216,90)`.
- **Risk Matrix (matrix visual)** `(64,170,600,260)` — Supplier rows,
  columns = Lead Time bucket vs. Risk Flag, conditional-formatted cell
  background — a true 2D risk matrix, not just a table.
- **Supplier Scorecard (table)** `(680,170,536,260)` — ranked by
  `[Supplier Scorecard Composite]`, columns for lead time, risk rate,
  DC.
- **DC Revenue Contribution (bar)** `(64,450,300,220)` — all 5 DCs, real
  spread (₹446M–₹959M), no aggregation risk here.
- **Warehouse Health (bar incl. UNKNOWN)** `(380,450,300,220)` —
  deliberately includes the `UNKNOWN` warehouse bucket rather than
  filtering it out, with a callout noting the 2% data-completeness gap.
- **Inventory Status breakdown (stacked bar)** `(696,450,520,220)` — In
  Stock / Low Stock / Reserved / Out of Stock by Region.

**Drillthrough target:** right-click any Supplier → **Supplier Profile** page.

---

## Page 7 — Drillthrough (4 variants: Brand / City / Store / Supplier Profile)

Built as **one page template duplicated 4 times** (Power BI drillthrough
pages must be separate pages, but the layout is identical — only the
drillthrough filter field differs). Each has:
- Drillthrough filter well pre-set to the relevant field (Brand / City /
  Store_ID / Supplier_ID).
- Header row: selected entity name (large callout text, dynamic title) +
  a "Back" button (built-in Back arrow action, top-left `(80,56,32,32)`).
- KPI row: Revenue, Units, Rank vs. peers, Risk flag — 4 cards
  `(64,110,1216,100)`.
- Trend line for the selected entity `(64,220,600,240)`.
- Peer comparison bar (selected entity highlighted vs. top 10 peers)
  `(680,220,536,240)`.
- Full transaction-level table (only place `PRODUCT_ID`/`BARCODE` detail
  is shown — appropriate here since the user has already filtered down to
  one entity, so per-transaction detail is meaningful, unlike an
  unfiltered product ranking) `(64,470,1152,200)`.

---

## Page 8 — Hidden Tooltip Pages (2 variants)

Set page size to **Tooltip (320×240px)** in Page Information settings,
and mark "Allow use as tooltip" on. Two tooltip pages:

**Tooltip A — KPI Trend Mini-Dashboard**
- Small sparkline of the hovered measure over the last 12 months
  `(10,10,300,140)`.
- Current vs. prior-period comparison text `(10,155,300,40)`.
- Applied to every KPI card across all pages via each visual's
  Format → Tooltips → Report Page Tooltip = "Tooltip A".

**Tooltip B — Entity Quick-Profile** (for bar/map hover)
- Entity name + revenue + rank, 3-line compact card.
- Applied to Region/City/Brand/Store visuals.

---

## Hidden/Technical Pages (not in nav rail)

- **Measure Table page** — a plain table listing every DAX measure by
  folder, for reviewer/recruiter transparency (shows the measure names,
  not the DAX code itself — code lives in this document and the .pbix).
- **Data Quality Notes page** — a documentation page inside the report
  itself: the 3.5-year date range, the near-degenerate Product dimension
  decision, the 2% Warehouse UNKNOWN rate, the 15 negative-value
  transactions. Hidden from nav, accessible via a small "ℹ" icon in the
  bottom-right corner of every page (View → Page Navigator settings:
  hide from nav bar, but page itself is not "Hidden" so the icon can
  still navigate to it).

---

## Interactions Matrix (cross-filtering / cross-highlighting)

| Source Visual | Target Visual | Interaction |
|---|---|---|
| Category slicer (global) | All visuals, all pages | Filter |
| KPI cards | (none — cards are terminal, no outgoing interaction) | — |
| Region bar (Page 3) | City drilldown chart | Cross-highlight |
| Treemap (Page 4) | Pareto chart, ABC matrix | Filter |
| Store Type heatmap (Page 5) | Scorecard table | Cross-highlight |
| Risk Matrix (Page 6) | Supplier Scorecard | Filter |

All other visual-pairs on the same page default to Power BI's automatic
cross-highlight — explicitly reviewed per page in Format → Edit
Interactions to switch to "None" wherever a visual shouldn't filter its
neighbor (e.g. the Dynamic Narrative textbox never filters anything back).

## Navigation Buttons & Actions

- Nav rail icons: **Action = Page Navigation**, target = respective page.
- "Back" button on all drillthrough/tooltip-adjacent pages: **Action =
  Back**.
- Bookmark toggle buttons (This Year/Last Year/All Time, Monthly/
  Quarterly/YoY, Top/Worst): **Action = Bookmark**, each button paired
  1:1 with a bookmark in the Bookmarks pane, grouped by page.

## Field Parameters & What-If Parameters

- **`Top N Parameter`** (What-if): values 5, 10, 15, 20 — drives the Top
  N Brand selector on Page 4.
- **`Metric Selector` (Field Parameter):** lets the Executive Overview
  trend line swap between Revenue / Units / ASP without needing 3
  separate charts — a single dropdown slicer bound to the field parameter.

---

## Page 9 — Data Engineering (new: emphasizes engineering maturity, not just BI)

**Business question:** Can this data be trusted, and does the person who
built this pipeline understand production data engineering? *(This page
exists specifically because the audience includes recruiters and senior
BI/data engineers, not just business stakeholders — it makes the ETL
rigor visible inside the deliverable itself, not just in a separate repo.)*

Layout:
- **Pipeline flow diagram (image/SVG import of the Mermaid architecture
  diagram, rendered to PNG)** `(64,64,600,260)` — Raw CSV → Validation →
  Cleaning → Feature Engineering → Star Schema → Curated Export, matching
  `docs/diagrams/system_architecture.md` from the repo.
- **Data Quality Scorecard (KPI card row)** `(680,64,536,120)`:
  - Rows Loaded: 11,050 → 11,050 after cleaning (0 dropped)
  - Duplicate Rows Removed (from raw)
  - Invalid Numeric Values Corrected (placeholder tokens nulled)
  - `[Warehouse Data Completeness %]` — 98% (221/11,050 imputed as UNKNOWN)
- **Star Schema ERD (image import of `star_schema.md` Mermaid diagram)**
  `(680,200,536,260)`.
- **Known Data Limitations (table/text callout)** `(64,340,1152,120)` —
  states explicitly, in plain business language:
  - "Product-level detail exists at near-1:1 transaction granularity
    (10,932 of 10,991 products appear in exactly one transaction) —
    product analysis is performed at Category/Segment/Brand level instead."
  - "15 transactions have negative revenue not fully explained by order
    status alone — isolated in the `Net Revenue` measure."
  - "2% of transactions have an unresolved warehouse, imputed as UNKNOWN
    during cleaning rather than dropped."
- **Tech Stack badges (icon row)** `(64,480,1152,60)` — PySpark, Python,
  YAML, pytest, Power BI, Git — small logo/text chips, consistent with
  the README's Technology Stack table.
- **Link-out card** `(64,560,600,60)` — "Full pipeline source, 39 passing
  tests, and documentation: [GitHub repo link]" — text box, not a live
  hyperlink action (Power BI Service sometimes blocks outbound links by
  default; documented as a manual paste-in step during publish).

This page is **included in the nav rail** (unlike the hidden technical
pages) — it's a first-class page precisely because the audience for this
report is the audience for this page.

---

## Key Influencers Visual

Added to **Page 6 (Supply Chain Intelligence)**, `(64,340,600,180)`,
replacing/supplementing part of the Risk Matrix row on smaller screens:
- **Analyze:** `InventoryRiskFlag = "High Risk"`
- **Explain by:** `supplier_lead_time_days`, `DISTRIBUTION_CENTER`,
  `STORE TYPE`, `SALES_CHANNEL`
- Rationale for inclusion here specifically: lead time and DC are the two
  fields most plausibly causal for risk, so this is the one page where
  Key Influencers adds real analytical value rather than being a novelty
  visual bolted on for feature-checklist reasons.

## Q&A Visual

Added to **Page 1 (Executive Overview)** as a collapsible visual at
`(64,650,1216,60)` (expands upward on click, minimized by default so it
doesn't compete with the KPI strip). Pre-seeded starter questions
(Q&A → Configure → Featured Questions) since natural-language Q&A over a
star schema with abbreviated column names (`PACK unit`, `BRAND_2`) works
far better with example phrasing than a blank box:
- "What is total revenue by category?"
- "Show units sold by region this year"
- "Which brand has the highest revenue?"

Synonyms configured in Q&A setup: `BRAND_2` → "brand", `CATEGORY` →
"category", `value_sales` → "revenue" / "sales", `units_sales` → "units" /
"volume" — without this, Q&A's natural-language matching against the raw
technical field names would perform poorly and undercut the "enterprise"
impression rather than support it.

---

## Build Order (recommended sequence in Power BI Desktop)

1. Import all 7 curated CSVs, build relationships (star schema, all
   1-to-many from dimensions to fact, single-direction filter).
2. Add the `dim_date[Date]` calculated column, mark as Date Table.
3. Import `executive_theme.json` (File → Options → Themes → Import).
4. Create the Measures Table (Enter Data → empty table named
   "📐 Measures"), paste in every measure from `dax_measures.md`, organize
   into Display Folders matching the section headers there.
5. Build Page 1 first (Executive Overview) — validates the theme and
   core measures visually before replicating the pattern across pages 2–6.
6. Build drillthrough pages, wire up drillthrough fields.
7. Build tooltip pages, assign to visuals last (once base visuals exist).
8. Add nav rail + bookmarks + interactions last, once every page's
   content is final — bookmarks capture page state, so building them
   before the layout is finished means re-recording them after every
   layout change.
9. Build Page 9 (Data Engineering) — best done after the ETL repo's own
   docs/diagrams are finalized, since this page re-uses those diagrams
   as static images rather than recreating them natively in Power BI.
10. Configure Key Influencers (Page 6) and Q&A (Page 1) last — both
    depend on the full data model and measures already existing, and
    Q&A synonym configuration is easiest to get right once you already
    know which fields end users actually ask about during a dry run.

