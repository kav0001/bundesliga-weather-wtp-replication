"""
Scrape stadium capacity from German Wikipedia for every stadium in the dataset.
Uses the Wikipedia API (official JSON API, no HTML scraping).

Input:  data/processed/bundesliga_with_weather.csv (for the list of stadium names)
Output: data/own_collected/stadium_capacity.csv, feeds merge_capacity.py

MANUAL maps dataset stadium names to their (often renamed/sponsored) current
Wikipedia article title, with an optional hard-coded capacity override.
"""

import requests
import pandas as pd
import time
import re
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_IN  = os.path.join(REPO_ROOT, "data", "processed", "bundesliga_with_weather.csv")
CSV_OUT = os.path.join(REPO_ROOT, "data", "own_collected", "stadium_capacity.csv")

# dataset_name -> (wikipedia_search_term, capacity_override_or_None)
MANUAL = {
    "SIGNAL IDUNA PARK":            ("Signal Iduna Park", None),
    "Allianz Arena":                ("Allianz Arena", None),
    "RheinEnergieSTADION":         ("RheinEnergieStadion", None),
    "Olympiastadion Berlin":        ("Olympiastadion Berlin", None),
    "Olympiastadion München":       ("Olympiastadion München", None),
    "Volksparkstadion":             ("Volksparkstadion Hamburg", None),
    "Veltins-Arena":                ("Veltins-Arena", None),
    "BayArena":                     ("BayArena", None),
    "Europa-Park Stadion":          ("Europa-Park Stadion", None),
    "Red Bull Arena":               ("Red Bull Arena Leipzig", None),
    "MHPArena Stuttgart":           ("MHPArena", None),
    "Deutsche Bank Park":           ("Deutsche Bank Park", None),
    "Commerzbank Arena":            ("Deutsche Bank Park", None),
    "WWK ARENA":                    ("WWK Arena", None),
    "Weserstadion":                 ("Weserstadion", None),
    "Wohninvest-Weserstadion":      ("Weserstadion", None),
    "Vonovia Ruhrstadion":          ("Vonovia Ruhrstadion", None),
    "Volkswagen Arena":             ("Volkswagen Arena", None),
    "Audi Sportpark":               ("Audi Sportpark", None),
    "Max-Morlock-Stadion":          ("Max-Morlock-Stadion", None),
    "SchücoArena":                  ("SchücoArena", None),
    "Stadion im Borussia-Park":     ("Borussia-Park", None),
    "Mewa Arena":                   ("Mewa Arena", None),
    "Stadion am Bruchweg":          ("Stadion am Bruchweg", None),
    "ESPRIT arena":                 ("Merkur Spiel-Arena", None),
    "Parkstadion":                  ("Parkstadion Gelsenkirchen", None),
    "Bökelberg":                    ("Bökelberg", None),
    "Ostseestadion":                ("Ostseestadion", None),
    "Millerntor-Stadion":           ("Millerntor-Stadion", None),
    "Stadion An der Alten Försterei": ("Stadion An der Alten Försterei", None),
    "PreZero Arena":                ("PreZero Arena", None),
    "MSV-Arena":                    ("MSV-Arena", None),
    "Fritz-Walter-Stadion":         ("Fritz Walter Stadion", None),
    "BBBank Wildpark":              ("BBBank Wildpark", None),
    "Sportpark Ronhof | Thomas Sommer": ("Sportpark Ronhof Thomas Sommer", None),
    "Dreisamstadion":               ("Dreisamstadion", None),
    "EINTRACHT-Stadion":            ("Eintracht-Stadion Braunschweig", None),
    "LEAG Energie Stadion":         ("LEAG Energie Stadion", None),
    "Merck-Stadion am Böllenfalltor": ("Merck-Stadion am Böllenfalltor", None),
    "Voith-Arena":                  ("Voith-Arena", None),
    "Heinz-von-Heiden-Arena":       ("Heinz von Heiden Arena", None),
    "Home Deluxe Arena":            ("Home Deluxe Arena", None),
    "Uhlsport Park":                ("Uhlsport Haudenschild Stadion", None),
    "Carl-Benz-Stadion":            ("Carl-Benz-Stadion", None),
    "Tivoli (alt)":                 ("Tivoli Stadion Aachen", None),
    "Stadion der Freundschaft":     ("Stadion der Freundschaft Frankfurt Oder", None),
    "VfL-Stadion am Elsterweg":     ("VfL-Stadion am Elsterweg", None),
    "Stadion an der Lohmühle":      ("Stadion an der Lohmühle", None),
    "Rudolf-Harbig-Stadion":        ("Rudolf-Harbig-Stadion", None),
    "Holstein-Stadion":             ("Holstein-Stadion", None),
    "Jahnstadion Regensburg":       ("Jahnstadion Regensburg", None),
    "Bremer Brücke":                ("Bremer Brücke", None),
    "BRITA Arena":                  ("Brita-Arena", None),
    "Tivoli":                       ("Tivoli Aachen neu", None),
    "Ludwigsparkstadion":           ("Ludwigsparkstadion", None),
    "Rosenaustadion":               ("Rosenaustadion", None),
    "Hermann-Löns-Stadion":         ("Hermann-Löns-Stadion", None),
    "eins Erzgebirgsstadion":       ("Erzgebirgsstadion", None),
    "Jahnstadion":                  ("Jahnstadion Regensburg", None),
    "Donaustadion":                 ("Donaustadion", None),
    "Stadion am Hardtwald":         ("Stadion am Hardtwald", None),
    "Moselstadion":                 ("Moselstadion", None),
    "Wersestadion":                 ("Wersestadion", None),
    "Stadion Niederrhein":          ("Stadion Niederrhein", None),
    "Städtisches Stadion an der Grünwalder Straße": ("Städtisches Stadion an der Grünwalder Straße", None),
    "Leimbachstadion":              ("Leimbachstadion", None),
    "Stadion am Bieberer Berg":     ("Stadion am Bieberer Berg", None),
    "Stadion am Alsenweg":          ("Stadion am Alsenweg", None),
    "GAZi-Stadion auf der Waldau":  ("GAZi-Stadion auf der Waldau", None),
    "Wacker-Arena":                 ("Wacker-Arena", None),
    "Dietmar-Hopp-Stadion":         ("Dietmar-Hopp-Stadion", None),
    "Karl-Liebknecht-Stadion":      ("Karl-Liebknecht-Stadion", None),
    "ad hoc Arena im Ernst-Abbe-Sportfeld": ("Ernst-Abbe-Sportfeld", None),
    "Stadion - An der Gellertstraße": ("Stadion an der Gellertstraße", None),
    "Stadion Oberwerth":            ("Stadion Oberwerth", None),
    "Stadion an der Kreuzeiche":    ("Stadion an der Kreuzeiche", None),
    "Tuja-Stadion":                 ("Tuja-Stadion", None),
    "Riedel Bau Arena im Sachs-Stadion": ("Sachs-Stadion", None),
    "AKON ARENA":                   ("AKON Arena", None),
    "CENTUS Arena":                 ("CENTUS Arena", None),
    "Avnet-Arena":                  ("Avnet-Arena", None),
    "Ursapharm-Arena an der Kaiserlinde": ("Ursapharm-Arena an der Kaiserlinde", None),
}


def wiki_search_capacity(search_term):
    """Search German Wikipedia and extract capacity from the article's plain text."""
    session = requests.Session()
    headers = {"User-Agent": "thesis-capacity-scraper/1.0 (research)"}
    search_url = "https://de.wikipedia.org/w/api.php"

    # Step 1: find the article title.
    params = {"action": "query", "list": "search", "srsearch": search_term, "srlimit": 1, "format": "json"}
    try:
        r = session.get(search_url, params=params, headers=headers, timeout=10)
        results = r.json().get("query", {}).get("search", [])
        if not results:
            return None, "no search result"
        title = results[0]["title"]
    except Exception as e:
        return None, str(e)

    # Step 2: pull the article's plain text.
    params2 = {"action": "query", "titles": title, "prop": "extracts",
               "explaintext": True, "exsectionformat": "plain", "format": "json"}
    try:
        r2 = session.get(search_url, params=params2, headers=headers, timeout=10)
        pages = r2.json().get("query", {}).get("pages", {})
        text = list(pages.values())[0].get("extract", "")
    except Exception as e:
        return None, str(e)

    # Step 3: match one of the German infobox capacity labels.
    patterns = [
        r'Zuschauer[^\d]{0,20}([\d\.]+)',
        r'Kapazit[äa]t[^\d]{0,20}([\d\.]+)',
        r'Fassungsverm[öo]gen[^\d]{0,20}([\d\.]+)',
        r'(\d[\d\.]{3,6})\s*Zuschauer',
        r'(\d[\d\.]{3,6})\s*Pl[äa]tze',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1).replace(".", "")
            try:
                cap = int(raw)
                if 1000 < cap < 120000:
                    return cap, title
            except ValueError:
                continue

    return None, f"found article '{title}' but no capacity pattern matched"


def main():
    df = pd.read_csv(CSV_IN)
    stadiums = sorted(df[df["Div"].isin(["D1", "D2"])]["Stadium"].dropna().unique())
    print(f"Stadiums to look up: {len(stadiums)}")

    rows = []
    for i, stadium in enumerate(stadiums):
        search_term, override = MANUAL.get(stadium, (stadium, None))

        if override is not None:
            cap, note = override, "manual override"
        else:
            cap, note = wiki_search_capacity(search_term)

        status = "OK" if cap else "MISSING"
        print(f"[{i+1:02d}/{len(stadiums)}] {stadium[:45]:<45} -> {cap or '?':>6}  ({note})")
        rows.append({"Stadium": stadium, "capacity": cap, "wiki_note": note, "status": status})
        time.sleep(0.3)

    out_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
    out_df.to_csv(CSV_OUT, index=False)
    print(f"\nSaved: {CSV_OUT}")
    print(f"OK: {(out_df.status == 'OK').sum()} / {len(out_df)}")
    print(f"Missing: {(out_df.status == 'MISSING').sum()}")
    print("\nMissing stadiums:")
    print(out_df[out_df.status == 'MISSING'][['Stadium', 'wiki_note']].to_string(index=False))


if __name__ == "__main__":
    main()
