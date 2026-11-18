# Pinned R packages (list: requirements-r.txt at the repo root).
#   Rscript run/rpkgs.R install <R-lib> <requirements-r.txt>   install missing/wrong ones into <R-lib>
#   Rscript run/rpkgs.R check   <R-lib> <requirements-r.txt>   print one line per package
# Each package comes from its CRAN source tarball (current folder, else the Archive folder) and is
# installed with install.packages(<file>, repos = NULL, type = "source"), in file order, so no
# dependency resolution is needed. Exit status 1 if any package is not at its pin afterwards.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3 || !(args[1] %in% c("install", "check"))) {
  cat("usage: Rscript rpkgs.R install|check <R-lib> <requirements-r.txt>\n"); quit(status = 2)
}
mode <- args[1]; lib <- args[2]; req <- args[3]
dir.create(lib, showWarnings = FALSE, recursive = TRUE)
lib <- normalizePath(lib)
.libPaths(c(lib, .libPaths()))
lines <- trimws(sub("#.*$", "", readLines(req)))
lines <- lines[nzchar(lines)]
pins <- do.call(rbind, lapply(strsplit(lines, "==", fixed = TRUE), function(p) data.frame(pkg = p[1], ver = p[2])))
cran <- "https://cran.r-project.org/src/contrib"
ver_in <- function(pkg, where) {
  d <- system.file("DESCRIPTION", package = pkg, lib.loc = where)
  if (!nzchar(d)) return(NA_character_)
  unname(read.dcf(d, fields = "Version")[1, 1])
}
seen <- function(pkg) {  # version R would load (R-lib first), and from where
  for (l in .libPaths()) { v <- ver_in(pkg, l); if (!is.na(v)) return(c(v, l)) }
  c(NA_character_, "")
}
bad <- 0
for (i in seq_len(nrow(pins))) {
  pkg <- pins$pkg[i]; ver <- pins$ver[i]
  if (mode == "install" && !identical(ver_in(pkg, lib), ver)) {
    tgz <- sprintf("%s_%s.tar.gz", pkg, ver)
    dest <- file.path(tempdir(), tgz)
    urls <- c(sprintf("%s/%s", cran, tgz), sprintf("%s/Archive/%s/%s", cran, pkg, tgz))
    got <- FALSE
    for (u in urls) {
      ok <- tryCatch(download.file(u, dest, mode = "wb", quiet = TRUE) == 0, error = function(e) FALSE, warning = function(w) FALSE)
      if (isTRUE(ok) && file.exists(dest) && file.size(dest) > 0) { cat(sprintf("downloaded %s\n", u)); got <- TRUE; break }
    }
    if (!got) { cat(sprintf("ERROR: could not download %s from CRAN (tried %s)\n", tgz, paste(urls, collapse = " , "))); bad <- bad + 1; next }
    cat(sprintf("installing %s %s into %s\n", pkg, ver, lib))
    install.packages(dest, lib = lib, repos = NULL, type = "source")
  }
  s <- seen(pkg)
  if (mode == "install") s <- c(ver_in(pkg, lib), lib)
  status <- if (is.na(s[1])) "MISSING" else if (identical(s[1], ver)) "ok" else "DIFFERS"
  if (status != "ok") bad <- bad + 1
  cat(sprintf("R package %-14s pinned %-7s found %-7s %-7s %s\n", pkg, ver, ifelse(is.na(s[1]), "-", s[1]), status, s[2]))
}
quit(status = if (bad > 0) 1 else 0)
