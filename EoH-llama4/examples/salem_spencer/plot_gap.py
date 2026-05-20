#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import pandas as pd
import matplotlib.pyplot as plt
from typing import List

def get_run_names(df: pd.DataFrame) -> List[str]:
    return sorted(set(c.split("__")[0] for c in df.columns if c.endswith("__len")))

def main():
    ap = argparse.ArgumentParser(
        description="Plot optimal gap (opt_high - run_len) per n for each run; also compute per-run average gap."
    )
    ap.add_argument("--summary-csv", required=True, help="Path to merged/summary CSV.")
    ap.add_argument("--png-out", required=True, help="Output PNG path for the line chart.")
    ap.add_argument("--avg-out", default=None, help="Optional CSV to save per-run average gaps.")
    ap.add_argument("--mode", choices=["exact", "all"], default="exact",
                    help="exact: only rows where bound_type=='exact'; all: any row with opt_high present.")
    ap.add_argument("--min-n", type=int, default=None, help="Optional lower n bound for plotting/stats.")
    ap.add_argument("--max-n", type=int, default=None, help="Optional upper n bound for plotting/stats.")
    args = ap.parse_args()

    df = pd.read_csv(args.summary_csv)

    # Filter rows to compute/plot gaps on
    if args.mode == "exact":
        mask = (df["bound_type"] == "exact") & df["opt_high"].notna()
        title_suffix = "(exact only)"
    else:
        mask = df["opt_high"].notna()
        title_suffix = "(exact + range)"

    if args.min_n is not None:
        mask &= (df["n"] >= args.min_n)
    if args.max_n is not None:
        mask &= (df["n"] <= args.max_n)

    work = df.loc[mask].copy()
    if work.empty:
        raise SystemExit("No rows to compute gaps on (check --mode / n-range).")

    run_names = get_run_names(df)
    if not run_names:
        raise SystemExit("No run columns (*__len) found in the CSV.")

    # Compute per-run per-n gap series and average gaps
    avg_rows = []
    plt.figure(figsize=(18, 6))
    ax = plt.gca()

    for i, run in enumerate(run_names):
        len_col = f"{run}__len"
        if len_col not in work.columns:
            continue

        # gap = opt_high - run_len (skip where run_len is NaN)
        sub = work[["n", "opt_high", len_col]].dropna(subset=[len_col, "opt_high"]).copy()
        if sub.empty:
            continue
        sub["gap"] = sub["opt_high"] - sub[len_col]

        # Plot gap vs n
        ax.plot(sub["n"].values, sub["gap"].values, label=run, linewidth=1.8)

        # Average gap for this run (over the rows we used)
        avg_gap = float(sub["gap"].mean())
        avg_rows.append({"run": run, "avg_gap": avg_gap, "count_n": int(sub.shape[0])})

    # Finalize plot
    ax.set_xlabel("n")
    ax.set_ylabel("Optimal gap (opt_high - length)")
    ax.set_title(f"Optimal gap per n for each run {title_suffix}")
    ax.grid(True, alpha=0.3, linestyle="--")
    if run_names:
        ax.legend(ncol=2, fontsize=8, frameon=False, loc="upper right")
    plt.tight_layout()
    plt.savefig(args.png_out, dpi=220)
    plt.close()

    # Save averages (optional) and echo to console
    if avg_rows:
        avg_df = pd.DataFrame(avg_rows).sort_values(["avg_gap", "run"], ascending=[True, True])
        if args.avg_out:
            avg_df.to_csv(args.avg_out, index=False)
        # Print a quick summary
        print("=== Average optimal gap per run ===")
        for _, r in avg_df.iterrows():
            print(f"{r['run']}: avg_gap={r['avg_gap']:.3f} over {int(r['count_n'])} n")
    else:
        print("No averages computed (no valid rows after filtering).")

if __name__ == "__main__":
    main()
