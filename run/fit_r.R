#!/usr/bin/env Rscript
# One R fit (or load-only baseline) per process; peak RSS comes from /usr/bin/time outside.
# The fit is timed inside R around the call only.
# Usage: Rscript fit_r.R INPUT_F64 METHOD K M [WEIGHTS_F64]
#   METHOD  R_load      library(Ckmeans.1d.dp) + readBin (baseline for the Ckmeans rows)
#           ckmeans     Ckmeans.1d.dp(x, k, method = "linear")         (y = weights if given)
#           rb_load     library(lex1d) + readBin (baseline for the binding rows)
#           rb_hybrid   lex1d::lex_hybrid(x, k, coarse_groups = M)     (lex1d R binding, frozen 8a691ee)
# Prints: RESULT key=value ...
args <- commandArgs(trailingOnly = TRUE)
if (!(length(args) %in% c(4, 5))) stop("usage: Rscript fit_r.R INPUT_F64 METHOD K M [WEIGHTS_F64]")
path <- args[[1]]; method <- args[[2]]; k <- as.integer(args[[3]]); M <- as.integer(args[[4]])
now <- function() as.numeric(Sys.time())
rd <- function(p) {
  nb <- file.info(p)$size
  v <- readBin(p, what = "double", n = nb / 8, size = 8, endian = "little")
  if (length(v) * 8 != nb) stop("short read of ", p)
  v
}
t0 <- now()
pkg <- if (method %in% c("R_load", "ckmeans")) "Ckmeans.1d.dp" else "lex1d"
if (!(method %in% c("R_load", "ckmeans", "rb_load", "rb_hybrid"))) stop("unknown method ", method)
suppressPackageStartupMessages(library(pkg, character.only = TRUE))
x <- rd(path)
w <- if (length(args) == 5) rd(args[[5]]) else NULL
if (!is.null(w) && length(w) != length(x)) stop("weights length differs")
t1 <- now()
ver <- as.character(packageVersion(pkg))
sz <- function(cl, kk) paste(tabulate(cl, nbins = kk), collapse = "|")
if (method %in% c("R_load", "rb_load")) {
  cat(sprintf("RESULT method=%s n=%d weighted=%d load_s=%.9f checksum=%.17g version=%s\n",
              method, length(x), as.integer(!is.null(w)), t1 - t0, sum(x), ver))
} else if (method == "ckmeans") {
  t2 <- now()
  res <- if (is.null(w)) Ckmeans.1d.dp(x, k = k, method = "linear") else Ckmeans.1d.dp(x, k = k, y = w, method = "linear")
  t3 <- now()
  kk <- length(res$size)
  cat(sprintf("RESULT method=ckmeans k=%d n=%d weighted=%d k_eff=%d sse=%.17g fit_s=%.9f load_s=%.9f version=%s sizes=%s\n",
              k, length(x), as.integer(!is.null(w)), kk, res$tot.withinss, t3 - t2, t1 - t0, ver, sz(res$cluster, kk)))
} else {
  t2 <- now()
  res <- lex_hybrid(x, k, coarse_groups = M)
  t3 <- now()
  kk <- as.integer(res$k_used)
  cat(sprintf("RESULT method=rb_hybrid k=%d M=%d n=%d weighted=0 atoms=%d k_eff=%d sse=%.17g fit_s=%.9f load_s=%.9f sweeps=%d moves=%d version=%s sizes=%s\n",
              k, M, length(x), as.integer(res$atoms), kk, res$sse, t3 - t2, t1 - t0,
              as.integer(res$sweeps), as.integer(res$moves), ver, paste(as.integer(res$count), collapse = "|")))
}
