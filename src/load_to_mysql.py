"""
Step 4: Load the clean CSVs into MySQL (creates the database + tables first).

Set your MySQL login with environment variables (defaults shown):
    DB_HOST=localhost  DB_PORT=3306  DB_USER=root  DB_PASSWORD=""  DB_NAME=call_center

Windows (PowerShell):  $env:DB_PASSWORD="your_password" ; python src/load_to_mysql.py
Mac / Linux         :  DB_PASSWORD=your_password python src/load_to_mysql.py

Run:  python src/load_to_mysql.py
"""
import os
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
SQL = ROOT / "sql"

HOST = os.getenv("DB_HOST", "localhost")
PORT = os.getenv("DB_PORT", "3306")
USER = os.getenv("DB_USER", "root")
PASSWORD = quote_plus(os.getenv("DB_PASSWORD", ""))
DB = os.getenv("DB_NAME", "call_center")

server_url = f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/"
db_url = f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB}"

# 1) run the schema file (statements are separated by ';')
schema = (SQL / "01_schema.sql").read_text(encoding="utf-8")
lines = [ln for ln in schema.splitlines() if not ln.strip().startswith("--")]
statements = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
engine0 = create_engine(server_url)
with engine0.begin() as conn:
    for stmt in statements:
        conn.execute(text(stmt))
print("Schema created.")

# 2) load data
engine = create_engine(db_url)
agents = pd.read_csv(CLEAN / "agents.csv")
calls = pd.read_csv(CLEAN / "calls_clean.csv", parse_dates=["call_datetime"])
calls["call_date"] = pd.to_datetime(calls["call_date"]).dt.date
for col in ["csat_score", "fcr_flag"]:
    calls[col] = calls[col].astype("Int64")
calls["agent_id"] = calls["agent_id"].where(calls["agent_id"].notna(), None)

agents.to_sql("agents", engine, if_exists="append", index=False)
calls.to_sql("calls", engine, if_exists="append", index=False, chunksize=5000, method="multi")

with engine.connect() as conn:
    n_calls = conn.execute(text("SELECT COUNT(*) FROM calls")).scalar()
    n_agents = conn.execute(text("SELECT COUNT(*) FROM agents")).scalar()
print(f"Loaded {n_agents} agents and {n_calls:,} calls into `{DB}`.")
