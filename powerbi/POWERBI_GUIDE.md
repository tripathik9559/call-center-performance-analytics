# Power BI Dashboard - Step by Step

You will build a 2-page dashboard in about 60-90 minutes. Every number it shows will match
`outputs/key_insights.md` and the SQL queries (same KPI definitions).

## 1. Load the data (pick ONE option)

**Option A - CSV (easiest, no database needed)**
1. Power BI Desktop -> Home -> Get data -> Text/CSV -> `data/clean/calls_clean.csv` -> Transform Data
2. Repeat for `data/clean/agents.csv`

**Option B - MySQL (shows SQL skills)**
1. Run `python src/load_to_mysql.py` and `sql/04_views_for_powerbi.sql` first
2. Get data -> MySQL database -> server `localhost`, database `call_center`
3. Select the views `vw_call_facts` and `vw_agent_scorecard` (install the MySQL connector if Power BI asks)

## 2. Power Query clean-up (Transform Data)

For `calls_clean.csv`:
1. `call_datetime` -> Data type: Date/Time
2. `call_date` -> Data type: Date
3. `call_hour`, `weekday_num`, `wait_seconds`, `handle_seconds`, `is_abandoned`, `within_sla`, `fcr_flag`, `csat_score`, `repeat_within_7d` -> Whole Number
4. Add column -> Custom column `Handle Minutes` = `[handle_seconds] / 60`
5. Add column -> Conditional column `Wait Bucket`:
   - `wait_seconds <= 20` -> "0-20 sec"; `<= 60` -> "21-60 sec"; `<= 120` -> "61-120 sec"; else "120+ sec"
6. Close & Apply

## 3. Data model

Model view -> create ONE relationship:
`agents[agent_id]` (one) -> `calls_clean[agent_id]` (many), single direction.
(Abandoned calls have no agent - that is normal.)

Then create a Date table: Modeling -> New table:

```DAX
Date =
ADDCOLUMNS (
    CALENDAR ( DATE ( 2026, 4, 1 ), DATE ( 2026, 9, 30 ) ),
    "Year", YEAR ( [Date] ),
    "Month No", MONTH ( [Date] ),
    "Month", FORMAT ( [Date], "MMM yyyy" ),
    "Weekday No", WEEKDAY ( [Date], 2 ),
    "Weekday", FORMAT ( [Date], "dddd" )
)
```

Relationship: `Date[Date]` (one) -> `calls_clean[call_date]` (many). Sort `Month` by `Month No`
and `Weekday` by `Weekday No` (Column tools -> Sort by column).

## 4. DAX measures

Create a blank table called `_Measures` (Home -> Enter data) and add these measures to it.

```DAX
Total Calls = COUNTROWS ( calls_clean )

Answered Calls = CALCULATE ( [Total Calls], calls_clean[call_status] = "Answered" )

Abandoned Calls = CALCULATE ( [Total Calls], calls_clean[call_status] = "Abandoned" )

Abandon Rate % = DIVIDE ( [Abandoned Calls], [Total Calls] )

SLA % = DIVIDE ( SUM ( calls_clean[within_sla] ), [Total Calls] )

AHT (min) =
DIVIDE (
    CALCULATE ( AVERAGE ( calls_clean[handle_seconds] ), calls_clean[call_status] = "Answered" ),
    60
)

ASA (sec) =
CALCULATE ( AVERAGE ( calls_clean[wait_seconds] ), calls_clean[call_status] = "Answered" )

FCR % = DIVIDE ( SUM ( calls_clean[fcr_flag] ), [Answered Calls] )

Avg CSAT = AVERAGE ( calls_clean[csat_score] )

Repeat Call % = DIVIDE ( SUM ( calls_clean[repeat_within_7d] ), [Total Calls] )

Calls Previous Month =
CALCULATE ( [Total Calls], DATEADD ( 'Date'[Date], -1, MONTH ) )

Calls MoM % = DIVIDE ( [Total Calls] - [Calls Previous Month], [Calls Previous Month] )

Abandon Rate vs Overall =
[Abandon Rate %] - CALCULATE ( [Abandon Rate %], ALL ( calls_clean ) )
```

Format: `Abandon Rate %`, `SLA %`, `FCR %`, `Repeat Call %`, `Calls MoM %` as Percentage (1 decimal);
`AHT (min)` 1 decimal; `Avg CSAT` 2 decimals.

**Check:** with no filters the cards must show: 59,976 calls, 5.1% abandon, 63.1% SLA,
7.5 min AHT, 39 sec ASA, 75.2% FCR, 3.84 CSAT, 12.5% repeat. If they match, your model is correct.

## 5. Page 1 - "Executive Overview"

| Visual | Fields |
|---|---|
| 6 KPI cards (top row) | Total Calls, Abandon Rate %, SLA %, AHT (min), FCR %, Avg CSAT |
| Column + line chart | X: `call_hour` - Columns: Total Calls - Line: Abandon Rate % |
| Clustered bar | Y: `queue` - X: FCR % (sort ascending, highlight lowest in red) |
| Line chart | X: `Date[Month]` - Y: Total Calls and Avg CSAT (secondary axis) |
| Matrix (heatmap) | Rows: `Date[Weekday]` - Columns: `call_hour` - Values: Abandon Rate % - Conditional formatting (background colour scale, white to red) |
| Slicers | `Date[Month]`, `queue`, `agents[shift]` |

## 6. Page 2 - "Agent & Staffing Performance"

| Visual | Fields |
|---|---|
| Clustered column | X: `agents[tenure_band]` - Y: AHT (min); line: FCR % |
| Table | agent_name, team, tenure_months, Answered Calls, AHT (min), FCR %, Avg CSAT - conditional format FCR % (red = low) |
| Scatter chart | X: AHT (min) - Y: Avg CSAT - Details: agent_name - Size: Answered Calls - Legend: team |
| Column chart | X: `Wait Bucket` - Y: Abandon Rate % ; second visual Avg CSAT |
| Slicers | `agents[team]`, `agents[shift]`, `agents[tenure_band]` |
| Text box | 3 bullet recommendations copied from `outputs/key_insights.md` |

## 7. Finishing touches (recruiters notice these)
- Use one colour theme (navy `#1F3864`, teal `#2A9D8F`, red `#E63946` for problems).
- Give every visual a clear title, e.g. "Abandon rate peaks at 10:00 and 16:00-17:00".
- Page background light grey, visuals white with small rounded corners.
- Add a small footer text box: "Synthetic dataset - for portfolio use".
- Save as `call_center_dashboard.pbix`, take screenshots of both pages and save them in `docs/`
  (create the folder), then link them in the README.
- Optional: File -> Publish -> Publish to web gives a public link you can put on your resume
  (check that it does not expose real company data - yours is synthetic, so it is safe).
