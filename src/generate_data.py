"""
Step 1: Generate a SYNTHETIC call-center dataset (raw, intentionally messy).

Why synthetic?  Real call-center data is private. This script simulates one with
realistic patterns (peak hours, staffing gaps, new-agent effect, queue difficulty)
so the analysis has real signal to find. Always describe it as a "synthetic
dataset" on your resume / in interviews.

Output (data/raw/):
    agents_raw.csv   -> 60 agents
    calls_raw.csv    -> ~60,000 calls (Apr-Sep 2026) with dirty values to clean

Run:  python src/generate_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

START, END = "2026-04-01", "2026-09-30"
QUEUES = ["Billing", "Technical Support", "Account Services", "Sales", "Retention"]
QUEUE_SHARE = np.array([0.28, 0.30, 0.20, 0.12, 0.10])
AGENTS_PER_QUEUE = {"Billing": 16, "Technical Support": 18, "Account Services": 12, "Sales": 7, "Retention": 7}
SHIFT_HOURS = {
    "Morning": list(range(6, 14)),
    "Evening": list(range(14, 22)),
    "Night": list(range(22, 24)) + list(range(0, 6)),
}
BASE_AHT = {"Billing": 340, "Technical Support": 560, "Account Services": 300, "Sales": 270, "Retention": 400}
BASE_FCR = {"Billing": 0.80, "Technical Support": 0.66, "Account Services": 0.82, "Sales": 0.85, "Retention": 0.70}
AVG_AHT_SECONDS = 420  # used only to estimate agent utilisation
RHO_SCALE = 5.5        # agents also do after-call work, training, breaks -> effective capacity is lower

# ------------------------------------------------------------------ agents
first = ["Aarav", "Priya", "Rohan", "Sneha", "Vikram", "Anjali", "Karan", "Neha", "Arjun", "Pooja",
         "Rahul", "Divya", "Amit", "Kavya", "Siddharth", "Ritu", "Manish", "Isha", "Nikhil", "Meera",
         "Varun", "Shreya", "Harsh", "Tanvi", "Deepak", "Simran", "Gaurav", "Aditi", "Sachin", "Nisha"]
last = ["Sharma", "Verma", "Singh", "Gupta", "Mishra", "Yadav", "Tiwari", "Pandey", "Kumar", "Joshi"]

agents = []
aid = 1
for q, n_agents in AGENTS_PER_QUEUE.items():
    for _ in range(n_agents):
        shift = rng.choice(["Morning", "Evening", "Night"], p=[0.42, 0.42, 0.16])
        # ~25% of agents are new (< 6 months)
        tenure = int(rng.integers(1, 6)) if rng.random() < 0.25 else int(rng.integers(6, 61))
        agents.append({
            "agent_id": f"A{aid:03d}",
            "agent_name": f"{rng.choice(first)} {rng.choice(last)}",
            "team": q,
            "shift": str(shift),
            "tenure_months": tenure,
        })
        aid += 1
agents = pd.DataFrame(agents)

# make sure every team has at least one agent in every shift (so no empty pools)
for q in QUEUES:
    for s in ["Morning", "Evening", "Night"]:
        if not ((agents.team == q) & (agents["shift"] == s)).any():
            i = agents[(agents.team == q)].index[0 if s == "Morning" else (1 if s == "Evening" else 2)]
            agents.loc[i, "shift"] = s

# ------------------------------------------------------------------ calls
days = pd.date_range(START, END, freq="D")
weekday_mult = {0: 1.25, 1: 1.05, 2: 1.00, 3: 0.98, 4: 1.00, 5: 0.80, 6: 0.60}
hour_w = np.array([0.5, 0.3, 0.2, 0.2, 0.3, 0.6, 1.5, 3, 5, 7, 9, 9, 7, 6, 6.5, 7.5, 8.5, 8, 6, 4.5, 3.5, 2.5, 1.5, 0.9])
hour_w = hour_w / hour_w.sum()

times, queues_list = [], []
for d in days:
    month_growth = 1 + 0.015 * (d.month - 4)  # slow growth Apr -> Sep
    n = int(rng.normal(330, 20) * weekday_mult[d.weekday()] * month_growth)
    hours = rng.choice(24, size=n, p=hour_w)
    mins = rng.integers(0, 60, n)
    secs = rng.integers(0, 60, n)
    share = QUEUE_SHARE.copy()
    if d.day <= 7:  # billing cycle: more billing calls in the first week
        share = share + np.array([0.10, -0.03, -0.03, -0.02, -0.02])
    share = share / share.sum()
    q = rng.choice(QUEUES, size=n, p=share)
    base_ts = d + pd.to_timedelta(hours * 3600 + mins * 60 + secs, unit="s")
    times.extend(base_ts)
    queues_list.extend(q)

calls = pd.DataFrame({"call_datetime": times, "queue": queues_list})
calls = calls.sort_values("call_datetime").reset_index(drop=True)
calls["call_id"] = [f"C{i:06d}" for i in range(1, len(calls) + 1)]

# customers: 30% of calls come from a smaller "frequent caller" pool -> repeat callers
pool_all, pool_freq = 22000, 2500
is_freq = rng.random(len(calls)) < 0.30
cust = np.where(is_freq, rng.integers(1, pool_freq + 1, len(calls)),
                rng.integers(pool_freq + 1, pool_all + 1, len(calls)))
calls["customer_id"] = [f"CU{x:05d}" for x in cust]

# ---- staffing vs load per (date, hour, queue) -> wait time
calls["date"] = calls["call_datetime"].dt.normalize()
calls["hour"] = calls["call_datetime"].dt.hour


def shift_of_hour(h):
    for s, hrs in SHIFT_HOURS.items():
        if h in hrs:
            return s


calls["shift"] = calls["hour"].map(shift_of_hour)
staff = agents.groupby(["team", "shift"]).size().rename("agents_on_shift").reset_index()
load = calls.groupby(["date", "hour", "queue", "shift"]).size().rename("calls_in_slot").reset_index()
load = load.merge(staff, left_on=["queue", "shift"], right_on=["team", "shift"], how="left")
load["agents_on_shift"] = load["agents_on_shift"].fillna(1)
load["available"] = np.maximum(1, np.round(load["agents_on_shift"] * 0.85))  # ~15% absence/breaks
load["rho"] = np.clip(load["calls_in_slot"] * AVG_AHT_SECONDS / 3600 / load["available"] * RHO_SCALE, 0, 1.6)
calls = calls.merge(load[["date", "hour", "queue", "rho"]], on=["date", "hour", "queue"], how="left")

# wait grows sharply once utilisation passes ~55%
mean_wait = 6 + 260 * np.maximum(0, calls["rho"] - 0.55) ** 2
calls["wait_seconds"] = np.round(rng.exponential(mean_wait)).astype(int)
p_abandon = np.clip(0.005 + (calls["wait_seconds"] / 420) ** 1.3 * 0.55, 0, 0.60)
calls["abandoned"] = rng.random(len(calls)) < p_abandon

# ---- assign agents to answered calls (same team + shift)
calls["agent_id"] = None
answered_groups = calls[~calls["abandoned"]].groupby(["queue", "shift"]).groups
for (team, shift), idx in answered_groups.items():
    pool = agents[(agents.team == team) & (agents["shift"] == shift)]["agent_id"].to_numpy()
    if len(pool) == 0:
        pool = agents[agents.team == team]["agent_id"].to_numpy()
    calls.loc[idx, "agent_id"] = rng.choice(pool, size=len(idx))

tenure_map = agents.set_index("agent_id")["tenure_months"]
ten = calls["agent_id"].map(tenure_map)
ten_factor = np.select([ten < 6, ten < 12, ten > 24], [1.25, 1.10, 0.92], default=1.0)
base = calls["queue"].map(BASE_AHT).astype(float)
aht = np.clip(rng.lognormal(np.log(base.to_numpy() * ten_factor), 0.45), 30, 2400)
calls["handle_seconds"] = np.where(calls["abandoned"], 0, np.round(aht)).astype(int)

p_fcr = calls["queue"].map(BASE_FCR).astype(float).to_numpy()
p_fcr = p_fcr + np.select([ten < 6, ten > 24], [-0.10, 0.04], default=0.0) - (calls["wait_seconds"].to_numpy() > 120) * 0.05
fcr = rng.random(len(calls)) < np.clip(p_fcr, 0.2, 0.95)

mu = 4.3 - 0.9 * (~fcr) - np.minimum(calls["wait_seconds"].to_numpy(), 300) / 200 - (calls["handle_seconds"].to_numpy() > 900) * 0.3
csat = np.clip(np.round(rng.normal(mu, 0.8)), 1, 5)
responded = rng.random(len(calls)) < 0.55  # only ~55% fill the survey

ans = ~calls["abandoned"].to_numpy()
calls["call_status"] = np.where(calls["abandoned"], "Abandoned", "Answered")
calls["resolved_first_call"] = np.where(ans, np.where(fcr, "Y", "N"), None)
calls["csat_score"] = np.where(ans & responded, csat, np.nan)

calls = calls[["call_id", "call_datetime", "customer_id", "queue", "agent_id", "wait_seconds",
               "handle_seconds", "call_status", "resolved_first_call", "csat_score"]].copy()

# ------------------------------------------------------------------ make it messy (to practise cleaning)
# 1) duplicate rows
dups = calls.sample(frac=0.012, random_state=1)
calls = pd.concat([calls, dups], ignore_index=True)
n = len(calls)
# 2) inconsistent text in queue / status
idx = rng.choice(n, int(n * 0.03), replace=False)
calls.loc[idx, "queue"] = [
    rng.choice([s.lower(), s.upper(), " " + s + " ", s.replace(" ", "_")]) for s in calls.loc[idx, "queue"]
]
idx = rng.choice(n, int(n * 0.02), replace=False)
calls.loc[idx, "call_status"] = [rng.choice([s.lower(), s.upper(), s + " "]) for s in calls.loc[idx, "call_status"]]
# 3) missing queue
idx = rng.choice(n, int(n * 0.008), replace=False)
calls.loc[idx, "queue"] = None
# 4) negative handle times (sign error) on answered calls
ans_idx = calls.index[calls["call_status"].str.strip().str.lower() == "answered"]
idx = rng.choice(ans_idx, int(n * 0.004), replace=False)
calls.loc[idx, "handle_seconds"] = -calls.loc[idx, "handle_seconds"]
# 5) impossible CSAT values
cs_idx = calls.index[calls["csat_score"].notna()]
idx = rng.choice(cs_idx, int(n * 0.003), replace=False)
calls.loc[idx, "csat_score"] = rng.choice([0, 7, 9], size=len(idx))

calls = calls.sample(frac=1, random_state=7).reset_index(drop=True)  # unsorted, like a real export
calls["call_datetime"] = pd.to_datetime(calls["call_datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")

calls.to_csv(RAW / "calls_raw.csv", index=False)
agents.to_csv(RAW / "agents_raw.csv", index=False)
print(f"agents_raw.csv : {len(agents):,} rows")
print(f"calls_raw.csv  : {len(calls):,} rows  ({START} to {END})")
