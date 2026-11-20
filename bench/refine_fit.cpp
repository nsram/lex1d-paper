// Refine-ablation driver for GOLD run 4: one lex_hybrid fit per process, so /usr/bin/time gives
// that fit's own peak RSS. Built against the frozen lex1d tree in ../lex1d/cpp (commit 8a691ee),
// which is not modified. An instrumented copy of lex::lex_hybrid (same internal pieces as bench/fit.cpp)
// records the coarse-DP SSE after Collapse(M)+DP(k) and before Refine, then the final SSE after
// the standard (right-to-left) Refine, and an exploratory left-to-right Refine started from the
// same coarse-DP bounds (bench/refine_ltr.cpp; frozen lex1d is not modified).
// Not library code.
//
// Usage: refine_fit INPUT_F64 hybrid K M verify|timed [WEIGHTS_F64]
//   The argv layout matches bench/fit.cpp's hybrid fits, so run/run.py can call this driver the same way.
//   INPUT_F64  little-endian float64 values (raw order or presorted; both the library and the
//              instrumented copy detect sorted input with one O(n) pass and skip the sort)
//   METHOD     hybrid (the only method this driver accepts)
//   K          clusters; M: coarse_groups
//   MODE       verify: one public-API call (timed as api_s, result kept), then one instrumented call;
//                      api_match = 1 if both give the same bounds, final SSE and start (warm-up round)
//              timed:  one instrumented call only (timed repeats)
//   Extra RESULT fields: coarse_sse, coarse_sizes (the partition after the coarse DP, before Refine).
//   When M >= atoms the coarse DP is the exact DP, so coarse_sse equals the exact SSE (gap 0).
// Prints one line: RESULT key=value ...
#include "lex/lex.hpp"
#include "detail.hpp"
#include "refine_ltr.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <vector>

using namespace lex::detail;
using clk = std::chrono::steady_clock;
using Bounds = std::vector<int>;

namespace {

double secs(clk::time_point a, clk::time_point b) { return std::chrono::duration<double>(b - a).count(); }

std::vector<double> load_f64(const std::string& path) {
    std::FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) throw std::runtime_error("cannot open " + path);
    std::fseek(f, 0, SEEK_END);
    const long bytes = std::ftell(f);
    std::fseek(f, 0, SEEK_SET);
    if (bytes < 0 || bytes % 8 != 0) throw std::runtime_error("bad float64 file " + path);
    std::vector<double> v(static_cast<std::size_t>(bytes / 8));
    if (!v.empty() && std::fread(v.data(), 8, v.size(), f) != v.size()) throw std::runtime_error("short read " + path);
    std::fclose(f);
    return v; // little-endian hosts only (x86-64, arm64)
}

long long max_rss_bytes() { // ru_maxrss is bytes on macOS, kilobytes on Linux
    struct rusage ru;
    if (getrusage(RUSAGE_SELF, &ru) != 0) return -1;
#if defined(__APPLE__)
    return static_cast<long long>(ru.ru_maxrss);
#else
    return static_cast<long long>(ru.ru_maxrss) * 1024LL;
#endif
}

struct Stages { double prep = 0, sort = 0, atoms = 0, collapse = 0, dp = 0, starts = 0, refine = 0, summary = 0; };
struct Run {
    Bounds b, coarse_b, ltr_b;
    double sse = 0, coarse_sse = 0, ltr_sse = 0, t_refine_ltr = 0;
    lex::Start start = lex::Start::Collapse;
    int atoms = 0, sweeps = 0, moves = 0, ltr_sweeps = 0, ltr_moves = 0, ltr_same_partition = -1;
    bool did_sort = false;
    Stages t;
    double total = 0;
};

// Final SSE exactly as lex.cpp summarize() / summarize_weighted().
double raw_sse(const Atoms& a, const Bounds& b) {
    double sse = 0;
    for (std::size_t i = 0; i + 1 < b.size(); ++i) {
        const int lo = b[i], hi = b[i + 1];
        if (a.weighted) {
            double W = 0, S = 0;
            for (int e = lo; e < hi; ++e) { W += a.elem_weight[e]; S += a.elem_weight[e] * (a.sorted[e] - a.center); }
            const double m = W == 0 ? 0.0 : S / W;
            if (W > 0)
                for (int e = lo; e < hi; ++e) { const double dv = a.sorted[e] - a.center - m; sse += a.elem_weight[e] * dv * dv; }
        } else {
            double s = 0;
            for (int e = lo; e < hi; ++e) s += a.sorted[e] - a.center;
            const double m = s / (hi - lo);
            for (int e = lo; e < hi; ++e) { const double dv = a.sorted[e] - a.center - m; sse += dv * dv; }
        }
    }
    return sse;
}

// Instrumented copy of lex::lex_hybrid (lex_plain = coarse_groups 0) and lex::ckmeans_exact
// (the earlier bench's run_fit, unchanged apart from recording whether the sort ran).
Run run_fit(const std::vector<double>& xs, const std::vector<double>* ws, int k, const lex::Options& o, bool exact_only) {
    Run r;
    const double precision = exact_only ? 0.0 : o.precision;
    const auto t0 = clk::now();
    for (double x : xs) if (!std::isfinite(x)) throw std::invalid_argument("non-finite input");
    if (ws) for (double w : *ws) if (!std::isfinite(w) || w < 0) throw std::invalid_argument("bad weight");
    std::vector<double> s(xs), w;
    if (ws) w = *ws;
    const auto t1 = clk::now();
    r.did_sort = ws ? sort_pairs(s, w) : sort_values(s);
    const auto ts = clk::now();
    const Atoms a = ws ? Atoms(std::move(s), std::move(w), precision) : Atoms(std::move(s), precision);
    if (k > a.d) k = a.d;
    const auto t2 = clk::now();
    auto t3 = t2, t4 = t2, t5 = t2, t6 = t2;
    Bounds b;
    if (exact_only) {
        t3 = clk::now();
        b = exact(a, k);
        t4 = t5 = clk::now();
        const RefineStats st = refine(a, b, lex::Options{}.tolerance); // tie pass, as lex::ckmeans_exact
        r.moves = st.moves;
        t6 = clk::now();
        r.start = lex::Start::Exact;
    } else {
        const std::size_t m = std::max<std::size_t>(k, std::min<std::size_t>(o.coarse_groups, a.d));
        r.start = lex::Start::Collapse;
        if (m <= static_cast<std::size_t>(k)) {
            b = collapse(a, k);
            t3 = t4 = clk::now();
        } else if (m == static_cast<std::size_t>(a.d)) {
            t3 = clk::now();
            b = exact(a, k);
            t4 = clk::now();
            r.start = lex::Start::CoarseExact;
        } else {
            const Bounds groups = collapse(a, static_cast<int>(m));
            t3 = clk::now();
            if (a.weighted) b = exact_weighted(a, groups, k);
            else {
                std::vector<double> means(m);
                for (std::size_t g = 0; g < m; ++g) means[g] = a.mean(groups[g], groups[g + 1]);
                b = exact(groups, means, k);
            }
            t4 = clk::now();
            r.start = lex::Start::CoarseExact;
        }
        if (o.multi_start) {
            double best = a.sse(b);
            Bounds ef = equal_frequency(a.n, k);
            if (const double v = a.sse(ef); v < best) { best = v; b = std::move(ef); r.start = lex::Start::EqualFrequency; }
            Bounds ew = equal_width(a.sorted, k);
            if (!ew.empty())
                if (const double v = a.sse(ew); v < best) { b = std::move(ew); r.start = lex::Start::EqualWidth; }
        }
        t5 = clk::now();
        r.coarse_b = b;
        r.coarse_sse = raw_sse(a, b);
        const RefineStats st = refine(a, b, o.tolerance);
        r.sweeps = st.sweeps;
        r.moves = st.moves;
        t6 = clk::now();
        // Exploratory LTR Refine from the same coarse-DP bounds. Timed separately; not in fit_s
        // or t_refine_s, which stay comparable to GOLD's standard (RTL) lex_hybrid.
        r.ltr_b = r.coarse_b;
        const auto tl0 = clk::now();
        const RefineStats st_ltr = lex::detail_ltr::refine(a, r.ltr_b, o.tolerance);
        r.t_refine_ltr = secs(tl0, clk::now());
        r.ltr_sse = raw_sse(a, r.ltr_b);
        r.ltr_sweeps = st_ltr.sweeps;
        r.ltr_moves = st_ltr.moves;
        r.ltr_same_partition = (r.ltr_b == b) ? 1 : 0;
    }
    r.sse = raw_sse(a, b);
    const auto t7 = clk::now();
    r.b = std::move(b);
    r.atoms = a.d;
    r.t = {secs(t0, t1), secs(t1, ts), secs(ts, t2), secs(t2, t3), secs(t3, t4), secs(t4, t5), secs(t5, t6), secs(t6, t7)};
    r.total = secs(t0, t7); // RTL path only (excludes the LTR Refine)
    return r;
}

const char* start_name(lex::Start s) {
    switch (s) {
        case lex::Start::Collapse: return "collapse";
        case lex::Start::EqualFrequency: return "equal_freq";
        case lex::Start::EqualWidth: return "equal_width";
        case lex::Start::Exact: return "exact";
        case lex::Start::CoarseExact: return "coarse_exact";
    }
    return "?";
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 6 && argc != 7) {
        std::fprintf(stderr, "usage: refine_fit INPUT_F64 hybrid K M verify|timed [WEIGHTS_F64]\n");
        return 2;
    }
    try {
        const std::string path = argv[1], method = argv[2], mode = argv[5];
        const int k = std::atoi(argv[3]);
        const std::size_t M = static_cast<std::size_t>(std::strtoull(argv[4], nullptr, 10));
        const auto tl = clk::now();
        const std::vector<double> xs = load_f64(path);
        std::vector<double> wv;
        const bool weighted = argc == 7;
        if (weighted) {
            wv = load_f64(argv[6]);
            if (wv.size() != xs.size()) throw std::runtime_error("weights length differs from values");
        }
        const double load_s = secs(tl, clk::now());
        const long long rss_load = max_rss_bytes();
        if (method == "load") {
            double sum = 0;
            for (double x : xs) sum += x;
            std::printf("RESULT method=load n=%zu weighted=%d load_s=%.9f checksum=%.17g rss_self=%lld\n", xs.size(),
                        weighted ? 1 : 0, load_s, sum, rss_load);
            return 0;
        }
        if (method != "hybrid") throw std::runtime_error("refine_fit accepts only method=hybrid, got " + method);
        if (mode != "verify" && mode != "timed") throw std::runtime_error("unknown mode " + mode);
        const bool is_exact = method == "exact";
        lex::Options o;
        o.coarse_groups = method == "plain" ? 0 : M;
        const std::vector<double>* ws = weighted ? &wv : nullptr;

        double api_s = NAN;
        int api_match = -1;
        lex::Result api{};
        if (mode == "verify") {
            const auto ta = clk::now();
            if (weighted)
                api = is_exact ? lex::ckmeans_exact(xs.data(), xs.size(), k, wv.data())
                               : lex::lex_hybrid(xs.data(), xs.size(), k, wv.data(), o);
            else
                api = is_exact ? lex::ckmeans_exact(xs, k) : lex::lex_hybrid(xs, k, o);
            api_s = secs(ta, clk::now());
        }
        const Run r = run_fit(xs, ws, k, o, is_exact);
        if (mode == "verify") api_match = (r.b == api.bounds && r.sse == api.sse && r.start == api.start) ? 1 : 0;
        std::string sizes, coarse_sizes, ltr_sizes;
        for (std::size_t i = 0; i + 1 < r.b.size(); ++i) sizes += (i ? "|" : "") + std::to_string(r.b[i + 1] - r.b[i]);
        for (std::size_t i = 0; i + 1 < r.coarse_b.size(); ++i)
            coarse_sizes += (i ? "|" : "") + std::to_string(r.coarse_b[i + 1] - r.coarse_b[i]);
        for (std::size_t i = 0; i + 1 < r.ltr_b.size(); ++i)
            ltr_sizes += (i ? "|" : "") + std::to_string(r.ltr_b[i + 1] - r.ltr_b[i]);
        const int k_eff = static_cast<int>(r.b.size()) - 1;
        std::printf("RESULT method=%s k=%d M=%zu n=%zu weighted=%d atoms=%d k_eff=%d sse=%.17g coarse_sse=%.17g "
                    "ltr_sse=%.17g t_refine_ltr_s=%.9f ltr_sweeps=%d ltr_moves=%d ltr_same_partition=%d "
                    "fit_s=%.9f post_sort_s=%.9f "
                    "api_s=%.9f api_match=%d did_sort=%d t_prep_s=%.9f t_sort_s=%.9f t_atoms_s=%.9f t_collapse_s=%.9f "
                    "t_dp_s=%.9f t_starts_s=%.9f t_refine_s=%.9f t_summary_s=%.9f sweeps=%d moves=%d start=%s load_s=%.9f "
                    "rss_load=%lld rss_self=%lld api_presorted=%d sizes=%s coarse_sizes=%s ltr_sizes=%s\n",
                    method.c_str(), k, M, xs.size(),
                    weighted ? 1 : 0, r.atoms, k_eff, r.sse, r.coarse_sse,
                    r.ltr_sse, r.t_refine_ltr, r.ltr_sweeps, r.ltr_moves, r.ltr_same_partition,
                    r.total, r.total - r.t.prep - r.t.sort, api_s, api_match,
                    r.did_sort ? 1 : 0, r.t.prep, r.t.sort, r.t.atoms, r.t.collapse, r.t.dp, r.t.starts, r.t.refine,
                    r.t.summary, r.sweeps, r.moves, start_name(r.start), load_s, rss_load, max_rss_bytes(),
                    mode == "verify" ? (api.presorted ? 1 : 0) : -1, sizes.c_str(), coarse_sizes.c_str(), ltr_sizes.c_str());
        return api_match == 0 ? 3 : 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "ERROR %s\n", e.what());
        std::printf("RESULT error=1\n");
        return 1;
    }
}
