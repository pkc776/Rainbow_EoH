#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evaluate Salem–Spencer (no 3-term AP) from argument input JSON files,
merge with a previous summary.csv (optional), write one merged CSV and one overview PNG,
and report per-run counts of exact-optimal hits.

NEW (this patch):
- Parallel evaluation across N using multiple processes (since N are independent).
  Use --jobs to control process count, and --chunk-size to control how many N each worker handles.

Usage:
  python salem_spencer_eval_cli.py <run_json> [<run_json> ...] \
      --csv-out out.csv --png-out out.png \
      [--summary-in summary.csv] [--stats-out hits.csv] [--log eval.log] [--verbose] \
      [--a-series-csv /path/to/salem_spencer_a_series.csv] [--n-min 80] [--n-max 250] \
      [--jobs 8] [--chunk-size 32]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import inspect
import math
from typing import Any, Dict, List, Tuple, Callable, Optional, Iterable

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from matplotlib import cm

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed


# ---------------------------
# 0) Color utilities (avoid repeats even when >10 series)
# ---------------------------
def distinct_colors(n: int) -> List[Tuple[float, float, float, float]]:
    """
    Return n visually distinct RGBA colors.
    Strategy:
      - If n <= 20, use tab20 (good categorical palette).
      - Else, sample HSV evenly around the color wheel.
    """
    if n <= 20:
        cmap = cm.get_cmap("tab20", 20)
        return [cmap(i) for i in range(n)]
    hues = np.linspace(0.0, 1.0, n, endpoint=False)
    hsv = cm.get_cmap("hsv")
    return [hsv(h) for h in hues]


# ---------------------------
# 1) Known upper bounds / ranges (digitized)
# ---------------------------
EXACT_OPT: Dict[int, int] = {
    80: 22, 81: 22, 82: 23, 83: 23, 84: 24, 85: 24, 86: 24, 87: 24, 88: 24, 89: 24, 90: 24, 91: 24,
    92: 25, 93: 25, 94: 25, 95: 26, 96: 26, 97: 26, 98: 26, 99: 26, 100: 27,
    101: 27, 102: 27, 103: 27, 104: 28, 105: 28, 106: 28, 107: 28, 108: 28, 109: 28, 110: 28,
    111: 29, 112: 29, 113: 29, 114: 30, 115: 30, 116: 30, 117: 30, 118: 30, 119: 30, 120: 30,
    121: 31, 122: 32, 123: 32, 124: 32, 125: 32, 126: 32, 127: 32, 128: 32, 129: 32, 130: 32,
    131: 32, 132: 32, 133: 32, 134: 32, 135: 32, 136: 32, 137: 33, 138: 33, 139: 33, 140: 33,
    141: 33, 142: 33, 143: 33, 144: 33, 145: 34, 146: 34, 147: 34, 148: 34, 149: 34, 150: 35,
    151: 35, 152: 35, 153: 35, 154: 35, 155: 35, 156: 35, 157: 36, 158: 36, 159: 36, 160: 36,
    161: 36, 162: 36, 163: 37, 164: 37, 165: 38, 166: 38, 167: 38, 168: 38, 169: 39, 170: 39,
    171: 39, 172: 39, 173: 39, 174: 40, 175: 40, 176: 40, 177: 40, 178: 40, 179: 40, 180: 40,
    181: 40, 182: 40, 183: 40, 184: 40, 185: 40, 186: 40, 187: 40
}
RANGE_OPT: Dict[int, Tuple[int, int]] = {
    188: (40, 41), 189: (40, 42), 190: (40, 42), 191: (40, 43), 192: (40, 44), 193: (40, 44),
    194: (41, 44), 195: (41, 44), 196: (41, 45), 197: (41, 45), 198: (41, 46), 199: (41, 46),
    200: (41, 47), 201: (41, 48), 202: (41, 48), 203: (41, 48), 204: (42, 48), 205: (42, 48),
    206: (42, 48), 207: (42, 49), 208: (42, 49), 209: (43, 49), 210: (43, 49), 211: (43, 49),
    212: (43, 50), 213: (43, 50), 214: (43, 51), 215: (44, 51), 216: (44, 51), 217: (44, 51),
    218: (44, 51), 219: (44, 51), 220: (44, 52), 221: (44, 52), 222: (44, 52), 223: (44, 52),
    224: (44, 53), 225: (44, 54), 226: (44, 54), 227: (45, 55), 228: (45, 55), 229: (45, 55),
    230: (45, 55), 231: (45, 56), 232: (45, 56), 233: (46, 56), 234: (46, 56), 235: (46, 56),
    236: (46, 56), 237: (46, 56), 238: (46, 57), 239: (47, 57), 240: (47, 57), 241: (47, 58),
    242: (47, 58), 243: (47, 58), 244: (47, 58), 245: (47, 58), 246: (47, 59), 247: (48, 59),
    248: (48, 59), 249: (48, 59), 250: (48, 60)
}


# ---------------------------
# 1.1) Load extra N from a-series CSV (as lower bounds only)
# ---------------------------
def load_a_series_lower_bounds(csv_path: Optional[str],
                               n_lo: int = 250,
                               n_hi: int = 1023) -> Dict[int, int]:
    """
    Read CSV with columns [N, Largest Salem Spencer Set Length, Solution].
    Returns {N: length} for n_lo <= N <= n_hi.
    These are LOWER bounds (achieved sizes), not upper bounds.
    """
    lb: Dict[int, int] = {}
    if not csv_path:
        return lb
    df = pd.read_csv(csv_path)

    cols = {c.strip().lower(): c for c in df.columns}
    n_col = cols.get("n", "N" if "N" in df.columns else None)
    len_col = cols.get("largest salem spencer set length", None)
    if not n_col or not len_col:
        raise ValueError("CSV must have columns 'N' and 'Largest Salem Spencer Set Length'")

    for _, r in df.iterrows():
        try:
            N = int(r[n_col])
            if N < n_lo or N > n_hi:
                continue
            L = int(r[len_col])
            lb[N] = max(lb.get(N, 0), L)
        except Exception:
            continue
    return lb


def bounds_of(n: int,
              extra_lowers: Optional[Dict[int, int]] = None) -> Tuple[str, Optional[int], Optional[int]]:
    """
    Returns (bound_type, opt_low, opt_high)
      - 'exact' : opt_low ignored, opt_high is the exact value
      - 'range' : both opt_low and opt_high present
      - 'lower' : only opt_low known (from CSV), opt_high unknown
      - 'unknown' : neither known
    """
    if n in EXACT_OPT:
        s = EXACT_OPT[n]
        return ("exact", 0, s)
    if n in RANGE_OPT:
        lo, hi = RANGE_OPT[n]
        return ("range", lo, hi)
    if extra_lowers and (n in extra_lowers):
        return ("lower", extra_lowers[n], None)
    return ("unknown", None, None)


# ---------------------------
# 2) Helpers (generation-aware run naming)
# ---------------------------
def extract_run_base(path: str) -> str:
    m = re.search(r"/(results-[^/]+)/results/", path)
    if m:
        return m.group(1)
    return os.path.basename(os.path.dirname(os.path.dirname(path))) or os.path.basename(path)


def extract_generation(path: str) -> Optional[str]:
    m = re.search(r"population_generation_(\d+)\.json$", os.path.basename(path))
    if m:
        return m.group(1)
    return None


def extract_run_label(path: str) -> str:
    base = extract_run_base(path)
    gen = extract_generation(path)
    return f"{base}_{gen}" if gen is not None else base


def builtin_is_three_ap_free(S: List[int]) -> Tuple[bool, Tuple[int, int, int]]:
    A = sorted(set(int(x) for x in S))
    H = set(A)
    L = len(A)
    for i in range(L):
        a = A[i]
        for j in range(i + 1, L):
            b = A[j]
            c = 2 * b - a
            if c in H:
                return (False, (a, b, c))
    return (True, ())


def find_heuristic_and_checker(ns: Dict[str, Any]) -> Tuple[Callable[[int, Any], List[int]],
                                                            Callable[[List[int]], Tuple[bool, Any]]]:
    if callable(ns.get("heuristic", None)):
        heuristic_fn = ns["heuristic"]
        checker = ns.get("is_three_ap_free", None)
        if not callable(checker):
            checker = builtin_is_three_ap_free
        return heuristic_fn, checker

    for _, obj in ns.items():
        if inspect.isclass(obj) and hasattr(obj, "heuristic") and callable(getattr(obj, "heuristic")):
            try:
                inst = obj()
            except Exception:
                continue

            def heuristic_wrapper(n, rng=None, _inst=inst):
                return _inst.heuristic(n, rng=rng)

            checker = ns.get("is_three_ap_free", None)
            if not callable(checker):
                checker = builtin_is_three_ap_free
            return heuristic_wrapper, checker

    raise RuntimeError("No usable heuristic() found (neither global nor class method).")


# ---------------------------
# 3) Parallel evaluation workers
# ---------------------------
def _chunk_list(xs: List[int], chunk_size: int) -> List[List[int]]:
    if chunk_size <= 0:
        return [xs]
    return [xs[i:i + chunk_size] for i in range(0, len(xs), chunk_size)]


def _eval_code_on_n_chunk(code: str,
                          json_basename: str,
                          n_chunk: List[int],
                          verbose: bool) -> Tuple[Dict[int, Dict[str, Any]], List[str]]:
    """
    Worker function (runs in a separate process):
      - exec(code)
      - find heuristic + checker
      - evaluate best set for each n in n_chunk
    Returns:
      - results dict for n_chunk
      - list of log strings (errors/warnings)
    """
    logs: List[str] = []
    ns: Dict[str, Any] = {}
    try:
        exec(code, ns, ns)
    except Exception as e:
        logs.append(f"[exec error] {json_basename}: {e}")
        return {}, logs

    try:
        heuristic_fn, checker_fn = find_heuristic_and_checker(ns)
    except Exception as e:
        logs.append(f"[symbol error] {json_basename}: {e}")
        return {}, logs

    results: Dict[int, Dict[str, Any]] = {}
    for n in n_chunk:
        best: List[int] = []
        for seed in range(42, 42 + 5 * 10 + 1, 5):  # 42,47,52,57,62,67
            try:
                # NOTE: preserved original behavior: rng=None (seed loop is effectively repeated tries)
                S = list(heuristic_fn(n, rng=None))
                is_free, _ = checker_fn(S)
            except Exception as e:
                logs.append(f"[runtime] {json_basename} n={n}, seed={seed}: {e}")
                continue

            if is_free and len(S) > len(best):
                best = S

        results[n] = {"best_len": len(best), "best_set": best}

        # Throttle progress printing from workers (optional)
        if verbose and (n % 10 == 0):
            # Returned to parent as log to avoid interleaved stdout
            logs.append(f"[progress] {json_basename}: n={n}, best={len(best)}")

    return results, logs


def evaluate_run_json(json_path: str,
                      n_list: List[int],
                      verbose: bool,
                      logf: Optional[Any],
                      jobs: int = 1,
                      chunk_size: int = 32) -> Dict[int, Dict[str, Any]]:
    """
    Evaluate one run JSON across n_list.
    If jobs > 1, split n_list into chunks and evaluate chunks in parallel processes.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    code = obj.get("code", "")
    json_basename = os.path.basename(json_path)

    if not n_list:
        return {}

    # Sequential fallback
    if jobs <= 1:
        results, logs = _eval_code_on_n_chunk(code, json_basename, n_list, verbose=verbose)
        for msg in logs:
            if logf:
                print(msg, file=logf)
            if verbose:
                # Only print non-progress or keep all? keep all for parity.
                print(msg)
        return results

    # Parallel: split N into chunks
    chunks = _chunk_list(n_list, chunk_size=chunk_size)

    # Use spawn for portability/safety
    ctx = mp.get_context("spawn")
    results_all: Dict[int, Dict[str, Any]] = {}

    with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx) as ex:
        futs = [
            ex.submit(_eval_code_on_n_chunk, code, json_basename, ch, verbose)
            for ch in chunks
        ]
        for fut in as_completed(futs):
            try:
                res_chunk, logs = fut.result()
            except Exception as e:
                msg = f"[worker crash] {json_basename}: {e}"
                if logf:
                    print(msg, file=logf)
                if verbose:
                    print(msg)
                continue

            # Merge chunk results
            results_all.update(res_chunk)

            # Flush logs deterministically in parent
            for msg in logs:
                if logf:
                    print(msg, file=logf)
                if verbose:
                    print(msg)

    # Ensure every n has an entry (even if worker returned nothing for that n)
    for n in n_list:
        if n not in results_all:
            results_all[n] = {"best_len": None, "best_set": []}

    return results_all


# ---------------------------
# 4) Build base bounds DF, aggregate runs, merge previous CSV
# ---------------------------
def base_bounds_df(n_list: List[int], extra_lowers: Dict[int, int]) -> pd.DataFrame:
    rows = []
    for n in n_list:
        btype, lo, hi = bounds_of(n, extra_lowers)
        rows.append({"n": n, "bound_type": btype, "opt_low": lo, "opt_high": hi})
    return pd.DataFrame(rows)


def aggregate_new_runs_to_df(run_paths: List[str],
                             n_list: List[int],
                             extra_lowers: Dict[int, int],
                             verbose: bool,
                             log_path: Optional[str],
                             jobs: int,
                             chunk_size: int) -> pd.DataFrame:
    logf = open(log_path, "a", encoding="utf-8") if log_path else None

    results_by_run: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for p in run_paths:
        if not os.path.exists(p):
            msg = f"[warn] not found: {p}"
            if logf:
                print(msg, file=logf)
            if verbose:
                print(msg)
            continue

        run_label = extract_run_label(p)
        results_by_run[run_label] = evaluate_run_json(
            p, n_list, verbose=verbose, logf=logf, jobs=jobs, chunk_size=chunk_size
        )

    if logf:
        logf.close()

    df = base_bounds_df(n_list, extra_lowers)
    for run_label, res in results_by_run.items():
        lens: List[Optional[int]] = []
        sets: List[str] = []
        for n in n_list:
            r = res.get(n, {"best_len": None, "best_set": []})
            lens.append(r["best_len"])
            sets.append(" ".join(map(str, r["best_set"])) if r["best_set"] else "")
        df[f"{run_label}__len"] = lens
        df[f"{run_label}__set"] = sets

    return df


def load_previous_summary(summary_path: str,
                          n_list: List[int],
                          extra_lowers: Dict[int, int]) -> pd.DataFrame:
    prev = pd.read_csv(summary_path)
    keep_cols = ["n"] + [c for c in prev.columns if c.endswith("__len") or c.endswith("__set")]
    prev = prev[keep_cols].copy()
    base = base_bounds_df(n_list, extra_lowers)
    merged = base.merge(prev, on="n", how="left")
    return merged


def merge_prev_and_new(prev_df: Optional[pd.DataFrame],
                       new_df: pd.DataFrame) -> pd.DataFrame:
    if prev_df is None:
        return new_df
    out = new_df.copy()
    prev_run_cols = [c for c in prev_df.columns if c.endswith("__len") or c.endswith("__set")]
    for col in prev_run_cols:
        if col not in out.columns:
            out[col] = prev_df[col]
        else:
            out[col] = out[col].where(out[col].notna(), prev_df[col])
    return out


def get_run_names(df: pd.DataFrame) -> List[str]:
    return sorted(set(c.split("__")[0] for c in df.columns if c.endswith("__len")))


# ---------------------------
# 5) Plot + stats (no repeated colors)
# ---------------------------
def plot_overview(df: pd.DataFrame,
                  png_out: str,
                  n_list: List[int],
                  n_slices: int = 1,
                  dpi_out: int = 220) -> None:
    """
    Adjusts x-axis width based on (number of runs * bar width) to ensure
    consistent spacing regardless of the number of data series.
    """
    if not n_list:
        return
    total_n = len(n_list)
    n_slices = max(1, int(n_slices))
    slice_size = math.ceil(total_n / n_slices)

    # --- Custom Spacing Parameters (Physical Inches) ---
    bar_phys_width = 0.05  # Width of each individual run's bar in inches
    group_gap = 0.4        # Extra padding between different n values in inches
    min_fig_width = 12.0   # Minimum width of the output image
    # --------------------------------------------------

    def rows_in_sub(n_sub: List[int]) -> pd.DataFrame:
        return df[df["n"].isin(n_sub)].copy()

    for s_idx in range(n_slices):
        start_i = s_idx * slice_size
        end_i = min((s_idx + 1) * slice_size, total_n)
        n_sub = n_list[start_i:end_i]
        if not n_sub:
            continue

        sub = rows_in_sub(n_sub)
        run_names = sorted(set(c.split("__")[0] for c in sub.columns if c.endswith("__len")))
        num_runs = len(run_names)

        width_per_n = (num_runs * bar_phys_width) + group_gap
        width_in = max(min_fig_width, len(n_sub) * width_per_n)

        max_pixels = (2**16) - 1024
        width_in = min(width_in, max_pixels / dpi_out)

        fig, ax = plt.subplots(figsize=(width_in, 6), facecolor="white")
        fig.set_dpi(dpi_out)

        ax.set_xlabel("n")
        ax.set_ylabel("AP-free set size")
        ax.set_title(f"Salem–Spencer Grouped View (n={n_sub[0]}–{n_sub[-1]})")

        ax.set_xticks(n_sub)
        ax.set_xticklabels([str(n) for n in n_sub], rotation=90, fontsize=7)

        # --- Background Blocks (Upper Bounds) ---
        def sig(row: pd.Series) -> Tuple[str, Optional[int]]:
            hi = row["opt_high"]
            return (row["bound_type"], int(hi) if pd.notna(hi) else None)

        blocks: List[Tuple[int, int, Tuple[str, Optional[int]]]] = []
        if not sub.empty:
            current_sig = sig(sub.iloc[0])
            block_start = int(sub.iloc[0]["n"])
            prev_n = block_start
            for _, r in sub.iloc[1:].iterrows():
                if sig(r) != current_sig:
                    blocks.append((block_start, int(prev_n), current_sig))
                    block_start = int(r["n"])
                    current_sig = sig(r)
                prev_n = int(r["n"])
            blocks.append((block_start, int(sub.iloc[-1]["n"]), current_sig))

        bg_palette = distinct_colors(max(1, len([b for b in blocks if b[2][1] is not None])))
        cidx = 0
        y_max_hint = 0

        for a, b, (btype, hi) in blocks:
            if hi is None:
                continue
            width = b - a + 1
            c = bg_palette[cidx % len(bg_palette)]
            cidx += 1

            lo = 0
            if btype == "range":
                lo_vals = sub.loc[(sub["n"] >= a) & (sub["n"] <= b), "opt_low"]
                lo = int(lo_vals.min()) if lo_vals.notna().any() else 0

            rect = Rectangle((a - 0.5, lo), width, hi - lo, alpha=0.10, facecolor=c, zorder=1)
            ax.add_patch(rect)
            ax.text(a, hi + 0.8, f"{hi}", fontsize=8, color=c)
            y_max_hint = max(y_max_hint, hi)

        # --- CSV Lower Bound Points ---
        csv_rows = sub[(sub["bound_type"] == "lower") & sub["opt_low"].notna()]
        if not csv_rows.empty:
            xs_csv = csv_rows["n"].astype(int).to_list()
            ys_csv = csv_rows["opt_low"].astype(int).to_list()
            ax.scatter(xs_csv, ys_csv, s=14, marker="o", zorder=4, color="black", label="lower bound (CSV)")
            for x, y in zip(xs_csv, ys_csv):
                ax.text(x, y + 0.8, f"{y}", fontsize=7, ha="center", va="bottom")
            y_max_hint = max(y_max_hint, max(ys_csv))

        # --- Multi-Run Bars ---
        legend_handles: List[Line2D] = []
        if run_names:
            run_palette = distinct_colors(len(run_names))
            coord_spacing = 0.8 / max(1, num_runs)
            offsets = [coord_spacing * (i - (num_runs - 1) / 2.0) for i in range(num_runs)]
            lw_pts = bar_phys_width * 72 * 0.8

            for idx, run in enumerate(run_names):
                xs, y0, y1 = [], [], []
                color = run_palette[idx]
                col_len = f"{run}__len"

                for _, row in sub.iterrows():
                    L = row.get(col_len)
                    if pd.isna(L):
                        continue
                    n_val = int(row["n"])
                    opt_hi = row.get("opt_high")
                    bar_top = min(int(L), int(opt_hi)) if pd.notna(opt_hi) else int(L)

                    xs.append(n_val + offsets[idx])
                    y0.append(0)
                    y1.append(bar_top)
                    y_max_hint = max(y_max_hint, bar_top)

                if xs:
                    ax.vlines(xs, y0, y1, colors=color, linewidth=lw_pts, zorder=6, antialiased=False)
                    legend_handles.append(Line2D([0], [0], color=color, lw=4, label=run))

        if legend_handles:
            ax.legend(handles=legend_handles, loc="upper left", ncol=2, fontsize=8, frameon=False)

        ax.set_xlim(n_sub[0] - 0.7, n_sub[-1] + 0.7)
        y_max = max(y_max_hint, 65)
        ax.set_ylim(0, y_max + 5)
        ax.grid(True, alpha=0.25, linestyle="--", zorder=0)

        fig.tight_layout()
        part_path = re.sub(r"\.png$", f"_part{s_idx + 1}.png", png_out)
        fig.savefig(part_path, dpi=dpi_out)
        plt.close(fig)
        print(f"[done] Slice {s_idx + 1}/{n_slices} -> {part_path} (Width: {width_in:.2f}in)")


def compute_exact_opt_hits(df: pd.DataFrame) -> pd.DataFrame:
    exact_mask = (df["bound_type"] == "exact") & df["opt_high"].notna()
    exact_df = df.loc[exact_mask, ["n", "opt_high"]].copy()
    run_names = get_run_names(df)
    rows = []
    total_exact = exact_df.shape[0]
    for run in run_names:
        lens = df.loc[exact_mask, f"{run}__len"]
        hits = int((lens == exact_df["opt_high"]).sum())
        rows.append({"run": run, "hits": hits, "total_exact_n": int(total_exact)})
    return pd.DataFrame(rows).sort_values(["hits", "run"], ascending=[False, True])


# ---------------------------
# 6) CLI
# ---------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_jsons", nargs="*", help="One or more run JSON files.")
    ap.add_argument("--csv-out", required=True, help="Merged CSV output path.")
    ap.add_argument("--png-out", required=True, help="Overview PNG output path.")
    ap.add_argument("--summary-in", default=None, help="Previous summary CSV to merge.")
    ap.add_argument("--stats-out", default=None, help="Optional CSV to save per-run exact-opt hit counts.")
    ap.add_argument("--n-min", type=int, default=80)
    ap.add_argument("--n-max", type=int, default=250)
    ap.add_argument("--a-series-csv", default=None,
                    help="Path to CSV with columns [N, Largest Salem Spencer Set Length, Solution].")
    ap.add_argument("--log", default=None, help="Optional log file for errors.")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--slice", type=int, default=1, help="Split x-axis into this many slices for PNG output.")

    # NEW: parallel evaluation knobs
    ap.add_argument("--jobs", type=int, default=1,
                    help="Number of worker processes for parallel evaluation across N (per run).")
    ap.add_argument("--chunk-size", type=int, default=32,
                    help="How many N values each worker evaluates per task (larger reduces exec overhead).")

    args = ap.parse_args()

    # Load extra lower bounds from CSV (only 250..1023)
    extra_lowers = load_a_series_lower_bounds(args.a_series_csv, n_lo=250, n_hi=1200)

    # Build the n-list:
    # - Start from contiguous [n_min..n_max]
    # - Add any CSV N in [250..1023]
    n_set = set(range(args.n_min, args.n_max + 1))
    n_set.update(extra_lowers.keys())
    # Clamp to <= 1023
    n_list = sorted(n for n in n_set if n <= 1023)

    # 1) new runs -> df_new
    df_new = aggregate_new_runs_to_df(
        args.run_jsons, n_list, extra_lowers,
        verbose=args.verbose, log_path=args.log,
        jobs=max(1, int(args.jobs)),
        chunk_size=max(1, int(args.chunk_size)),
    )

    # 2) prev summary (optional) -> df_prev
    df_prev = None
    if args.summary_in is not None:
        if os.path.exists(args.summary_in):
            df_prev = load_previous_summary(args.summary_in, n_list, extra_lowers)
        else:
            print(f"[warn] --summary-in not found: {args.summary_in}")

    # 3) merge (new preferred; fill with prev where new missing)
    df_merged = merge_prev_and_new(df_prev, df_new)

    # 4) save merged CSV + plot
    df_merged.to_csv(args.csv_out, index=False)
    plot_overview(df_merged, args.png_out, n_list, args.slice)

    # 5) compute per-run exact-opt hits (print + optional CSV)
    hits_df = compute_exact_opt_hits(df_merged)
    if not hits_df.empty:
        print("\n=== Exact-optimal hits per run (only where bounds are exact) ===")
        for _, r in hits_df.iterrows():
            print(f"{r['run']}: {int(r['hits'])} / {int(r['total_exact_n'])}")
        if args.stats_out:
            hits_df.to_csv(args.stats_out, index=False)
            print(f"[done] Stats CSV -> {args.stats_out}")
    else:
        print("[info] No runs or no exact-bound rows to compute hits.")

    print(f"[done] CSV -> {args.csv_out}")
    print(f"[done] PNG -> {args.png_out}")


if __name__ == "__main__":
    # On some platforms, explicit freeze_support() avoids multiprocessing issues when packaged.
    mp.freeze_support()
    main()
