"""
DWD weather downloader for Bundesliga 1 stadiums.

Downloads daily station data (temperature, precipitation, sunshine hours)
from the DWD (German Weather Service) open-data CDC archive for every BL1
stadium, then merges it onto bundesliga_unified.csv by date + nearest
station.

NOTE ON REPRODUCIBILITY: bundesliga_unified.csv (BL1 match records merged
with attendance, pre-weather) is not included in this package and has no
surviving generating script — see the README's "known gaps" section. This
script is included to document the weather-matching methodology (the
stadium -> DWD station mapping, in particular) even though it cannot be
re-run end-to-end without that input file. Everything from
data/processed/bundesliga_with_weather.csv onward (the committed, final
dataset) is fully reproducible regardless.

Run:
    pip install requests pandas
    python download_weather.py
"""

import requests
import pandas as pd
import zipfile
import io
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Stadium -> nearest DWD station with 2000-2024 coverage.
STADIUM_STATION = {
    "SIGNAL IDUNA PARK"                 : "01303",  # Essen-Bredeney (~30km)
    "Allianz Arena"                     : "03379",  # Munich-city
    "Olympiastadion München"            : "03379",  # Munich-city
    "Volksparkstadion"                  : "01975",  # Hamburg-Fuhlsbüttel
    "Millerntor-Stadion"                : "01975",  # Hamburg-Fuhlsbüttel
    "Olympiastadion Berlin"             : "00433",  # Berlin-Tempelhof
    "Stadion An der Alten Försterei"    : "00433",  # Berlin-Tempelhof
    "RheinEnergieSTADION"               : "02667",  # Cologne/Bonn
    "Deutsche Bank Park"                : "01420",  # Frankfurt/Main
    "Commerzbank Arena"                 : "01420",  # Frankfurt/Main
    "MHPArena Stuttgart"                : "04928",  # Stuttgart (Schnarrenberg)
    "Weserstadion"                      : "00691",  # Bremen
    "Wohninvest-Weserstadion"           : "00691",  # Bremen
    "BayArena"                          : "02667",  # Cologne/Bonn (~25km)
    "Volkswagen Arena"                  : "00662",  # Braunschweig (~40km)
    "VfL-Stadion am Elsterweg"          : "00662",  # Braunschweig
    "Heinz-von-Heiden-Arena"            : "02014",  # Hannover
    "Max-Morlock-Stadion"               : "03668",  # Nuremberg
    "PreZero Arena"                     : "01255",  # Eppingen-Elsenz (~10km)
    "Red Bull Arena"                    : "02932",  # Leipzig/Halle
    "WWK ARENA"                         : "00232",  # Augsburg
    "Dreisamstadion"                    : "01443",  # Freiburg
    "Europa-Park Stadion"               : "01443",  # Freiburg
    "SchücoArena"                       : "04371",  # Bad Salzuflen (~42km)
    "Vonovia Ruhrstadion"               : "01303",  # Essen-Bredeney
    "MSV-Arena"                         : "01078",  # Düsseldorf
    "ESPRIT arena"                      : "01078",  # Düsseldorf
    "Ostseestadion"                     : "04271",  # Rostock-Warnemünde
    "Fritz-Walter-Stadion"              : "02486",  # Kaiserslautern
    "Stadion am Bruchweg"               : "01420",  # Frankfurt/Main (~28km)
    "Mewa Arena"                        : "03137",  # Mainz-Lerchenberg
    "LEAG Energie Stadion"              : "00880",  # Cottbus
    "Stadion der Freundschaft"          : "00880",  # Cottbus
    "Stadion im Borussia-Park"          : "05064",  # Tönisvorst (~11km)
    "Bökelberg"                         : "05064",  # Tönisvorst
    "BBBank Wildpark"                   : "02522",  # Karlsruhe (until 2008; see KARLSRUHE_STATIONS)
    "EINTRACHT-Stadion"                 : "00662",  # Braunschweig
    "Merck-Stadion am Böllenfalltor"    : "01420",  # Frankfurt/Main
    "Sportpark Ronhof | Thomas Sommer"  : "03668",  # Nuremberg (~8km)
    "Tivoli (alt)"                      : "00003",  # Aachen
    "Uhlsport Park"                     : "03379",  # Munich-city
    "Home Deluxe Arena"                 : "03028",  # Bad Lippspringe (~12km)
    "Voith-Arena"                       : "04928",  # Stuttgart (~80km, best available)
    "Audi Sportpark"                    : "02410",  # Ingolstadt-Manching
    "Carl-Benz-Stadion"                 : "05906",  # Mannheim
    "Veltins-Arena"                     : "01303",  # Essen-Bredeney
    "Parkstadion"                       : "01303",  # Essen-Bredeney
}

# Karlsruhe changed its representative station in 2009.
KARLSRUHE_STATIONS = {"pre": "02522", "post": "04177"}

ALL_STATIONS = sorted(set(STADIUM_STATION.values()) | {"04177"})

BASE_URL_HIST   = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/historical/"
BASE_URL_RECENT = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/recent/"

CACHE_DIR = REPO_ROOT / "data" / "cache" / "dwd_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_file_list(base_url: str) -> list[str]:
    """List available station zip files on a DWD index page."""
    resp = requests.get(base_url, timeout=30)
    resp.raise_for_status()
    if 'historical' in base_url:
        return re.findall(r'tageswerte_KL_[\d_]+hist\.zip', resp.text)
    return re.findall(r'tageswerte_KL_[\d_]+akt\.zip', resp.text)


def download_station(station_id: str, file_list_hist: list, file_list_recent: list) -> pd.DataFrame:
    """Download and concatenate a station's historical + recent daily records."""
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
    """Select and rename the relevant DWD columns; convert -999 sentinels to NaN."""
    if df.empty:
        return df

    df['date'] = pd.to_datetime(df['MESS_DATUM'].astype(str), format='%Y%m%d', errors='coerce')
    df['station_id'] = station_id

    col_map = {}
    for col in df.columns:
        c = col.strip().upper()
        if c == 'TMK': col_map[col] = 'temp_mean'    # daily mean temperature, C
        if c == 'TXK': col_map[col] = 'temp_max'     # daily max temperature, C
        if c == 'TNK': col_map[col] = 'temp_min'     # daily min temperature, C
        if c == 'RSK': col_map[col] = 'precip_mm'    # precipitation, mm
        if c == 'SDK': col_map[col] = 'sunshine_h'   # sunshine duration, hours

    df = df.rename(columns=col_map)
    keep = ['date', 'station_id'] + [c for c in ['temp_mean', 'temp_max', 'temp_min', 'precip_mm', 'sunshine_h'] if c in df.columns]
    df = df[keep].copy()

    for col in df.columns:
        if col not in ['date', 'station_id']:
            df[col] = pd.to_numeric(df[col], errors='coerce').replace(-999.0, float('nan'))

    return df.dropna(subset=['date'])


if __name__ == "__main__":
    print("Fetching DWD file listings...")
    file_list_hist = get_file_list(BASE_URL_HIST)
    file_list_recent = get_file_list(BASE_URL_RECENT)
    print(f"  historical files: {len(file_list_hist)}, recent files: {len(file_list_recent)}")

    print(f"\nDownloading {len(ALL_STATIONS)} stations...")
    weather_dfs = {}
    for sid in ALL_STATIONS:
        print(f"  station {sid}...", end=' ')
        raw = download_station(sid, file_list_hist, file_list_recent)
        if raw.empty:
            print("no data")
            continue
        parsed = parse_weather(raw, sid)
        weather_dfs[sid] = parsed
        print(f"{len(parsed)} days ({parsed['date'].min().date()} to {parsed['date'].max().date()})")

    print("\nConcatenating all stations...")
    all_weather = pd.concat(weather_dfs.values(), ignore_index=True)

    print("Reading bundesliga_unified.csv (BL1 matches + attendance, pre-weather)...")
    df = pd.read_csv(REPO_ROOT / "bundesliga_unified.csv", encoding="utf-8-sig", low_memory=False)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    df['station_id'] = df['Stadium'].map(STADIUM_STATION)

    # Karlsruhe used a different station before/after 2009.
    mask_kl = df['Stadium'] == 'BBBank Wildpark'
    df.loc[mask_kl & (df['Date'].dt.year < 2009), 'station_id'] = KARLSRUHE_STATIONS['pre']
    df.loc[mask_kl & (df['Date'].dt.year >= 2009), 'station_id'] = KARLSRUHE_STATIONS['post']

    df['_date'] = df['Date'].dt.date
    all_weather['_date'] = all_weather['date'].dt.date

    print("Merging weather onto matches (by date + station_id)...")
    df = df.merge(
        all_weather[['_date', 'station_id', 'temp_mean', 'temp_max', 'temp_min', 'precip_mm', 'sunshine_h']],
        on=['_date', 'station_id'], how='left',
    )
    df.drop(columns=['_date'], inplace=True)

    OUTPUT = REPO_ROOT / "data" / "processed" / "bundesliga_with_weather.csv"
    df.to_csv(OUTPUT, index=False, encoding='utf-8-sig')

    d1 = df[df['Div'] == 'D1']
    n, n_w, n_a = len(d1), d1['temp_mean'].notna().sum(), d1['Attendance'].notna().sum()

    print(f"\nDone: {OUTPUT}")
    print(f"   BL1 rows total:        {n}")
    print(f"   with attendance:       {n_a} ({100*n_a/n:.1f}%)")
    print(f"   with weather:          {n_w} ({100*n_w/n:.1f}%)")
    print(f"   with both:             {(d1['temp_mean'].notna() & d1['Attendance'].notna()).sum()}")
    print(f"\nColumns: {list(df.columns)}")
