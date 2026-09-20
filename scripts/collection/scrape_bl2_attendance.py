"""
Transfermarkt BL2 attendance scraper.

Scrapes match date, teams, attendance, and stadium for every Bundesliga 2
fixture, 2000/01-2023/24 (2020/21 excluded, see thesis Data chapter for why).
Writes to data/own_collected/attendance_bl2.csv as it goes (resumable: already
scraped URLs are skipped on rerun). Spieltag (matchday) list pages are cached
in data/cache/bl2_cache/ purely to recover match IDs cheaply on rerun; the
per-match pages themselves are always fetched fresh.

Output feeds scripts/collection/merge_bl2.py.
"""

import requests
import pandas as pd
import csv
import time
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT    = REPO_ROOT / "data" / "own_collected" / "attendance_bl2.csv"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "bl2_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

SEASONS = [s for s in range(2000, 2024) if s != 2020]

CSV_COLS = ["season", "date", "home_team", "away_team", "attendance", "stadium", "url"]


def get_spieltag_html(season_year: int, spieltag: int) -> str:
    """Fetch (or read from cache) one matchday's fixture-list page, to recover match IDs."""
    cache_file = CACHE_DIR / f"bl2_{season_year}_st{spieltag:02d}.html"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    url = (f"https://www.transfermarkt.de/zweite-bundesliga/spieltag"
           f"/wettbewerb/L2/plus/?saison_id={season_year}&spieltag={spieltag}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        cache_file.write_text(resp.text, encoding="utf-8")
        time.sleep(1.2)
        return resp.text
    except Exception as e:
        print(f"  [error] spieltag {season_year}/{spieltag}: {e}")
        return ""


def get_match_ids(season_year: int) -> list[str]:
    all_ids = []
    for st in range(1, 35):
        html = get_spieltag_html(season_year, st)
        ids = re.findall(r'spielbericht/index/spielbericht/(\d+)', html)
        all_ids.extend(ids)
    return list(dict.fromkeys(all_ids))


def fetch_and_parse(match_id: str) -> dict | None:
    """Fetch one match report page and extract date/teams/attendance/stadium."""
    url = f"https://www.transfermarkt.de/spielbericht/index/spielbericht/{match_id}"
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            html = resp.text
            time.sleep(1.5)
            break
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"  [retry] {match_id} (attempt {attempt + 1}/3): {e} - waiting {wait}s")
            time.sleep(wait)
    else:
        print(f"  [skip] {match_id}: giving up after 3 attempts")
        return None

    title_m = re.search(r'<title>([^<]+)</title>', html)
    if not title_m:
        return None
    teams_date = re.match(r'^(.+?)\s*-\s*(.+?),\s*(\d{2}\.\d{2}\.\d{4})', title_m.group(1))
    if not teams_date:
        return None

    att_m = re.search(r'(\d{1,3}(?:\.\d{3})+)\s*Zuschauer', html)
    if not att_m:
        return None

    stad_m = re.search(
        r'href="[^"]+/stadion/[^"]+">([^<]+)</a>\s*(?:&nbsp;)*\s*\|\s*(?:&nbsp;)*\s*<strong>\d',
        html
    )

    return {
        "date"      : teams_date.group(3),
        "home_team" : teams_date.group(1).strip(),
        "away_team" : teams_date.group(2).strip(),
        "attendance": int(att_m.group(1).replace('.', '')),
        "stadium"   : stad_m.group(1).strip() if stad_m else "",
        "url"       : url,
    }


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Resume support: skip URLs already present in the output file.
    done_urls: set[str] = set()
    if OUTPUT.exists():
        try:
            existing = pd.read_csv(OUTPUT, encoding="utf-8-sig", usecols=["url"])
            done_urls = set(existing["url"].dropna())
            print(f"Resuming: {len(done_urls)} matches already scraped")
        except Exception:
            done_urls = set()

    if not OUTPUT.exists() or OUTPUT.stat().st_size == 0:
        with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=CSV_COLS).writeheader()

    total_written = len(done_urls)

    for season_year in SEASONS:
        season_label = f"{season_year}/{str(season_year + 1)[-2:]}"
        print(f"\n-- {season_label} --")

        ids = get_match_ids(season_year)
        print(f"   Matches found: {len(ids)}")

        season_count, skipped = 0, 0
        with open(OUTPUT, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLS)
            for match_id in ids:
                url = f"https://www.transfermarkt.de/spielbericht/index/spielbericht/{match_id}"
                if url in done_urls:
                    skipped += 1
                    continue
                result = fetch_and_parse(match_id)
                if result:
                    result["season"] = season_label
                    writer.writerow(result)
                    f.flush()
                    season_count += 1
                    total_written += 1
                    print(f"  {result['date']}  {result['home_team']} vs {result['away_team']}  "
                          f"{result['attendance']:,}  {result['stadium']}")

        if skipped:
            print(f"   (skipped, already present: {skipped})")
        print(f"   Season done: {season_count} matches (total so far: {total_written})")

    print(f"\nDone: {OUTPUT}  -  {total_written} matches")
