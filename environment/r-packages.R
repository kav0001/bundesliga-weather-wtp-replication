# R package dependencies for scripts/04_regressions/*.R and scripts/05_figures/*.R.
# Run once: Rscript environment/r-packages.R

pkgs <- c(
  "tidyverse",  # data wrangling + ggplot2
  "fixest",     # fixed-effects regressions (feols)
  "maps",       # base map polygons for the stadium map figure
  "scales"      # axis label formatting (percent_format, etc.)
)

installed <- rownames(installed.packages())
missing <- setdiff(pkgs, installed)
if (length(missing) > 0) {
  install.packages(missing, repos = "https://cloud.r-project.org")
}
