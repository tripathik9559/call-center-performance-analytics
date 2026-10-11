"""
Step 3: KPI + EDA analysis in Python (pandas + matplotlib).

Input : data/clean/calls_clean.csv, data/clean/agents.csv
Output: outputs/charts/*.png, outputs/kpi_summary.csv, outputs/key_insights.md

KPI definitions (the SQL and the Power BI DAX use the SAME definitions):
  Abandon Rate = abandoned calls / total calls
  SLA %        = calls answered within 20 sec / total calls
  AHT (min)    = average handle time of answered calls
  ASA (sec)    = average wait of answered calls
  FCR %        = answered calls resolved on first call / answered calls
  CSAT         = average survey score (1-5) of calls that have a score

Run:  python src/eda_analysis.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "outputs"
CH = OUT / "charts"
CH.mkdir(parents=True, exist_ok=True)

calls = pd.read_csv(CLEAN / "calls_clean.csv", parse_dates=["call_datetime"])
agents = pd.read_csv(CLEAN / "agents.csv")
calls = calls.merge(agents[["agent_id", "shift", "tenure_months", "tenure_band"]], on="agent_id", how="left")
ans = calls[calls["call_status"] == "Answered"]

NAVY, TEAL, RED, GREY = "#1F3864", "#2A9D8F", "#E63946", "#8D99AE"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 12})


def kpis(df):
    a = df[df["call_status"] == "Answered"]
    return pd.Series({
        "total_calls": len(df),
        "abandon_rate_pct": df["is_abandoned"].mean() * 100,
        "sla_pct": df["within_sla"].mean() * 100,
        "aht_min": a["handle_seconds"].mean() / 60,
        "asa_sec": a["wait_seconds"].mean(),
        "fcr_pct": a["fcr_flag"].mean() * 100,
        "csat": df["csat_score"].mean(),
        "repeat_call_pct": df["repeat_within_7d"].mean() * 100,
    })


overall = kpis(calls)
overall.round(2).to_frame("value").to_csv(OUT / "kpi_summary.csv")

# ------------------------------------------------------------ aggregations
by_hour = calls.groupby("call_hour").apply(kpis, include_groups=False)
by_queue = calls[calls["queue"] != "Unknown"].groupby("queue").apply(kpis, include_groups=False)
by_month = calls.groupby("month").apply(kpis, include_groups=False)
weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
by_weekday = calls.groupby("weekday").apply(kpis, include_groups=False).reindex(weekday_order)
by_tenure = ans.merge(agents[["agent_id"]], on="agent_id").groupby("tenure_band").agg(
    aht_min=("handle_seconds", lambda s: s.mean() / 60), fcr_pct=("fcr_flag", lambda s: s.mean() * 100),
    csat=("csat_score", "mean"), calls=("call_id", "count"))
tenure_order = ["0-6 months", "7-12 months", "13-24 months", "25+ months"]
by_tenure = by_tenure.reindex(tenure_order)
by_shift = calls.dropna(subset=["shift"]).groupby("shift").agg(
    calls=("call_id", "count"), aht_min=("handle_seconds", lambda s: s[s > 0].mean() / 60),
    csat=("csat_score", "mean"))
heat = calls.pivot_table(index="weekday", columns="call_hour", values="is_abandoned", aggfunc="mean").reindex(weekday_order) * 100

# ------------------------------------------------------------ charts
# 1) volume vs abandonment by hour
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.bar(by_hour.index, by_hour["total_calls"], color=NAVY, alpha=0.85, label="Calls")
ax.set_xlabel("Hour of day"); ax.set_ylabel("Calls"); ax.set_xticks(range(0, 24))
ax2 = ax.twinx(); ax2.spines["right"].set_visible(True)
ax2.plot(by_hour.index, by_hour["abandon_rate_pct"], color=RED, marker="o", lw=2, label="Abandon rate %")
ax2.set_ylabel("Abandon rate %")
ax.set_title("Call volume vs abandon rate by hour")
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="upper left", frameon=False)
fig.tight_layout(); fig.savefig(CH / "01_volume_vs_abandon_by_hour.png", dpi=150); plt.close(fig)

# 2) FCR by queue
fig, ax = plt.subplots(figsize=(8, 4.2))
d = by_queue.sort_values("fcr_pct")
bars = ax.barh(d.index, d["fcr_pct"], color=[RED if v == d["fcr_pct"].min() else TEAL for v in d["fcr_pct"]])
ax.bar_label(bars, fmt="%.1f%%", padding=3); ax.set_xlim(0, 100)
ax.axvline(overall["fcr_pct"], color=GREY, ls="--"); ax.set_xlabel("First Contact Resolution %")
ax.set_title(f"FCR by queue (overall {overall['fcr_pct']:.1f}%)")
fig.tight_layout(); fig.savefig(CH / "02_fcr_by_queue.png", dpi=150); plt.close(fig)

# 3) AHT + CSAT by tenure
fig, ax = plt.subplots(figsize=(8, 4.2))
bars = ax.bar(by_tenure.index, by_tenure["aht_min"], color=NAVY)
ax.bar_label(bars, fmt="%.1f min", padding=3); ax.set_ylabel("Average handle time (min)")
ax2 = ax.twinx(); ax2.spines["right"].set_visible(True)
ax2.plot(by_tenure.index, by_tenure["csat"], color=RED, marker="o", lw=2); ax2.set_ylabel("CSAT (1-5)")
ax2.set_ylim(3, 5)
ax.set_title("Agent tenure vs handle time (bars) and CSAT (line)")
fig.tight_layout(); fig.savefig(CH / "03_tenure_vs_aht_csat.png", dpi=150); plt.close(fig)

# 4) monthly trend
fig, ax = plt.subplots(figsize=(8.5, 4.2))
ax.bar(by_month.index, by_month["total_calls"], color=NAVY, alpha=0.85)
ax.set_ylabel("Calls"); ax.set_xlabel("Month")
ax2 = ax.twinx(); ax2.spines["right"].set_visible(True)
ax2.plot(by_month.index, by_month["csat"], color=TEAL, marker="o", lw=2, label="CSAT")
ax2.set_ylabel("CSAT (1-5)"); ax2.set_ylim(3, 5)
ax.set_title("Monthly call volume and CSAT")
fig.tight_layout(); fig.savefig(CH / "04_monthly_trend.png", dpi=150); plt.close(fig)

# 5) heatmap
fig, ax = plt.subplots(figsize=(11, 4))
im = ax.imshow(heat.values, aspect="auto", cmap="Reds")
ax.set_xticks(range(24)); ax.set_xticklabels(heat.columns); ax.set_yticks(range(7)); ax.set_yticklabels(heat.index)
ax.set_xlabel("Hour of day"); ax.set_title("Abandon rate % - weekday x hour")
fig.colorbar(im, ax=ax, label="Abandon rate %")
fig.tight_layout(); fig.savefig(CH / "05_abandon_heatmap.png", dpi=150); plt.close(fig)

# ------------------------------------------------------------ insights (numbers computed from data)
busy = by_hour[by_hour["total_calls"] >= by_hour["total_calls"].quantile(0.5)]
peak = busy.sort_values("abandon_rate_pct", ascending=False).head(3)
peak_hours = ", ".join(f"{h:02d}:00" for h in sorted(peak.index))
peak_rate = peak["abandon_rate_pct"].mean()
night = by_hour.loc[[22, 23]]
night_rate = (night["abandon_rate_pct"] * night["total_calls"]).sum() / night["total_calls"].sum()
recoverable = int(round(((peak["abandon_rate_pct"] - overall["abandon_rate_pct"]).clip(lower=0) / 100 * peak["total_calls"]).sum()))
worst_q = by_queue["fcr_pct"].idxmin(); best_q = by_queue["fcr_pct"].idxmax()
new_aht, exp_aht = by_tenure.loc["0-6 months", "aht_min"], by_tenure.loc["25+ months", "aht_min"]
new_fcr, exp_fcr = by_tenure.loc["0-6 months", "fcr_pct"], by_tenure.loc["25+ months", "fcr_pct"]
new_cs, exp_cs = by_tenure.loc["0-6 months", "csat"], by_tenure.loc["25+ months", "csat"]
wd_worst = by_weekday["abandon_rate_pct"].idxmax(); wd_best = by_weekday["abandon_rate_pct"].idxmin()
csat_wait = ans.assign(wb=pd.cut(ans["wait_seconds"], [-1, 20, 60, 120, 10_000],
                                 labels=["0-20s", "21-60s", "61-120s", "120s+"])).groupby("wb", observed=True)["csat_score"].mean()
bill = calls[calls["queue"] == "Billing"].copy()
bill["dom"] = bill["call_datetime"].dt.day
bill_per_day = bill.groupby(bill["call_datetime"].dt.date).size()
bill_dom = pd.Series(bill_per_day.index.map(lambda d: d.day), index=bill_per_day.index)
bill_early = bill_per_day[bill_dom <= 7].mean()
bill_rest = bill_per_day[bill_dom > 7].mean()

md = f"""# Key Insights (auto-generated from the dataset)

> Dataset: SYNTHETIC call-center data, {len(calls):,} calls, {calls['call_datetime'].min():%d %b %Y} to {calls['call_datetime'].max():%d %b %Y}.

## Overall KPIs
| KPI | Value |
|---|---|
| Total calls | {int(overall['total_calls']):,} |
| Abandon rate | {overall['abandon_rate_pct']:.1f}% |
| SLA (answered within 20s) | {overall['sla_pct']:.1f}% |
| Average handle time | {overall['aht_min']:.1f} min |
| Average speed of answer | {overall['asa_sec']:.0f} sec |
| First contact resolution | {overall['fcr_pct']:.1f}% |
| Average CSAT | {overall['csat']:.2f} / 5 |
| Repeat calls (within 7 days) | {overall['repeat_call_pct']:.1f}% |

## Findings
1. **Peak-hour abandonment.** The busiest hours with the worst abandonment are {peak_hours}, where {peak_rate:.1f}% of callers hang up vs {overall['abandon_rate_pct']:.1f}% overall. Bringing those hours down to the overall average would save about **{recoverable:,} calls** over the period.
2. **Night shift is understaffed.** At 22:00-23:59 the abandon rate is {night_rate:.1f}% ({night_rate / overall['abandon_rate_pct']:.1f}x the overall rate) because very few agents are rostered.
3. **{wd_worst} is the worst day** ({by_weekday.loc[wd_worst, 'abandon_rate_pct']:.1f}% abandon) and {wd_best} the best ({by_weekday.loc[wd_best, 'abandon_rate_pct']:.1f}%).
4. **{worst_q} has the lowest FCR** at {by_queue.loc[worst_q, 'fcr_pct']:.1f}% (best: {best_q} at {by_queue.loc[best_q, 'fcr_pct']:.1f}%). Low FCR means repeat calls and more load.
5. **New agents (0-6 months)** take {new_aht:.1f} min per call vs {exp_aht:.1f} min for 25+ months ({(new_aht / exp_aht - 1) * 100:.0f}% longer), with FCR {new_fcr:.1f}% vs {exp_fcr:.1f}% and CSAT {new_cs:.2f} vs {exp_cs:.2f}. Better onboarding / call-shadowing would help.
6. **Waiting hurts satisfaction.** Average CSAT is {csat_wait.iloc[0]:.2f} when answered within 20s, falling to {csat_wait.iloc[-1]:.2f} when the wait is over 120s.
7. **Billing spikes in the first week of every month.** Billing gets {bill_early:.0f} calls/day on days 1-7 vs {bill_rest:.0f} calls/day for the rest of the month ({(bill_early / bill_rest - 1) * 100:.0f}% higher) - staff Billing up around bill-cycle dates.

## Recommendations
- Add agents (or split breaks / shift starts) around {peak_hours} and on {wd_worst}s.
- Roster more agents for the 22:00-24:00 window.
- Add Billing agents on days 1-7 of each month.
- Fix the root causes of repeat contacts in **{worst_q}** (knowledge base, escalation path).
- Pair new agents with a mentor for their first 6 months.
"""
(OUT / "key_insights.md").write_text(md, encoding="utf-8")
print(md)
