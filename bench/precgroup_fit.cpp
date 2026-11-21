// Precision-grouping driver for run 5 (exploratory, audio): one lex_hybrid fit per process, built against
// the frozen lex1d tree in ../lex1d/cpp (commit 8a691ee), which is not modified. Not library code.
//
// Usage: precgroup_fit RAW_F64 SORTED_F64 K M SIG verify|timed
//   RAW_F64     values in file order; only used to time the sort (the sorted copy must equal SORTED_F64)
//   SORTED_F64  the same values sorted ascending; every fit below starts from this array
//   SIG         0 = raw variant (lex_hybrid on all values, unweighted, as GOLD)
//               s > 0 = round each value to s significant digits, key = nearbyint(x/q)*q with
//               q = 10^(floor(log10|x|)-s+1) (0 for x == 0). Each run of equal keys in the sorted array is
//               one atom: weight n and the mean of its TRUE values. lex_hybrid runs on the atoms with
//               weights, so no bin can split an atom. Its weighted SSE plus the within-atom sum of squares
//               is the SSE of the raw values under the mapped cuts (checked: sse_raw, rel_diff).
//   MODE        verify: also runs the public API (lex::lex_hybrid) and checks that the instrumented copy
//               gives the same bounds, SSE and start (api_match), and checks the fast grouping against
//               the reference per-value log10/pow key (group_match); the warm-up round
//               timed: instrumented fit only (timed repeats)
// Stage times come from an instrumented copy of lex::lex_hybrid (the same pieces as bench/fit.cpp and
// bench/refine_fit.cpp). total_s = group_s + fit_s, both measured from the sorted array.
// Prints one line: RESULT key=value ...
#include "lex/lex.hpp"
#include "detail.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
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

long long max_rss_bytes() {
    struct rusage ru;
    if (getrusage(RUSAGE_SELF, &ru) != 0) return -1;
#if defined(__APPLE__)
    return static_cast<long long>(ru.ru_maxrss);
#else
    return static_cast<long long>(ru.ru_maxrss) * 1024LL;
#endif
}

// ---- grouping ----
struct Groups { std::vector<double> mean, weight; std::vector<std::size_t> start; }; // start has atoms+1 entries

// Reference key (the exploratory box driver precgroup.cpp): log10 and pow for every value.
double ref_key(double x, int s) {
    if (x == 0) return 0;
    const int e = static_cast<int>(std::floor(std::log10(std::fabs(x))));
    const double q = std::pow(10.0, e - s + 1);
    return std::nearbyint(x / q) * q;
}

Groups group_ref(const std::vector<double>& x, int s) {
    Groups g;
    const std::size_t n = x.size();
    std::size_t i = 0;
    while (i < n) {
        const double kk = ref_key(x[i], s);
        std::size_t j = i;
        double sum = 0;
        while (j < n && ref_key(x[j], s) == kk) { sum += x[j]; ++j; }
        g.start.push_back(i); g.mean.push_back(sum / static_cast<double>(j - i)); g.weight.push_back(static_cast<double>(j - i));
        i = j;
    }
    g.start.push_back(n);
    return g;
}

// Decade of a positive double, cached: e = floor(log10(a)) holds for every a in [lo, hi). The bounds are
// found once per decade by bisection over the bit patterns of positive doubles with the same libm log10,
// so the key is the reference key whenever floor(log10(.)) is monotone (verify mode checks this).
int decade(double a) { return static_cast<int>(std::floor(std::log10(a))); }
double first_with_decade_at_least(int e) { // smallest positive double a with decade(a) >= e
    std::uint64_t lo = 1, hi = 0x7fefffffffffffffULL; // decade(hi) >= e for any e we meet
    while (lo < hi) {
        const std::uint64_t mid = lo + (hi - lo) / 2;
        double a; std::memcpy(&a, &mid, 8);
        if (decade(a) >= e) hi = mid; else lo = mid + 1;
    }
    double a; std::memcpy(&a, &lo, 8);
    return a;
}

Groups group_fast(const std::vector<double>& x, int s) {
    Groups g;
    const std::size_t n = x.size();
    g.mean.reserve(n / 8); g.weight.reserve(n / 8); g.start.reserve(n / 8);
    int e = 0; double lo = 1, hi = 0, q = 1; // empty cache
    auto key = [&](double v) {
        if (v == 0) return 0.0;
        const double a = std::fabs(v);
        if (!(a >= lo && a < hi)) {
            e = decade(a);
            lo = first_with_decade_at_least(e);
            hi = first_with_decade_at_least(e + 1);
            q = std::pow(10.0, e - s + 1);
        }
        return std::nearbyint(v / q) * q;
    };
    std::size_t i = 0;
    double cur = key(x[0]), sum = 0;
    for (std::size_t j = 0; j < n; ++j) {
        const double kk = key(x[j]);
        if (kk != cur) {
            g.start.push_back(i); g.mean.push_back(sum / static_cast<double>(j - i)); g.weight.push_back(static_cast<double>(j - i));
            i = j; sum = 0; cur = kk;
        }
        sum += x[j];
    }
    g.start.push_back(i); g.mean.push_back(sum / static_cast<double>(n - i)); g.weight.push_back(static_cast<double>(n - i));
    g.start.push_back(n);
    return g;
}

// ---- instrumented lex_hybrid (bench/refine_fit.cpp's run_fit without the exact-only and LTR parts) ----
struct Stages { double prep = 0, sort = 0, atoms = 0, collapse = 0, dp = 0, starts = 0, refine = 0, summary = 0; };
struct Run {
    Bounds b;
    double sse = 0;
    lex::Start start = lex::Start::Collapse;
    int atoms = 0, sweeps = 0, moves = 0;
    bool did_sort = false;
    Stages t;
    double total = 0;
};

double lib_sse(const Atoms& a, const Bounds& b) { // as lex.cpp summarize() / summarize_weighted()
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

Run run_fit(const std::vector<double>& xs, const std::vector<double>* ws, int k, const lex::Options& o) {
    Run r;
    const auto t0 = clk::now();
    for (double x : xs) if (!std::isfinite(x)) throw std::invalid_argument("non-finite input");
    if (ws) for (double w : *ws) if (!std::isfinite(w) || w < 0) throw std::invalid_argument("bad weight");
    std::vector<double> s(xs), w;
    if (ws) w = *ws;
    const auto t1 = clk::now();
    r.did_sort = ws ? sort_pairs(s, w) : sort_values(s);
    const auto ts = clk::now();
    const Atoms a = ws ? Atoms(std::move(s), std::move(w), o.precision) : Atoms(std::move(s), o.precision);
    if (k > a.d) k = a.d;
    const auto t2 = clk::now();
    auto t3 = t2, t4 = t2;
    Bounds b;
    const std::size_t m = std::max<std::size_t>(k, std::min<std::size_t>(o.coarse_groups, a.d));
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
    const auto t5 = clk::now();
    const RefineStats st = refine(a, b, o.tolerance);
    r.sweeps = st.sweeps;
    r.moves = st.moves;
    const auto t6 = clk::now();
    r.sse = lib_sse(a, b);
    const auto t7 = clk::now();
    r.b = std::move(b);
    r.atoms = a.d;
    r.t = {secs(t0, t1), secs(t1, ts), secs(ts, t2), secs(t2, t3), secs(t3, t4), secs(t4, t5), secs(t5, t6), secs(t6, t7)};
    r.total = secs(t0, t7);
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

// Two-pass SSE in long double of sorted raw values over the bins [cut[i], cut[i+1]).
long double sse_cuts(const std::vector<double>& x, const std::vector<std::size_t>& cut) {
    long double sse = 0;
    for (std::size_t c = 0; c + 1 < cut.size(); ++c) {
        long double s = 0;
        for (std::size_t i = cut[c]; i < cut[c + 1]; ++i) s += x[i];
        const long double m = s / static_cast<long double>(cut[c + 1] - cut[c]);
        for (std::size_t i = cut[c]; i < cut[c + 1]; ++i) { const long double d = x[i] - m; sse += d * d; }
    }
    return sse;
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 7) {
        std::fprintf(stderr, "usage: precgroup_fit RAW_F64 SORTED_F64 K M SIG verify|timed\n");
        return 2;
    }
    try {
        const std::string mode = argv[6];
        const int k = std::atoi(argv[3]);
        const std::size_t M = static_cast<std::size_t>(std::strtoull(argv[4], nullptr, 10));
        const int sig = std::atoi(argv[5]);
        if (mode != "verify" && mode != "timed") throw std::runtime_error("unknown mode " + mode);
        if (sig < 0 || sig > 17) throw std::runtime_error("SIG must be 0..17");
        const auto tl = clk::now();
        const std::vector<double> raw = load_f64(argv[1]);
        const std::vector<double> xs = load_f64(argv[2]);
        const double load_s = secs(tl, clk::now());
        if (raw.size() != xs.size() || xs.empty()) throw std::runtime_error("raw and sorted lengths differ");

        // sort time, as the library sorts unsorted input (same for both variants; not in total_s)
        std::vector<double> rs(raw);
        const auto tq = clk::now();
        sort_values(rs);
        const double sort_s = secs(tq, clk::now());
        // == rather than bitwise: the library sort may order or normalise -0.0 and +0.0 differently from Python's sorted()
        if (!std::equal(rs.begin(), rs.end(), xs.begin())) throw std::runtime_error("sorted raw != SORTED_F64");
        std::vector<double>().swap(rs);

        lex::Options o;
        o.coarse_groups = M;
        Groups g;
        double group_s = 0;
        int group_match = -1;
        if (sig > 0) {
            const auto tg = clk::now();
            g = group_fast(xs, sig);
            group_s = secs(tg, clk::now());
            if (mode == "verify") {
                const Groups ref = group_ref(xs, sig);
                group_match = (ref.start == g.start && ref.mean == g.mean && ref.weight == g.weight) ? 1 : 0;
            }
        }
        const std::vector<double>& fx = sig > 0 ? g.mean : xs;
        const std::vector<double>* fw = sig > 0 ? &g.weight : nullptr;

        double api_s = NAN;
        int api_match = -1;
        lex::Result api{};
        if (mode == "verify") {
            const auto ta = clk::now();
            api = fw ? lex::lex_hybrid(fx.data(), fx.size(), k, fw->data(), o) : lex::lex_hybrid(fx, k, o);
            api_s = secs(ta, clk::now());
        }
        const Run r = run_fit(fx, fw, k, o);
        if (mode == "verify") api_match = (r.b == api.bounds && r.sse == api.sse && r.start == api.start) ? 1 : 0;

        // map cuts to raw indices; within-atom SS; SSE recomputed on the raw values
        std::vector<std::size_t> cut(r.b.size());
        for (std::size_t i = 0; i < cut.size(); ++i) cut[i] = sig > 0 ? g.start[r.b[i]] : static_cast<std::size_t>(r.b[i]);
        long double within = 0;
        if (sig > 0)
            for (std::size_t a = 0; a + 1 < g.start.size(); ++a) {
                const long double m = g.mean[a]; // the atom mean the fit used
                for (std::size_t i = g.start[a]; i < g.start[a + 1]; ++i) { const long double d = xs[i] - m; within += d * d; }
            }
        const long double sse_total = static_cast<long double>(r.sse) + within;
        const long double sse_raw = sse_cuts(xs, cut);
        const long double rel = sse_raw != 0 ? std::fabs(sse_total - sse_raw) / sse_raw : 0;
        std::size_t d_raw = 1;
        for (std::size_t i = 1; i < xs.size(); ++i) d_raw += xs[i] != xs[i - 1];
        std::string sizes;
        for (std::size_t i = 0; i + 1 < cut.size(); ++i) sizes += (i ? "|" : "") + std::to_string(cut[i + 1] - cut[i]);
        std::printf("RESULT variant=%s sig=%d k=%d M=%zu n=%zu d_raw=%zu D=%d k_eff=%d group_s=%.9f fit_s=%.9f total_s=%.9f "
                    "sort_s=%.9f did_sort=%d t_prep_s=%.9f t_sort_s=%.9f t_atoms_s=%.9f t_collapse_s=%.9f t_dp_s=%.9f "
                    "t_starts_s=%.9f t_refine_s=%.9f t_summary_s=%.9f sweeps=%d moves=%d start=%s "
                    "sse_lib=%.17g within_ss=%.17Lg sse=%.17Lg sse_raw=%.17Lg rel_diff=%.3Le "
                    "api_s=%.9f api_match=%d group_match=%d load_s=%.9f rss_self=%lld sizes=%s\n",
                    sig > 0 ? ("sig" + std::to_string(sig)).c_str() : "raw", sig, k, M, xs.size(), d_raw, r.atoms,
                    static_cast<int>(r.b.size()) - 1, group_s, r.total, group_s + r.total, sort_s, r.did_sort ? 1 : 0,
                    r.t.prep, r.t.sort, r.t.atoms, r.t.collapse, r.t.dp, r.t.starts, r.t.refine, r.t.summary,
                    r.sweeps, r.moves, start_name(r.start), r.sse, within, sse_total, sse_raw, rel,
                    api_s, api_match, group_match, load_s, max_rss_bytes(), sizes.c_str());
        return (api_match == 0 || group_match == 0) ? 3 : 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "ERROR %s\n", e.what());
        std::printf("RESULT error=1\n");
        return 1;
    }
}
