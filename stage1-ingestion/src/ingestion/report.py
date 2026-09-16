"""
Stage 1 -- data-quality report.

Takes the ValidationResult / RasterValidationResult objects produced by
validators.py and writes a single markdown report summarizing what came in,
what got flagged, and why -- meant to be dropped straight into the
capstone's appendix or read on its own before Stage 2 begins.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import List, Union

from .validators import RasterValidationResult, ValidationResult


def _tabular_section(result: ValidationResult) -> str:
    lines = [f"## {result.source}", ""]
    lines.append(f"- Records in: **{result.n_records_in:,}**")
    lines.append(f"- Records out (all retained, flagged not dropped): **{result.n_records_out:,}**")
    lines.append("")
    if result.issues:
        lines.append("| Check | Flagged count | % of records |")
        lines.append("|---|---:|---:|")
        for check, count in result.issues.items():
            pct = f"{100 * count / result.n_records_in:.1f}%" if result.n_records_in else "n/a"
            lines.append(f"| `{check}` | {count:,} | {pct} |")
        lines.append("")
    if result.notes:
        lines.append("**Notes:**")
        for note in result.notes:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)


def _raster_section(result: RasterValidationResult) -> str:
    lines = [f"## {result.source}", ""]
    lines.append(f"- Grid shape: **{result.shape}**")
    lines.append("")
    if result.issues:
        lines.append("| Check | Value |")
        lines.append("|---|---:|")
        for check, val in result.issues.items():
            lines.append(f"| `{check}` | {val} |")
        lines.append("")
    if result.stats:
        lines.append("| Stat | Value |")
        lines.append("|---|---:|")
        for stat, val in result.stats.items():
            lines.append(f"| `{stat}` | {val:,.2f} |" if isinstance(val, float) else f"| `{stat}` | {val} |")
        lines.append("")
    if result.notes:
        lines.append("**Notes:**")
        for note in result.notes:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)


def generate_data_quality_report(
    results: List[Union[ValidationResult, RasterValidationResult]],
    out_path: Union[str, Path],
    city: str = None,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "# Stage 1 -- Data Quality Report",
        "",
        f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]
    if city:
        header.append(f"City: **{city}**")
    header.append("")
    header.append(
        "This report covers all four raw sources after ingestion. Flagged records are "
        "**retained** in the interim data with boolean `_flag_*` columns (tabular sources) "
        "or masked to NaN (raster sources) -- nothing is silently dropped at this stage. "
        "Stage 2/3 decide what to do with flagged records."
    )
    header.append("")

    sections = []
    for r in results:
        if isinstance(r, ValidationResult):
            sections.append(_tabular_section(r))
        elif isinstance(r, RasterValidationResult):
            sections.append(_raster_section(r))

    # Overall summary table
    summary_lines = ["## Summary", "", "| Source | Type | Records / Cells | Key concern |", "|---|---|---:|---|"]
    for r in results:
        if isinstance(r, ValidationResult):
            top_issue = max(r.issues.items(), key=lambda kv: kv[1], default=(None, 0))
            concern = f"{top_issue[0]} ({top_issue[1]})" if top_issue[0] else "none flagged"
            summary_lines.append(f"| {r.source} | tabular | {r.n_records_in:,} | {concern} |")
        elif isinstance(r, RasterValidationResult):
            count_issues = {k: v for k, v in r.issues.items() if k.startswith("n_")}
            top_issue = max(count_issues.items(), key=lambda kv: kv[1], default=(None, 0))
            concern = f"{top_issue[0]} ({top_issue[1]})" if top_issue[0] else "none flagged"
            n_cells = 1
            for d in r.shape:
                n_cells *= d
            summary_lines.append(f"| {r.source} | raster | {n_cells:,} | {concern} |")
    summary_lines.append("")

    content = "\n".join(header) + "\n" + "\n".join(summary_lines) + "\n" + "\n".join(sections)
    out_path.write_text(content, encoding="utf-8")
    return out_path
