# Kuruc-et-al.-exact interacted fixed-effects robustness check.
#
# The thesis's preferred specification (M3 = temp_mean + precip_mm +
# sunshine_h + is_weekend) uses ADDITIVE Stadium + Season + month fixed
# effects; Kuruc, LoPalo & O'Connor (2025) - the base paper this thesis
# extends - use INTERACTED Stadium x month + Season x month FE. This script
# re-estimates M3 under that interacted FE structure and compares it,
# row by row, against the additive M3 numbers already in
# tables/robustness_results.csv: both to sanity-check this script (the
# additive run here should reproduce those numbers exactly) and to answer
# the actual question (does the FE choice change the conclusion? it does
# not - BL2 stays positive and gets slightly more significant, BL1 stays
# null).
#
# Kept as its own script rather than folded into regression_robustness.R so
# the two robustness passes stay independently checkable. The data-loading
# block below is intentionally identical to regression_robustness.R, to
# guarantee the same sample.
#
# Reads:  data/processed/bundesliga_with_weather.csv
# Writes: tables/robustness_kurucfe_results.csv

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

# -- Load & clean (identical to regression_robustness.R, for a matching sample) --
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
bdf <- bdf[!(bdf$Season == "2021/22" & !is.na(bdf$fill_rate) & bdf$fill_rate < 0.5), ]

bdf$log_att    <- log(bdf$Attendance)
bdf$month      <- as.integer(format(bdf$Date, "%m"))
bdf$dow        <- as.integer(format(bdf$Date, "%u"))
bdf$is_weekend <- as.integer(bdf$dow >= 6)
bdf$Div        <- factor(bdf$Div, levels = c("D1", "D2"))

d1 <- bdf[bdf$Div == "D1", ]
d2 <- bdf[bdf$Div == "D2", ]

extract <- function(m, var, label) {
  ct <- summary(m)$coeftable
  if (!(var %in% rownames(ct))) return(NULL)
  r <- ct[var, ]
  data.frame(label = label, n = nobs(m), var = var,
             coef = unname(r[1]), se = unname(r[2]),
             t = unname(r[3]), p = unname(r[4]))
}

results <- list()

for (nm in c("D1", "D2")) {
  d <- if (nm == "D1") d1 else d2
  lab <- if (nm == "D1") "BL1" else "BL2"

  # Sanity check: re-estimate the additive M3 spec here and confirm it
  # reproduces tables/robustness_results.csv before trusting the new
  # interacted-FE number below.
  m3_additive <- feols(log_att ~ temp_mean + precip_mm + sunshine_h + is_weekend
                        | Stadium + Season + month,
                        data = d, cluster = ~Stadium)
  results[[paste0(nm, "_additive_check")]] <-
    extract(m3_additive, "sunshine_h", paste0(lab, " M3 additive (sanity check vs. committed)"))

  # Kuruc-exact interacted FE: Stadium x month, Season x month.
  m3_kuruc <- feols(log_att ~ temp_mean + precip_mm + sunshine_h + is_weekend
                     | Stadium^month + Season^month,
                     data = d, cluster = ~Stadium)
  results[[paste0(nm, "_kuruc")]] <-
    extract(m3_kuruc, "sunshine_h", paste0(lab, " M3 Kuruc-exact FE (Stadium^month + Season^month)"))
}

out <- bind_rows(results)
write.csv(out, file.path(TAB, "robustness_kurucfe_results.csv"), row.names = FALSE)
cat("Wrote robustness_kurucfe_results.csv\n")
print(out)
