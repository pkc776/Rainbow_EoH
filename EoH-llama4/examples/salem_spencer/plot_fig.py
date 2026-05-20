# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-

# import argparse
# import json
# import os
# import re
# from glob import glob
# from typing import Any, Dict, List, Tuple, Optional

# import numpy as np
# import matplotlib.pyplot as plt


# def natural_step_key(path: str) -> Tuple[int, str]:
#     """
#     用檔名中的第一個整數作為排序 key（step 編號）。
#     找不到數字則回傳極大值，並以完整路徑字典序作第二 key。
#     """
#     name = os.path.basename(path)
#     m = re.search(r'(\d+)', name)
#     if m:
#         return (int(m.group(1)), name)
#     # 沒有數字 → 擺到後面，並用名稱保底排序
#     return (10**12, name)


# def load_json(path: str) -> Any:
#     with open(path, "r", encoding="utf-8") as f:
#         return json.load(f)


# def extract_objectives_from_item(item: Any) -> List[float]:
#     """
#     從單一 dict 或 list[dict] 裡取出 objective 值（轉為 float）。
#     過濾 None/NaN/非數字。
#     - 若是 dict：回傳單元素 list
#     - 若是 list：回傳多個值
#     其他型別 → 回傳空 list
#     """
#     def safe_to_float(x: Any) -> Optional[float]:
#         try:
#             v = float(x)
#             if np.isnan(v):
#                 return None
#             return v
#         except Exception:
#             return None

#     if isinstance(item, dict):
#         val = safe_to_float(item.get("objective", None))
#         return [val] if val is not None else []
#     elif isinstance(item, list):
#         vals = []
#         for it in item:
#             if isinstance(it, dict):
#                 v = safe_to_float(it.get("objective", None))
#                 if v is not None:
#                     vals.append(v)
#         return vals
#     else:
#         return []


# def collect_steps(input_dir: str) -> Tuple[List[int], List[List[float]], bool]:
#     """
#     讀取資料夾內的所有 .json 檔，依步數排序後逐檔抽取 objectives。
#     回傳：
#       steps            : step 整數列表（與 files 一一對應）
#       objectives_by_step: 每個 step 的 objective 值列表（單一或多個）
#       any_multi        : 是否存在「某檔案有多個 dict」的情況
#     """
#     files = sorted(glob(os.path.join(input_dir, "*.json")), key=natural_step_key)
#     if not files:
#         raise FileNotFoundError(f"No .json files found under: {input_dir}")

#     steps: List[int] = []
#     all_obj_lists: List[List[float]] = []
#     any_multi = False

#     for path in files:
#         step_num, _ = natural_step_key(path)
#         data = load_json(path)
#         objs = extract_objectives_from_item(data)
#         if not objs:
#             # 允許空檔（沒有有效 objective），用 np.nan 佔位，避免中斷
#             objs = [np.nan]
#         if len(objs) > 1:
#             any_multi = True

#         steps.append(step_num if step_num != 10**12 else len(steps))
#         all_obj_lists.append(objs)

#     return steps, all_obj_lists, any_multi


# def plot_single_line(steps: List[int], obj_single: List[float], out_dir: str) -> None:
#     plt.figure(figsize=(10, 6), dpi=110)
#     plt.plot(steps, obj_single, marker="o", linewidth=2)
#     plt.title("Objective Across Steps (Single per Step)")
#     plt.xlabel("Step")
#     plt.ylabel("Objective")
#     plt.grid(True, linestyle="--", alpha=0.5)

#     ymin = np.nanmin(obj_single)
#     ymax = np.nanmax(obj_single)
#     pad = (ymax - ymin) * 0.1 if np.isfinite(ymax - ymin) else 1.0
#     plt.ylim(ymin - pad, ymax + pad)

#     png_path = os.path.join(out_dir, "results_single_line.png")
#     pdf_path = os.path.join(out_dir, "results_single_line.pdf")
#     plt.tight_layout()
#     plt.savefig(png_path)
#     plt.savefig(pdf_path)
#     plt.close()
#     print(f"Saved: {png_path}\nSaved: {pdf_path}")


# def plot_quantile_lines(
#     steps: List[int],
#     obj_multi: List[List[float]],
#     out_dir: str
# ) -> None:
#     # 對每個 step 計算 min / median / max
#     mins, meds, maxs = [], [], []
#     for vals in obj_multi:
#         arr = np.array(vals, dtype=float)
#         if arr.size == 0 or np.all(np.isnan(arr)):
#             mins.append(np.nan)
#             meds.append(np.nan)
#             maxs.append(np.nan)
#         else:
#             mins.append(np.nanmin(arr))
#             meds.append(np.nanmedian(arr))
#             maxs.append(np.nanmax(arr))

#     plt.figure(figsize=(10, 6), dpi=110)
#     # 三條量化線
#     plt.plot(steps, mins, marker="o", linewidth=2, label="Min")
#     plt.plot(steps, meds, marker="o", linewidth=2, label="Median")
#     plt.plot(steps, maxs, marker="o", linewidth=2, label="Max")

#     # 同步也畫每個 step 的「垂直線」方便肉眼看該 step 的範圍（min-max）
#     for x, lo, hi in zip(steps, mins, maxs):
#         if np.isfinite(lo) and np.isfinite(hi):
#             plt.vlines(x, lo, hi, linestyles="dotted", alpha=0.6)

#     plt.title("Objective Quantiles Across Steps (Min / Median / Max)")
#     plt.xlabel("Step")
#     plt.ylabel("Objective")
#     plt.legend()
#     plt.grid(True, linestyle="--", alpha=0.5)

#     # 動態 y 軸
#     all_vals = np.array(mins + meds + maxs, dtype=float)
#     finite_vals = all_vals[np.isfinite(all_vals)]
#     if finite_vals.size:
#         ymin, ymax = np.min(finite_vals), np.max(finite_vals)
#         pad = (ymax - ymin) * 0.1 if np.isfinite(ymax - ymin) else 1.0
#         plt.ylim(ymin - pad, ymax + pad)

#     png_path = os.path.join(out_dir, "results_quantiles.png")
#     pdf_path = os.path.join(out_dir, "results_quantiles.pdf")
#     plt.tight_layout()
#     plt.savefig(png_path)
#     plt.savefig(pdf_path)
#     plt.close()
#     print(f"Saved: {png_path}\nSaved: {pdf_path}")


# def main():
#     parser = argparse.ArgumentParser(
#         description="Generate experiment result plots from per-step JSON files."
#     )
#     parser.add_argument(
#         "--input_dir",
#         required=True,
#         help="Folder containing per-step JSON files. Each file = one step; content is a dict or a list[dict].",
#     )
#     args = parser.parse_args()
#     input_dir = os.path.abspath(args.input_dir)

#     if not os.path.isdir(input_dir):
#         raise NotADirectoryError(f"Invalid directory: {input_dir}")

#     steps, obj_lists, any_multi = collect_steps(input_dir)

#     # 若「全部檔案」皆為單一 dict（每步只有一個 objective），畫單線
#     if not any_multi and all(len(v) == 1 for v in obj_lists):
#         single_vals = [v[0] if v else np.nan for v in obj_lists]
#         plot_single_line(steps, single_vals, input_dir)
#     else:
#         # 只要有任一步是多個 dict，就畫量化線（min/median/max）
#         plot_quantile_lines(steps, obj_lists, input_dir)

#     print("Done.")


# if __name__ == "__main__":
#     main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
from glob import glob
from typing import Any, List, Tuple, Optional

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


# =========================
# Global seaborn style
# =========================
sns.set_theme(
    style="whitegrid",
    # context="talk",
    font_scale=0.9,
)


def natural_step_key(path: str) -> Tuple[int, str]:
    name = os.path.basename(path)
    m = re.search(r"(\d+)", name)
    if m:
        return (int(m.group(1)), name)
    return (10**12, name)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_objectives_from_item(item: Any) -> List[float]:
    def safe_to_float(x: Any) -> Optional[float]:
        try:
            v = float(x)
            if np.isnan(v):
                return None
            return v
        except Exception:
            return None

    if isinstance(item, dict):
        val = safe_to_float(item.get("objective", None))
        return [val] if val is not None else []
    elif isinstance(item, list):
        vals = []
        for it in item:
            if isinstance(it, dict):
                v = safe_to_float(it.get("objective", None))
                if v is not None:
                    vals.append(v)
        return vals
    else:
        return []


def collect_steps(input_dir: str) -> Tuple[List[int], List[List[float]], bool]:
    files = sorted(glob(os.path.join(input_dir, "*.json")), key=natural_step_key)
    if not files:
        raise FileNotFoundError(f"No .json files found under: {input_dir}")

    steps: List[int] = []
    all_obj_lists: List[List[float]] = []
    any_multi = False

    for path in files:
        step_num, _ = natural_step_key(path)
        data = load_json(path)
        objs = extract_objectives_from_item(data)
        if not objs:
            objs = [np.nan]
        if len(objs) > 1:
            any_multi = True

        steps.append(step_num if step_num != 10**12 else len(steps))
        all_obj_lists.append(objs)

    return steps, all_obj_lists, any_multi


# =========================
# Turning point logic
# =========================
def turning_point_indices_by_change(ys: List[float]) -> List[int]:
    if not ys:
        return []

    idxs = [0]
    prev = ys[0]
    prev_ok = np.isfinite(prev)

    for i in range(1, len(ys)):
        cur = ys[i]
        cur_ok = np.isfinite(cur)

        if not prev_ok or not cur_ok:
            prev, prev_ok = cur, cur_ok
            continue

        if cur != prev:
            idxs.append(i)

        prev, prev_ok = cur, cur_ok

    return idxs


def annotate_values(ax, xs, ys, indices, fmt="{:.6g}", dy=6):
    for i in indices:
        x = xs[i]
        y = ys[i]
        if not (np.isfinite(x) and np.isfinite(y)):
            continue
        ax.annotate(
            fmt.format(float(y)),
            xy=(x, y),
            xytext=(0, dy),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            color="black",
        )


# =========================
# Plotting
# =========================
def plot_single_line(steps: List[int], obj_single: List[float], out_dir: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 6), dpi=120)

    sns.lineplot(
        x=steps,
        y=obj_single,
        marker="o",
        linewidth=2.5,
        ax=ax,
    )

    ax.set_title("Objective Across Steps (Single per Step)")
    ax.set_xlabel("Step")
    ax.set_ylabel("Objective")

    ymin = np.nanmin(obj_single)
    ymax = np.nanmax(obj_single)
    pad = (ymax - ymin) * 0.1 if np.isfinite(ymax - ymin) else 1.0
    ax.set_ylim(ymin - pad, ymax + pad)

    # only turning points
    idx = turning_point_indices_by_change(obj_single)
    annotate_values(ax, steps, obj_single, idx)

    png = os.path.join(out_dir, "results_single_line.png")
    pdf = os.path.join(out_dir, "results_single_line.pdf")
    fig.tight_layout()
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)

    print(f"Saved: {png}\nSaved: {pdf}")


def plot_quantile_lines(
    steps: List[int],
    obj_multi: List[List[float]],
    out_dir: str,
) -> None:
    mins, meds, maxs = [], [], []
    for vals in obj_multi:
        arr = np.asarray(vals, dtype=float)
        if arr.size == 0 or np.all(np.isnan(arr)):
            mins.append(np.nan)
            meds.append(np.nan)
            maxs.append(np.nan)
        else:
            mins.append(np.nanmin(arr))
            meds.append(np.nanmedian(arr))
            maxs.append(np.nanmax(arr))

    fig, ax = plt.subplots(figsize=(10, 6), dpi=120)

    sns.lineplot(x=steps, y=mins, marker="o", linewidth=2, label="Min", ax=ax)
    sns.lineplot(x=steps, y=meds, marker="o", linewidth=2, label="Median", ax=ax)
    sns.lineplot(x=steps, y=maxs, marker="o", linewidth=2, label="Max", ax=ax)

    # vertical min-max bars
    for x, lo, hi in zip(steps, mins, maxs):
        if np.isfinite(lo) and np.isfinite(hi):
            ax.vlines(x, lo, hi, linestyles="dotted", alpha=0.4)

    ax.set_title("Objective Quantiles Across Steps (Min / Median / Max)")
    ax.set_xlabel("Step")
    ax.set_ylabel("Objective")

    all_vals = np.array(mins + meds + maxs, dtype=float)
    finite = all_vals[np.isfinite(all_vals)]
    if finite.size:
        ymin, ymax = finite.min(), finite.max()
        pad = (ymax - ymin) * 0.1 if ymax > ymin else 1.0
        ax.set_ylim(ymin - pad, ymax + pad)

    # annotate turning points only
    annotate_values(ax, steps, mins, turning_point_indices_by_change(mins), dy=8)
    annotate_values(ax, steps, meds, turning_point_indices_by_change(meds), dy=0)
    annotate_values(ax, steps, maxs, turning_point_indices_by_change(maxs), dy=16)

    png = os.path.join(out_dir, "results_quantiles.png")
    pdf = os.path.join(out_dir, "results_quantiles.pdf")
    fig.tight_layout()
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)

    print(f"Saved: {png}\nSaved: {pdf}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True)
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    if not os.path.isdir(input_dir):
        raise NotADirectoryError(input_dir)

    steps, obj_lists, any_multi = collect_steps(input_dir)

    if not any_multi and all(len(v) == 1 for v in obj_lists):
        single_vals = [v[0] if v else np.nan for v in obj_lists]
        plot_single_line(steps, single_vals, input_dir)
    else:
        plot_quantile_lines(steps, obj_lists, input_dir)

    print("Done.")


if __name__ == "__main__":
    main()
