"""
Willingness-to-pay calculation from the sunshine coefficient.
WTP = P_bar x beta_sunshine / |eta_p|  (eta_p = -1, unit elasticity, from Krautmann & Berri 2007)
WTP_true = WTP_observed / (1 - f)  (attenuation correction for season tickets)

Also reports fill-rate heterogeneity descriptives (high/low fill_rate subsamples).

Reads:  data/processed/bundesliga_with_weather.csv
Writes: tables/wtp_results.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV = REPO_ROOT / "data" / "processed" / "bundesliga_with_weather.csv"

df = pd.read_csv(CSV, low_memory=False)
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

# Regression sample: post-2000, no COVID, BL1+BL2, weather available.
# 2021/22 matches played under COVID capacity caps (fill_rate < 0.5) are also
# dropped - German federal (2 Dec 2021) and state-level (Berlin 5,000 cap
# from 8 Dec 2021; Baden-Wuerttemberg 750 cap from 4 Dec 2021) restrictions
# suppressed attendance independent of weather from roughly Dec 2021 to
# Feb 2022. See regression_bl1_bl2.R for the same filter and its
# leave-one-season-out / placebo-check justification.
reg = df[
    df["Div"].isin(["D1", "D2"]) &
    (df["Date"].dt.year >= 2000) &
    (df["Season"] != "2020/21") &
    ~((df["Season"] == "2021/22") & (df["fill_rate"] < 0.5)) &
    df["sunshine_h"].notna() &
    df["Attendance"].notna()
].copy()

print(f"Regression sample: {len(reg)} matches ({len(reg[reg['Div']=='D1'])} D1, {len(reg[reg['Div']=='D2'])} D2)")

# Beta coefficients from tables/regression_results.csv, M3 (main spec).
beta = {
    "D1": 0.000761,   # BL1 M3 sunshine_h
    "D2": 0.002553,   # BL2 M3 sunshine_h
    "Pool": 0.001814, # Pooled M3
}
se = {
    "D1": 0.000589,
    "D2": 0.001307,
    "Pool": 0.000709,
}

# Season-ticket shares (from data/own_collected/ticket_prices.csv, see thesis Data chapter).
f = {"D1": 0.57, "D2": 0.46}

print("\n=== Average ticket prices in regression sample ===")
for div in ["D1", "D2"]:
    sub = reg[(reg["Div"] == div) & reg["avg_price"].notna()]
    print(f"{div}: n={len(sub)}, mean P_bar = EUR{sub['avg_price'].mean():.2f}  "
          f"(min EUR{sub['avg_price'].min():.2f} / max EUR{sub['avg_price'].max():.2f})")

p_bar = {}
for div in ["D1", "D2"]:
    sub = reg[(reg["Div"] == div) & reg["avg_price"].notna()]
    p_bar[div] = sub["avg_price"].mean()

eta_p = -1.0  # unit elasticity assumption

print("\n=== WTP Calculation (per sunshine hour) ===")
print(f"Formula: WTP = P_bar x beta / |eta_p|, eta_p = {eta_p}")
print()

wtp_rows = []
for div in ["D1", "D2"]:
    b = beta[div]
    s = se[div]
    p = p_bar[div]
    fi = f[div]

    wtp_obs = p * b / abs(eta_p)
    wtp_obs_lo = p * (b - 1.96 * s) / abs(eta_p)
    wtp_obs_hi = p * (b + 1.96 * s) / abs(eta_p)

    wtp_true = wtp_obs / (1 - fi)
    wtp_true_lo = wtp_obs_lo / (1 - fi)
    wtp_true_hi = wtp_obs_hi / (1 - fi)

    print(f"{div}:")
    print(f"  beta = {b:.6f} (SE={s:.6f})")
    print(f"  P_bar = EUR{p:.2f}")
    print(f"  f  = {fi:.0%}  ->  attenuation factor (1-f) = {1-fi:.2f}")
    print(f"  WTP_observed = EUR{wtp_obs:.4f}  [95% CI: EUR{wtp_obs_lo:.4f} - EUR{wtp_obs_hi:.4f}]")
    print(f"  WTP_true     = EUR{wtp_true:.4f}  [95% CI: EUR{wtp_true_lo:.4f} - EUR{wtp_true_hi:.4f}]")
    print()

    wtp_rows.append({"division": "BL1" if div == "D1" else "BL2", "measure": "WTP_observed",
                      "wtp": wtp_obs, "ci_lo": wtp_obs_lo, "ci_hi": wtp_obs_hi})
    wtp_rows.append({"division": "BL1" if div == "D1" else "BL2", "measure": "WTP_true",
                      "wtp": wtp_true, "ci_lo": wtp_true_lo, "ci_hi": wtp_true_hi})

(REPO_ROOT / "tables").mkdir(parents=True, exist_ok=True)
pd.DataFrame(wtp_rows).to_csv(REPO_ROOT / "tables" / "wtp_results.csv", index=False)

print("=== Sensitivity: WTP at current prices (2023/24) ===")
p_current = {"D1": 28.30, "D2": 22.93}
for div in ["D1", "D2"]:
    b = beta[div]
    fi = f[div]
    p = p_current[div]
    wtp_obs = p * b / abs(eta_p)
    wtp_true = wtp_obs / (1 - fi)
    print(f"{div}: WTP_observed = EUR{wtp_obs:.4f}, WTP_true = EUR{wtp_true:.4f} (at P_bar=EUR{p})")

print("\n=== Fill_rate heterogeneity (descriptives) ===")
if "fill_rate" in reg.columns:
    for div in ["D1", "D2"]:
        sub = reg[reg["Div"] == div]
        q25 = sub["fill_rate"].quantile(0.25)
        q50 = sub["fill_rate"].quantile(0.50)
        q75 = sub["fill_rate"].quantile(0.75)
        print(f"{div}: fill_rate p25={q25:.1%}  median={q50:.1%}  p75={q75:.1%}")

    high_cut = 0.85
    low_cut = 0.70

    print(f"\nSplit: high fill_rate > {high_cut:.0%}, low fill_rate < {low_cut:.0%}")
    for div in ["D1", "D2"]:
        sub = reg[reg["Div"] == div]
        high = sub[sub["fill_rate"] >= high_cut]
        low = sub[sub["fill_rate"] < low_cut]
        mid = sub[(sub["fill_rate"] >= low_cut) & (sub["fill_rate"] < high_cut)]
        print(f"{div}: high={len(high)} ({len(high)/len(sub):.0%}),  "
              f"low={len(low)} ({len(low)/len(sub):.0%}),  "
              f"mid={len(mid)} ({len(mid)/len(sub):.0%})")
        print(f"     avg attendance: high={high['Attendance'].mean():.0f},  "
              f"low={low['Attendance'].mean():.0f}")
else:
    print("fill_rate column not found - skipping heterogeneity block")

print("\n=== Summary Table ===")
print(f"{'':30s} {'BL1':>12s} {'BL2':>12s}")
print(f"{'beta_sunshine (M3)':30s} {beta['D1']:>12.6f} {beta['D2']:>12.6f}")
print(f"{'SE':30s} {se['D1']:>12.6f} {se['D2']:>12.6f}")
print(f"{'P_bar (period avg, EUR)':30s} {p_bar['D1']:>12.2f} {p_bar['D2']:>12.2f}")
print(f"{'P_bar (2023/24, EUR)':30s} {p_current['D1']:>12.2f} {p_current['D2']:>12.2f}")
print(f"{'Season ticket share f':30s} {f['D1']:>12.2%} {f['D2']:>12.2%}")
print(f"{'Attenuation (1-f)':30s} {1-f['D1']:>12.2f} {1-f['D2']:>12.2f}")
print(f"{'WTP_obs (period P_bar, EUR/h)':30s} {p_bar['D1']*beta['D1']:>12.4f} {p_bar['D2']*beta['D2']:>12.4f}")
print(f"{'WTP_true (period P_bar, EUR/h)':30s} {p_bar['D1']*beta['D1']/(1-f['D1']):>12.4f} {p_bar['D2']*beta['D2']/(1-f['D2']):>12.4f}")
print(f"{'WTP_obs (2023/24 P_bar, EUR/h)':30s} {p_current['D1']*beta['D1']:>12.4f} {p_current['D2']*beta['D2']:>12.4f}")
print(f"{'WTP_true (2023/24 P_bar, EUR/h)':30s} {p_current['D1']*beta['D1']/(1-f['D1']):>12.4f} {p_current['D2']*beta['D2']/(1-f['D2']):>12.4f}")
