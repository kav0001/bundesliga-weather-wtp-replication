# Fill-rate subgroup heterogeneity model family.
#
# Re-estimates the M3 preferred specification (temp_mean + precip_mm +
# sunshine_h + is_weekend | Stadium + Season + month) separately on
# high/mid/low stadium fill-rate subgroups, for BL1 and BL2 separately. This
# is the core evidence for the season-ticket attenuation mechanism: the
# sunshine coefficient should be largest where the fewest seats are already
# claimed by season-ticket holders.
#
# Reads:  data/processed/bundesliga_with_weather.csv
# Writes: tables/fillrate_subgroup_results.csv

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

# -- Fill-rate subgroups --
HIGH <- 0.85
LOW  <- 0.70

bdf$fr_group <- ifelse(bdf$fill_rate >= HIGH, "high",
                ifelse(bdf$fill_rate <  LOW,  "low", "mid"))

cat("=== Fill_rate group sizes ===\n")
print(table(bdf$Div, bdf$fr_group))
cat("\n")

# M3 spec: log_att ~ temp_mean + precip_mm + sunshine_h + is_weekend | Stadium + Season + month
run_m3 <- function(data, label) {
  if (sum(!is.na(data$sunshine_h)) < 50) {
    cat(sprintf("%-40s  SKIPPED (n too small)\n", label))
    return(NULL)
  }
  m <- feols(log_att ~ temp_mean + precip_mm + sunshine_h + is_weekend |
               Stadium + Season + month,
             data = data, cluster = ~Stadium)
  ct <- summary(m)$coeftable
  if (!"sunshine_h" %in% rownames(ct)) return(NULL)
  r <- ct["sunshine_h", ]
  data.frame(label = label, n = nobs(m),
             coef = r[1], se = r[2], t = r[3], p = r[4])
}

results <- list()

d1 <- bdf[bdf$Div == "D1", ]
results[["BL1 all"]]  <- run_m3(d1,                           "BL1 - all matches")
results[["BL1 high"]] <- run_m3(d1[d1$fr_group == "high", ], "BL1 - high fill (>85%)")
results[["BL1 mid"]]  <- run_m3(d1[d1$fr_group == "mid",  ], "BL1 - mid fill (70-85%)")
results[["BL1 low"]]  <- run_m3(d1[d1$fr_group == "low",  ], "BL1 - low fill (<70%)")

d2 <- bdf[bdf$Div == "D2", ]
results[["BL2 all"]]  <- run_m3(d2,                           "BL2 - all matches")
results[["BL2 high"]] <- run_m3(d2[d2$fr_group == "high", ], "BL2 - high fill (>85%)")
results[["BL2 mid"]]  <- run_m3(d2[d2$fr_group == "mid",  ], "BL2 - mid fill (70-85%)")
results[["BL2 low"]]  <- run_m3(d2[d2$fr_group == "low",  ], "BL2 - low fill (<70%)")

tab <- do.call(rbind, Filter(Negate(is.null), results))
rownames(tab) <- NULL

cat("=== Fill_rate subgroup regression (M3 spec, sunshine_h coef) ===\n\n")
tab$stars <- ifelse(tab$p < 0.01, "***",
             ifelse(tab$p < 0.05, "**",
             ifelse(tab$p < 0.10, "*", "")))
tab$ci_lo <- tab$coef - 1.96 * tab$se
tab$ci_hi <- tab$coef + 1.96 * tab$se

for (i in seq_len(nrow(tab))) {
  r <- tab[i, ]
  cat(sprintf("%-40s  n=%5d  beta=%.5f (SE=%.5f) %s  [%.5f, %.5f]  p=%.4f\n",
              r$label, r$n, r$coef, r$se, r$stars, r$ci_lo, r$ci_hi, r$p))
}

# WTP per subgroup, for reference only (the thesis's actual reported WTP
# figure is computed in wtp_calculation.py from the M3 all-matches coefficient,
# not from these subgroups - see that script and the Results chapter for why).
cat("\n=== WTP per sunshine hour, for reference (Pbar: BL1=EUR21.16, BL2=EUR14.48; f: BL1=0.57, BL2=0.46) ===\n\n")

p_bar <- list(D1 = 21.16, D2 = 14.48)
f_share <- list(D1 = 0.57, D2 = 0.46)

for (i in seq_len(nrow(tab))) {
  r <- tab[i, ]
  div <- ifelse(grepl("BL1", r$label), "D1", "D2")
  p   <- p_bar[[div]]
  fi  <- f_share[[div]]
  wtp_obs  <- p * r$coef
  wtp_true <- wtp_obs / (1 - fi)
  cat(sprintf("%-40s  WTP_obs=EUR%.4f  WTP_true=EUR%.4f%s\n",
              r$label, wtp_obs, wtp_true,
              ifelse(is.na(r$p) || r$p >= 0.10, "  (n.s.)", "")))
}

write.csv(tab, file.path(TAB, "fillrate_subgroup_results.csv"), row.names = FALSE)
cat("\nSaved:", file.path(TAB, "fillrate_subgroup_results.csv"), "\n")
