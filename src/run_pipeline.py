"""
Run the whole project with one command.

    python src/run_pipeline.py            -> generate data, clean it, run analysis + charts
    python src/run_pipeline.py --mysql    -> same, then also load the clean data into MySQL

For --mysql set your login first (see src/load_to_mysql.py).
"""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
steps = ["generate_data.py", "clean_data.py", "eda_analysis.py"]
if "--mysql" in sys.argv:
    steps.append("load_to_mysql.py")

for i, step in enumerate(steps, 1):
    print(f"\n=== Step {i}/{len(steps)}: {step} ===")
    result = subprocess.run([sys.executable, str(SRC / step)])
    if result.returncode != 0:
        sys.exit(f"Step failed: {step}")

print("\nDone. Look in outputs/ for charts, key_insights.md and kpi_summary.csv")
