# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# Evaluate Salem–Spencer (no 3-term AP) runs from argument input JSON files,
# and output a combined CSV + one overview PNG.

# Each input JSON must contain keys: ["algorithm", "code", "objective", "null"].
# We exec the "code" to obtain `heuristic(n, rng=None)` and `is_three_ap_free(S)`,
# then run the provided loop for n=80..250 and seeds {42,47,52,57,62,67}.

# Usage:
#   python salem_spencer_eval_cli.py <run_json> [<run_json> ...] \
#       --csv-out out.csv --png-out out.png
# """
# import argparse
# import json
# import os
# import re
# from typing import Any, Dict, List, Tuple

# import matplotlib.pyplot as plt
# import pandas as pd
# from matplotlib.patches import Rectangle

# # ---------------------------
# # 1) Embed known upper bounds / ranges (digitized from your tables/images)
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

# def bounds_of(n: int) -> Tuple[str, int, int]:
#     """Return ('exact'|'range'|'unknown', low, high)."""
#     if n in EXACT_OPT:
#         s = EXACT_OPT[n]
#         return ("exact", 0, s)
#     if n in RANGE_OPT:
#         lo, hi = RANGE_OPT[n]
#         return ("range", 0, hi)
#     return ("unknown", None, None)

# # ---------------------------
# # 2) Run loading & evaluation
# # ---------------------------

# def extract_run_name(path: str) -> str:
#     """
#     /.../results-ec_pop_size_8_n_pop_96-minimize-absolute-len-flash-dynamic-reasoning/results/pops_best/population_generation_29.json
#       -> results-ec_pop_size_8_n_pop_96-minimize-absolute-len-flash-dynamic-reasoning
#     """
#     m = re.search(r"/(results-[^/]+)/results/", path)
#     if m:
#         return m.group(1)
#     # fallback: parent folder(s)
#     return os.path.basename(os.path.dirname(os.path.dirname(path))) or os.path.basename(path)

# def evaluate_run_json(json_path: str,
#                       n_min: int = 80,
#                       n_max: int = 250,
#                       verbose: bool = False) -> Dict[int, Dict[str, Any]]:
#     """
#     Load a JSON (must have key 'code'), exec it to obtain `heuristic` and `is_three_ap_free`,
#     then evaluate for n in [n_min..n_max] with the requested seed schedule.
#     Returns: { n: {'best_len': int, 'best_set': List[int]} }
#     """
#     with open(json_path, "r", encoding="utf-8") as f:
#         obj = json.load(f)
#     code = obj.get("code", "")
#     ns: Dict[str, Any] = {}
#     try:
#         exec(code, ns, ns)  # expect to define heuristic, is_three_ap_free
#     except Exception as e:
#         if verbose:
#             print(f"[exec error] {json_path}: {e}")
#         return {}

#     if "heuristic" not in ns or "is_three_ap_free" not in ns:
#         if verbose:
#             missing = [k for k in ("heuristic", "is_three_ap_free") if k not in ns]
#             print(f"[missing] {json_path}: {missing}")
#         return {}

#     out: Dict[int, Dict[str, Any]] = {}
#     for n in range(n_min, n_max + 1):
#         best: List[int] = []
#         for seed in range(42, 42 + 5*5 + 1, 5):  # 42..67 step 5 (42,47,52,57,62,67)
#             try:
#                 S = list(ns["heuristic"](n, rng=None))
#                 is_free, witness = ns["is_three_ap_free"](S)
#             except Exception as e:
#                 if verbose:
#                     print(f"[runtime] {json_path} n={n}, seed={seed}: {e}")
#                 continue
#             if is_free and len(S) > len(best):
#                 best = S
#         out[n] = {"best_len": len(best), "best_set": best}
#         if verbose and (n % 10 == 0):
#             print(f"{os.path.basename(json_path)}: n={n}, best={len(best)}")
#     return out

# # ---------------------------
# # 3) Aggregation & plotting
# # ---------------------------

# def aggregate_to_dataframe(run_paths: List[str],
#                            n_min: int = 80,
#                            n_max: int = 250) -> pd.DataFrame:
#     results_by_run: Dict[str, Dict[int, Dict[str, Any]]] = {}
#     for p in run_paths:
#         if not os.path.exists(p):
#             print(f"[warn] not found: {p}")
#             continue
#         run_name = extract_run_name(p)
#         results_by_run[run_name] = evaluate_run_json(p, n_min=n_min, n_max=n_max)

#     rows: List[Dict[str, Any]] = []
#     for n in range(n_min, n_max + 1):
#         btype, lo, hi = bounds_of(n)
#         row: Dict[str, Any] = {"n": n, "bound_type": btype, "opt_low": lo, "opt_high": hi}
#         for run_name, res in results_by_run.items():
#             r = res.get(n, {"best_len": None, "best_set": []})
#             row[f"{run_name}__len"] = r["best_len"]
#             row[f"{run_name}__set"] = " ".join(map(str, r["best_set"])) if r["best_set"] else ""
#         rows.append(row)
#     return pd.DataFrame(rows)

# def plot_overview(df: pd.DataFrame,
#                   png_out: str,
#                   n_min: int = 80,
#                   n_max: int = 250) -> None:
#     fig, ax = plt.subplots(figsize=(18, 6))
#     ax.set_xlabel("n")
#     ax.set_ylabel("AP-free set size")
#     ax.set_title("Salem–Spencer (no 3-term AP): runs vs. known upper bounds")

#     # Build contiguous background blocks by (opt_low, opt_high, bound_type)
#     blocks: List[Tuple[int,int,Tuple[str,int,int]]] = []
#     def b_of(n: int): 
#         return bounds_of(n)
#     start = n_min
#     cur = b_of(n_min)
#     for n in range(n_min + 1, n_max + 1):
#         if b_of(n) != cur:
#             blocks.append((start, n - 1, cur))
#             start, cur = n, b_of(n)
#     blocks.append((start, n_max, cur))

#     # cycle default mpl colors for blocks
#     colors = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['#cccccc'])
#     cidx = 0
#     for a, b, (btype, lo, hi) in blocks:
#         if lo is None:  # unknown bounds
#             continue
#         width = b - a + 1
#         c = colors[cidx % len(colors)]
#         cidx += 1

#         # big translucent band for [lo..hi]
#         rect = Rectangle((a-0.5, lo-0.5), width, (hi - lo + 1), alpha=0.08,
#                          edgecolor=None, facecolor=c)
#         ax.add_patch(rect)

#         # thin darker band: exact -> at lo; range -> at hi
#         band_y = lo if (btype == "exact") else hi
#         rect2 = Rectangle((a-0.5, band_y-0.5), width, 1.0, alpha=0.18,
#                           edgecolor=None, facecolor=c)
#         ax.add_patch(rect2)

#         # annotate at start of block
#         ax.text(a, band_y + 0.8, f"{hi if btype=='range' else lo}", fontsize=8, color=c)

#     # plot runs
#     run_names = sorted(set(
#         n.split("__")[0] for n in df.columns if n.endswith("__len")
#     ))
#     if run_names:
#         spacing = 0.15
#         offsets = [spacing*(i - (len(run_names)-1)/2.0) for i in range(len(run_names))]
#         for idx, run in enumerate(run_names):
#             xs, ys = [], []
#             for _, row in df.iterrows():
#                 L = row.get(f"{run}__len")
#                 if pd.isna(L): 
#                     continue
#                 xs.append(row["n"] + offsets[idx])
#                 ys.append(int(L))
#             ax.plot(xs, ys, marker="|", linestyle="None", label=run)

#     ax.set_xlim(n_min - 0.5, n_max + 0.5)
#     ax.set_ylim(0, 65)
#     ax.grid(True, alpha=0.25, linestyle="--")
#     if run_names:
#         ax.legend(loc="upper left", ncol=2, fontsize=8, frameon=False)
#     fig.tight_layout()
#     fig.savefig(png_out, dpi=200)
#     plt.close(fig)

# # ---------------------------
# # 4) CLI
# # ---------------------------

# def main():
#     ap = argparse.ArgumentParser(
#         description="Evaluate Salem–Spencer runs (AP-free) and plot overview."
#     )
#     ap.add_argument("run_jsons", nargs="+",
#                     help="One or more run JSON files (each contains 'code').")
#     ap.add_argument("--csv-out", required=True, help="Output CSV filename.")
#     ap.add_argument("--png-out", required=True, help="Output PNG filename.")
#     ap.add_argument("--n-min", type=int, default=80)
#     ap.add_argument("--n-max", type=int, default=250)
#     ap.add_argument("--verbose", action="store_true")
#     args = ap.parse_args()

#     df = aggregate_to_dataframe(args.run_jsons, n_min=args.n_min, n_max=args.n_max)
#     df.to_csv(args.csv_out, index=False)
#     plot_overview(df, args.png_out, n_min=args.n_min, n_max=args.n_max)

#     print(f"[done] CSV -> {args.csv_out}")
#     print(f"[done] PNG -> {args.png_out}")

# if __name__ == "__main__":
#     main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evaluate Salem–Spencer (no 3-term AP) from argument input JSON files,
write one CSV and one overview PNG.

JSON must contain keys: ["algorithm", "code", "objective", "null"].
We exec the "code". We then try to obtain a usable `heuristic(n, rng=None)`:
  1) prefer a global function named `heuristic`;
  2) else search classes that define `heuristic(self, n, rng=None)` and try to
     instantiate with no-arg, then call obj.heuristic(...).

If `is_three_ap_free(S)` is missing, we use a built-in checker.

Plot: background shows 0→upper_bound blocks; run results are thin rectangles
(or vertical markers) on top of the background.

Usage:
  python salem_spencer_eval_cli.py <run_json> [<run_json> ...] \
      --csv-out out.csv --png-out out.png [--log eval.log] [--verbose]
"""
import argparse, json, os, re, inspect, math
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
        return ("exact", 0, s)      # 你要的 0 → 上界 畫法
    if n in RANGE_OPT:
        lo, hi = RANGE_OPT[n]
        return ("range", 0, hi)     # 0 → 最高已知上界
    return ("unknown", None, None)

# ---------------------------
# 2) Helpers
# ---------------------------
def extract_run_name(path: str) -> str:
    m = re.search(r"/(results-[^/]+)/results/", path)
    if m:
        return m.group(1)
    return os.path.basename(os.path.dirname(os.path.dirname(path))) or os.path.basename(path)

def builtin_is_three_ap_free(S: List[int]) -> Tuple[bool, Tuple[int,int,int]]:
    """Return (is_free, witness). witness=(a,b,c) if found a 3-term AP."""
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
    """Return (heuristic_callable, is_three_ap_free_callable). Raises if not found."""
    # 1) global function heuristic
    if callable(ns.get("heuristic", None)):
        heuristic_fn = ns["heuristic"]
        # checker
        checker = ns.get("is_three_ap_free", None)
        if not callable(checker):
            checker = builtin_is_three_ap_free
        return heuristic_fn, checker

    # 2) search classes that define heuristic(self, n, rng=None)
    for name, obj in ns.items():
        if inspect.isclass(obj):
            if hasattr(obj, "heuristic") and callable(getattr(obj, "heuristic")):
                try:
                    inst = obj()  # try no-arg ctor
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
                is_free, witness = checker_fn(S)
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
# 4) Aggregation & plotting
# ---------------------------
def aggregate_to_dataframe(run_paths: List[str],
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
        run_name = extract_run_name(p)
        results_by_run[run_name] = evaluate_run_json(p, n_min, n_max, verbose, logf)
    if logf: logf.close()

    rows: List[Dict[str, Any]] = []
    for n in range(n_min, n_max + 1):
        btype, lo, hi = bounds_of(n)
        row: Dict[str, Any] = {"n": n, "bound_type": btype, "opt_low": lo, "opt_high": hi}
        for run_name, res in results_by_run.items():
            r = res.get(n, {"best_len": None, "best_set": []})
            row[f"{run_name}__len"] = r["best_len"]
            row[f"{run_name}__set"] = " ".join(map(str, r["best_set"])) if r["best_set"] else ""
        rows.append(row)
    return pd.DataFrame(rows)

def plot_overview(df: pd.DataFrame,
                  png_out: str,
                  n_min: int,
                  n_max: int) -> None:
    fig, ax = plt.subplots(figsize=(60, 6))
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
        if b_of(n) != cur:
            blocks.append((start, n-1, cur))
            start, cur = n, b_of(n)
    blocks.append((start, n_max, cur))

    colors = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['#cccccc'])
    cidx = 0
    for a, b, (btype, lo, hi) in blocks:
        if hi is None: 
            continue
        width = b - a + 1
        c = colors[cidx % len(colors)]; cidx += 1

        # 0 → hi 的大背景
        # rect = Rectangle((a-0.5, 0-0.5), width, (hi - 0 + 1), alpha=0.07,
        #                  edgecolor=None, facecolor=c, zorder=1)
        rect = Rectangle((a-0.5, 0), width, hi, alpha=0.07, edgecolor=None, facecolor=c, zorder=1)

        ax.add_patch(rect)

        # 「較細長」的矩形條（在 high 處），讓 block 的 top 更明顯
        # rect2 = Rectangle((a-0.5, hi-0.5), width, 1.0, alpha=0.18,
        #                   edgecolor=None, facecolor=c, zorder=2)
        # ax.add_patch(rect2)

        ax.text(a, hi + 0.8, f"{hi}", fontsize=8, color=c)

    # runs
    # run_names = sorted(set(c.split("__")[0] for c in df.columns if c.endswith("__len")))
    # if run_names:
    #     spacing = 0.18
    #     offsets = [spacing*(i - (len(run_names)-1)/2.0) for i in range(len(run_names))]

    #     for idx, run in enumerate(run_names):
    #         xs, ys = [], []
    #         for _, row in df.iterrows():
    #             L = row.get(f"{run}__len")
    #             if pd.isna(L): 
    #                 continue
    #             xs.append(row["n"] + offsets[idx])
    #             ys.append(int(L))
    #         # 用豎線 + 高 zorder 疊在最上層
    #         ax.plot(xs, ys, marker="|", markersize=12, linestyle="None",
    #                 label=run, zorder=6)
    #         # 也可描一條很窄的矩形帶（視覺像細長矩形）
    #         for x, y in zip(xs, ys):
    #             rect_run = Rectangle((x-0.08, y-0.5), 0.16, 1.0, alpha=0.9,
    #                                  edgecolor=None, facecolor="black", zorder=5)
    #             ax.add_patch(rect_run)

    # ax.set_xlim(n_min - 0.5, n_max + 0.5)
    # ax.set_ylim(0, 65)
    # ax.grid(True, alpha=0.25, linestyle="--", zorder=0)
    # if run_names:
    #     ax.legend(loc="upper left", ncol=2, fontsize=8, frameon=False)
    # fig.tight_layout()
    # fig.savefig(png_out, dpi=220)
    # plt.close(fig)
    run_names = sorted(set(c.split("__")[0] for c in df.columns if c.endswith("__len")))
    colors = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['#111'])
    if run_names:
        spacing = 0.18
        offsets = [spacing*(i - (len(run_names)-1)/2.0) for i in range(len(run_names))]

        # 用 proxy 建 legend，不要再用 ax.plot 疊 marker
        legend_handles = []

        for idx, run in enumerate(run_names):
            xs, y0, y1 = [], [], []
            color = colors[idx % len(colors)]

            for _, row in df.iterrows():
                L = row.get(f"{run}__len")
                if pd.isna(L):
                    continue
                n_val  = int(row["n"])
                opt_hi = row.get("opt_high")
                opt_hi = int(opt_hi) if pd.notna(opt_hi) else None

                # bar_top = min(upper bound, result+1)
                bar_top = int(L) + 1
                if opt_hi is not None:
                    bar_top = min(bar_top, opt_hi)

                xs.append(n_val + offsets[idx])
                y0.append(0)
                y1.append(bar_top)

            # 單一層：用 vlines 畫 0 -> bar_top 的直線；關閉抗鋸齒避免模糊邊緣
            ax.vlines(xs, y0, y1, colors=color, linewidth=2.0, zorder=6, antialiased=False)

            # 建 legend handle
            legend_handles.append(Line2D([0], [0], color=color, lw=2, label=run))

    # 以 proxy handles 建 legend（不會再觸發「沒有標籤的 artist」）
    ax.legend(handles=legend_handles, loc="upper left", ncol=2, fontsize=8, frameon=False)
    ax.set_xlim(n_min - 0.5, n_max + 0.5)
    ax.set_ylim(0, 65)
    ax.grid(True, alpha=0.25, linestyle="--", zorder=0)
    # if run_names:
    #     ax.legend(loc="upper left", ncol=2, fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(png_out, dpi=220)
    plt.close(fig)
# ---------------------------
# 5) CLI
# ---------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_jsons", nargs="+", help="One or more run JSON files.")
    ap.add_argument("--csv-out", required=True)
    ap.add_argument("--png-out", required=True)
    ap.add_argument("--n-min", type=int, default=80)
    ap.add_argument("--n-max", type=int, default=250)
    ap.add_argument("--log", default=None, help="Optional log file for errors.")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    df = aggregate_to_dataframe(args.run_jsons, args.n_min, args.n_max,
                                verbose=args.verbose, log_path=args.log)
    df.to_csv(args.csv_out, index=False)
    plot_overview(df, args.png_out, args.n_min, args.n_max)
    print(f"[done] CSV -> {args.csv_out}")
    print(f"[done] PNG -> {args.png_out}")

if __name__ == "__main__":
    main()
