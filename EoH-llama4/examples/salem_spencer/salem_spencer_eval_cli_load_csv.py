# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# Evaluate Salem–Spencer (no 3-term AP) from argument input JSON files,
# merge with a previous summary.csv (optional), write one merged CSV and one overview PNG,
# and report per-run counts of exact-optimal hits.

# JSON must contain keys: ["algorithm", "code", "objective", "null"].
# We exec the "code". We then try to obtain a usable `heuristic(n, rng=None)`:
#   1) prefer a global function named `heuristic`;
#   2) else search classes that define `heuristic(self, n, rng=None)` and try to
#      instantiate with no-arg, then call obj.heuristic(...).

# If `is_three_ap_free(S)` is missing, we use a built-in checker.

# Plot: background shows 0→upper_bound blocks; run results are vertical bars from 0→min(result+1, upper_bound).

# Usage:
#   python salem_spencer_eval_cli.py <run_json> [<run_json> ...] \
#       --csv-out out.csv --png-out out.png \
#       [--summary-in summary.csv] [--stats-out hits.csv] [--log eval.log] [--verbose]
# """
# import argparse, json, os, re, inspect
# from typing import Any, Dict, List, Tuple, Callable, Optional

# import matplotlib.pyplot as plt
# from matplotlib.patches import Rectangle
# import pandas as pd
# from matplotlib.lines import Line2D

# # ---------------------------
# # 1) Known upper bounds / ranges (digitized)
# # ---------------------------
# EXACT_OPT: Dict[int, int] = {
#     80:22,81:22,82:23,83:23,84:24,85:24,86:24,87:24,88:24,89:24,90:24,91:24,92:25,93:25,94:25,95:26,96:26,97:26,98:26,99:26,100:27,
#     101:27,102:27,103:27,104:28,105:28,106:28,107:28,108:28,109:28,110:28,111:29,112:29,113:29,114:30,115:30,116:30,117:30,118:30,119:30,120:30,
#     121:31,122:32,123:32,124:32,125:32,126:32,127:32,128:32,129:32,130:32,131:32,132:32,133:32,134:32,135:32,136:32,137:33,138:33,139:33,140:33,
#     141:33,142:33,143:33,144:33,145:34,146:34,147:34,148:34,149:34,150:35,151:35,152:35,153:35,154:35,155:35,156:35,157:36,158:36,159:36,160:36,
#     161:36,162:36,163:37,164:37,165:38,166:38,167:38,168:38,169:39,170:39,171:39,172:39,173:39,174:40,175:40,176:40,177:40,178:40,179:40,180:40,
#     181:40,182:40,183:40,184:40,185:40,186:40,187:40
# }
# RANGE_OPT: Dict[int, Tuple[int, int]] = {
#     188:(40,41),189:(40,42),190:(40,42),191:(40,43),192:(40,44),193:(40,44),
#     194:(41,44),195:(41,44),196:(41,45),197:(41,45),198:(41,46),199:(41,46),
#     200:(41,47),201:(41,48),202:(41,48),203:(41,48),204:(42,48),205:(42,48),
#     206:(42,48),207:(42,49),208:(42,49),209:(43,49),210:(43,49),211:(43,49),
#     212:(43,50),213:(43,50),214:(43,51),215:(44,51),216:(44,51),217:(44,51),
#     218:(44,51),219:(44,51),220:(44,52),221:(44,52),222:(44,52),223:(44,52),
#     224:(44,53),225:(44,54),226:(44,54),227:(45,55),228:(45,55),229:(45,55),
#     230:(45,55),231:(45,56),232:(45,56),233:(46,56),234:(46,56),235:(46,56),
#     236:(46,56),237:(46,56),238:(46,57),239:(47,57),240:(47,57),241:(47,58),
#     242:(47,58),243:(47,58),244:(47,58),245:(47,58),246:(47,59),247:(48,59),
#     248:(48,59),249:(48,59),250:(48,60)
# }

# def bounds_of(n: int) -> Tuple[str, Optional[int], Optional[int]]:
#     if n in EXACT_OPT:
#         s = EXACT_OPT[n]
#         return ("exact", 0, s)      # draw 0 → upper bound band
#     if n in RANGE_OPT:
#         lo, hi = RANGE_OPT[n]
#         return ("range", 0, hi)
#     return ("unknown", None, None)

# # ---------------------------
# # 2) Helpers
# # ---------------------------
# def extract_run_name(path: str) -> str:
#     m = re.search(r"/(results-[^/]+)/results/", path)
#     if m:
#         return m.group(1)
#     return os.path.basename(os.path.dirname(os.path.dirname(path))) or os.path.basename(path)

# def builtin_is_three_ap_free(S: List[int]) -> Tuple[bool, Tuple[int,int,int]]:
#     A = sorted(set(int(x) for x in S))
#     H = set(A)
#     L = len(A)
#     for i in range(L):
#         a = A[i]
#         for j in range(i+1, L):
#             b = A[j]
#             c = 2*b - a
#             if c in H:
#                 return (False, (a,b,c))
#     return (True, ())

# def find_heuristic_and_checker(ns: Dict[str, Any]) -> Tuple[Callable[[int, Any], List[int]],
#                                                             Callable[[List[int]], Tuple[bool, Any]]]:
#     # 1) global function heuristic
#     if callable(ns.get("heuristic", None)):
#         heuristic_fn = ns["heuristic"]
#         checker = ns.get("is_three_ap_free", None)
#         if not callable(checker): checker = builtin_is_three_ap_free
#         return heuristic_fn, checker

#     # 2) search classes that define heuristic(self, n, rng=None)
#     for name, obj in ns.items():
#         if inspect.isclass(obj) and hasattr(obj, "heuristic") and callable(getattr(obj, "heuristic")):
#             try:
#                 inst = obj()
#             except Exception:
#                 continue
#             def heuristic_wrapper(n, rng=None, _inst=inst):
#                 return _inst.heuristic(n, rng=rng)
#             checker = ns.get("is_three_ap_free", None)
#             if not callable(checker): checker = builtin_is_three_ap_free
#             return heuristic_wrapper, checker

#     raise RuntimeError("No usable heuristic() found (neither global nor class method).")

# # ---------------------------
# # 3) Core evaluation
# # ---------------------------
# def evaluate_run_json(json_path: str,
#                       n_min: int,
#                       n_max: int,
#                       verbose: bool,
#                       logf: Optional[Any]) -> Dict[int, Dict[str, Any]]:
#     with open(json_path, "r", encoding="utf-8") as f:
#         obj = json.load(f)
#     code = obj.get("code", "")
#     ns: Dict[str, Any] = {}
#     try:
#         exec(code, ns, ns)
#     except Exception as e:
#         msg = f"[exec error] {json_path}: {e}"
#         if logf: print(msg, file=logf)
#         if verbose: print(msg)
#         return {}

#     try:
#         heuristic_fn, checker_fn = find_heuristic_and_checker(ns)
#     except Exception as e:
#         msg = f"[symbol error] {json_path}: {e}"
#         if logf: print(msg, file=logf)
#         if verbose: print(msg)
#         return {}

#     results: Dict[int, Dict[str, Any]] = {}
#     for n in range(n_min, n_max+1):
#         best: List[int] = []
#         for seed in range(42, 42 + 5*10 + 1, 5):   # 42,47,52,57,62,67
#             try:
#                 S = list(heuristic_fn(n, rng=None))
#                 is_free, _ = checker_fn(S)
#             except Exception as e:
#                 msg = f"[runtime] {os.path.basename(json_path)} n={n}, seed={seed}: {e}"
#                 if logf: print(msg, file=logf)
#                 if verbose: print(msg)
#                 continue
#             if is_free and len(S) > len(best):
#                 best = S
#         results[n] = {"best_len": len(best), "best_set": best}
#         if verbose and (n % 10 == 0):
#             print(f"{os.path.basename(json_path)}: n={n}, best={len(best)}")
#     return results

# # ---------------------------
# # 4) Build base bounds DF, aggregate new runs, load+merge previous CSV
# # ---------------------------
# def base_bounds_df(n_min: int, n_max: int) -> pd.DataFrame:
#     rows = []
#     for n in range(n_min, n_max + 1):
#         btype, lo, hi = bounds_of(n)
#         rows.append({"n": n, "bound_type": btype, "opt_low": lo, "opt_high": hi})
#     return pd.DataFrame(rows)

# def aggregate_new_runs_to_df(run_paths: List[str],
#                              n_min: int,
#                              n_max: int,
#                              verbose: bool,
#                              log_path: Optional[str]) -> pd.DataFrame:
#     logf = open(log_path, "a", encoding="utf-8") if log_path else None
#     results_by_run: Dict[str, Dict[int, Dict[str, Any]]] = {}
#     for p in run_paths:
#         if not os.path.exists(p):
#             msg = f"[warn] not found: {p}"
#             if logf: print(msg, file=logf)
#             if verbose: print(msg)
#             continue
#         run_name = extract_run_name(p)
#         results_by_run[run_name] = evaluate_run_json(p, n_min, n_max, verbose, logf)
#     if logf: logf.close()

#     df = base_bounds_df(n_min, n_max)
#     for run_name, res in results_by_run.items():
#         lens = []; sets = []
#         for n in range(n_min, n_max+1):
#             r = res.get(n, {"best_len": None, "best_set": []})
#             lens.append(r["best_len"])
#             sets.append(" ".join(map(str, r["best_set"])) if r["best_set"] else "")
#         df[f"{run_name}__len"] = lens
#         df[f"{run_name}__set"] = sets
#     return df

# def load_previous_summary(summary_path: str,
#                           n_min: int,
#                           n_max: int) -> pd.DataFrame:
#     prev = pd.read_csv(summary_path)
#     # 只保留 n 與各 run 欄位（__len/__set），邊界欄位重新依 n 計算，避免不同區間/舊格式干擾
#     keep_cols = ["n"] + [c for c in prev.columns if c.endswith("__len") or c.endswith("__set")]
#     prev = prev[keep_cols].copy()
#     # 只保留 n_min..n_max，並補齊缺 n（外連到完整基底）
#     base = base_bounds_df(n_min, n_max)
#     merged = base.merge(prev, on="n", how="left")
#     return merged

# def merge_prev_and_new(prev_df: Optional[pd.DataFrame],
#                        new_df: pd.DataFrame) -> pd.DataFrame:
#     """
#     以 new_df 為主（因為一定含有正確的 bounds 欄位），把 prev_df 的 run 欄位補進來。
#     若同名 run 同欄位在 new_df 也存在，保留 new_df（覆蓋舊值）。
#     """
#     if prev_df is None:
#         return new_df

#     out = new_df.copy()
#     prev_run_cols = [c for c in prev_df.columns if c.endswith("__len") or c.endswith("__set")]
#     for col in prev_run_cols:
#         if col not in out.columns:
#             out[col] = prev_df[col]
#         else:
#             # 兩邊都有，以新資料優先；舊資料補 NaN 欄位
#             out[col] = out[col].where(out[col].notna(), prev_df[col])
#     return out

# def get_run_names(df: pd.DataFrame) -> List[str]:
#     return sorted(set(c.split("__")[0] for c in df.columns if c.endswith("__len")))

# # ---------------------------
# # 5) Plot + stats (exact-opt hits)
# # ---------------------------
# def plot_overview(df: pd.DataFrame,
#                   png_out: str,
#                   n_min: int,
#                   n_max: int) -> None:
#     fig, ax = plt.subplots(figsize=(60, 6))
#     ax.set_xlabel("n")
#     ax.set_ylabel("AP-free set size")
#     ax.set_title("Salem–Spencer (no 3-term AP): runs vs. known upper bounds")
#     ax.set_xticks(list(range(n_min, n_max+1)))
#     ax.set_xticklabels([str(n) for n in range(n_min, n_max+1)], rotation=90, fontsize=7)

#     # background blocks by identical (bound_type, opt_high)
#     blocks = []
#     def b_of(n): return bounds_of(n)
#     start = n_min; cur = b_of(n_min)
#     for n in range(n_min+1, n_max+1):
#         nxt = b_of(n)
#         if nxt != cur:
#             blocks.append((start, n-1, cur))
#             start, cur = n, nxt
#     blocks.append((start, n_max, cur))

#     colors = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['#cccccc'])
#     cidx = 0
#     for a, b, (btype, lo, hi) in blocks:
#         if hi is None: 
#             continue
#         width = b - a + 1
#         c = colors[cidx % len(colors)]; cidx += 1
#         rect = Rectangle((a-0.5, 0), width, hi, alpha=0.07, edgecolor=None, facecolor=c, zorder=1)
#         ax.add_patch(rect)
#         ax.text(a, hi + 0.8, f"{hi}", fontsize=8, color=c)

#     # runs as 0→min(result+1, upper_bound) vertical bars
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
#                 if pd.isna(L): continue
#                 n_val  = int(row["n"])
#                 opt_hi = row.get("opt_high")
#                 opt_hi = int(opt_hi) if pd.notna(opt_hi) else None
#                 bar_top = int(L)
#                 if opt_hi is not None:
#                     bar_top = min(bar_top, opt_hi)
#                 xs.append(n_val + offsets[idx]); y0.append(0); y1.append(bar_top)
#             ax.vlines(xs, y0, y1, colors=color, linewidth=2.0, zorder=6, antialiased=False)
#             legend_handles.append(Line2D([0], [0], color=color, lw=2, label=run))

#     if legend_handles:
#         ax.legend(handles=legend_handles, loc="upper left", ncol=2, fontsize=8, frameon=False)
#     ax.set_xlim(n_min - 0.5, n_max + 0.5)
#     ax.set_ylim(0, 65)
#     ax.grid(True, alpha=0.25, linestyle="--", zorder=0)
#     fig.tight_layout()
#     fig.savefig(png_out, dpi=220)
#     plt.close(fig)

# def compute_exact_opt_hits(df: pd.DataFrame) -> pd.DataFrame:
#     """
#     只在 bound_type == 'exact' 的 n 上計算：
#     hit 當且僅當 <run>__len == opt_high（exact 即最優長度）
#     回傳 columns: [run, hits, total_exact_n]
#     """
#     exact_mask = (df["bound_type"] == "exact") & df["opt_high"].notna()
#     exact_df = df.loc[exact_mask, ["n", "opt_high"]].copy()
#     run_names = get_run_names(df)

#     rows = []
#     total_exact = exact_df.shape[0]
#     for run in run_names:
#         lens = df.loc[exact_mask, f"{run}__len"]
#         hits = int((lens == exact_df["opt_high"]).sum())
#         rows.append({"run": run, "hits": hits, "total_exact_n": int(total_exact)})
#     return pd.DataFrame(rows).sort_values(["hits", "run"], ascending=[False, True])

# # ---------------------------
# # 6) CLI
# # ---------------------------
# def main():
#     ap = argparse.ArgumentParser()
#     ap.add_argument("run_jsons", nargs="+", help="One or more run JSON files.")
#     ap.add_argument("--csv-out", required=True, help="Merged CSV output path.")
#     ap.add_argument("--png-out", required=True, help="Overview PNG output path.")
#     ap.add_argument("--summary-in", default=None, help="Previous summary CSV to merge.")
#     ap.add_argument("--stats-out", default=None, help="Optional CSV to save per-run exact-opt hit counts.")
#     ap.add_argument("--n-min", type=int, default=80)
#     ap.add_argument("--n-max", type=int, default=250)
#     ap.add_argument("--log", default=None, help="Optional log file for errors.")
#     ap.add_argument("--verbose", action="store_true")
#     args = ap.parse_args()

#     # 1) new runs -> df_new
#     df_new = aggregate_new_runs_to_df(args.run_jsons, args.n_min, args.n_max,
#                                       verbose=args.verbose, log_path=args.log)

#     # 2) prev summary (optional) -> df_prev
#     df_prev = None
#     if args.summary_in is not None:
#         if os.path.exists(args.summary_in):
#             df_prev = load_previous_summary(args.summary_in, args.n_min, args.n_max)
#         else:
#             print(f"[warn] --summary-in not found: {args.summary_in}")

#     # 3) merge (new preferred; fill with prev where new missing)
#     df_merged = merge_prev_and_new(df_prev, df_new)

#     # 4) save merged CSV + plot
#     df_merged.to_csv(args.csv_out, index=False)
#     plot_overview(df_merged, args.png_out, args.n_min, args.n_max)

#     # 5) compute per-run exact-opt hits (print + optional CSV)
#     hits_df = compute_exact_opt_hits(df_merged)
#     if not hits_df.empty:
#         print("\n=== Exact-optimal hits per run (only where bounds are exact) ===")
#         for _, r in hits_df.iterrows():
#             print(f"{r['run']}: {int(r['hits'])} / {int(r['total_exact_n'])}")
#         if args.stats_out:
#             hits_df.to_csv(args.stats_out, index=False)
#             print(f"[done] Stats CSV -> {args.stats_out}")
#     else:
#         print("[info] No runs or no exact-bound rows to compute hits.")

#     print(f"[done] CSV -> {args.csv_out}")
#     print(f"[done] PNG -> {args.png_out}")

# if __name__ == "__main__":
#     main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evaluate Salem–Spencer (no 3-term AP) from argument input JSON files,
merge with a previous summary.csv (optional), write one merged CSV and one overview PNG,
and report per-run counts of exact-optimal hits.

NEW:
- Run naming now appends generation number parsed from filename like
  ".../population_generation_29.json" -> "<base_run_name>_29".
  This applies to CSV column names and the plot legend.

Usage:
  python salem_spencer_eval_cli.py <run_json> [<run_json> ...] \
      --csv-out out.csv --png-out out.png \
      [--summary-in summary.csv] [--stats-out hits.csv] [--log eval.log] [--verbose]
"""
import argparse, json, os, re, inspect
from typing import Any, Dict, List, Tuple, Callable, Optional

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
from matplotlib.lines import Line2D

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

def bounds_of(n: int) -> Tuple[str, Optional[int], Optional[int]]:
    if n in EXACT_OPT:
        s = EXACT_OPT[n]
        return ("exact", 0, s)
    if n in RANGE_OPT:
        lo, hi = RANGE_OPT[n]
        return ("range", lo, hi)
    return ("unknown", None, None)

# ---------------------------
# 2) Helpers (now with generation-aware run naming)
# ---------------------------
def extract_run_base(path: str) -> str:
    """
    /.../results-ec_pop_size_8_n_pop_96-.../results/pops_best/population_generation_29.json
      -> results-ec_pop_size_8_n_pop_96-...
    """
    m = re.search(r"/(results-[^/]+)/results/", path)
    if m:
        return m.group(1)
    return os.path.basename(os.path.dirname(os.path.dirname(path))) or os.path.basename(path)

def extract_generation(path: str) -> Optional[str]:
    """
    Extract '29' from '.../population_generation_29.json'.
    If not found, return None (we'll keep base name without suffix).
    """
    m = re.search(r"population_generation_(\d+)\.json$", os.path.basename(path))
    if m:
        return m.group(1)
    return None

def extract_run_label(path: str) -> str:
    """
    Final run label used for CSV columns / legend:
      <base>_<gen>   if generation number exists
      <base>         otherwise
    """
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
# 3) Core evaluation
# ---------------------------
def evaluate_run_json(json_path: str,
                      n_min: int,
                      n_max: int,
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
    for n in range(n_min, n_max+1):
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
# 4) Build base bounds DF, aggregate new runs, load+merge previous CSV
# ---------------------------
def base_bounds_df(n_min: int, n_max: int) -> pd.DataFrame:
    rows = []
    for n in range(n_min, n_max + 1):
        btype, lo, hi = bounds_of(n)
        rows.append({"n": n, "bound_type": btype, "opt_low": lo, "opt_high": hi})
    return pd.DataFrame(rows)

def aggregate_new_runs_to_df(run_paths: List[str],
                             n_min: int,
                             n_max: int,
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
        run_label = extract_run_label(p)   # <-- generation-aware name
        results_by_run[run_label] = evaluate_run_json(p, n_min, n_max, verbose, logf)
    if logf: logf.close()

    df = base_bounds_df(n_min, n_max)
    for run_label, res in results_by_run.items():
        lens = []; sets = []
        for n in range(n_min, n_max+1):
            r = res.get(n, {"best_len": None, "best_set": []})
            lens.append(r["best_len"])
            sets.append(" ".join(map(str, r["best_set"])) if r["best_set"] else "")
        df[f"{run_label}__len"] = lens
        df[f"{run_label}__set"] = sets
    return df

def load_previous_summary(summary_path: str,
                          n_min: int,
                          n_max: int) -> pd.DataFrame:
    prev = pd.read_csv(summary_path)
    keep_cols = ["n"] + [c for c in prev.columns if c.endswith("__len") or c.endswith("__set")]
    prev = prev[keep_cols].copy()
    base = base_bounds_df(n_min, n_max)
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
# 5) Plot + stats (exact-opt hits)
# ---------------------------
def plot_overview(df: pd.DataFrame,
                  png_out: str,
                  n_min: int,
                  n_max: int) -> None:
    fig, ax = plt.subplots(figsize=(120, 6))
    ax.set_xlabel("n")
    ax.set_ylabel("AP-free set size")
    ax.set_title("Salem–Spencer (no 3-term AP): runs vs. known upper bounds")
    ax.set_xticks(list(range(n_min, n_max+1)))
    ax.set_xticklabels([str(n) for n in range(n_min, n_max+1)], rotation=90, fontsize=7)

    # background blocks by identical (bound_type, opt_high)
    blocks = []
    def b_of(n): return bounds_of(n)
    start = n_min; cur = b_of(n_min)
    for n in range(n_min+1, n_max+1):
        nxt = b_of(n)
        if nxt != cur:
            blocks.append((start, n-1, cur))
            start, cur = n, nxt
    blocks.append((start, n_max, cur))

    colors = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['#cccccc'])
    cidx = 0
    for a, b, (btype, lo, hi) in blocks:
        if hi is None: 
            continue
        width = b - a + 1
        c = colors[cidx % len(colors)]; cidx += 1
        rect = Rectangle((a-0.5, 0), width, hi, alpha=0.07, edgecolor=None, facecolor=c, zorder=1)
        ax.add_patch(rect)
        ax.text(a, hi + 0.8, f"{hi}", fontsize=8, color=c)

    # runs as 0→min(result+1, upper_bound) vertical bars
    run_names = get_run_names(df)  # now includes "_<gen>" suffix
    palette = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['#111'])
    legend_handles: List[Line2D] = []
    if run_names:
        spacing = 0.18
        offsets = [spacing*(i - (len(run_names)-1)/2.0) for i in range(len(run_names))]
        for idx, run in enumerate(run_names):
            xs, y0, y1 = [], [], []
            color = palette[idx % len(palette)]
            for _, row in df.iterrows():
                L = row.get(f"{run}__len")
                if pd.isna(L): continue
                n_val  = int(row["n"])
                opt_hi = row.get("opt_high")
                opt_hi = int(opt_hi) if pd.notna(opt_hi) else None
                bar_top = int(L) 
                if opt_hi is not None:
                    bar_top = min(bar_top, opt_hi)
                xs.append(n_val + offsets[idx]); y0.append(0); y1.append(bar_top)
            ax.vlines(xs, y0, y1, colors=color, linewidth=2.0, zorder=6, antialiased=False)
            legend_handles.append(Line2D([0], [0], color=color, lw=2, label=run))

    if legend_handles:
        ax.legend(handles=legend_handles, loc="upper left", ncol=2, fontsize=8, frameon=False)
    ax.set_xlim(n_min - 0.5, n_max + 0.5)
    ax.set_ylim(0, 65)
    ax.grid(True, alpha=0.25, linestyle="--", zorder=0)
    fig.tight_layout()
    fig.savefig(png_out, dpi=220)
    plt.close(fig)

def compute_exact_opt_hits(df: pd.DataFrame) -> pd.DataFrame:
    """
    Count hits only where bounds are exact:
    hit iff <run>__len == opt_high.
    Returns columns: [run, hits, total_exact_n]
    """
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
    ap.add_argument("run_jsons", nargs="+", help="One or more run JSON files.")
    ap.add_argument("--csv-out", required=True, help="Merged CSV output path.")
    ap.add_argument("--png-out", required=True, help="Overview PNG output path.")
    ap.add_argument("--summary-in", default=None, help="Previous summary CSV to merge.")
    ap.add_argument("--stats-out", default=None, help="Optional CSV to save per-run exact-opt hit counts.")
    ap.add_argument("--n-min", type=int, default=80)
    ap.add_argument("--n-max", type=int, default=250)
    ap.add_argument("--log", default=None, help="Optional log file for errors.")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    # 1) new runs -> df_new
    df_new = aggregate_new_runs_to_df(args.run_jsons, args.n_min, args.n_max,
                                      verbose=args.verbose, log_path=args.log)

    # 2) prev summary (optional) -> df_prev
    df_prev = None
    if args.summary_in is not None:
        if os.path.exists(args.summary_in):
            df_prev = load_previous_summary(args.summary_in, args.n_min, args.n_max)
        else:
            print(f"[warn] --summary-in not found: {args.summary_in}")

    # 3) merge (new preferred; fill with prev where new missing)
    df_merged = merge_prev_and_new(df_prev, df_new)

    # 4) save merged CSV + plot
    df_merged.to_csv(args.csv_out, index=False)
    plot_overview(df_merged, args.png_out, args.n_min, args.n_max)

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
