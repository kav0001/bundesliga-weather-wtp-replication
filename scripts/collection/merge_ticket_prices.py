"""
Merge average ticket prices into the master dataset.
Adds columns: avg_price (league-season level), price_type (observed/interpolated).

Input:  data/own_collected/ticket_prices.csv
Output: data/processed/bundesliga_with_weather.csv (updated in place)
"""

import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_MAIN   = REPO_ROOT / "data" / "processed" / "bundesliga_with_weather.csv"
CSV_PRICES = REPO_ROOT / "data" / "own_collected" / "ticket_prices.csv"

bdf = pd.read_csv(CSV_MAIN, low_memory=False)
prices = pd.read_csv(CSV_PRICES)

for col in ["avg_price", "price_type"]:
    if col in bdf.columns:
        bdf = bdf.drop(columns=[col])

# Build lookup: (season, div) -> (price, type).
price_map = {}
for _, row in prices.iterrows():
    season = row["season"]
    if pd.notna(row["bl1_price"]):
        price_map[(season, "D1")] = (row["bl1_price"], row["bl1_price_type"])
    if pd.notna(row["bl2_price"]):
        price_map[(season, "D2")] = (row["bl2_price"], row["bl2_price_type"])

bdf["avg_price"]  = bdf.apply(lambda r: price_map.get((r["Season"], r["Div"]), (None, None))[0], axis=1)
bdf["price_type"] = bdf.apply(lambda r: price_map.get((r["Season"], r["Div"]), (None, None))[1], axis=1)

bdf.to_csv(CSV_MAIN, index=False)

# -- Report --
print("=== avg_price coverage in regression sample ===")
for div in ["D1", "D2"]:
    d = bdf[
        (bdf["Div"] == div) &
        (pd.to_datetime(bdf["Date"], errors="coerce").dt.year >= 2000) &
        (bdf["Season"] != "2020/21") &
        bdf["avg_price"].notna() &
        (bdf["avg_price"] > 0)
    ]
    total = bdf[
        (bdf["Div"] == div) &
        (pd.to_datetime(bdf["Date"], errors="coerce").dt.year >= 2000) &
        (bdf["Season"] != "2020/21")
    ]
    print(f"{div}: {len(d)}/{len(total)} rows with price ({100*len(d)/len(total):.1f}%)")
    obs = d[d["price_type"] == "observed"]
    interp = d[d["price_type"] == "interpolated"]
    print(f"     observed={len(obs)}, interpolated={len(interp)}")
    print(f"     price range: EUR {d['avg_price'].min():.2f} - {d['avg_price'].max():.2f}")
