// Exploratory left-to-right Refine variant for GOLD run 4. This is a copy of frozen lex1d
// 8a691ee cpp/src/refine.cpp, kept in the paper-repo harness so lex1d/ is untouched.
// The only algorithmic change is the sweep loop: windows are visited left to right
// (x = 1 .. top) instead of right to left (x = top .. 1). Every tie rule is unchanged
// (among equal deltas the larger bounds win; tie sweeps still push bounds right;
// kTieRounds, kTieEps, cycle guard and gain tests are the same).
// Namespace: lex::detail_ltr. Called only by bench/refine_fit.cpp, from a copy of the
// coarse-DP bounds, after the standard (RTL) Refine has already run.
#include "detail.hpp"

#include <algorithm>
#include <cmath>
#include <set>

namespace lex::detail_ltr {

using lex::detail::Atoms;
using lex::detail::RefineStats;
using lex::detail::kTieRounds;
using lex::detail::kTieEps;

namespace {

//                         move: 0  1  2  3  4  5  6  7
constexpr int kLeftOp[8]  = {1, 1, 0, 2, 0, 2, 1, 2}; // 0 stay, 1 give, 2 take
constexpr int kRightOp[8] = {1, 0, 1, 0, 2, 1, 2, 2};

struct Refiner {
    const Atoms& a;
    std::vector<int>& b;
    double tolerance;
    double tie_eps = a.weighted ? 0.0 : kTieEps; // weighted: only exactly zero deltas are ties
    double mag = 0; // accumulated by shift()

    /// SSE change from moving the bound between bins lo..mid-1 and mid..hi-1 to `to` (one piece of
    /// k elements with value g). Closed form: k n2/(n2+k) (g-m2)^2 - k n1/(n1-k) (g-m1)^2,
    /// where 1 is the bin losing the piece and 2 the bin gaining it.
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
        const bool right = to > mid; // piece moves from the right bin to the left bin
        const int n1 = right ? hi - mid : mid - lo; // bin losing the piece
        const double m1 = right ? a.mean(mid, hi) : a.mean(lo, mid);
        const int n2 = right ? mid - lo : hi - mid; // bin gaining it
        const double m2 = right ? a.mean(lo, mid) : a.mean(mid, hi);
        const double w1 = k * n1 / (n1 - k);
        const double w2 = k * n2 / (n2 + k);
        const double s1 = std::abs(g) + std::abs(m1);
        const double s2 = std::abs(g) + std::abs(m2);
        mag += w2 * s2 * s2 + w1 * s1 * s1;
        return w2 * (g - m2) * (g - m2) - w1 * (g - m1) * (g - m1);
    }

    /// Gain mode: applies the best move around bin x if it lowers SSE by more than tolerance * mag.
    /// Tie mode: among moves that shift the bounds right with |delta| <= tie_eps * mag (tie_eps is
    /// kTieEps unweighted, 0 weighted; `tolerance` is not used here), applies the one with the
    /// largest new bounds.
    bool window(int x, bool tie) {
        const bool has_b = x + 2 < static_cast<int>(b.size());
        const int al = b[x - 1], l = b[x], r = b[x + 1];
        const int br = has_b ? b[x + 2] : r;
        const auto& id = a.atom_id;
        const int x_pieces = id[r - 1] - id[l] + 1;
        const int a_pieces = id[l - 1] - id[al] + 1;
        const int b_pieces = has_b ? id[br - 1] - id[r] + 1 : 0;
        // new position of each bound per op: stay, give, take
        const int give_l = std::min(a.start[id[l] + 1], r);
        const int take_l = std::max(a.start[id[l - 1]], al);
        const int give_r = std::max(a.start[id[r - 1]], l);
        const int take_r = has_b ? std::min(a.start[id[r] + 1], br) : r;

        // The first shift of the usual order depends only on the left op, so its delta and its mag
        // contribution are computed once per left op (mag starts at 0 for each move, so 0 + m1 == m1
        // exactly and results are unchanged). The give-left/take-right move shifts in the other order.
        double first_delta[3], first_mag[3];
        bool first_done[3] = {false, false, false};
        int best = -1;
        double best_delta = 0, best_mag = 0;
        int best_l = 0, best_r = 0;
        for (int j = 0; j < 8; ++j) {
            const int lo = kLeftOp[j], ro = kRightOp[j];
            const int gives = (lo == 1) + (ro == 1);
            const bool viable = (lo != 2 || a_pieces >= 2) && (ro == 0 || has_b) && (ro != 2 || b_pieces >= 2) &&
                                (lo == 2 || ro == 2 || x_pieces > gives);
            if (!viable) continue;
            const int nl = lo == 0 ? l : lo == 1 ? give_l : take_l;
            const int nr = ro == 0 ? r : ro == 1 ? give_r : take_r;
            mag = 0;
            // apply X's "take" first so X is never empty mid-move
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
                if (best < 0 || larger) { best = j; best_l = nl; best_r = nr; }
                continue;
            }
            // equal deltas: the move whose new bounds are larger, right bound first (exact equality)
            if (best < 0 || delta < best_delta || (delta == best_delta && larger)) {
                best = j; best_delta = delta; best_mag = mag; best_l = nl; best_r = nr;
            }
        }
        if (best >= 0 && (tie || best_delta < -tolerance * best_mag)) {
            b[x] = best_l;
            b[x + 1] = best_r;
            return true;
        }
        return false;
    }
};

} // namespace

RefineStats refine(const Atoms& a, std::vector<int>& b, double tolerance,
                   const std::function<void(const std::vector<int>&)>& on_move) {
    RefineStats stats;
    const int k = static_cast<int>(b.size()) - 1;
    if (k < 2) return stats;
    Refiner r{a, b, tolerance};
    const int top = k == 2 ? 1 : k - 2;
    auto run = [&](bool tie) { // sweeps until none applies; true if any move was applied
        bool any = false;
        std::set<std::vector<int>> seen; // partitions at the end of each sweep (cycle guard)
        for (bool improved = true; improved;) {
            if (!tie) ++stats.sweeps;
            improved = false;
            for (int x = 1; x <= top; ++x) { // LTR variant: left-to-right windows; ties unchanged
                if (r.window(x, tie)) {
                    improved = any = true;
                    ++stats.moves;
                    if (on_move) on_move(b);
                }
            }
            if (improved && !seen.insert(b).second) break; // cycle: only with extreme weight ratios
        }
        return any;
    };
    run(false);
    for (int round = 0; round < kTieRounds && run(true); ++round)
        if (!run(false)) break;
    return stats;
}

} // namespace lex::detail_ltr
