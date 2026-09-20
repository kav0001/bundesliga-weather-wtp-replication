# Robustness-check model family: M_D1-M_D3 (weekday/weekend), M8/M9
# (temperature bins, two reference categories), M_B1/M_B2 (sunshine-only,
# with/without temp_mean), and clustered-vs-robust SE for the preferred
# spec M3. All four checks are DIFFERENT from the M1-M5 headline family in
# regression_bl1_bl2.R and from the Kuruc-et-al.-exact interacted-FE check
# in regression_robustness_kurucfe.R - do not confuse the three.
#
# Reads:  data/processed/bundesliga_with_weather.csv
# Writes: tables/robustness_results.csv

rm(list = ls())

library(tidyverse)
library(fixest)

get_script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) == 1) return(dirname(normalizePath(sub("^--file=", "", file_arg))))
  return(getwd())  # fallback for interactive/sourced use
}
REPO_ROOT <- normalizePath(file.path(get_script_dir(), "..", ".."))
TAB <- file.path(REPO_ROOT, "tables")
dir.create(TAB, showWarnings = FALSE)

# -- Load & clean (same sample construction as regression_bl1_bl2.R) --
bdf <- read.csv(file.path(REPO_ROOT, "data", "processed", "bundesliga_with_weather.csv"), stringsAsFactors = FALSE)
bdf <- bdf[bdf$Div %in% c("D1", "D2"), ]
bdf$Date       <- as.Date(bdf$Date)
bdf$Attendance <- as.numeric(bdf$Attendance)
bdf$temp_mean  <- as.numeric(bdf$temp_mean)
bdf$precip_mm  <- as.numeric(bdf$precip_mm)
bdf$sunshine_h <- as.numeric(bdf$sunshine_h)
bdf$fill_rate  <- as.numeric(bdf$fill_rate)

bdf <- bdf[!is.na(bdf$Attendance) & bdf$Attendance > 0, ]
bdf <- bdf[format(bdf$Date, "%Y") >= "2000", ]
bdf <- bdf[bdf$Season != "2020/21", ]
# Drop 2021/22 matches played under COVID capacity caps (fill_rate < 0.5) -
# see regression_bl1_bl2.R for the justification.
bdf <- bdf[!(bdf$Season == "2021/22" & !is.na(bdf$fill_rate) & bdf$fill_rate < 0.5), ]

bdf$log_att    <- log(bdf$Attendance)
bdf$month      <- as.integer(format(bdf$Date, "%m"))
bdf$dow        <- as.integer(format(bdf$Date, "%u"))
bdf$is_weekend <- as.integer(bdf$dow >= 6)
bdf$Div        <- factor(bdf$Div, levels = c("D1", "D2"))

d1 <- bdf[bdf$Div == "D1", ]
d2 <- bdf[bdf$Div == "D2", ]

results <- list()

extract <- function(m, var, label) {
  ct <- summary(m)$coeftable
  if (!(var %in% rownames(ct))) return(NULL)
  r <- ct[var, ]
  data.frame(label = label, n = nobs(m), var = var,
             coef = unname(r[1]), se = unname(r[2]),
             t = unname(r[3]), p = unname(r[4]))
}

# -- Check: weekday vs weekend sub-samples (M_D1-M_D3) --
cat("=== Weekday vs weekend sub-samples ===\n")

for (nm in c("D1", "D2")) {
  d <- if (nm == "D1") d1 else d2
  lab <- if (nm == "D1") "BL1" else "BL2"

  m_int <- feols(log_att ~ sunshine_h * is_weekend + precip_mm | Stadium + Season + month,
                 data = d, cluster = ~Stadium)
  results[[paste0(nm, "_interact")]] <- extract(m_int, "sunshine_h", paste0(lab, " M_D1: sunshine_h (weekend interaction model)"))
  results[[paste0(nm, "_interact_x")]] <- extract(m_int, "sunshine_h:is_weekend", paste0(lab, " M_D1: sunshine_h x is_weekend"))

  d_wd <- d[d$is_weekend == 0, ]
  if (nrow(d_wd) > 100) {
    m_wd <- feols(log_att ~ sunshine_h + precip_mm | Stadium + Season + month,
                   data = d_wd, cluster = ~Stadium)
    results[[paste0(nm, "_weekday")]] <- extract(m_wd, "sunshine_h", paste0(lab, " M_D2: sunshine_h (weekday only)"))
  }

  d_we <- d[d$is_weekend == 1, ]
  m_we <- feols(log_att ~ sunshine_h + precip_mm | Stadium + Season + month,
                 data = d_we, cluster = ~Stadium)
  results[[paste0(nm, "_weekend")]] <- extract(m_we, "sunshine_h", paste0(lab, " M_D3: sunshine_h (weekend only)"))
}

# -- Check: temperature bins with FE, two reference categories (M8, M9) --
cat("=== Temperature bins (with FE) ===\n")

make_bins <- function(t) {
  cut(t, breaks = c(-Inf, 0, 5, 10, 15, 20, 25, Inf),
      labels = c("frost", "cold_0_5", "cool_5_10", "ref_10_15",
                 "mild_15_20", "warm_20_25", "hot_25plus"))
}
bdf$temp_bin <- make_bins(bdf$temp_mean)

for (nm in c("D1", "D2")) {
  d <- bdf[bdf$Div == nm, ]
  lab <- if (nm == "D1") "BL1" else "BL2"

  # M8: reference bin = 10-15C
  d$temp_bin_ref1015 <- relevel(d$temp_bin, ref = "ref_10_15")
  m8 <- feols(log_att ~ temp_bin_ref1015 + precip_mm + sunshine_h | Stadium + Season + month,
              data = d, cluster = ~Stadium)
  ct8 <- summary(m8)$coeftable
  for (v in rownames(ct8)) {
    if (grepl("^temp_bin_ref1015", v)) {
      bin_name <- sub("temp_bin_ref1015", "", v)
      r <- ct8[v, ]
      results[[paste0(nm, "_M8_", bin_name)]] <- data.frame(
        label = paste0(lab, " M8 [ref 10-15]: ", bin_name), n = nobs(m8), var = v,
        coef = unname(r[1]), se = unname(r[2]), t = unname(r[3]), p = unname(r[4]))
    }
  }

  # M9: reference bin = frost (<0C)
  d$temp_bin_reffrost <- relevel(d$temp_bin, ref = "frost")
  m9 <- feols(log_att ~ temp_bin_reffrost + precip_mm + sunshine_h | Stadium + Season + month,
              data = d, cluster = ~Stadium)
  ct9 <- summary(m9)$coeftable
  for (v in rownames(ct9)) {
    if (grepl("^temp_bin_reffrost", v)) {
      bin_name <- sub("temp_bin_reffrost", "", v)
      r <- ct9[v, ]
      results[[paste0(nm, "_M9_", bin_name)]] <- data.frame(
        label = paste0(lab, " M9 [ref frost]: ", bin_name), n = nobs(m9), var = v,
        coef = unname(r[1]), se = unname(r[2]), t = unname(r[3]), p = unname(r[4]))
    }
  }
}

# -- Check: sunshine-and-precipitation-only spec, omitting temp_mean (M_B2) --
cat("=== Sunshine-only (no temp_mean) spec ===\n")

for (nm in c("D1", "D2")) {
  d <- bdf[bdf$Div == nm, ]
  lab <- if (nm == "D1") "BL1" else "BL2"

  m_full <- feols(log_att ~ temp_mean + precip_mm + sunshine_h | Stadium + Season + month,
                   data = d, cluster = ~Stadium)
  results[[paste0(nm, "_withtemp")]] <- extract(m_full, "sunshine_h", paste0(lab, " M_B1: sunshine_h (with temp_mean)"))

  m_notemp <- feols(log_att ~ precip_mm + sunshine_h | Stadium + Season + month,
                     data = d, cluster = ~Stadium)
  results[[paste0(nm, "_notemp")]] <- extract(m_notemp, "sunshine_h", paste0(lab, " M_B2: sunshine_h (no temp_mean)"))
}

# -- Check: clustered vs. heteroskedasticity-robust SE (preferred spec M3) --
cat("=== Clustered vs. robust SE ===\n")

for (nm in c("D1", "D2")) {
  d <- bdf[bdf$Div == nm, ]
  lab <- if (nm == "D1") "BL1" else "BL2"

  m3 <- feols(log_att ~ temp_mean + precip_mm + sunshine_h + is_weekend | Stadium + Season + month,
              data = d)

  ct_cl <- summary(m3, cluster = ~Stadium)$coeftable["sunshine_h", ]
  results[[paste0(nm, "_se_clustered")]] <- data.frame(
    label = paste0(lab, " M3: sunshine_h (clustered SE)"), n = nobs(m3), var = "sunshine_h",
    coef = unname(ct_cl[1]), se = unname(ct_cl[2]), t = unname(ct_cl[3]), p = unname(ct_cl[4]))

  ct_rb <- summary(m3, vcov = "hetero")$coeftable["sunshine_h", ]
  results[[paste0(nm, "_se_robust")]] <- data.frame(
    label = paste0(lab, " M3: sunshine_h (robust SE)"), n = nobs(m3), var = "sunshine_h",
    coef = unname(ct_rb[1]), se = unname(ct_rb[2]), t = unname(ct_rb[3]), p = unname(ct_rb[4]))
}

# -- Combine and save --
tab <- do.call(rbind, Filter(Negate(is.null), results))
rownames(tab) <- NULL
tab$stars <- ifelse(tab$p < 0.01, "***", ifelse(tab$p < 0.05, "**", ifelse(tab$p < 0.10, "*", "")))
tab$ci_lo <- tab$coef - 1.96 * tab$se
tab$ci_hi <- tab$coef + 1.96 * tab$se

cat("\n=== Combined robustness results ===\n\n")
for (i in seq_len(nrow(tab))) {
  r <- tab[i, ]
  cat(sprintf("%-55s n=%5d  coef=%9.5f (SE=%.5f) %-3s  p=%.4f\n",
              r$label, r$n, r$coef, r$se, r$stars, r$p))
}

write.csv(tab, file.path(TAB, "robustness_results.csv"), row.names = FALSE)
cat("\nSaved:", file.path(TAB, "robustness_results.csv"), "\n")
