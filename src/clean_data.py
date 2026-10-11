"""
Step 2: Clean the raw data and add analysis columns.

Input : data/raw/calls_raw.csv, data/raw/agents_raw.csv
Output: data/clean/calls_clean.csv, data/clean/agents.csv, outputs/cleaning_report.txt

Cleaning rules (and the assumption behind each):
  1. Duplicate rows            -> drop exact repeats of call_id (keep first)
  2. Queue / status text mess  -> strip spaces, fix case, map "technical_support" -> "Technical Support"
  3. Missing queue             -> take the agent's team if an agent handled the call, else "Unknown"
  4. Negative handle_seconds   -> treated as a sign error, converted with abs()
  5. CSAT outside 1-5          -> invalid, set to NULL (survey scores are only 1-5)
  6. Feature columns           -> date, hour, weekday, month, SLA flag, repeat caller flag

Run:  python src/clean_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "outputs"
CLEAN.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

SLA_SECONDS = 20  # a call is "within SLA" if answered in <= 20 seconds (80/20 standard)
QUEUE_MAP = {
    "billing": "Billing",
    "technical support": "Technical Support",
    "account services": "Account Services",
    "sales": "Sales",
    "retention": "Retention",
}

calls = pd.read_csv(RAW / "calls_raw.csv")
agents = pd.read_csv(RAW / "agents_raw.csv")
report = []
n_raw = len(calls)
report.append(f"Raw rows: {n_raw:,}")

# 1) duplicates
dups = calls.duplicated(subset="call_id").sum()
calls = calls.drop_duplicates(subset="call_id", keep="first").copy()
report.append(f"Duplicate call_id rows removed: {dups:,}")

# 2) text standardisation
q_clean = calls["queue"].str.strip().str.lower().str.replace("_", " ", regex=False)
calls["queue"] = q_clean.map(QUEUE_MAP)
calls["call_status"] = calls["call_status"].str.strip().str.title()
bad_status = (~calls["call_status"].isin(["Answered", "Abandoned"])).sum()
report.append(f"Rows with unknown call_status after cleanup: {bad_status:,}")

# 3) missing queue -> agent's team, else Unknown
team_map = agents.set_index("agent_id")["team"]
missing_q = calls["queue"].isna().sum()
calls["queue"] = calls["queue"].fillna(calls["agent_id"].map(team_map)).fillna("Unknown")
still_unknown = (calls["queue"] == "Unknown").sum()
report.append(f"Missing queue: {missing_q:,} -> filled from agent team; still 'Unknown': {still_unknown:,}")

# 4) negative handle time
neg = (calls["handle_seconds"] < 0).sum()
calls["handle_seconds"] = calls["handle_seconds"].abs()
report.append(f"Negative handle_seconds fixed with abs(): {neg:,}")

# 5) invalid CSAT
bad_csat = (calls["csat_score"].notna() & ~calls["csat_score"].between(1, 5)).sum()
calls.loc[~calls["csat_score"].between(1, 5), "csat_score"] = np.nan
report.append(f"CSAT values outside 1-5 set to NULL: {bad_csat:,}")

# 6) features
calls["call_datetime"] = pd.to_datetime(calls["call_datetime"])
calls["call_date"] = calls["call_datetime"].dt.date
calls["call_hour"] = calls["call_datetime"].dt.hour
calls["weekday"] = calls["call_datetime"].dt.day_name()
calls["weekday_num"] = calls["call_datetime"].dt.dayofweek + 1  # Mon=1 ... Sun=7
calls["month"] = calls["call_datetime"].dt.strftime("%Y-%m")
calls["is_abandoned"] = (calls["call_status"] == "Abandoned").astype(int)
calls["within_sla"] = ((calls["call_status"] == "Answered") & (calls["wait_seconds"] <= SLA_SECONDS)).astype(int)
calls["fcr_flag"] = calls["resolved_first_call"].map({"Y": 1, "N": 0})

# repeat caller: same customer called again within 7 days of their previous call
calls = calls.sort_values(["customer_id", "call_datetime"]).reset_index(drop=True)
gap = calls.groupby("customer_id")["call_datetime"].diff().dt.total_seconds() / 86400
calls["repeat_within_7d"] = ((gap > 0) & (gap <= 7)).astype(int)
calls = calls.sort_values("call_datetime").reset_index(drop=True)
report.append(f"Repeat calls (same customer within 7 days): {int(calls['repeat_within_7d'].sum()):,}")

# agents: tenure band
agents["tenure_band"] = pd.cut(
    agents["tenure_months"], bins=[0, 6, 12, 24, 1000],
    labels=["0-6 months", "7-12 months", "13-24 months", "25+ months"], right=True,
).astype(str)

cols = ["call_id", "call_datetime", "call_date", "call_hour", "weekday", "weekday_num", "month",
        "customer_id", "queue", "agent_id", "wait_seconds", "handle_seconds", "call_status",
        "is_abandoned", "within_sla", "resolved_first_call", "fcr_flag", "csat_score", "repeat_within_7d"]
calls["csat_score"] = calls["csat_score"].astype("Int64")   # whole numbers, blank when missing
calls["fcr_flag"] = calls["fcr_flag"].astype("Int64")
calls = calls[cols]
calls.to_csv(CLEAN / "calls_clean.csv", index=False)
agents.to_csv(CLEAN / "agents.csv", index=False)

report.append(f"Clean rows: {len(calls):,}  (removed {n_raw - len(calls):,})")
report.append(f"Date range: {calls['call_datetime'].min()}  to  {calls['call_datetime'].max()}")
(OUT / "cleaning_report.txt").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report))
