"""
DWD weather downloader - BL2 extension.

Adds weather for Bundesliga 2 stadiums, reusing the BL1 station cache
(data/cache/dwd_cache/) where the same city/station already applies.

Run AFTER prepare_attendance_bl2.py (needs attendance_bl2.csv for the list of
real Transfermarkt stadium names) and after the D2 rows have been merged into
the master CSV by merge_bl2.py.

Steps:
  1. Read attendance_bl2.csv to get the real stadium names as scraped from TM.
  2. Map stadium -> DWD station (BL2-specific stations plus the ones already
     known from BL1).
  3. Download any station not already cached.
  4. Merge weather onto the D2 rows of data/processed/bundesliga_with_weather.csv.
"""

import requests
import pandas as pd
import zipfile
import io
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Stadiums also used by BL1 clubs (same city) - copied from the BL1 mapping.
# BL2-only stadiums are listed further below, grouped roughly by region.
BL2_STADIUM_STATION = {

    # -- Clubs that have also played in BL1 (station already known) --
    "Allianz Arena"                     : "03379",  # Munich
    "Olympiastadion München"            : "03379",  # Munich
    "Volksparkstadion"                  : "01975",  # Hamburg
    "Millerntor-Stadion"                : "01975",  # Hamburg
    "Olympiastadion Berlin"             : "00433",  # Berlin
    "Stadion An der Alten Försterei"    : "00433",  # Berlin
    "RheinEnergieSTADION"               : "02667",  # Cologne
    "BayArena"                          : "02667",  # Leverkusen
    "Deutsche Bank Park"                : "01420",  # Frankfurt
    "Commerzbank Arena"                 : "01420",  # Frankfurt
    "MHPArena Stuttgart"                : "04928",  # Stuttgart
    "Weserstadion"                      : "00691",  # Bremen
    "Wohninvest-Weserstadion"           : "00691",  # Bremen
    "Volkswagen Arena"                  : "00662",  # Wolfsburg
    "Heinz-von-Heiden-Arena"            : "02014",  # Hannover
    "Max-Morlock-Stadion"               : "03668",  # Nuremberg
    "PreZero Arena"                     : "01255",  # Sinsheim
    "Red Bull Arena"                    : "02932",  # Leipzig
    "WWK ARENA"                         : "00232",  # Augsburg
    "Dreisamstadion"                    : "01443",  # Freiburg
    "Europa-Park Stadion"               : "01443",  # Freiburg
    "SchücoArena"                       : "04371",  # Bielefeld
    "Vonovia Ruhrstadion"               : "01303",  # Bochum
    "MSV-Arena"                         : "01078",  # Duisburg
    "ESPRIT arena"                      : "01078",  # Düsseldorf
    "Merkur Spiel-Arena"                : "01078",  # Düsseldorf (new arena name)
    "Fortuna Düsseldorf Arena"          : "01078",  # Düsseldorf
    "Ostseestadion"                     : "04271",  # Rostock
    "Fritz-Walter-Stadion"              : "02486",  # Kaiserslautern
    "Stadion am Bruchweg"               : "01420",  # Mainz
    "Mewa Arena"                        : "03137",  # Mainz
    "LEAG Energie Stadion"              : "00880",  # Cottbus
    "Stadion der Freundschaft"          : "00880",  # Cottbus
    "Stadion im Borussia-Park"          : "05064",  # M'gladbach
    "BBBank Wildpark"                   : "04177",  # Karlsruhe (post-2009)
    "Wildparkstadion"                   : "04177",  # Karlsruhe (older name)
    "EINTRACHT-Stadion"                 : "00662",  # Braunschweig
    "Eintracht-Stadion"                 : "00662",  # Braunschweig
    "Merck-Stadion am Böllenfalltor"    : "01420",  # Darmstadt
    "Sportpark Ronhof | Thomas Sommer"  : "03668",  # Fürth
    "Ronhof"                            : "03668",  # Fürth (older name)
    "Home Deluxe Arena"                 : "03028",  # Paderborn
    "Benteler-Arena"                    : "03028",  # Paderborn (older name)
    "Voith-Arena"                       : "04928",  # Heidenheim
    "Audi Sportpark"                    : "02410",  # Ingolstadt
    "Carl-Benz-Stadion"                 : "05906",  # Mannheim
    "Veltins-Arena"                     : "01303",  # Gelsenkirchen
    "Parkstadion"                       : "01303",  # Gelsenkirchen (old)
    "Holstein-Stadion"                  : "02564",  # Kiel
    "SIGNAL IDUNA PARK"                 : "01303",  # Dortmund

    # -- BL2-only stadiums --

    # Saxony / Thuringia
    "DDV-Stadion"                       : "01048",  # Dresden
    "Rudolf-Harbig-Stadion"             : "01048",  # Dresden (older name)
    "MDCC-Arena"                        : "03126",  # Magdeburg
    "AVNET Arena"                       : "03126",  # Magdeburg (newer name)
    "Ernst-Abbe-Sportfeld"              : "02597",  # Jena
    "Erzgebirgsstadion"                 : "00853",  # Aue -> Chemnitz station (~30km)
    "Steigerwaldstadion"                : "01270",  # Erfurt
    "GGZ Arena"                         : "00853",  # Zwickau -> Chemnitz (~25km)
    "Stadion Zwickau"                   : "00853",  # Zwickau
    "Chemnitz Stadion"                  : "00853",  # Chemnitz
    "community4you ARENA"               : "00853",  # Chemnitz

    # Bavaria (BL2-only)
    "Donaustadion"                      : "05705",  # Ulm
    "Jahnstadion Regensburg"            : "03761",  # Regensburg
    "KPMG Arena"                        : "03761",  # Regensburg
    "wuestenrot Stadion"                : "05705",  # Schweinfurt -> Ulm (far; best available)
    "Schweinfurter Stadion"             : "05705",  # Schweinfurt -> Ulm (far; best available)
    "Uhlsport Park"                     : "03379",  # Munich (1860 Munich home)
    "Grünwalder Stadion"                : "03379",  # Munich (1860 Munich home, alt.)

    # Lower Saxony / NRW (BL2-only)
    "Bremer Brücke"                     : "03631",  # Osnabrück
    "Hänsch-Arena"                      : "02991",  # Meppen
    "VfB-Stadion"                       : "02990",  # Oldenburg
    "Stadion Niederrhein"               : "01078",  # Oberhausen -> Düsseldorf (~25km)
    "Stadion Essen"                     : "01303",  # Essen
    "Lohrheidestadion"                  : "01303",  # Bochum-Wattenscheid -> Essen
    "Stadion am Lohrheidestadion"       : "01303",  # Wattenscheid
    "Grotenburg-Stadion"                : "01078",  # Krefeld (Uerdingen) -> Düsseldorf
    "Leimbachstadion"                   : "02667",  # Siegen -> Cologne (~70km, imprecise)

    # Saarland / Rhineland-Palatinate (BL2-only)
    "Ludwigsparkstadion"                : "04313",  # Saarbrücken
    "URSAPHARM-Arena an der Kaiserlinde": "04313",  # Elversberg -> Saarbrücken
    "Waldstadion Homburg"               : "04313",  # Homburg -> Saarbrücken
    "Stadion Oberwerth"                 : "03017",  # Koblenz

    # Hesse / Baden-Württemberg (BL2-only)
    "Brita-Arena"                       : "01420",  # Wiesbaden -> Frankfurt (~40km)
    "Sparda-Bank-Hessen-Stadion"        : "01420",  # Offenbach -> Frankfurt (~10km)
    "Brentanobad Stadion"               : "01420",  # Frankfurt (FSV Frankfurt)
    "BWT-Stadion am Hardtwald"          : "05906",  # Sandhausen -> Mannheim (~15km)
    "Gazi-Stadion auf der Waldau"       : "04928",  # Stuttgart (Kickers)
    "Ostalb-Stadion"                    : "04928",  # Aalen -> Stuttgart (~80km, imprecise)
    "Kreuzeichenstadion"                : "04928",  # Reutlingen -> Stuttgart (~40km)
    "flyeralarm Arena"                  : "05705",  # Würzburg -> Ulm (imprecise, no closer station mapped)

    # Brandenburg / Saxony-Anhalt (BL2-only)
    "Karl-Liebknecht-Stadion"           : "03811",  # Potsdam

    # Northern Germany (BL2-only)
    "Lohmühle"                          : "01975",  # Lübeck -> Hamburg (~65km)
    "Lohmühle-Stadion"                  : "01975",  # Lübeck

    # Wuppertal
    "Stadion am Sonnborn"               : "01078",  # Wuppertal -> Düsseldorf (~25km)
    "Wuppertaler Stadion"               : "01078",  # Wuppertal

    # -- Alternate spellings of stadiums already mapped above --
    "eins Erzgebirgsstadion"                      : "00853",  # Aue
    "Avnet-Arena"                                  : "03126",  # Magdeburg
    "BRITA Arena"                                  : "01420",  # Wiesbaden -> Frankfurt
    "GAZi-Stadion auf der Waldau"                  : "04928",  # Stuttgart
    "Jahnstadion"                                  : "03761",  # Regensburg
    "MERKUR SPIEL-ARENA"                           : "01078",  # Düsseldorf
    "Ursapharm-Arena an der Kaiserlinde"           : "04313",  # Elversberg -> Saarbrücken
    "Stadion an der Lohmühle"                      : "01975",  # Lübeck -> Hamburg
    "ad hoc Arena im Ernst-Abbe-Sportfeld"         : "02597",  # Jena
    "Stadion am Hardtwald"                         : "05906",  # Sandhausen -> Mannheim
    "PSD Bank Arena"                               : "01078",  # Düsseldorf
    "Städtisches Stadion an der Grünwalder Straße" : "03379",  # Munich
    "Stadion an der Kreuzeiche"                    : "04928",  # Reutlingen -> Stuttgart

    # -- Historical / renamed stadiums --
    "Bökelberg"                                    : "05064",  # Mönchengladbach (pre-2006)
    "Dietmar-Hopp-Stadion"                         : "01255",  # Sinsheim (pre-PreZero Arena)
    "Georg-Melches-Stadion"                        : "01303",  # Essen (RW Essen)
    "Hermann-Löns-Stadion"                         : "04371",  # Bielefeld (old Arminia ground)
    "Rosenaustadion"                               : "00232",  # Augsburg (pre-WWK Arena)
    "Stadion - An der Gellertstraße"               : "00853",  # Chemnitz
    "Stadion am Bieberer Berg"                     : "01420",  # Offenbach -> Frankfurt
    "Frankfurter Volksbank Stadion"                : "01420",  # FSV Frankfurt
    "Tivoli"                                       : "15000",  # Aachen (new ground, since 2009)
    "Tivoli (alt)"                                 : "00003",  # Aachen (old ground, until 2009)
    "Moselstadion"                                 : "05100",  # Trier
    "Wersestadion"                                 : "00042",  # Ahlen in Westphalia

    # -- Previously-unmapped stadiums --
    "AKON ARENA"                                   : "05705",  # Würzburg
    "CENTUS Arena"                                 : "01197",  # Aalen -> Ellwangen-Rindelbach
    "Tuja-Stadion"                                 : "01161",  # Ingolstadt -> Eichstätt-Landershofen
    "Wacker-Arena"                                 : "10971",  # Burghausen
    "Wacker-Arena Platz 2"                         : "10971",  # Burghausen
    "Riedel Bau Arena im Sachs-Stadion"            : "02597",  # Schweinfurt -> Bad Kissingen
    "Stadion am Alsenweg"                          : "05906",  # Mannheim
    "airberlin world"                              : "01078",  # Düsseldorf
}

ALL_BL2_STATIONS = sorted(set(BL2_STADIUM_STATION.values()))

BASE_URL_HIST   = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/historical/"
BASE_URL_RECENT = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/recent/"

CACHE_DIR = REPO_ROOT / "data" / "cache" / "dwd_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_file_list(base_url: str) -> list[str]:
    resp = requests.get(base_url, timeout=30)
    resp.raise_for_status()
    if 'historical' in base_url:
        return re.findall(r'tageswerte_KL_[\d_]+hist\.zip', resp.text)
    return re.findall(r'tageswerte_KL_[\d_]+akt\.zip', resp.text)


def download_station(station_id: str, file_list_hist: list, file_list_recent: list) -> pd.DataFrame:
    sid = station_id.zfill(5)
    dfs = []
    for base_url, file_list in [(BASE_URL_HIST, file_list_hist), (BASE_URL_RECENT, file_list_recent)]:
        matches = [f for f in file_list if f"KL_{sid}_" in f]
        if not matches:
            continue
        filename = matches[0]
        cache_path = CACHE_DIR / filename
        if cache_path.exists():
            with open(cache_path, 'rb') as f:
                zip_data = f.read()
        else:
            resp = requests.get(base_url + filename, timeout=60)
            resp.raise_for_status()
            zip_data = resp.content
            with open(cache_path, 'wb') as f:
                f.write(zip_data)
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            data_files = [n for n in zf.namelist() if n.startswith('produkt_klima_tag_')]
            if not data_files:
                continue
            with zf.open(data_files[0]) as csvfile:
                df = pd.read_csv(csvfile, sep=';', encoding='latin-1')
                df.columns = df.columns.str.strip()
                dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    combined = pd.concat(dfs, ignore_index=True)
    return combined.drop_duplicates(subset=['MESS_DATUM'])


def parse_weather(df: pd.DataFrame, station_id: str) -> pd.DataFrame:
    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['MESS_DATUM'].astype(str), format='%Y%m%d', errors='coerce')
    df['station_id'] = station_id
    col_map = {}
    for col in df.columns:
        c = col.strip().upper()
        if c == 'TMK': col_map[col] = 'temp_mean'
        if c == 'TXK': col_map[col] = 'temp_max'
        if c == 'TNK': col_map[col] = 'temp_min'
        if c == 'RSK': col_map[col] = 'precip_mm'
        if c == 'SDK': col_map[col] = 'sunshine_h'
    df = df.rename(columns=col_map)
    keep = ['date', 'station_id'] + [c for c in ['temp_mean', 'temp_max', 'temp_min', 'precip_mm', 'sunshine_h'] if c in df.columns]
    df = df[keep].copy()
    for col in df.columns:
        if col not in ['date', 'station_id']:
            df[col] = pd.to_numeric(df[col], errors='coerce').replace(-999.0, float('nan'))
    return df.dropna(subset=['date'])


if __name__ == "__main__":
    print("Reading attendance_bl2.csv to check stadium names...")
    att_bl2 = pd.read_csv(REPO_ROOT / "data" / "own_collected" / "attendance_bl2.csv", encoding="utf-8-sig")
    real_stadiums = set(att_bl2["stadium"].dropna().unique())

    unmapped = real_stadiums - set(BL2_STADIUM_STATION.keys())
    if unmapped:
        print(f"\nStadiums without a DWD mapping ({len(unmapped)}):")
        for s in sorted(unmapped):
            print(f"   '{s}'")
        print("   -> add them to BL2_STADIUM_STATION above\n")
    else:
        print("  all stadiums mapped")

    # Stations already downloaded as part of the BL1 pass (see download_weather.py).
    bl1_stations = {
        "01303", "03379", "01975", "00433", "02667", "01420", "04928", "00691",
        "02667", "00662", "02014", "03668", "01255", "02932", "00232", "01443",
        "04371", "01303", "01078", "04271", "02486", "03137", "00880", "05064",
        "02522", "04177", "03028", "02410", "05906", "00003",
    }
    new_stations = [s for s in ALL_BL2_STATIONS if s not in bl1_stations]
    print(f"\nNew DWD stations to download: {len(new_stations)}")
    print(f"Already cached from BL1: {len(ALL_BL2_STATIONS) - len(new_stations)}")

    print("\nFetching DWD file listings...")
    file_list_hist = get_file_list(BASE_URL_HIST)
    file_list_recent = get_file_list(BASE_URL_RECENT)

    print(f"\nDownloading {len(ALL_BL2_STATIONS)} stations (BL1 + BL2)...")
    weather_dfs = {}
    for sid in ALL_BL2_STATIONS:
        label = "(new)" if sid in new_stations else "(cached)"
        print(f"  {sid} {label}...", end=' ')
        raw = download_station(sid, file_list_hist, file_list_recent)
        if raw.empty:
            print("no data")
            continue
        parsed = parse_weather(raw, sid)
        weather_dfs[sid] = parsed
        print(f"{len(parsed)} days")

    all_weather = pd.concat(weather_dfs.values(), ignore_index=True)

    print("\nReading data/processed/bundesliga_with_weather.csv...")
    master_path = REPO_ROOT / "data" / "processed" / "bundesliga_with_weather.csv"
    df = pd.read_csv(master_path, encoding="utf-8-sig", low_memory=False)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # D2 rows only: map station by the stadium name (already set by merge_bl2.py).
    d2_mask = df["Div"] == "D2"
    df.loc[d2_mask, "station_id"] = df.loc[d2_mask, "Stadium"].map(BL2_STADIUM_STATION)

    weather_cols = ["temp_mean", "temp_max", "temp_min", "precip_mm", "sunshine_h"]
    df["_date"] = df["Date"].dt.date
    all_weather["_date"] = all_weather["date"].dt.date

    print("Merging weather for D2 rows...")
    df_d1 = df[~d2_mask].copy()
    df_d2 = df[d2_mask].copy()

    for col in weather_cols:
        if col in df_d2.columns:
            df_d2.drop(columns=[col], inplace=True)

    df_d2 = df_d2.merge(
        all_weather[["_date", "station_id"] + weather_cols],
        on=["_date", "station_id"], how="left",
    )

    df_final = pd.concat([df_d1, df_d2], ignore_index=True)
    df_final.sort_values(["Season", "Date"], inplace=True)
    df_final.drop(columns=["_date"], inplace=True)

    df_final.to_csv(master_path, index=False, encoding="utf-8-sig")

    print(f"\nDone: {master_path}")
    for div in ["D1", "D2"]:
        sub = df_final[df_final["Div"] == div]
        n, n_a, n_w = len(sub), sub["Attendance"].notna().sum(), sub["temp_mean"].notna().sum()
        print(f"   {div}: {n} matches | attendance: {n_a} ({100*n_a/n:.0f}%) | weather: {n_w} ({100*n_w/n:.0f}%)")
