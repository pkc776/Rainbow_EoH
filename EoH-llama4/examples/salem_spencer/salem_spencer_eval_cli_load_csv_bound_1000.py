"""
Evaluate Salem–Spencer (no 3-term AP) from argument input JSON files,
merge with a previous summary.csv (optional), write one merged CSV and one overview PNG,
and report per-run counts of exact-optimal hits.

NEW:
- Run naming now appends generation number parsed from filename like
  ".../population_generation_29.json" -> "<base_run_name>_29".
  This applies to CSV column names and the plot legend.
- (2025-10-28) Support loading extra N in [250..1023] from an a-series CSV
  (columns: N, Largest Salem Spencer Set Length, Solution), to extend bounds table
  and expand the evaluation/plot range. Upper bounds are drawn where known (opt_high).
  CSV values are treated as lower bounds (opt_low) only.

Usage:
  python salem_spencer_eval_cli.py <run_json> [<run_json> ...] \
      --csv-out out.csv --png-out out.png \
      [--summary-in summary.csv] [--stats-out hits.csv] [--log eval.log] [--verbose] \
      [--a-series-csv /path/to/salem_spencer_a_series.csv] [--n-min 80] [--n-max 250]
"""
import argparse, json, os, re, inspect
from typing import Any, Dict, List, Tuple, Callable, Optional

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import pandas as pd
import math

# ---------------------------
# 1) Known upper bounds / ranges (digitized)
# ---------------------------
EXACT_OPT: Dict[int, int] = {
    80:22,81:22,82:23,83:23,84:24,85:24,86:24,87:24,88:24,89:24,90:24,91:24,92:25,93:25,94:25,95:26,96:26,97:26,98:26,99:26,100:27,
    101:27,102:27,103:27,104:28,105:28,106:28,107:28,108:28,109:28,110:28,111:29,112:29,113:29,114:30,115:30,116:30,117:30,118:30,119:30,120:30,
    121:31,122:32,123:32,124:32,125:32,126:32,127:32,128:32,129:32,130:32,131:32,132:32,133:32,134:32,135:32,136:32,137:33,138:33,139:33,140:33,
    141:33,142:33,143:33,144:33,145:34,146:34,147:34,148:34,149:34,150:35,151:35,152:35,153:35,154:35,155:35,156:35,157:36,158:36,159:36,160:36,
    161:36,162:36,163:37,164:37,165:38,166:38,167:38,168:38,169:39,170:39,171:39,172:39,173:39,174:40,175:40,176:40,177:40,178:40,179:40,180:40,
    181:40,182:40,183:40,184:40,185:40,186:40,187:40
}
RANGE_OPT: Dict[int, Tuple[int, int]] = {
    188:(40,41),189:(40,42),190:(40,42),191:(40,43),192:(40,44),193:(40,44),
    194:(41,44),195:(41,44),196:(41,45),197:(41,45),198:(41,46),199:(41,46),
    200:(41,47),201:(41,48),202:(41,48),203:(41,48),204:(42,48),205:(42,48),
    206:(42,48),207:(42,49),208:(42,49),209:(43,49),210:(43,49),211:(43,49),
    212:(43,50),213:(43,50),214:(43,51),215:(44,51),216:(44,51),217:(44,51),
    218:(44,51),219:(44,51),220:(44,52),221:(44,52),222:(44,52),223:(44,52),
    224:(44,53),225:(44,54),226:(44,54),227:(45,55),228:(45,55),229:(45,55),
    230:(45,55),231:(45,56),232:(45,56),233:(46,56),234:(46,56),235:(46,56),
    236:(46,56),237:(46,56),238:(46,57),239:(47,57),240:(47,57),241:(47,58),
    242:(47,58),243:(47,58),244:(47,58),245:(47,58),246:(47,59),247:(48,59),
    248:(48,59),249:(48,59),250:(48,60)
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
    # Robust column name resolution
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
# 2) Helpers (generation-aware run naming) — unchanged
# ---------------------------
import os, re, inspect
from typing import Any, Dict, List, Tuple, Callable, Optional

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

def builtin_is_three_ap_free(S: List[int]) -> Tuple[bool, Tuple[int,int,int]]:
    A = sorted(set(int(x) for x in S))
    H = set(A)
    L = len(A)
    for i in range(L):
        a = A[i]
        for j in range(i+1, L):
            b = A[j]
            c = 2*b - a
            if c in H:
                return (False, (a,b,c))
    return (True, ())

def find_heuristic_and_checker(ns: Dict[str, Any]) -> Tuple[Callable[[int, Any], List[int]],
                                                            Callable[[List[int]], Tuple[bool, Any]]]:
    if callable(ns.get("heuristic", None)):
        heuristic_fn = ns["heuristic"]
        checker = ns.get("is_three_ap_free", None)
        if not callable(checker): checker = builtin_is_three_ap_free
        return heuristic_fn, checker
    for name, obj in ns.items():
        if inspect.isclass(obj) and hasattr(obj, "heuristic") and callable(getattr(obj, "heuristic")):
            try:
                inst = obj()
            except Exception:
                continue
            def heuristic_wrapper(n, rng=None, _inst=inst):
                return _inst.heuristic(n, rng=rng)
            checker = ns.get("is_three_ap_free", None)
            if not callable(checker): checker = builtin_is_three_ap_free
            return heuristic_wrapper, checker
    raise RuntimeError("No usable heuristic() found (neither global nor class method).")

# ---------------------------
# 3) Core evaluation — unchanged logic, but we'll dynamically extend N range
# ---------------------------
def evaluate_run_json(json_path: str,
                      n_list: List[int],
                      verbose: bool,
                      logf: Optional[Any]) -> Dict[int, Dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    code = obj.get("code", "")
    ns: Dict[str, Any] = {}
    try:
        exec(code, ns, ns)
    except Exception as e:
        msg = f"[exec error] {json_path}: {e}"
        if logf: print(msg, file=logf)
        if verbose: print(msg)
        return {}

    try:
        heuristic_fn, checker_fn = find_heuristic_and_checker(ns)
    except Exception as e:
        msg = f"[symbol error] {json_path}: {e}"
        if logf: print(msg, file=logf)
        if verbose: print(msg)
        return {}

    results: Dict[int, Dict[str, Any]] = {}
    for n in n_list:
        best: List[int] = []
        for seed in range(42, 42 + 5*10 + 1, 5):   # 42,47,52,57,62,67
            try:
                S = list(heuristic_fn(n, rng=None))
                is_free, _ = checker_fn(S)
            except Exception as e:
                msg = f"[runtime] {os.path.basename(json_path)} n={n}, seed={seed}: {e}"
                if logf: print(msg, file=logf)
                if verbose: print(msg)
                continue
            if is_free and len(S) > len(best):
                best = S
        results[n] = {"best_len": len(best), "best_set": best}
        if verbose and (n % 10 == 0):
            print(f"{os.path.basename(json_path)}: n={n}, best={len(best)}")
    return results

# ---------------------------
# 4) Build base bounds DF (now accepts extra lowers), aggregate new runs, load+merge previous CSV
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
                             log_path: Optional[str]) -> pd.DataFrame:
    logf = open(log_path, "a", encoding="utf-8") if log_path else None
    results_by_run: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for p in run_paths:
        if not os.path.exists(p):
            msg = f"[warn] not found: {p}"
            if logf: print(msg, file=logf)
            if verbose: print(msg)
            continue
        run_label = extract_run_label(p)
        results_by_run[run_label] = evaluate_run_json(p, n_list, verbose, logf)
    if logf: logf.close()

    df = base_bounds_df(n_list, extra_lowers)
    for run_label, res in results_by_run.items():
        lens = []; sets = []
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
# 5) Plot + stats (upper bound line added)
# ---------------------------
# def plot_overview(df: pd.DataFrame,
#                   png_out: str,
#                   n_list: List[int]) -> None:
#     n_min, n_max = min(n_list), max(n_list)
#     fig, ax = plt.subplots(figsize=(len(n_list)*0.2, 6))
#     ax.set_xlabel("n")
#     ax.set_ylabel("AP-free set size")
#     ax.set_title("Salem–Spencer (no 3-term AP): runs vs. known bounds")

#     ax.set_xticks(n_list)
#     ax.set_xticklabels([str(n) for n in n_list], rotation=90, fontsize=7)

#     # Background blocks where opt_high is constant and known
#     blocks = []
#     def b_of(n): 
#         row = df.loc[df["n"]==n].iloc[0]
#         return (row["bound_type"], row["opt_low"], row["opt_high"])
#     start = n_list[0]; cur = b_of(start)
#     for n in n_list[1:]:
#         nxt = b_of(n)
#         if (nxt != cur):
#             blocks.append((start, prev, cur))
#             start = n
#         prev = n
#         cur = nxt
#     blocks.append((start, n_list[-1], cur))

#     colors = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['#cccccc'])
#     cidx = 0
#     y_max_hint = 0
#     for a, b, (btype, lo, hi) in blocks:
#         if pd.notna(hi):
#             width = (b - a + 1)
#             c = colors[cidx % len(colors)]; cidx += 1
#             rect = Rectangle((a-0.5, 0), width, hi, alpha=0.07, edgecolor=None, facecolor=c, zorder=1)
#             ax.add_patch(rect)
#             y_max_hint = max(y_max_hint, int(hi))

#     # Draw an upper-bound polyline where opt_high is known
#     ub_x, ub_y = [], []
#     for _, row in df.iterrows():
#         if pd.notna(row["opt_high"]):
#             ub_x.append(int(row["n"]))
#             ub_y.append(int(row["opt_high"]))
#     if ub_x:
#         ax.plot(ub_x, ub_y, linewidth=1.6, linestyle="--", label="upper bound (opt_high)", zorder=3)

#     # Draw lower-bound dots from CSV (where bound_type == 'lower')
#     lb_x, lb_y = [], []
#     for _, row in df.iterrows():
#         if row["bound_type"] == "lower" and pd.notna(row["opt_low"]):
#             lb_x.append(int(row["n"]))
#             lb_y.append(int(row["opt_low"]))
#     if lb_x:
#         ax.scatter(lb_x, lb_y, s=12, marker="o", label="lower bound (CSV)", zorder=4)

#     # Draw runs
#     run_names = get_run_names(df)
#     palette = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['#111'])
#     legend_handles: List[Line2D] = []
#     if run_names:
#         spacing = 0.18
#         offsets = [spacing*(i - (len(run_names)-1)/2.0) for i in range(len(run_names))]
#         for idx, run in enumerate(run_names):
#             xs, y0, y1 = [], [], []
#             color = palette[idx % len(palette)]
#             for _, row in df.iterrows():
#                 L = row.get(f"{run}__len")
#                 if pd.isna(L): 
#                     continue
#                 n_val  = int(row["n"])
#                 opt_hi = row.get("opt_high")
#                 bar_top = int(L)
#                 if pd.notna(opt_hi):
#                     bar_top = min(bar_top, int(opt_hi))
#                 xs.append(n_val + offsets[idx]); y0.append(0); y1.append(bar_top)
#                 y_max_hint = max(y_max_hint, bar_top)
#             ax.vlines(xs, y0, y1, colors=color, linewidth=2.0, zorder=6, antialiased=False)
#             legend_handles.append(Line2D([0], [0], color=color, lw=2, label=run))

#     if run_names or ub_x or lb_x:
#         ax.legend(loc="upper left", ncol=2, fontsize=8, frameon=False)
#     ax.set_xlim(n_min - 0.5, n_max + 0.5)
#     ax.set_ylim(0, max(65, y_max_hint + 5))
#     ax.grid(True, alpha=0.25, linestyle="--", zorder=0)
#     fig.tight_layout()
#     fig.savefig(png_out, dpi=220)
#     plt.close(fig)

# def plot_overview(df: pd.DataFrame,
#                   png_out: str,
#                   n_list: List[int],
#                   n_slices: int = 1) -> None:
#     """
#     依 args.slice 將整個 x 軸分成 n_slices 等分，
#     依序輸出 overview_part1.png, overview_part2.png ...。
#     """
#     n_min, n_max = min(n_list), max(n_list)
#     total_n = len(n_list)
#     slice_size = math.ceil(total_n / max(1, n_slices))

#     for s_idx in range(n_slices):
#         start_i = s_idx * slice_size
#         end_i = min((s_idx + 1) * slice_size, total_n)
#         n_sub = n_list[start_i:end_i]
#         if not n_sub:
#             continue

#         fig, ax = plt.subplots(figsize=(max(12, len(n_sub)*0.8), 6))
#         ax.set_xlabel("n")
#         ax.set_ylabel("AP-free set size")
#         ax.set_title(f"Salem–Spencer bounds slice {s_idx+1}/{n_slices} (n={n_sub[0]}–{n_sub[-1]})")

#         ax.set_xticks(n_sub)
#         ax.set_xticklabels([str(n) for n in n_sub], rotation=90, fontsize=7)

#         # 上限曲線
#         ub_x, ub_y = [], []
#         for _, row in df[df["n"].isin(n_sub)].iterrows():
#             if pd.notna(row["opt_high"]):
#                 ub_x.append(int(row["n"]))
#                 ub_y.append(int(row["opt_high"]))
#         if ub_x:
#             ax.plot(ub_x, ub_y, "--", lw=1.5, label="upper bound", zorder=3)

#         # 下限散點
#         lb_x, lb_y = [], []
#         for _, row in df[df["n"].isin(n_sub)].iterrows():
#             if row["bound_type"] == "lower" and pd.notna(row["opt_low"]):
#                 lb_x.append(int(row["n"]))
#                 lb_y.append(int(row["opt_low"]))
#         if lb_x:
#             ax.scatter(lb_x, lb_y, s=12, c="tab:orange", label="lower bound (CSV)", zorder=4)

#         # 各 run 直條
#         run_names = get_run_names(df)
#         palette = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['#111'])
#         if run_names:
#             spacing = 0.18
#             offsets = [spacing*(i - (len(run_names)-1)/2.0) for i in range(len(run_names))]
#             for idx, run in enumerate(run_names):
#                 xs, y0, y1 = [], [], []
#                 color = palette[idx % len(palette)]
#                 for _, row in df[df["n"].isin(n_sub)].iterrows():
#                     L = row.get(f"{run}__len")
#                     if pd.isna(L): 
#                         continue
#                     n_val = int(row["n"])
#                     opt_hi = row.get("opt_high")
#                     bar_top = int(L)
#                     if pd.notna(opt_hi):
#                         bar_top = min(bar_top, int(opt_hi))
#                     xs.append(n_val + offsets[idx]); y0.append(0); y1.append(bar_top)
#                 ax.vlines(xs, y0, y1, colors=color, lw=2.0, zorder=6)
#             ax.legend(loc="upper left", fontsize=8, frameon=False)

#         # ax.set_xlim(n_sub[0]-0.5, n_sub[-1]+0.5)
#         # y_max = max(df.loc[df["n"].isin(n_sub), "opt_high"].dropna(default=[0]).max(initial=60), 65)
#         # ax.set_ylim(0, y_max + 5)
#         # ax.grid(True, alpha=0.25, linestyle="--", zorder=0)
#         # fig.tight_layout()

#         # part_path = re.sub(r"\.png$", f"_part{s_idx+1}.png", png_out)
#         # fig.savefig(part_path, dpi=220)
#         # plt.close(fig)
#         # print(f"[done] Slice {s_idx+1}/{n_slices} -> {part_path}")
#         ax.set_xlim(n_sub[0]-0.5, n_sub[-1]+0.5)

#         # 安全取得 y 軸上限（相容舊 pandas）
#         subset = df.loc[df["n"].isin(n_sub), "opt_high"].dropna()
#         y_max_val = subset.max() if not subset.empty else 60
#         y_max = max(y_max_val, 65)

#         ax.set_ylim(0, y_max + 5)
#         ax.grid(True, alpha=0.25, linestyle="--", zorder=0)
#         fig.tight_layout()

#         part_path = re.sub(r"\.png$", f"_part{s_idx+1}.png", png_out)
#         fig.savefig(part_path, dpi=220)
#         plt.close(fig)
#         print(f"[done] Slice {s_idx+1}/{n_slices} -> {part_path}")
import math
import re
import pandas as pd
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

def plot_overview(df: pd.DataFrame,
                  png_out: str,
                  n_list: list[int],
                  n_slices: int = 1,
                  dpi_out: int = 220) -> None:
    """
    依 n_list 與 n_slices 將 x 軸切成多段輸出。
    視覺規則：
      - 背景以 0→opt_high 的色帶表示上界，並在每個色帶左邊 n 上方標註該 opt_high 數字（沿用你的原版習慣）
      - 不畫上界折線
      - 來自 --a-series-csv 的點（bound_type == 'lower'，或你在 DF 中標成 'csv' 也可）
        會以散點顯示，並在點的上方標註該值（df['opt_low']）
      - 各 run 仍以 0→min(result, opt_high) 的直條表示
    """
    if not n_list:
        return
    total_n = len(n_list)
    n_slices = max(1, int(n_slices))
    slice_size = math.ceil(total_n / n_slices)

    # 一些共用顏色
    palette = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['#111'])
    bg_colors = palette  # 背景色帶輪替

    # 輔助：這個切片的資料列
    def rows_in_sub(n_sub):
        return df[df['n'].isin(n_sub)].copy()

    for s_idx in range(n_slices):
        start_i = s_idx * slice_size
        end_i   = min((s_idx + 1) * slice_size, total_n)
        n_sub   = n_list[start_i:end_i]
        if not n_sub:
            continue

        # 動態決定圖寬（每個 n 給多少英吋），並限制像素不超過 2^16（留 buffer）
        per_n_in = 0.55   # 你可以依需要改 0.35/0.4/0.5
        min_w_in = 12.0
        width_in = max(min_w_in, len(n_sub) * per_n_in)
        max_pixels = (2**16) - 1024
        width_in = min(width_in, max_pixels / dpi_out)

        fig, ax = plt.subplots(figsize=(width_in, 6))
        fig.set_dpi(dpi_out)

        ax.set_xlabel("n")
        ax.set_ylabel("AP-free set size")
        ax.set_title(f"Salem–Spencer bounds slice {s_idx+1}/{n_slices} (n={n_sub[0]}–{n_sub[-1]})")

        ax.set_xticks(n_sub)
        # 稀疏 x 軸，避免字擠：最多 ~40 個刻度
        k = max(1, len(n_sub)//40)
        show_ticks = n_sub[::k]
        ax.set_xticks(show_ticks)
        ax.set_xticklabels([str(n) for n in show_ticks], rotation=90, fontsize=7)

        sub = rows_in_sub(n_sub)

        # ---------------------------
        # 背景色帶 + 上方數字（opt_high）
        # ---------------------------
        # 以 (bound_type, opt_high) 連續區段切換為 block
        def sig(row):
            # 把 None 當成 NaN 來比較
            hi = row['opt_high']
            return (row['bound_type'], int(hi) if pd.notna(hi) else None)

        blocks = []
        if not sub.empty:
            current_sig = sig(sub.iloc[0])
            block_start = int(sub.iloc[0]['n'])
            for _, r in sub.iloc[1:].iterrows():
                if sig(r) != current_sig:
                    blocks.append((block_start, int(prev_n), current_sig))
                    block_start = int(r['n'])
                    current_sig = sig(r)
                prev_n = int(r['n'])
            blocks.append((block_start, int(sub.iloc[-1]['n']), current_sig))

        cidx = 0
        y_max_hint = 0
        for a, b, (btype, hi) in blocks:
            if hi is None:
                continue
            width = b - a + 1
            c = bg_colors[cidx % len(bg_colors)]; cidx += 1
            rect = Rectangle((a-0.5, 0), width, hi,
                             alpha=0.07, edgecolor=None, facecolor=c, zorder=1)
            ax.add_patch(rect)
            # 在色帶左邊 n（a）上方標註 hi
            ax.text(a, hi + 0.8, f"{hi}", fontsize=8, color=c)
            y_max_hint = max(y_max_hint, hi)

        # ---------------------------
        # 來自 CSV 的點（當成 lower bound 顯示）+ 在點上方標註該值
        # ---------------------------
        csv_rows = sub[(sub['bound_type'] == 'lower') & sub['opt_low'].notna()]
        if not csv_rows.empty:
            xs = csv_rows['n'].astype(int).to_list()
            ys = csv_rows['opt_low'].astype(int).to_list()
            ax.scatter(xs, ys, s=14, marker="o", zorder=4, label="CSV value")
            for x, y in zip(xs, ys):
                ax.text(x, y + 0.8, f"{y}", fontsize=7, ha='center', va='bottom')
            y_max_hint = max(y_max_hint, max(ys))

        # ---------------------------
        # 各 run 直條（截頂於 opt_high）
        # ---------------------------
        run_names = sorted(set(c.split("__")[0] for c in sub.columns if c.endswith("__len")))
        legend_handles: List[Line2D] = []
        if run_names:
            spacing = 0.18
            offsets = [spacing*(i - (len(run_names)-1)/2.0) for i in range(len(run_names))]
            for idx, run in enumerate(run_names):
                xs, y0, y1 = [], [], []
                color = palette[idx % len(palette)]
                for _, row in sub.iterrows():
                    L = row.get(f"{run}__len")
                    if pd.isna(L):
                        continue
                    n_val  = int(row["n"])
                    opt_hi = row.get("opt_high")
                    bar_top = int(L)
                    if pd.notna(opt_hi):
                        bar_top = min(bar_top, int(opt_hi))
                    xs.append(n_val + offsets[idx]); y0.append(0); y1.append(bar_top)
                    y_max_hint = max(y_max_hint, bar_top)
                if xs:
                    ax.vlines(xs, y0, y1, colors=color, linewidth=2.0, zorder=6, antialiased=False)
                    legend_handles.append(Line2D([0], [0], color=color, lw=2, label=run))

        if legend_handles:
            ax.legend(handles=legend_handles, loc="upper left", ncol=2, fontsize=8, frameon=False)

        ax.set_xlim(n_sub[0]-0.5, n_sub[-1]+0.5)

        # 取得 y 上限（相容舊版 pandas）
        subset_hi = sub['opt_high'].dropna()
        y_hi = int(subset_hi.max()) if not subset_hi.empty else 60
        y_max = max(y_hi, y_max_hint, 65)

        ax.set_ylim(0, y_max + 5)
        ax.grid(True, alpha=0.25, linestyle="--", zorder=0)
        fig.tight_layout()

        part_path = re.sub(r"\.png$", f"_part{s_idx+1}.png", png_out)
        fig.savefig(part_path, dpi=dpi_out)
        plt.close(fig)
        print(f"[done] Slice {s_idx+1}/{n_slices} -> {part_path}")



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
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_jsons", nargs="*", help="One or more run JSON files.")
    ap.add_argument("--csv-out", required=True, help="Merged CSV output path.")
    ap.add_argument("--png-out", required=True, help="Overview PNG output path.")
    ap.add_argument("--summary-in", default=None, help="Previous summary CSV to merge.")
    ap.add_argument("--stats-out", default=None, help="Optional CSV to save per-run exact-opt hit counts.")
    ap.add_argument("--n-min", type=int, default=80)
    ap.add_argument("--n-max", type=int, default=250)
    ap.add_argument("--a-series-csv", default=None, help="Path to CSV with columns [N, Largest Salem Spencer Set Length, Solution].")
    ap.add_argument("--log", default=None, help="Optional log file for errors.")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--slice", type=int, default=1, help="Split x-axis into this many slices for PNG output.")
    args = ap.parse_args()

    # Load extra lower bounds from CSV (only 250..1023)
    extra_lowers = load_a_series_lower_bounds(args.a_series_csv, n_lo=250, n_hi=1023)

    # Build the n-list:
    # - Start from contiguous [n_min..n_max]
    # - Add any CSV N in [250..1023]
    n_set = set(range(args.n_min, args.n_max + 1))
    n_set.update(extra_lowers.keys())
    # Clamp to <= 1023 as requested
    n_list = sorted(n for n in n_set if n <= 1023)

    # 1) new runs -> df_new
    df_new = aggregate_new_runs_to_df(args.run_jsons, n_list, extra_lowers,
                                      verbose=args.verbose, log_path=args.log)

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
    main()
