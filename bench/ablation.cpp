// Paired-move ablation for LEX Refine (bench only; the library is not changed).
//
// Refine's 3-bin window has 8 moves (lex1d/cpp/src/refine.cpp). This driver runs two
// variants from the same start partition:
//   all8   : a copy of the current Refiner, plus move counters and per-move SSE gains
//   single : the same code with paired moves 0, 5, 6, and 7 disabled
//
// The 8 move numbers, from kLeftOp / kRightOp in refine.cpp (0 stay, 1 give, 2 take):
//   0  left give,  right give   paired shrink of the middle bin
//   1  left give,  right stay   single move of the left cut
//   2  left stay,  right give   single move of the right cut
//   3  left take,  right stay   single move of the left cut
//   4  left stay,  right take   single move of the right cut
//   5  left take,  right give   paired translate of the middle bin one piece left
//   6  left give,  right take   paired translate of the middle bin one piece right
//   7  left take,  right take   paired grow of the middle bin
//
// Summary types (analyze.py):
//   single       moves 1, 2, 3, 4
//   shrink_grow  moves 0, 7
//   translate    moves 5, 6
//
// Starts: collapse (lex_plain) and coarse4096 (lex_hybrid, M = 4096).
// Reference optimum: ckmeans_exact. SSE is recomputed from raw values the same way
// lex::summarize does. all8 must be bit-identical to lex_plain / lex_hybrid on the
// same start. No fit may fall below the exact SSE by more than 1e-12 relative.
//
// Usage: ablation --out FILE [--reps N] [--k LIST] [--smoke] [--slice dataset,N,path]...
// If --smoke is given with no --slice, a 256-value synthetic input is used (not paper data).
#include "lex/lex.hpp"
#include "detail.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <set>
#include <string>
#include <vector>

using lex::detail::Atoms;
using lex::detail::collapse;
using lex::detail::exact;
using lex::detail::kTieEps;
using lex::detail::kTieRounds;
using lex::detail::sort_values;
using clk = std::chrono::steady_clock;

static double secs(clk::time_point t0) {
    return std::chrono::duration<double>(clk::now() - t0).count();
}

namespace {

//                         move: 0  1  2  3  4  5  6  7
constexpr int kLeftOp[8]  = {1, 1, 0, 2, 0, 2, 1, 2}; // 0 stay, 1 give, 2 take
constexpr int kRightOp[8] = {1, 0, 1, 0, 2, 1, 2, 2};
constexpr bool kPaired[8] = {true, false, false, false, false, true, true, true};

// Copy of refine.cpp's Refiner with a paired-move mask, an accepted-move
// histogram, and the sum of computed SSE reductions (gains) per move number.
struct Refiner {
    const Atoms& a;
    std::vector<int>& b;
    double tolerance;
    bool allow_paired;
    std::array<long, 8> hist{};
    std::array<double, 8> gain{};
    long tie_moves = 0;
    double tie_eps = a.weighted ? 0.0 : kTieEps;
    double mag = 0;

    double shift(int lo, int mid, int to, int hi) {
        if (a.weighted) {
            if (to == mid) return 0.0;
            const int p0 = std::min(to, mid), p1 = std::max(to, mid);
            const double Wp = a.wsum(p0, p1);
            if (Wp == 0) return 0.0;
            const bool right = to > mid;
            const double W1 = right ? a.wsum(mid, hi) : a.wsum(lo, mid);
            const double W2 = right ? a.wsum(lo, mid) : a.wsum(mid, hi);
            const double m1 = right ? a.mean(mid, hi) : a.mean(lo, mid);
            const double m2 = right ? a.mean(lo, mid) : a.mean(mid, hi);
            if (W1 > Wp) {
                const double g = a.value[a.atom_id[p0]];
                const double ww1 = Wp * W1 / (W1 - Wp);
                const double ww2 = Wp * W2 / (W2 + Wp);
                const double s1 = std::abs(g) + std::abs(m1);
                const double s2 = std::abs(g) + std::abs(m2);
                mag += ww2 * s2 * s2 + ww1 * s1 * s1;
                return ww2 * (g - m2) * (g - m2) - ww1 * (g - m1) * (g - m1);
            }
            const double before = a.range_sse(lo, mid) + a.range_sse(mid, hi);
            const double after = a.range_sse(lo, to) + a.range_sse(to, hi);
            mag += std::abs(before) + std::abs(after);
            return after - before;
        }
        if (to == mid) return 0.0;
        const double k = std::abs(to - mid);
        const double g = a.value[a.atom_id[std::min(to, mid)]];
        const bool right = to > mid;
        const int n1 = right ? hi - mid : mid - lo;
        const double m1 = right ? a.mean(mid, hi) : a.mean(lo, mid);
        const int n2 = right ? mid - lo : hi - mid;
        const double m2 = right ? a.mean(lo, mid) : a.mean(mid, hi);
        const double w1 = k * n1 / (n1 - k);
        const double w2 = k * n2 / (n2 + k);
        const double s1 = std::abs(g) + std::abs(m1);
        const double s2 = std::abs(g) + std::abs(m2);
        mag += w2 * s2 * s2 + w1 * s1 * s1;
        return w2 * (g - m2) * (g - m2) - w1 * (g - m1) * (g - m1);
    }

    bool window(int x, bool tie) {
        const bool has_b = x + 2 < static_cast<int>(b.size());
        const int al = b[x - 1], l = b[x], r = b[x + 1];
        const int br = has_b ? b[x + 2] : r;
        const auto& id = a.atom_id;
        const int x_pieces = id[r - 1] - id[l] + 1;
        const int a_pieces = id[l - 1] - id[al] + 1;
        const int b_pieces = has_b ? id[br - 1] - id[r] + 1 : 0;
        const int give_l = std::min(a.start[id[l] + 1], r);
        const int take_l = std::max(a.start[id[l - 1]], al);
        const int give_r = std::max(a.start[id[r - 1]], l);
        const int take_r = has_b ? std::min(a.start[id[r] + 1], br) : r;

        double first_delta[3], first_mag[3];
        bool first_done[3] = {false, false, false};
        int best = -1;
        double best_delta = 0, best_mag = 0;
        int best_l = 0, best_r = 0;
        for (int j = 0; j < 8; ++j) {
            if (!allow_paired && kPaired[j]) continue;
            const int lo = kLeftOp[j], ro = kRightOp[j];
            const int gives = (lo == 1) + (ro == 1);
            const bool viable = (lo != 2 || a_pieces >= 2) && (ro == 0 || has_b) && (ro != 2 || b_pieces >= 2) &&
                                (lo == 2 || ro == 2 || x_pieces > gives);
            if (!viable) continue;
            const int nl = lo == 0 ? l : lo == 1 ? give_l : take_l;
            const int nr = ro == 0 ? r : ro == 1 ? give_r : take_r;
            mag = 0;
            double delta;
            if (lo == 1 && ro == 2) {
                delta = shift(l, r, nr, br);
                delta += shift(al, l, nl, nr);
            } else {
                if (!first_done[lo]) {
                    first_delta[lo] = shift(al, l, nl, r);
                    first_mag[lo] = mag;
                    first_done[lo] = true;
                }
                mag = first_mag[lo];
                delta = first_delta[lo];
                delta += shift(nl, r, nr, br);
            }
            const bool larger = best >= 0 && (nr > best_r || (nr == best_r && nl > best_l));
            if (tie) {
                if (!(nr > r || (nr == r && nl > l)) || !(std::abs(delta) <= tie_eps * mag)) continue;
                if (best < 0 || larger) {
                    best = j;
                    best_l = nl;
                    best_r = nr;
                    best_delta = delta;
                    best_mag = mag;
                }
                continue;
            }
            if (best < 0 || delta < best_delta || (delta == best_delta && larger)) {
                best = j;
                best_delta = delta;
                best_mag = mag;
                best_l = nl;
                best_r = nr;
            }
        }
        if (best >= 0 && (tie || best_delta < -tolerance * best_mag)) {
            b[x] = best_l;
            b[x + 1] = best_r;
            ++hist[best];
            gain[best] += -best_delta; // computed SSE reduction
            if (tie) ++tie_moves;
            return true;
        }
        return false;
    }
};

struct Run {
    int sweeps = 0;
    long moves = 0;
    long tie_moves = 0;
    std::array<long, 8> hist{};
    std::array<double, 8> gain{};
};

Run refine_masked(const Atoms& a, std::vector<int>& b, double tolerance, bool allow_paired) {
    Run out;
    const int k = static_cast<int>(b.size()) - 1;
    if (k < 2) return out;
    Refiner r{a, b, tolerance, allow_paired};
    const int top = k == 2 ? 1 : k - 2;
    auto run = [&](bool tie) {
        bool any = false;
        std::set<std::vector<int>> seen;
        for (bool improved = true; improved;) {
            if (!tie) ++out.sweeps;
            improved = false;
            for (int x = top; x >= 1; --x) {
                if (r.window(x, tie)) {
                    improved = any = true;
                    ++out.moves;
                }
            }
            if (improved && !seen.insert(b).second) break;
        }
        return any;
    };
    run(false);
    for (int round = 0; round < kTieRounds && run(true); ++round)
        if (!run(false)) break;
    out.hist = r.hist;
    out.gain = r.gain;
    out.tie_moves = r.tie_moves;
    return out;
}

// Same two-pass centred SSE as lex::summarize.
double raw_sse(const Atoms& a, const std::vector<int>& b) {
    double sse = 0;
    for (size_t i = 0; i + 1 < b.size(); ++i) {
        const int lo = b[i], hi = b[i + 1];
        double s = 0;
        for (int e = lo; e < hi; ++e) s += a.sorted[e] - a.center;
        const double m = s / (hi - lo);
        for (int e = lo; e < hi; ++e) {
            const double d = a.sorted[e] - a.center - m;
            sse += d * d;
        }
    }
    return sse;
}

std::vector<int> make_start(const Atoms& a, int k, std::size_t M) {
    const std::size_t m = std::max<std::size_t>(k, std::min<std::size_t>(M, a.d));
    if (m <= static_cast<std::size_t>(k)) return collapse(a, k);
    if (m == static_cast<std::size_t>(a.d)) return exact(a, k);
    const std::vector<int> groups = collapse(a, static_cast<int>(m));
    std::vector<double> means(m);
    for (std::size_t g = 0; g < m; ++g) means[g] = a.mean(groups[g], groups[g + 1]);
    return exact(groups, means, k);
}

std::vector<double> load_f64(const std::string& path, std::size_t n) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        std::fprintf(stderr, "cannot open %s\n", path.c_str());
        std::exit(1);
    }
    std::vector<double> xs(n);
    in.read(reinterpret_cast<char*>(xs.data()), static_cast<std::streamsize>(n * sizeof(double)));
    if (static_cast<std::size_t>(in.gcount()) != n * sizeof(double)) {
        std::fprintf(stderr, "short read from %s (wanted %zu values)\n", path.c_str(), n);
        std::exit(1);
    }
    return xs;
}

double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    return v[v.size() / 2];
}

const char* header =
    "dataset,N,k,start,variant,exact_sse,sse,start_gap_pct,gap_pct,refine_s,"
    "sweeps,moves,tie_moves,"
    "m0,m1,m2,m3,m4,m5,m6,m7,"
    "g0,g1,g2,g3,g4,g5,g6,g7,"
    "check,single_vs_all8\n";

struct Slice {
    std::string dataset;
    std::size_t n = 0;
    std::string path;
};

std::vector<int> parse_ks(const std::string& s) {
    std::vector<int> ks;
    std::size_t i = 0;
    while (i < s.size()) {
        const std::size_t j = s.find(',', i);
        const std::string t = s.substr(i, (j == std::string::npos ? s.size() : j) - i);
        if (!t.empty()) ks.push_back(std::atoi(t.c_str()));
        if (j == std::string::npos) break;
        i = j + 1;
    }
    return ks;
}

Slice parse_slice(const std::string& s) {
    // dataset,N,path  (path may contain commas? we split only the first two)
    const auto c1 = s.find(',');
    const auto c2 = (c1 == std::string::npos) ? std::string::npos : s.find(',', c1 + 1);
    if (c1 == std::string::npos || c2 == std::string::npos) {
        std::fprintf(stderr, "bad --slice %s (expected dataset,N,path)\n", s.c_str());
        std::exit(2);
    }
    Slice sl;
    sl.dataset = s.substr(0, c1);
    sl.n = std::strtoull(s.substr(c1 + 1, c2 - c1 - 1).c_str(), nullptr, 10);
    sl.path = s.substr(c2 + 1);
    return sl;
}

std::vector<double> smoke_values(std::size_t n) {
    // Deterministic, not paper data. Only used when --smoke is given with no --slice.
    std::vector<double> xs(n);
    std::uint64_t s = 0x9E3779B97F4A7C15ULL;
    for (std::size_t i = 0; i < n; ++i) {
        s ^= s >> 12; s ^= s << 25; s ^= s >> 27;
        const std::uint64_t u = s * 0x2545F4914F6CDD1DULL;
        xs[i] = (u >> 11) * (1.0 / 9007199254740992.0);
    }
    return xs;
}

void usage() {
    std::fprintf(stderr,
        "usage: ablation --out FILE [--reps N] [--k LIST] [--smoke] [--slice dataset,N,path]...\n");
}

} // namespace

int main(int argc, char** argv) {
    std::string out_path;
    bool smoke = false;
    int reps = 3;
    bool reps_set = false;
    std::vector<int> ks;
    std::vector<Slice> slices;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "--out" && i + 1 < argc) out_path = argv[++i];
        else if (a == "--smoke") smoke = true;
        else if (a == "--reps" && i + 1 < argc) { reps = std::atoi(argv[++i]); reps_set = true; }
        else if (a == "--k" && i + 1 < argc) ks = parse_ks(argv[++i]);
        else if (a == "--slice" && i + 1 < argc) slices.push_back(parse_slice(argv[++i]));
        else if (a == "-h" || a == "--help") { usage(); return 0; }
        else {
            usage();
            return 2;
        }
    }
    if (out_path.empty() || reps < 1) {
        usage();
        return 2;
    }
    if (smoke && !reps_set) reps = 1;
    if (ks.empty()) ks = smoke ? std::vector<int>{4} : std::vector<int>{8, 64, 256, 512};
    if (slices.empty()) {
        if (!smoke) {
            std::fprintf(stderr, "ablation: pass one or more --slice dataset,N,path\n");
            return 2;
        }
        slices.push_back(Slice{"smoke_uniform", 256, ""});
    }

    std::ofstream out(out_path);
    if (!out) {
        std::fprintf(stderr, "cannot write %s\n", out_path.c_str());
        return 1;
    }
    out << header;
    out.setf(std::ios::fmtflags(0), std::ios::floatfield);
    out.precision(17);

    const double tol = lex::Options{}.tolerance;
    int failures = 0;
    int rows = 0;

    for (const Slice& sl : slices) {
        const char* dataset = sl.dataset.c_str();
        const std::size_t n = sl.n;
        std::vector<double> xs = sl.path.empty() ? smoke_values(n) : load_f64(sl.path, n);

            std::vector<double> sorted = xs;
            sort_values(sorted);
            const Atoms atoms(std::move(sorted), 0.0);

            for (int k : ks) {
                std::fprintf(stderr, "%s N=%zu k=%d exact...\n", dataset, n, k);
                const auto t_ex = clk::now();
                const lex::Result exact_fit = lex::ckmeans_exact(xs, k);
                const double exact_sse = exact_fit.sse;
                std::fprintf(stderr, "  exact %.3fs  sse=%.17g\n", secs(t_ex), exact_sse);

                for (const char* start_name : {"collapse", "coarse4096"}) {
                    const bool coarse = std::string(start_name) == "coarse4096";
                    const std::size_t M = coarse ? 4096 : 0;
                    const std::vector<int> start = make_start(atoms, k, M);
                    const double start_sse = raw_sse(atoms, start);
                    const lex::Result ref = coarse ? lex::lex_hybrid(xs, k) : lex::lex_plain(xs, k);

                    std::vector<int> b_all, b_single;
                    for (const char* variant : {"all8", "single"}) {
                        const bool allow = std::string(variant) == "all8";
                        std::vector<double> ts;
                        Run run;
                        std::vector<int> b;
                        for (int i = 0; i < reps; ++i) {
                            b = start;
                            const auto t1 = clk::now();
                            run = refine_masked(atoms, b, tol, allow);
                            ts.push_back(secs(t1));
                        }
                        const double sse = raw_sse(atoms, b);
                        const double gap = 100.0 * (sse - exact_sse) / exact_sse;
                        const double start_gap = 100.0 * (start_sse - exact_sse) / exact_sse;
                        std::string check = "ok";
                        if (sse < exact_sse * (1.0 - 1e-12)) {
                            check = "BELOW_EXACT";
                            ++failures;
                        }
                        if (allow && (b != ref.bounds || sse != ref.sse)) {
                            check = "MISMATCH_LIB";
                            ++failures;
                        }
                        if (allow) b_all = b;
                        else b_single = b;
                        const char* vs = allow ? "" : (b_single == b_all ? "same" : "diff");

                        out << dataset << ',' << n << ',' << k << ',' << start_name << ',' << variant
                            << ',' << exact_sse << ',' << sse << ',' << start_gap << ',' << gap << ','
                            << median(ts) << ',' << run.sweeps << ',' << run.moves << ',' << run.tie_moves;
                        for (int j = 0; j < 8; ++j) out << ',' << run.hist[j];
                        for (int j = 0; j < 8; ++j) out << ',' << run.gain[j];
                        out << ',' << check << ',' << vs << '\n';
                        ++rows;
                        std::fprintf(stderr, "  %s %s  gap=%.6g%%  moves=%ld  check=%s\n",
                                     start_name, variant, gap, run.moves, check.c_str());
                    }
                }
            }
    }
    out.flush();
    std::fprintf(stderr, "rows=%d  failures=%d\n", rows, failures);
    return failures ? 1 : 0;
}
