"""
BL2 attendance preparation.

Builds a BL2 attendance file from games.csv (transfermarkt-datasets,
competition_id == "L2"). Output format matches attendance_clean.csv (BL1).

WARNING - KNOWN PIPELINE GOTCHA (see README "known gaps"): this script
OVERWRITES data/own_collected/attendance_bl2.csv rather than appending to it.
scripts/collection/scrape_bl2_attendance.py writes 2000-2011 rows to that same
file; running this script straight afterwards destroys them. If rebuilding
attendance_bl2.csv from scratch: run scrape_bl2_attendance.py first, copy its
output aside, run this script, then pd.concat the two (dedup on
date+home_team+away_team) before merge_bl2.py.

Requires: games.csv (see README for where to get it)
Output:   data/own_collected/attendance_bl2.csv
"""

import pandas as pd
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GAMES_FILE = REPO_ROOT / "games.csv"
OUTPUT     = REPO_ROOT / "data" / "own_collected" / "attendance_bl2.csv"


def extract_teams_from_url(url: str):
    """Parse team names out of a Transfermarkt match-report URL."""
    m = re.search(r"transfermarkt\.[a-z.]+/([^/]+)_([^/]+)/index/spielbericht", str(url))
    if not m:
        return None, None
    def clean(s):
        return s.replace("-", " ").title().strip()
    return clean(m.group(1)), clean(m.group(2))


print("Reading games.csv...")
df_games = pd.read_csv(GAMES_FILE, low_memory=False, sep=';')

print(f"  Total rows: {len(df_games)}")
print(f"  competition_id values: {df_games['competition_id'].value_counts().head(10).to_dict()}")

# BL2 in transfermarkt-datasets is competition_id == "L2".
df_l2 = df_games[df_games["competition_id"] == "L2"].copy()
print(f"  BL2 (L2) rows: {len(df_l2)}")
print(f"  Seasons: {sorted(df_l2['season'].unique())}")

if len(df_l2) == 0:
    print("\nNo BL2 data found in games.csv.")
    print("   competition_id values present:")
    print(f"   {df_games['competition_id'].value_counts().to_dict()}")
    exit(1)

df_l2[["home_team", "away_team"]] = df_l2["url"].apply(lambda u: pd.Series(extract_teams_from_url(str(u))))
df_l2["date"] = pd.to_datetime(df_l2["date"], errors="coerce")
df_l2["season_label"] = df_l2["season"].apply(lambda y: f"{y}/{str(y+1)[-2:]}")

df_out = pd.DataFrame({
    "season"     : df_l2["season_label"],
    "date"       : df_l2["date"],
    "home_team"  : df_l2["home_team"],
    "away_team"  : df_l2["away_team"],
    "home_goals" : pd.to_numeric(df_l2["home_club_goals"], errors="coerce"),
    "away_goals" : pd.to_numeric(df_l2["away_club_goals"], errors="coerce"),
    "attendance" : pd.to_numeric(df_l2["attendance"], errors="coerce"),
    "stadium"    : df_l2["stadium"],
    "source"     : "tm_github_l2",
})

df_out.sort_values("date", inplace=True)
df_out.reset_index(drop=True, inplace=True)
df_out.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

print(f"\nDone: {OUTPUT}")
print(f"   Rows: {len(df_out)}")
print(f"   With attendance: {df_out['attendance'].notna().sum()}")
print(f"   Seasons: {sorted(df_out['season'].unique())}")
print(f"\n   Unique stadiums: {df_out['stadium'].nunique()}")
print(f"   Top 30 stadiums by match count:")
for s, n in df_out['stadium'].value_counts().head(30).items():
    print(f"     {n:4d}  {s}")
