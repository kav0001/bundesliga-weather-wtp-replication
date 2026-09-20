"""
Merge stadium capacity into the master dataset and compute fill_rate.
Uses historical (pre-renovation) capacity for stadiums whose capacity
changed during the sample period.

Input:  data/own_collected/stadium_capacity.csv
Output: data/processed/bundesliga_with_weather.csv (updated in place)

NOTE on historical capacities (see stadium_capacity.csv's
capacity_pre_renovation column): for stadiums where current capacity differs
from the capacity during part of the sample period, matches played before
renovation_year use capacity_pre_renovation instead of the current value.
This avoids spurious fill_rate > 1 for historical games played when the
ground was still larger.
"""

import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_MAIN = REPO_ROOT / "data" / "processed" / "bundesliga_with_weather.csv"
CSV_CAP  = REPO_ROOT / "data" / "own_collected" / "stadium_capacity.csv"

bdf = pd.read_csv(CSV_MAIN, low_memory=False)
for col in ["capacity", "fill_rate", "capacity_pre_renovation", "renovation_year"]:
    if col in bdf.columns:
        bdf = bdf.drop(columns=[col])

cap = pd.read_csv(CSV_CAP)
cap = cap.drop_duplicates(subset="Stadium")

bdf = bdf.merge(cap[["Stadium", "capacity", "capacity_pre_renovation", "renovation_year"]],
                 on="Stadium", how="left")

bdf["Date"]       = pd.to_datetime(bdf["Date"], errors="coerce")
bdf["Attendance"] = pd.to_numeric(bdf["Attendance"], errors="coerce")
bdf["capacity"]   = pd.to_numeric(bdf["capacity"], errors="coerce")
bdf["capacity_pre_renovation"] = pd.to_numeric(bdf["capacity_pre_renovation"], errors="coerce")
bdf["renovation_year"]         = pd.to_numeric(bdf["renovation_year"], errors="coerce")

pre_mask = (
    bdf["capacity_pre_renovation"].notna() &
    bdf["renovation_year"].notna() &
    (bdf["Date"].dt.year < bdf["renovation_year"])
)
bdf.loc[pre_mask, "capacity"] = bdf.loc[pre_mask, "capacity_pre_renovation"]
n_historical = pre_mask.sum()

bdf = bdf.drop(columns=["capacity_pre_renovation", "renovation_year"])

bdf["fill_rate"] = bdf["Attendance"] / bdf["capacity"]
bdf.loc[bdf["fill_rate"] > 1.05, "fill_rate"] = float("nan")

bdf.to_csv(CSV_MAIN, index=False)

# -- Report --
reg = bdf[
    bdf["Div"].isin(["D1", "D2"]) &
    bdf["Attendance"].notna() & (bdf["Attendance"] > 0) &
    (bdf["Date"].dt.year >= 2000) &
    (bdf["Season"] != "2020/21")
].copy()

print(f"Historical capacity applied to {n_historical} rows")
print()
print("=== Regression sample ===")
for div in ["D1", "D2"]:
    d = reg[reg["Div"] == div]
    cap_ok  = d["capacity"].notna().sum()
    fill_ok = d["fill_rate"].notna().sum()
    capped  = (d["Attendance"] / d["capacity"] > 1.05).sum() if d["capacity"].notna().any() else 0
    print(f"{div}: total={len(d)} | capacity={cap_ok} ({100*cap_ok/len(d):.1f}%) "
          f"| fill_rate={fill_ok} ({100*fill_ok/len(d):.1f}%) | capped >1.05: {capped}")

print()
remaining = reg[reg["fill_rate"].isna() & reg["capacity"].notna() & reg["Attendance"].notna()]
if len(remaining):
    print(f"Remaining rows without fill_rate: {len(remaining)}")
    print(remaining.groupby("Stadium")["Attendance"].count().sort_values(ascending=False).to_string())

print()
print("fill_rate descriptives:")
for div in ["D1", "D2"]:
    d = reg[reg["Div"] == div]["fill_rate"].dropna()
    print(f"  {div}: n={len(d)} mean={d.mean():.3f} median={d.median():.3f} "
          f"p25={d.quantile(0.25):.3f} p75={d.quantile(0.75):.3f}")
