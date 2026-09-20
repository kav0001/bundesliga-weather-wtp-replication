# How Much Is a Cool Day Worth? Evidence from European Football

Data and code for the Master's thesis by **Aleksei Kalashnikov**, Chair of
Quantitative International & Environmental Economics, Julius-Maximilians-
Universität Würzburg, 2026 (supervisor: Prof. Dr. Joschka Wanner).

The thesis tests whether the revealed-preference approach to valuing thermal
discomfort developed by Kuruc, LoPalo & O'Connor (2025) for Major League
Baseball extends to German professional football (Bundesliga 1 and 2,
2000/01-2023/24), where season tickets commit a large share of stadium
capacity months before match-day weather is known.

## Quickstart: reproduce the thesis's tables and figures

The final dataset is already included - **you do not need to scrape or
download anything** to reproduce the results.

```
pip install -r requirements.txt
Rscript environment/r-packages.R

# Regressions (writes tables/*.csv)
Rscript scripts/analysis/regression_bl1_bl2.R
Rscript scripts/analysis/regression_fillrate.R
Rscript scripts/analysis/regression_robustness.R
Rscript scripts/analysis/regression_robustness_kurucfe.R
python3 scripts/analysis/wtp_calculation.py

# Figures (writes figures/*.png)
Rscript scripts/make_figures.R
```

That's the whole workflow. `data/processed/bundesliga_with_weather.csv` is
the dataset every result in the thesis is computed from.

## Repository layout

```
data/
  own_collected/     Data collected directly for this thesis (scraped
                      attendance, scraped stadium capacity, hand-extracted
                      ticket prices)
  processed/          bundesliga_with_weather.csv - the master dataset
scripts/
  analysis/            Regressions + WTP calculation - run these to reproduce
                        every table in the thesis
  make_figures.R        Every figure used in the thesis, one script
  collection/           How the data was originally collected (see "Data
                        collection" below) - informational, not required
tables/                Regression/WTP output, at full numeric precision
figures/                The 10 PNG figures used in the thesis
```

## The four regression model families - do not confuse them

This thesis runs several genuinely different sets of specifications. Each
lives in its own script and is labeled distinctly in every output table:

| Family | Script | Labels | What it's for |
|---|---|---|---|
| Headline | `scripts/analysis/regression_bl1_bl2.R` | M1-M5 | The main Results-chapter table: BL1, BL2, pooled, and the BL1-vs-BL2 interaction test |
| Exploratory build-up | (documented in the thesis text only, not separately scripted) | M_P1-M_P5, M6-M8, M_B1, M_final | How the fixed-effects structure and functional form were arrived at, before the M1-M5 sequence was run |
| Robustness | `scripts/analysis/regression_robustness.R` | M_D1-M_D3 (weekday/weekend), M8/M9 (temperature bins, two reference categories), M_B1/M_B2 (sunshine-only), clustered-vs-robust SE | Checks that the headline result isn't an artifact of a modeling choice |
| Kuruc-exact FE | `scripts/analysis/regression_robustness_kurucfe.R` | M3 additive vs. M3 interacted FE | Re-estimates the preferred spec under the exact fixed-effects structure Kuruc et al. (2025) use, instead of this thesis's additive one |

Full-precision output for all four lives in `tables/*.csv`.

## Data collection (informational - not required to reproduce results)

`scripts/collection/` documents how `data/processed/bundesliga_with_weather.csv`
was originally built, from five sources: football-data.co.uk (BL1 match
records), two Transfermarkt scrapes (BL1 and BL2 attendance), the German
Weather Service (DWD, daily weather by station), Wikipedia (stadium
capacity), and hand-extracted DFL Economic Reports (ticket prices). You do
not need to run any of this - the dataset it produces is already committed.
It's included for transparency about the data-construction methodology
(team-name reconciliation across sources, stadium-to-weather-station
matching, etc.), not as a pipeline you're expected to execute.

Two things worth knowing if you do look at it:

- **Two intermediate files have no surviving generating script**:
  `bundesliga_all.csv` (raw BL1 match records) and
  `tm_attendance_2000_2011.csv` (a one-off 2011-era Transfermarkt scrape for
  BL1). The scripts that consume them (`prepare_attendance.py`,
  `merge_unified.py`, `download_weather.py`) are included anyway to document
  the method, but cannot be re-run end to end. The BL2 equivalent
  (`scrape_bl2_attendance.py`) does survive and can be re-run.
- **`prepare_attendance_bl2.py` overwrites rather than appends to
  `data/own_collected/attendance_bl2.csv`**, while `scrape_bl2_attendance.py`
  writes to the same file. Running them back to back in the natural order
  destroys the first script's rows. The committed `attendance_bl2.csv`
  already contains both eras correctly; this only matters if you want to
  rebuild it from scratch (in which case: run `scrape_bl2_attendance.py`,
  copy its output aside, run `prepare_attendance_bl2.py`, concatenate the
  two and dedup on date + home_team + away_team before `merge_bl2.py`).
- `games.csv` (from the public `transfermarkt-datasets` GitHub project,
  filtered to `competition_id == "L1"`/`"L2"`) is not re-hosted here - fetch
  it from that project directly if you want to re-run this stage.

## Why some things are gitignored

`data/cache/` (Transfermarkt matchday HTML, DWD station archives) is a local
performance cache the collection scripts create on demand, purely so a
rerun doesn't re-fetch pages it already has. It is not committed because:
it's large (~200MB) relative to the actual data (~5MB), it's a scraped copy
of third-party pages rather than a research artifact, and anything in it is
trivially regenerated by rerunning the relevant script - there's no reason
to carry ~200MB of raw HTML in git history permanently for something that
takes minutes to rebuild if ever needed.

## License

Code in `scripts/` is MIT-licensed (see `LICENSE`). The DWD weather data is
German open government data (Deutscher Wetterdienst, freely usable with
attribution). Match/attendance data is sourced from Transfermarkt.de and the
public `transfermarkt-datasets` project for non-commercial research use.
Ticket price figures are hand-extracted from public DFL Economic Reports.

## Citation

Kalashnikov, Aleksei (2026). *How Much Is a Cool Day Worth? Evidence from
European Football*. Master's thesis, Julius-Maximilians-Universität Würzburg.
