# All 10 figures used in the thesis, in one script.
#
# Reads:  data/processed/bundesliga_with_weather.csv
#         data/own_collected/ticket_prices.csv
#         tables/robustness_results.csv, fillrate_subgroup_results.csv, wtp_results.csv
#         (the three tables/*.csv above are produced by scripts/analysis/ - run
#         those first if you want up-to-date figures 8, 10, 11)
# Writes: figures/fig1_attendance_dist.png  ... fig11_wtp_comparison.png
#         (fig9 does not exist - dropped during thesis writing, see thesis text)

library(tidyverse)
library(ggplot2)

get_script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) == 1) return(dirname(normalizePath(sub("^--file=", "", file_arg))))
  return(getwd())  # fallback for interactive/sourced use
}
REPO_ROOT <- normalizePath(file.path(get_script_dir(), ".."))
FIG_DIR <- file.path(REPO_ROOT, "figures")
dir.create(FIG_DIR, showWarnings = FALSE)

# -- Shared visual identity: one font, one theme, one BL1/BL2 color pair --
plot_font <- "Helvetica"
division_colors <- c("Bundesliga 1" = "#2A5C9A", "Bundesliga 2" = "#CC3300")
division_colors_short <- c("BL1" = "#2A5C9A", "BL2" = "#CC3300")

theme_thesis <- theme_minimal(base_size = 11, base_family = plot_font) +
  theme(
    panel.grid.minor = element_blank(),
    strip.text = element_text(face = "bold", family = plot_font),
    legend.position = "bottom",
    legend.text = element_text(family = plot_font),
    axis.title = element_text(family = plot_font),
    axis.text = element_text(family = plot_font),
    plot.title = element_text(face = "bold", size = 12, family = plot_font),
    plot.subtitle = element_text(size = 10, color = "grey40", family = plot_font)
  )

# ============================================================
# Figures 1-5: regression-sample distributions (Data chapter)
# ============================================================

df <- read_csv(file.path(REPO_ROOT, "data", "processed", "bundesliga_with_weather.csv"), show_col_types = FALSE)

df_reg <- df %>%
  filter(
    Div %in% c("D1", "D2"),
    as.numeric(substr(Season, 1, 4)) >= 2000,
    Season != "2020/21",
    !(Season == "2021/22" & !is.na(fill_rate) & fill_rate < 0.5),
    !is.na(Attendance), Attendance > 0,
    !is.na(temp_mean),
    !is.na(sunshine_h)
  ) %>%
  mutate(
    Division = ifelse(Div == "D1", "Bundesliga 1", "Bundesliga 2"),
    log_att = log(Attendance)
  )

# Fig 1: attendance distribution
p1 <- ggplot(df_reg, aes(x = Attendance / 1000, fill = Division)) +
  geom_histogram(binwidth = 2.5, alpha = 0.9, color = "white", linewidth = 0.2) +
  facet_wrap(~Division, scales = "free_y", ncol = 1) +
  scale_fill_manual(values = division_colors) +
  labs(title = "Match Attendance Distribution",
       subtitle = "Regression sample, 2000/01-2023/24 (excl. 2020/21)",
       x = "Attendance (thousands)", y = "Number of matches") +
  theme_thesis + theme(legend.position = "none")
ggsave(file.path(FIG_DIR, "fig1_attendance_dist.png"), p1, width = 7, height = 5, dpi = 150)

# Fig 2: fill-rate distribution
p2 <- ggplot(df_reg %>% filter(!is.na(fill_rate)), aes(x = fill_rate, fill = Division)) +
  geom_histogram(binwidth = 0.04, alpha = 0.9, color = "white", linewidth = 0.2) +
  facet_wrap(~Division, scales = "free_y", ncol = 1) +
  scale_fill_manual(values = division_colors) +
  scale_x_continuous(labels = scales::percent_format()) +
  geom_vline(data = df_reg %>% group_by(Division) %>% summarise(med = median(fill_rate, na.rm = TRUE)),
             aes(xintercept = med), linetype = "dashed", linewidth = 0.8, color = "black") +
  labs(title = "Stadium Fill Rate Distribution",
       subtitle = "Dashed line = median. BL1 median: 91.7%, BL2 median: 57.1%",
       x = "Fill rate (Attendance / Capacity)", y = "Number of matches") +
  theme_thesis + theme(legend.position = "none")
ggsave(file.path(FIG_DIR, "fig2_fillrate_dist.png"), p2, width = 7, height = 5, dpi = 150)

# Fig 3: sunshine-hours distribution
p3 <- ggplot(df_reg, aes(x = sunshine_h, fill = Division)) +
  geom_histogram(binwidth = 0.75, alpha = 0.9, color = "white", linewidth = 0.2) +
  facet_wrap(~Division, scales = "free_y", ncol = 1) +
  scale_fill_manual(values = division_colors) +
  labs(title = "Match-Day Sunshine Hours Distribution",
       subtitle = "Daily sunshine duration on match day (hours)",
       x = "Sunshine hours", y = "Number of matches") +
  theme_thesis + theme(legend.position = "none")
ggsave(file.path(FIG_DIR, "fig3_sunshine_dist.png"), p3, width = 7, height = 5, dpi = 150)

# Fig 4: observations per season
obs_by_season <- df_reg %>%
  group_by(Division, Season) %>%
  summarise(n = n(), .groups = "drop") %>%
  mutate(year_start = as.numeric(substr(Season, 1, 4)))
p4 <- ggplot(obs_by_season, aes(x = year_start, y = n, fill = Division)) +
  geom_col(alpha = 0.95, width = 0.7) +
  facet_wrap(~Division, ncol = 1) +
  scale_fill_manual(values = division_colors) +
  labs(title = "Observations per Season",
       subtitle = "Regression sample (with sunshine hours). Gap = 2020/21 excluded",
       x = "Season start year", y = "Observations") +
  theme_thesis + theme(legend.position = "none")
ggsave(file.path(FIG_DIR, "fig4_obs_by_season.png"), p4, width = 8, height = 5, dpi = 150)

# Fig 5: temperature vs. sunshine scatter
p5 <- ggplot(df_reg %>% sample_n(3000), aes(x = temp_mean, y = sunshine_h, color = Division)) +
  geom_point(alpha = 0.25, size = 0.8) +
  geom_smooth(method = "loess", se = FALSE, linewidth = 1.2) +
  scale_color_manual(values = division_colors) +
  labs(title = "Match-Day Temperature vs. Sunshine Hours",
       subtitle = "Random sample of 3,000 observations. r = 0.39",
       x = "Daily mean temperature (C)", y = "Sunshine hours", color = NULL) +
  theme_thesis
ggsave(file.path(FIG_DIR, "fig5_temp_sunshine.png"), p5, width = 7, height = 4, dpi = 150)

# ============================================================
# Figure 6: stadium location map
# ============================================================

stadiums <- tribble(
  ~Stadium, ~lat, ~lon, ~city, ~div,
  # BL1
  "Allianz Arena", 48.219, 11.625, "München", "BL1",
  "SIGNAL IDUNA PARK", 51.493, 7.452, "Dortmund", "BL1",
  "Olympiastadion Berlin", 52.515, 13.240, "Berlin", "BL1",
  "Olympiastadion München", 48.174, 11.547, "München", "BL1",
  "RheinEnergieSTADION", 50.933, 6.875, "Köln", "BL1",
  "Volksparkstadion", 53.587, 9.900, "Hamburg", "BL1",
  "AOL Arena", 53.587, 9.900, "Hamburg", "BL1",
  "Volksparkstadion Hamburg", 53.587, 9.900, "Hamburg", "BL1",
  "BayArena", 51.038, 7.002, "Leverkusen", "BL1",
  "MHPArena Stuttgart", 48.792, 9.232, "Stuttgart", "BL1",
  "Commerzbank Arena", 50.069, 8.645, "Frankfurt", "BL1",
  "Deutsche Bank Park", 50.069, 8.645, "Frankfurt", "BL1",
  "Europa-Park Stadion", 48.022, 7.893, "Freiburg", "BL1",
  "Dreisamstadion", 48.006, 7.893, "Freiburg", "BL1",
  "Volkswagen Arena", 52.434, 10.804, "Wolfsburg", "BL1",
  "Veltins-Arena", 51.555, 7.068, "Gelsenkirchen", "BL1",
  "Arena AufSchalke", 51.555, 7.068, "Gelsenkirchen", "BL1",
  "Parkstadion", 51.555, 7.068, "Gelsenkirchen", "BL1",
  "MSV-Arena", 51.499, 6.765, "Duisburg", "BL1",
  "LEAG Energie Stadion", 51.762, 14.329, "Cottbus", "BL1",
  "Red Bull Arena", 51.346, 12.348, "Leipzig", "BL1",
  "Max-Morlock-Stadion", 49.428, 11.124, "Nürnberg", "BL1",
  "Mewa Arena", 49.984, 8.224, "Mainz", "BL1",
  "Heinz-von-Heiden-Arena", 52.460, 9.468, "Hannover", "BL1",
  "Fritz-Walter-Stadion", 49.481, 7.787, "Kaiserslautern", "BL1",
  "Weserstadion", 53.066, 8.838, "Bremen", "BL1",
  "Millerntor-Stadion", 53.554, 9.968, "Hamburg", "BL1",
  "PreZero Arena", 49.238, 8.889, "Sinsheim", "BL1",
  "Bökelberg", 51.171, 6.463, "Mönchengladbach", "BL1",
  "Borussia-Park", 51.175, 6.386, "Mönchengladbach", "BL1",
  "Audi Sportpark", 48.553, 10.890, "Ingolstadt", "BL1",
  "BBBank Wildpark", 49.008, 8.416, "Karlsruhe", "BL1",
  "Carl-Benz-Stadion", 49.470, 8.488, "Mannheim", "BL1",
  "Merck-Stadion am Böllenfalltor", 49.867, 8.642, "Darmstadt", "BL1",
  "Ostseestadion", 54.088, 12.146, "Rostock", "BL1",
  "ESPRIT arena", 51.264, 6.733, "Düsseldorf", "BL1",
  "Home Deluxe Arena", 51.560, 8.767, "Paderborn", "BL1",
  "EINTRACHT-Stadion", 52.267, 10.527, "Braunschweig", "BL1",
  # BL2 (representative sample of cities)
  "Rudolf-Harbig-Stadion", 51.051, 13.739, "Dresden", "BL2",
  "MDCC-Arena", 52.139, 11.619, "Magdeburg", "BL2",
  "Holstein-Stadion", 54.312, 10.131, "Kiel", "BL2",
  "Volksstadion", 54.088, 12.146, "Rostock", "BL2",
  "Städtisches Stadion", 50.559, 12.139, "Zwickau", "BL2",
  "Stadion Essen", 51.471, 7.002, "Essen", "BL2",
  "Ruhrstadion", 51.483, 7.222, "Bochum", "BL2",
  "SchücoArena", 52.022, 8.533, "Bielefeld", "BL2",
  "Stadion an der Lohmühle", 53.868, 10.710, "Lübeck", "BL2",
  "Carl-Zeiss-Jena Stadion", 50.927, 11.589, "Jena", "BL2",
  "Donaustadion", 48.393, 9.988, "Ulm", "BL2",
  "Sportpark Ronhof", 49.472, 10.963, "Fürth", "BL2",
  "Grünwalder Stadion", 48.100, 11.548, "München", "BL2",
  "Wohninvest WESERSTADION", 53.066, 8.838, "Bremen", "BL2",
  "Städtisches Stadion Duisburg", 51.478, 6.763, "Duisburg", "BL2"
)

if (!requireNamespace("maps", quietly = TRUE)) install.packages("maps", repos = "https://cloud.r-project.org")
library(maps)
germany <- map_data("world", region = "Germany")

p6 <- ggplot() +
  geom_polygon(data = germany, aes(x = long, y = lat, group = group),
               fill = "grey90", color = "grey60", linewidth = 0.3) +
  geom_point(data = stadiums, aes(x = lon, y = lat, color = div, shape = div), size = 2.5, alpha = 0.85) +
  scale_color_manual(values = division_colors_short,
                      labels = c("BL1" = "Bundesliga 1", "BL2" = "Bundesliga 2"), name = NULL) +
  scale_shape_manual(values = c("BL1" = 16, "BL2" = 17),
                      labels = c("BL1" = "Bundesliga 1", "BL2" = "Bundesliga 2"), name = NULL) +
  coord_fixed(ratio = 1.5, xlim = c(5.5, 15.5), ylim = c(47, 55.5)) +
  labs(title = "Stadium Locations - Bundesliga 1 & 2",
       subtitle = "Venues matched to DWD weather stations (all BL1 venues; representative BL2 subset)") +
  theme_thesis +
  theme(axis.title = element_blank(), axis.text = element_blank(), axis.ticks = element_blank(),
        panel.grid = element_blank(), legend.position = c(0.15, 0.15))
ggsave(file.path(FIG_DIR, "fig6_stadium_map.png"), p6, width = 7, height = 7.5, dpi = 150)

# ============================================================
# Figure 7: ticket price series
# ============================================================

prices <- read_csv(file.path(REPO_ROOT, "data", "own_collected", "ticket_prices.csv"), show_col_types = FALSE)

df_long <- prices %>%
  select(season, bl1_price, bl2_price, bl1_price_type, bl2_price_type) %>%
  pivot_longer(cols = c(bl1_price, bl2_price), names_to = "division", values_to = "price") %>%
  mutate(
    type = ifelse(division == "bl1_price", bl1_price_type, bl2_price_type),
    Division = ifelse(division == "bl1_price", "Bundesliga 1", "Bundesliga 2"),
    year_start = as.numeric(substr(season, 1, 4))
  ) %>%
  filter(!is.na(price)) %>%
  select(year_start, season, Division, price, type)

p7 <- ggplot(df_long, aes(x = year_start, y = price, color = Division, group = Division)) +
  geom_line(linewidth = 0.6, alpha = 0.6) +
  geom_point(aes(shape = type), size = 2.2) +
  scale_color_manual(values = division_colors) +
  scale_shape_manual(values = c("observed" = 16, "interpolated" = 1, "extrapolated" = 2),
                      labels = c("observed" = "Observed (DFL report)", "interpolated" = "Interpolated (gap fill)",
                                 "extrapolated" = "Extrapolated (pre-2004)")) +
  scale_x_continuous(breaks = seq(2000, 2024, 4)) +
  labs(title = "Average Ticket Price Series, BL1 vs. BL2",
       subtitle = "Open circles mark the 2011/12-2018/19 linear-interpolation gap between observed endpoints",
       x = "Season (start year)", y = "Average ticket price (EUR)", color = NULL, shape = NULL) +
  theme_thesis
ggsave(file.path(FIG_DIR, "fig7_ticket_prices.png"), p7, width = 7.5, height = 4.5, dpi = 150)

# ============================================================
# Figure 8: temperature bin coefficients (needs scripts/analysis/regression_robustness.R output)
# ============================================================

robustness_path <- file.path(REPO_ROOT, "tables", "robustness_results.csv")
if (file.exists(robustness_path)) {
  tab <- read.csv(robustness_path, stringsAsFactors = FALSE)

  bin_order <- c("frost", "cold_0_5", "cool_5_10", "ref_10_15", "mild_15_20", "warm_20_25", "hot_25plus")
  bin_labels <- c("<0", "0-5", "5-10", "10-15\n(ref.)", "15-20", "20-25", ">25")

  bins <- tab %>%
    filter(grepl("^BL[12] M8", label)) %>%
    mutate(
      division = ifelse(grepl("^BL1", label), "BL1", "BL2"),
      bin = str_extract(var, paste(bin_order, collapse = "|")),
      bin = factor(bin, levels = bin_order, labels = bin_labels)
    ) %>%
    bind_rows(
      data.frame(label = "ref", n = NA, var = NA, coef = 0, se = 0, t = NA, p = NA,
                 stars = "", ci_lo = 0, ci_hi = 0, division = "BL1", bin = factor("10-15\n(ref.)", levels = bin_labels)),
      data.frame(label = "ref", n = NA, var = NA, coef = 0, se = 0, t = NA, p = NA,
                 stars = "", ci_lo = 0, ci_hi = 0, division = "BL2", bin = factor("10-15\n(ref.)", levels = bin_labels))
    )

  p8 <- ggplot(bins, aes(x = bin, y = coef, color = division, group = division)) +
    geom_hline(yintercept = 0, linetype = "dashed", color = "grey50") +
    geom_pointrange(aes(ymin = ci_lo, ymax = ci_hi), position = position_dodge(width = 0.4), size = 0.5) +
    scale_color_manual(values = division_colors_short, name = NULL) +
    labs(title = "Temperature Bin Coefficients on log(Attendance)",
         subtitle = "Reference: 10-15C | FE: Stadium + Season + Month | 95% CI, clustered by stadium",
         x = "Match-day temperature bin (C)", y = "Coefficient (relative to 10-15C reference)") +
    theme_thesis
  ggsave(file.path(FIG_DIR, "fig8_tempbins_coef.png"), p8, width = 8, height = 5, dpi = 300)
} else {
  cat("Skipping fig8: run scripts/analysis/regression_robustness.R first to produce tables/robustness_results.csv\n")
}

# ============================================================
# Figure 10: sunshine coefficient by fill-rate subgroup (needs regression_fillrate.R output)
# ============================================================

fillrate_path <- file.path(REPO_ROOT, "tables", "fillrate_subgroup_results.csv")
if (file.exists(fillrate_path)) {
  tab <- read.csv(fillrate_path, stringsAsFactors = FALSE)
  subgroup_labels <- c("High fill\n(>85%)", "Mid fill\n(70-85%)", "Low fill\n(<70%)")

  dat <- tab %>%
    filter(grepl("high fill|mid fill|low fill", label)) %>%
    mutate(
      division = ifelse(grepl("^BL1", label), "BL1", "BL2"),
      subgroup = case_when(
        grepl("high fill", label) ~ "High fill\n(>85%)",
        grepl("mid fill",  label) ~ "Mid fill\n(70-85%)",
        grepl("low fill",  label) ~ "Low fill\n(<70%)"
      ),
      subgroup = factor(subgroup, levels = subgroup_labels)
    )

  p10 <- ggplot(dat, aes(x = subgroup, y = coef, fill = division)) +
    geom_hline(yintercept = 0, linetype = "dashed", color = "grey50") +
    geom_col(position = position_dodge(width = 0.6), width = 0.5) +
    geom_errorbar(aes(ymin = ci_lo, ymax = ci_hi), position = position_dodge(width = 0.6), width = 0.15) +
    scale_fill_manual(values = division_colors_short, name = NULL) +
    labs(title = "Sunshine Coefficient by Stadium Fill-Rate Subgroup",
         subtitle = "FE: Stadium + Season + Month | 95% CI, clustered by stadium",
         x = "Fill-rate subgroup", y = "Coefficient on sunshine_h") +
    theme_thesis
  ggsave(file.path(FIG_DIR, "fig10_fillrate_coef.png"), p10, width = 7, height = 5, dpi = 300)
} else {
  cat("Skipping fig10: run scripts/analysis/regression_fillrate.R first to produce tables/fillrate_subgroup_results.csv\n")
}

# ============================================================
# Figure 11: WTP comparison (needs wtp_calculation.py output)
# ============================================================

wtp_path <- file.path(REPO_ROOT, "tables", "wtp_results.csv")
if (file.exists(wtp_path)) {
  dat <- read.csv(wtp_path, stringsAsFactors = FALSE) %>%
    mutate(measure = factor(measure, levels = c("WTP_observed", "WTP_true"),
                             labels = c("Observed\n(full crowd)", "True\n(attenuation-corrected)")))

  p11 <- ggplot(dat, aes(x = measure, y = wtp, fill = division)) +
    geom_col(position = position_dodge(width = 0.6), width = 0.5) +
    geom_errorbar(aes(ymin = ci_lo, ymax = ci_hi), position = position_dodge(width = 0.6), width = 0.15) +
    scale_fill_manual(values = division_colors_short, name = NULL) +
    labs(title = "Willingness to Pay per Sunshine Hour",
         subtitle = "Period-average ticket price | 95% CI from sunshine_h coefficient SE",
         x = NULL, y = "WTP (EUR per sunshine hour)") +
    theme_thesis
  ggsave(file.path(FIG_DIR, "fig11_wtp_comparison.png"), p11, width = 7, height = 5, dpi = 300)
} else {
  cat("Skipping fig11: run scripts/analysis/wtp_calculation.py first to produce tables/wtp_results.csv\n")
}

cat("\nAll available figures saved to", FIG_DIR, "\n")
cat("(no fig9 - dropped during thesis writing, see thesis text)\n")
