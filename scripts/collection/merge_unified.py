"""
Final BL1 merge: takes bundesliga_all.csv as the match-record master and
attaches attendance from attendance_clean.csv by date + team names (team
names differ in spelling between the two sources, hence TEAM_MAP).

NOTE ON REPRODUCIBILITY: bundesliga_all.csv (raw BL1 match records from
football-data.co.uk) is not included in this package and has no surviving
generating script - see the README's "known gaps" section. This script is
included to document the team-name reconciliation logic, even though it
cannot be re-run without that input file.

Output: bundesliga_unified.csv, feeds scripts/collection/download_weather.py.
"""

import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MASTER     = REPO_ROOT / "bundesliga_all.csv"
ATTENDANCE = REPO_ROOT / "attendance_clean.csv"
OUTPUT     = REPO_ROOT / "bundesliga_unified.csv"

# attendance_clean.csv team spelling -> bundesliga_all.csv team spelling.
TEAM_MAP = {
    "1 Fc Heidenheim 1846"     : "Heidenheim",
    "1 Fc Kaiserslautern"      : "Kaiserslautern",
    "1 Fc Koln"                : "FC Koln",
    "1 Fc Nuremberg"           : "Nurnberg",
    "1 Fc Nurnberg"            : "Nurnberg",
    "1 Fc Union Berlin"        : "Union Berlin",
    "1 Fsv Mainz 05"           : "Mainz",
    "Alemannia Aachen"         : "Aachen",
    "Arminia Bielefeld"        : "Bielefeld",
    "Bayer 04 Leverkusen"      : "Leverkusen",
    "Bayern Munich"            : "Bayern Munich",
    "Borussia Dortmund"        : "Dortmund",
    "Borussia Monchengladbach" : "M'Gladbach",
    "Eintracht Braunschweig"   : "Braunschweig",
    "Eintracht Frankfurt"      : "Ein Frankfurt",
    "Fc Augsburg"              : "Augsburg",
    "Fc Bayern Munchen"        : "Bayern Munich",
    "Fc Energie Cottbus"       : "Cottbus",
    "Fc Hansa Rostock"         : "Hansa Rostock",
    "Fc Ingolstadt 04"         : "Ingolstadt",
    "Fc Schalke 04"            : "Schalke 04",
    "Fc St Pauli"              : "St Pauli",
    "Fortuna Dusseldorf"       : "Dusseldorf",
    "Hamburger Sv"             : "Hamburg",
    "Hannover 96"              : "Hannover",
    "Hertha Bsc"               : "Hertha",
    "Holstein Kiel"            : "Kiel",
    "Karlsruher Sc"            : "Karlsruhe",
    "Msv Duisburg"             : "Duisburg",
    "Rb Leipzig"               : "RB Leipzig",
    "Sc Freiburg"              : "Freiburg",
    "Sc Paderborn 07"          : "Paderborn",
    "Spvgg Greuther Furth"     : "Greuther Furth",
    "Spvgg Unterhaching"       : "Unterhaching",
    "Sv Darmstadt 98"          : "Darmstadt",
    "Sv Werder Bremen"         : "Werder Bremen",
    "Tsg 1899 Hoffenheim"      : "Hoffenheim",
    "Tsv 1860 Munchen"         : "Munich 1860",
    "Vfb Stuttgart"            : "Stuttgart",
    "Vfl Bochum"               : "Bochum",
    "Vfl Wolfsburg"            : "Wolfsburg",
}

print("Reading bundesliga_all.csv...")
df = pd.read_csv(MASTER, encoding="utf-8-sig", low_memory=False)

# Fix a couple of duplicate spellings in the master.
df["HomeTeam"] = df["HomeTeam"].replace({"M'gladbach": "M'Gladbach", "Leipzig": "RB Leipzig"})
df["AwayTeam"] = df["AwayTeam"].replace({"M'gladbach": "M'Gladbach", "Leipzig": "RB Leipzig"})

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df["_date"] = df["Date"].dt.date
print(f"  -> {len(df)} rows (D1: {(df['Div']=='D1').sum()}, D2: {(df['Div']=='D2').sum()})")

print("\nReading attendance_clean.csv...")
att = pd.read_csv(ATTENDANCE, encoding="utf-8-sig", low_memory=False)
att["date"] = pd.to_datetime(att["date"], errors="coerce")
att["_date"] = att["date"].dt.date

att["home_mapped"] = att["home_team"].map(TEAM_MAP).fillna(att["home_team"])
att["away_mapped"] = att["away_team"].map(TEAM_MAP).fillna(att["away_team"])

unmapped = set(att["home_team"].dropna()) - set(TEAM_MAP.keys())
if unmapped:
    print(f"  [warning] unmapped team names: {sorted(unmapped)}")
else:
    print("  all team names mapped")

print(f"  -> {len(att)} matches with attendance")

print("\nMerging...")
att_key = att[["_date", "home_mapped", "away_mapped", "attendance", "stadium", "source"]].copy()
att_key.columns = ["_date", "HomeTeam", "AwayTeam", "Attendance_new", "Stadium_new", "Source"]

if "Attendance" in df.columns:
    df.drop(columns=["Attendance"], inplace=True)

df = df.merge(att_key, on=["_date", "HomeTeam", "AwayTeam"], how="left")
df.rename(columns={"Attendance_new": "Attendance", "Stadium_new": "Stadium"}, inplace=True)
df.drop(columns=["_date"], inplace=True)

df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

print(f"\nDone: {OUTPUT} ({len(df)} rows)")
for div in ["D1", "D2"]:
    sub = df[df["Div"] == div]
    n, n_a = len(sub), sub["Attendance"].notna().sum()
    print(f"\n   {div}: {n} matches, with attendance: {n_a} ({100*n_a/n:.1f}%)")

print("\nBy season (D1):")
d1 = df[df["Div"] == "D1"]
summary = d1.groupby("Season").agg(
    matches=("Date", "count"),
    with_att=("Attendance", lambda x: x.notna().sum()),
    avg_att=("Attendance", "mean"),
).round(0)
summary["pct%"] = (summary["with_att"] / summary["matches"] * 100).round(1)
print(summary.to_string())
