# Headline model family: M1-M5.
#
# Runs the thesis's headline sequence of five specifications (adding
# controls one at a time) separately for BL1, BL2, the pooled sample, plus a
# BL1-vs-BL2 sunshine-sensitivity interaction test. This is the model family
# reported in the thesis's main Results table and in Appendix A (full
# precision). It is a DIFFERENT sequence from the exploratory build-up models
# (M_P1-M_P5, M6-M8, M_B1, M_final) documented only in the thesis text, and
# from the M_D1-M_D3 / M8-M9 robustness models in regression_robustness.R -
# do not confuse the three families.
#
# Reads:  data/processed/bundesliga_with_weather.csv
# Writes: tables/regression_results.csv

library(tidyverse)
library(fixest)

# Resolve paths relative to this script's own location, regardless of the
# working directory the script is launched from.
get_script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) == 1) return(dirname(normalizePath(sub("^--file=", "", file_arg))))
  return(getwd())  # fallback for interactive/sourced use
}
REPO_ROOT <- normalizePath(file.path(get_script_dir(), "..", ".."))
TAB <- file.path(REPO_ROOT, "tables")
dir.create(TAB, showWarnings = FALSE)

df <- read.csv(file.path(REPO_ROOT, "data", "processed", "bundesliga_with_weather.csv"), stringsAsFactors = FALSE)
df <- df[df$Div %in% c("D1", "D2"), ]
df$Date       <- as.Date(df$Date)
df$Attendance <- as.numeric(df$Attendance)
df$temp_mean  <- as.numeric(df$temp_mean)
df$temp_max   <- as.numeric(df$temp_max)
df$temp_min   <- as.numeric(df$temp_min)
df$precip_mm  <- as.numeric(df$precip_mm)
df$sunshine_h <- as.numeric(df$sunshine_h)
df$fill_rate  <- as.numeric(df$fill_rate)

df <- df[!is.na(df$Attendance) & df$Attendance > 0, ]
df <- df[format(df$Date, "%Y") >= "2000", ]
df <- df[df$Season != "2020/21", ]

# 2021/22 was not a fully "normal" season either: German federal and
# state-level COVID capacity limits (e.g. Berlin: 5,000-spectator cap from
# 8 Dec 2021; Baden-Wuerttemberg: 750-cap from 4 Dec 2021) suppressed
# attendance independent of weather from roughly Dec 2021 to Feb 2022.
# Rather than drop the whole season (as for 2020/21), only the specific
# matches played under an artificially low capacity cap are dropped
# (fill_rate < 0.5) - confirmed via leave-one-season-out and placebo checks
# to be driving a spurious BL1 "frost" bin coefficient and inflating the
# headline sunshine coefficient.
df <- df[!(df$Season == "2021/22" & !is.na(df$fill_rate) & df$fill_rate < 0.5), ]

df$log_att    <- log(df$Attendance)
df$month      <- as.integer(format(df$Date, "%m"))
df$dow        <- as.integer(format(df$Date, "%u"))
df$is_weekend <- as.integer(df$dow >= 6)
df$frost      <- as.integer(df$temp_min < 0)
df$hot        <- as.integer(df$temp_max > 28)
df$rain_light <- as.integer(df$precip_mm > 2 & df$precip_mm <= 10)
df$rain_heavy <- as.integer(df$precip_mm > 10)
df$cold_rain  <- as.integer(df$temp_mean < 5 & df$precip_mm > 2)
df$Div        <- factor(df$Div, levels = c("D1", "D2"))

d1   <- df[df$Div == "D1", ]
d2   <- df[df$Div == "D2", ]
pool <- df

extract <- function(m, var, label) {
  ct <- summary(m)$coeftable
  if (!(var %in% rownames(ct))) return(NULL)
  r <- ct[var, ]
  data.frame(label = label, n = nobs(m), coef = unname(r[1]), se = unname(r[2]),
             t = unname(r[3]), p = unname(r[4]))
}

results <- list()

run_5 <- function(d, lab) {
  m1 <- feols(log_att ~ temp_mean + precip_mm | Stadium + Season + month, data = d, cluster = ~Stadium)
  m2 <- feols(log_att ~ temp_mean + precip_mm + sunshine_h | Stadium + Season + month, data = d, cluster = ~Stadium)
  m3 <- feols(log_att ~ temp_mean + precip_mm + sunshine_h + is_weekend | Stadium + Season + month, data = d, cluster = ~Stadium)
  m4 <- feols(log_att ~ frost + hot + rain_light + rain_heavy + sunshine_h | Stadium + Season + month, data = d, cluster = ~Stadium)
  m5 <- feols(log_att ~ temp_mean + precip_mm + sunshine_h + cold_rain | Stadium + Season + month, data = d, cluster = ~Stadium)
  list(
    extract(m1, "temp_mean",  paste0(lab, " M1: temp_mean")),
    extract(m2, "sunshine_h", paste0(lab, " M2: sunshine_h")),
    extract(m3, "sunshine_h", paste0(lab, " M3: sunshine_h")),
    extract(m4, "sunshine_h", paste0(lab, " M4: sunshine_h")),
    extract(m5, "sunshine_h", paste0(lab, " M5: sunshine_h"))
  )
}

results <- c(results, run_5(d1, "BL1"))
results <- c(results, run_5(d2, "BL2"))

# Pooled: M1-M4 only (the thesis does not report a pooled M5 column - the
# division-specific cold-rain interaction is not meaningful pooled).
pm1 <- feols(log_att ~ temp_mean + precip_mm | Stadium + Season + month + Div, data = pool, cluster = ~Stadium)
pm2 <- feols(log_att ~ temp_mean + precip_mm + sunshine_h | Stadium + Season + month + Div, data = pool, cluster = ~Stadium)
pm3 <- feols(log_att ~ temp_mean + precip_mm + sunshine_h + is_weekend | Stadium + Season + month + Div, data = pool, cluster = ~Stadium)
pm4 <- feols(log_att ~ frost + hot + rain_light + rain_heavy + sunshine_h | Stadium + Season + month + Div, data = pool, cluster = ~Stadium)
results <- c(results, list(
  extract(pm1, "temp_mean",  "Pool M1: temp_mean"),
  extract(pm2, "sunshine_h", "Pool M2: sunshine_h"),
  extract(pm3, "sunshine_h", "Pool M3: sunshine_h"),
  extract(pm4, "sunshine_h", "Pool M4: sunshine_h")
))

# Interaction: sunshine_h x Div, BL1 as base. This is the direct statistical
# test of the thesis's headline claim (BL1 vs. BL2 sunshine sensitivity
# differs significantly).
pool$D2 <- as.integer(pool$Div == "D2")
m_int <- feols(log_att ~ sunshine_h * D2 + temp_mean + precip_mm | Stadium + Season + month, data = pool, cluster = ~Stadium)
results <- c(results, list(
  extract(m_int, "sunshine_h",    "Interact: sunshine_h (BL1 base)"),
  extract(m_int, "sunshine_h:D2", "Interact: sunshine_h x D2")
))

out <- bind_rows(results)
write.csv(out, file.path(TAB, "regression_results.csv"), row.names = FALSE)
cat("Wrote regression_results.csv\n")
print(out)
