"""
Build a clean BL1 attendance file (with home_team / away_team) from two
sources: a 2000-2011 Transfermarkt scrape and the public
transfermarkt-datasets games.csv (2012 onward). Teams are parsed out of the
Transfermarkt match-report URL for both sources, for a consistent format.

NOTE ON REPRODUCIBILITY: tm_attendance_2000_2011.csv (the 2000-2011
Transfermarkt scrape for BL1) is not included in this package and has no
surviving generating script - see the README's "known gaps" section. This
script is included to document the parsing logic, even though it cannot be
re-run without that input file.

Output: attendance_clean.csv, feeds merge_unified.py.
"""

import pandas as pd
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TM_FILE    = REPO_ROOT / "tm_attendance_2000_2011.csv"
GAMES_FILE = REPO_ROOT / "games.csv"
OUTPUT     = REPO_ROOT / "attendance_clean.csv"


def extract_teams_from_url(url: str):
    """
    Parse team names out of a Transfermarkt match-report URL, e.g.
    /borussia-dortmund_sv-werder-bremen/index/spielbericht/18456
    -> 'Borussia Dortmund', 'Sv Werder Bremen'
    """
    m = re.search(r"transfermarkt\.[a-z.]+/([^/]+)_([^/]+)/index/spielbericht", str(url))
    if not m:
        return None, None
    def clean(s):
        return s.replace("-", " ").title().strip()
    return clean(m.group(1)), clean(m.group(2))


def parse_score(score):
    m = re.match(r"(\d+)\s*:\s*(\d+)", str(score))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


# -- Source 1: 2000-2011 Transfermarkt scrape --
print("Reading tm_attendance_2000_2011.csv...")
df_tm = pd.read_csv(TM_FILE, encoding="utf-8-sig", low_memory=False)

df_tm[["home_team", "away_team"]] = df_tm["url"].apply(lambda u: pd.Series(extract_teams_from_url(u)))
df_tm["date"] = pd.to_datetime(df_tm["date_raw"], format="%d.%m.%Y", errors="coerce")
df_tm["attendance"] = pd.to_numeric(df_tm["attendance"], errors="coerce")
df_tm[["home_goals", "away_goals"]] = df_tm["score"].apply(lambda s: pd.Series(parse_score(s)))

df1 = pd.DataFrame({
    "season"     : df_tm["season"],
    "date"       : df_tm["date"],
    "home_team"  : df_tm["home_team"],
    "away_team"  : df_tm["away_team"],
    "home_goals" : df_tm["home_goals"],
    "away_goals" : df_tm["away_goals"],
    "attendance" : df_tm["attendance"],
    "stadium"    : df_tm["stadium"],
    "source"     : "tm_scraper",
})
print(f"  -> {len(df1)} matches")

# -- Source 2: games.csv (L1, 2012 onward) - teams also parsed from URL --
print("\nReading games.csv...")
df_games = pd.read_csv(GAMES_FILE, low_memory=False)
df_l1 = df_games[(df_games["competition_id"] == "L1") & (df_games["season"] >= 2012)].copy()

df_l1[["home_team", "away_team"]] = df_l1["url"].apply(lambda u: pd.Series(extract_teams_from_url(str(u))))
df_l1["date"] = pd.to_datetime(df_l1["date"], errors="coerce")
df_l1["season_label"] = df_l1["season"].apply(lambda y: f"{y}/{str(y+1)[-2:]}")

df2 = pd.DataFrame({
    "season"     : df_l1["season_label"],
    "date"       : df_l1["date"],
    "home_team"  : df_l1["home_team"],
    "away_team"  : df_l1["away_team"],
    "home_goals" : pd.to_numeric(df_l1["home_club_goals"], errors="coerce"),
    "away_goals" : pd.to_numeric(df_l1["away_club_goals"], errors="coerce"),
    "attendance" : pd.to_numeric(df_l1["attendance"], errors="coerce"),
    "stadium"    : df_l1["stadium"],
    "source"     : "tm_github",
})
print(f"  -> {len(df2)} matches")

# -- Combine --
df_att = pd.concat([df1, df2], ignore_index=True)
df_att.sort_values("date", inplace=True)
df_att.reset_index(drop=True, inplace=True)
df_att.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

print(f"\nDone: {OUTPUT}")
print(f"   Rows: {len(df_att)}")
print(f"   With attendance: {df_att['attendance'].notna().sum()}")
print(f"   Seasons: {sorted(df_att['season'].unique())}")
