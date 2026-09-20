"""
Merge BL2 attendance into the master dataset.

Adds BL2 attendance (from data/own_collected/attendance_bl2.csv) onto
data/processed/bundesliga_with_weather.csv, which by this point already
contains D2 rows from the match-record source but without attendance.

Run AFTER prepare_attendance_bl2.py and BEFORE download_weather_bl2.py.

Steps:
  - Read the current master dataset (D2 rows present, attendance still empty).
  - Merge attendance_bl2.csv onto it by date + team names.
  - Write the result back to the master dataset.
"""

import pandas as pd
from pathlib import Path

REPO_ROOT  = Path(__file__).resolve().parents[2]
MASTER     = REPO_ROOT / "data" / "processed" / "bundesliga_with_weather.csv"
ATTENDANCE = REPO_ROOT / "data" / "own_collected" / "attendance_bl2.csv"

# Transfermarkt team names (as scraped, with umlauts) -> football-data.co.uk
# team names used elsewhere in the master dataset.
TEAM_MAP_BL2 = {
    "1.FC Heidenheim 1846"      : "Heidenheim",
    "1.FC Kaiserslautern"       : "Kaiserslautern",
    "1.FC Köln"                 : "FC Koln",
    "1.FC Magdeburg"            : "Magdeburg",
    "1.FC Nürnberg"             : "Nurnberg",
    "1.FC Saarbrücken"          : "Saarbrucken",
    "1.FC Schweinfurt 05"       : "Schweinfurt",
    "1.FC Union Berlin"         : "Union Berlin",
    "1.FSV Mainz 05"            : "Mainz",
    "Alemannia Aachen"          : "Aachen",
    "Arminia Bielefeld"         : "Bielefeld",
    "Borussia Mönchengladbach"  : "M'Gladbach",
    "Chemnitzer FC"             : "Chemnitz",
    "Eintracht Braunschweig"    : "Braunschweig",
    "Eintracht Frankfurt"       : "Ein Frankfurt",
    "FC Augsburg"               : "Augsburg",
    "FC Carl Zeiss Jena"        : "CZ Jena",
    "FC Energie Cottbus"        : "Cottbus",
    "FC Erzgebirge Aue"         : "Erzgebirge Aue",
    "FC Hansa Rostock"          : "Hansa Rostock",
    "FC Ingolstadt 04"          : "Ingolstadt",
    "FC Schalke 04"             : "Schalke 04",
    "FC St. Pauli"              : "St Pauli",
    "FSV Frankfurt"             : "FSV Frankfurt",
    "Fortuna Düsseldorf"        : "Dusseldorf",
    "Hamburger SV"              : "Hamburg",
    "Hannover 96"               : "Hannover",
    "Hertha BSC"                : "Hertha",
    "Holstein Kiel"             : "Holstein Kiel",
    "Karlsruher SC"             : "Karlsruhe",
    "Kickers Offenbach"         : "Offenbach",
    "LR Ahlen"                  : "Ahlen",
    "MSV Duisburg"              : "Duisburg",
    "RB Leipzig"                : "RB Leipzig",
    "Rot"                       : "Oberhausen",   # "Rot-Weiß Oberhausen" truncated by the scraper regex
    "Rot Weiss Ahlen"           : "Ahlen",
    "SC Freiburg"               : "Freiburg",
    "SC Paderborn 07"           : "Paderborn",
    "SG Dynamo Dresden"         : "Dresden",
    "SSV Jahn Regensburg"       : "Regensburg",
    "SSV Reutlingen 05"         : "Reutlingen",
    "SSV Ulm 1846"              : "Ulm",
    "SV 07 Elversberg"          : "Elversberg",
    "SV Babelsberg 03"          : "Babelsberg",
    "SV Darmstadt 98"           : "Darmstadt",
    "SV Eintracht Trier 05"     : "Ein Trier",
    "SV Sandhausen"             : "Sandhausen",
    "SV Wacker Burghausen"      : "Burghausen",
    "SV Waldhof Mannheim"       : "Mannheim",
    "SV Wehen Wiesbaden"        : "Wehen",
    "SV Werder Bremen"          : "Werder Bremen",
    "SpVgg Greuther Fürth"      : "Greuther Furth",
    "SpVgg Unterhaching"        : "Unterhaching",
    "Sportfreunde Siegen"       : "Siegen",
    "Stuttgarter Kickers"       : "Stuttgarter K",
    "TSG 1899 Hoffenheim"       : "Hoffenheim",
    "TSV 1860 München"          : "Munich 1860",
    "TuS Koblenz"               : "Koblenz",
    "VfB Lübeck"                : "Lubeck",
    "VfB Stuttgart"             : "Stuttgart",
    "VfL Bochum"                : "Bochum",
    "VfL Osnabrück"             : "Osnabruck",
    "VfR Aalen"                 : "Aalen",
    "Würzburger Kickers"        : "Wurzburger Kickers",
    # Full-name variants that appear as away_team.
    "Rot-Weiß Oberhausen"       : "Oberhausen",
    "Rot-Weiss Essen"           : "RW Essen",
    "Rot-Weiß Erfurt"           : "Erfurt",
}


if __name__ == "__main__":
    print("Reading master dataset...")
    df = pd.read_csv(MASTER, encoding="utf-8-sig", low_memory=False)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["_date"] = df["Date"].dt.date
    d2_before = (df["Div"] == "D2") & df["Attendance"].notna()
    print(f"  D2 rows with attendance before merge: {d2_before.sum()}")

    print("\nReading attendance_bl2.csv...")
    att = pd.read_csv(ATTENDANCE, encoding="utf-8-sig", low_memory=False)
    att["date"] = pd.to_datetime(att["date"], dayfirst=True, errors="coerce")
    att["_date"] = att["date"].dt.date

    # Scraper regex bug: when home_team='Rot' (Oberhausen), away_team came out
    # as 'Weiß Oberhausen - actual_team'. Recover the real away team.
    rot_mask = att["away_team"].str.contains(" - ", na=False)
    att.loc[rot_mask, "away_team"] = att.loc[rot_mask, "away_team"].str.extract(r" - (.+)$")[0]

    att["home_mapped"] = att["home_team"].map(TEAM_MAP_BL2).fillna(att["home_team"])
    att["away_mapped"] = att["away_team"].map(TEAM_MAP_BL2).fillna(att["away_team"])

    unmapped = set(att["home_team"].dropna()) - set(TEAM_MAP_BL2.keys())
    if unmapped:
        print(f"  [warning] unmapped team names ({len(unmapped)}):")
        for t in sorted(unmapped):
            print(f"     '{t}'")
    else:
        print("  all team names mapped")

    print(f"  -> {len(att)} BL2 matches with attendance")

    att_key = att[["_date", "home_mapped", "away_mapped", "attendance", "stadium", "url"]].copy()
    att_key.columns = ["_date", "HomeTeam", "AwayTeam", "Attendance_bl2", "Stadium_bl2", "Source_bl2"]

    df = df.merge(att_key, on=["_date", "HomeTeam", "AwayTeam"], how="left")

    # Fill only D2 rows, only where currently missing.
    d2_mask = df["Div"] == "D2"
    df.loc[d2_mask & df["Attendance"].isna(), "Attendance"] = df.loc[d2_mask & df["Attendance"].isna(), "Attendance_bl2"]
    df.loc[d2_mask & df["Stadium"].isna(), "Stadium"] = df.loc[d2_mask & df["Stadium"].isna(), "Stadium_bl2"]
    df.loc[d2_mask & df["Source"].isna(), "Source"] = df.loc[d2_mask & df["Source"].isna(), "Source_bl2"]

    df.drop(columns=["Attendance_bl2", "Stadium_bl2", "Source_bl2", "_date"], inplace=True)
    df.to_csv(MASTER, index=False, encoding="utf-8-sig")

    d2_after = (df["Div"] == "D2") & df["Attendance"].notna()
    print(f"\nDone: {MASTER}")
    print(f"   D2 rows with attendance after merge: {d2_after.sum()}")

    for div in ["D1", "D2"]:
        sub = df[df["Div"] == div]
        n, n_a = len(sub), sub["Attendance"].notna().sum()
        print(f"   {div}: {n} matches, with attendance: {n_a} ({100*n_a/n:.1f}%)")

    d2_att = df[(df["Div"] == "D2") & df["Attendance"].notna()]
    print(f"\n   Unique BL2 stadiums: {d2_att['Stadium'].nunique()}")
