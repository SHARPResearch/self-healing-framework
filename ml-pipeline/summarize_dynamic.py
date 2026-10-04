"""
summarize_dynamic.py — Component 2: turn evaluate_dynamic.py's runs.csv into result tables.

Prints (and writes to <out-dir>/summary.md):
  1. mean metrics per scenario x variant across entities
  2. paired comparison of a target variant (default cadal) against every other variant:
     per (entity, scenario) wins/ties/losses on a metric, mean difference, and a two-sided
     Wilcoxon signed-rank p-value (paired, non-parametric: no normality assumption about
     per-entity F1, which is far from normal on SMD)
  3. latency summary (FR6) and lifecycle activity per variant

Usage:
  uv run python summarize_dynamic.py
  uv run python summarize_dynamic.py --metric post_drift_f1 --target cadal
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon


def to_markdown(df: pd.DataFrame, index: bool = True) -> str:
    """Minimal GitHub markdown table (avoids a tabulate dependency for pandas.to_markdown)."""
    if index:
        df = df.reset_index()
    cells = [[("" if (isinstance(v, float) and v != v) else str(v)) for v in row] for row in df.values]
    header = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    return "\n".join([header, sep] + ["| " + " | ".join(r) + " |" for r in cells])


MEAN_COLS = ["f1", "precision", "recall", "event_recall", "fa_rate",
             "post_drift_f1", "post_drift_fa_rate", "recovery_steps"]


def mean_table(runs: pd.DataFrame) -> pd.DataFrame:
    g = runs.groupby(["scenario", "variant"])
    table = g[MEAN_COLS].mean().round(4)
    table["recovered"] = g["recovery_steps"].apply(lambda s: f"{s.notna().sum()}/{len(s)}")
    table["n_entities"] = g["entity"].nunique()
    return table


def paired_table(runs: pd.DataFrame, target: str, metric: str) -> pd.DataFrame:
    rows = []
    pivot = runs.pivot_table(index=["entity", "scenario"], columns="variant", values=metric)
    for scenario in sorted(runs["scenario"].unique()):
        sub = pivot.xs(scenario, level="scenario")
        if target not in sub:
            continue
        for other in sub.columns:
            if other == target:
                continue
            pair = sub[[target, other]].dropna()
            if pair.empty:
                continue
            diff = pair[target] - pair[other]
            nonzero = diff[diff.abs() > 1e-12]
            p = wilcoxon(nonzero).pvalue if len(nonzero) >= 6 else np.nan
            rows.append({
                "scenario": scenario, "vs": other, "n": len(pair),
                "wins": int((diff > 1e-12).sum()), "ties": int((diff.abs() <= 1e-12).sum()),
                "losses": int((diff < -1e-12).sum()),
                f"mean_{target}": round(pair[target].mean(), 4),
                f"mean_{other if len(other) < 12 else 'other'}": round(pair[other].mean(), 4),
                "mean_diff": round(diff.mean(), 4), "wilcoxon_p": round(p, 4) if p == p else None,
            })
    return pd.DataFrame(rows)


def ops_table(runs: pd.DataFrame) -> pd.DataFrame:
    g = runs.groupby("variant")
    return pd.DataFrame({
        "latency_mean_ms": g["latency_mean_ms"].mean().round(3),
        "latency_p99_ms": g["latency_p99_ms"].mean().round(3),
        "latency_p99_max_ms": g["latency_p99_ms"].max().round(3),
        "transition_max_ms": g["transition_max_ms"].max().round(1),
        "promotions_per_run": g["n_promote"].mean().round(2),
        "rollbacks_per_run": g["n_rollback"].mean().round(2),
        "holds_per_run": g["n_hold"].mean().round(2),
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", default="outputs/component2")
    parser.add_argument("--target", default="cadal")
    parser.add_argument("--metric", default="f1")
    args = parser.parse_args()

    out = Path(args.out_dir)
    runs = pd.read_csv(out / "runs.csv")
    parts = [
        f"# Component 2 results ({runs['entity'].nunique()} entities, {len(runs)} runs)\n",
        "## Mean metrics per scenario and policy\n", to_markdown(mean_table(runs)), "",
        f"## Paired comparison: {args.target} vs each policy on {args.metric}\n",
        to_markdown(paired_table(runs, args.target, args.metric), index=False), "",
    ]
    if args.metric != "post_drift_f1" and "post_drift_f1" in runs:
        drifted = runs[runs["scenario"].isin(["deploy", "silent"])]
        if not drifted.empty:
            parts += [f"## Paired comparison: {args.target} vs each policy on post_drift_f1\n",
                      to_markdown(paired_table(drifted, args.target, "post_drift_f1"), index=False), ""]
    parts += ["## Latency (FR6) and lifecycle activity\n", to_markdown(ops_table(runs)), ""]
    text = "\n".join(parts)
    (out / "summary.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
