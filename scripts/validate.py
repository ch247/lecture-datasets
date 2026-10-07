#!/usr/bin/env python3
"""Validate lecture datasets against CSV-STANDARD.md and regenerate CATALOG.md.

Usage:
  python scripts/validate.py                  # validate all, rewrite CATALOG.md
  python scripts/validate.py --fix            # auto-fix encoding/delimiter/decimals first
  python scripts/validate.py --check-catalog  # CI mode: fail if CATALOG.md is stale
  python scripts/validate.py datasets/x/L01-y # validate selected folders only

Stdlib only. Exit code 1 on any error.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "datasets"
CATALOG = ROOT / "CATALOG.md"
MAX_BYTES = 5 * 1024 * 1024

META_REQUIRED = ["id", "course", "lecture", "source_name", "source_url",
                 "license", "retrieved", "sensitivity", "update_mode"]
UPDATE_MODES = {"static", "linked"}

SPEC_REQUIRED = ["title", "type", "data_file", "source_name"]
SPEC_ALLOWED = set(SPEC_REQUIRED) | {
    "intro", "notes", "source_url", "byline", "aria_description", "number_format",
    "number_prepend", "number_append", "theme", "language", "folder_id",
    "organization_id", "colors", "annotations", "highlight_ranges", "visualize",
    "publish", "axes", "export"}
SPEC_TYPES = {
    "d3-bars", "d3-bars-split", "d3-bars-stacked", "d3-bars-bullet", "d3-dot-plot",
    "d3-range-plot", "d3-arrow-plot", "column-chart", "grouped-column-chart",
    "stacked-column-chart", "d3-area", "d3-lines", "multiple-lines", "d3-pies",
    "d3-donuts", "d3-multiple-pies", "d3-multiple-donuts", "d3-scatter-plot",
    "election-donut-chart", "tables", "d3-maps-choropleth", "d3-maps-symbols",
    "locator-map"}

MISSING_TOKENS = {"n/a", "na", "-", "–", "null", "none", "nan", "#n/a"}
RE_NUMBER = re.compile(r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$")
RE_DE_DECIMAL = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d+$|^-?\d+,\d+$")
RE_THOUSANDS = re.compile(r"^-?\d{1,3}([,.' ]\d{3})+(\.\d+)?$")
RE_UNIT = re.compile(r"\d.*(€|\$|%|mio|mrd|bn|tsd)|(€|\$)\s*\d", re.I)
RE_BAD_DATE = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{2,4}$|^\d{1,2}/\d{1,2}/\d{2,4}$")
RE_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Report:
    def __init__(self, name: str):
        self.name, self.errors, self.warnings = name, [], []

    def err(self, msg: str): self.errors.append(msg)
    def warn(self, msg: str): self.warnings.append(msg)


# ---------- fixing ----------

def fix_csv(path: Path) -> list[str]:
    raw = path.read_bytes()
    changes = []
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]; changes.append("removed BOM")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252"); changes.append("re-encoded cp1252 → UTF-8")
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n"); changes.append("CRLF → LF")
    lines = text.rstrip("\n").split("\n")
    lines = [l for l in lines if l.strip(" ,;")] or lines
    header = lines[0]
    if ";" in header and "," not in header:
        rows = list(csv.reader(lines, delimiter=";"))
        n_dec = 0
        for r in rows[1:]:
            for i, cell in enumerate(r):
                c = cell.strip()
                if RE_DE_DECIMAL.match(c):
                    r[i] = c.replace(".", "").replace(",", "."); n_dec += 1
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\n").writerows(rows)
        text = buf.getvalue()
        changes.append(f"delimiter ; → , ({n_dec} decimal commas converted)")
    else:
        text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8", newline="")
    return changes


# ---------- validation ----------

def check_csv(path: Path, rep: Report) -> list[str]:
    if not path.exists():
        rep.err("data.csv missing"); return []
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES: rep.err(f"file > 5 MB ({len(raw)/1e6:.1f} MB)")
    if raw.startswith(b"\xef\xbb\xbf"): rep.err("UTF-8 BOM present (run --fix)")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        rep.err("not UTF-8 (run --fix)"); return []
    if "\r" in text: rep.err("CRLF line endings (run --fix)")
    if text.endswith("\n\n"): rep.err("trailing empty rows (run --fix)")
    lines = text.splitlines()
    if not lines:
        rep.err("empty file"); return []
    if ";" in lines[0] and "," not in lines[0]:
        rep.err("semicolon delimiter (run --fix)"); return []

    rows = list(csv.reader(lines))
    header, body = rows[0], rows[1:]
    if not body: rep.err("no data rows")
    stripped = [h.strip() for h in header]
    if any(not h for h in stripped): rep.err("empty header cell")
    dupes = {h for h in stripped if stripped.count(h) > 1 and h}
    if dupes: rep.err(f"duplicate headers: {sorted(dupes)}")
    if len(header) < 2: rep.warn("only one column — check delimiter")

    for i, r in enumerate(body, start=2):
        if len(r) != len(header):
            rep.err(f"row {i}: {len(r)} columns, header has {len(header)}")

    issues = 0
    for i, r in enumerate(body, start=2):
        for j, cell in enumerate(r):
            c = cell.strip()
            loc = f"row {i}, col '{header[j] if j < len(header) else j}'"
            if not c:
                continue
            if c.lower() in MISSING_TOKENS:
                rep.err(f"{loc}: '{c}' → use empty cell for missing"); issues += 1
            elif j == 0 and RE_BAD_DATE.match(c):
                rep.err(f"{loc}: '{c}' → use ISO date (YYYY-MM-DD)"); issues += 1
            elif j > 0 and not RE_NUMBER.match(c):
                if RE_DE_DECIMAL.match(c):
                    rep.err(f"{loc}: '{c}' → decimal comma, use dot"); issues += 1
                elif RE_THOUSANDS.match(c):
                    rep.err(f"{loc}: '{c}' → remove thousands separator"); issues += 1
                elif RE_UNIT.search(c):
                    rep.err(f"{loc}: '{c}' → unit in cell, move to header/spec"); issues += 1
            if issues >= 25:
                rep.err("… further value errors suppressed"); return stripped
    return stripped


def check_meta(path: Path, folder: Path, rep: Report) -> dict:
    if not path.exists():
        rep.err("meta.json missing"); return {}
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        rep.err(f"meta.json invalid JSON: {e}"); return {}
    for k in META_REQUIRED:
        if not str(meta.get(k, "")).strip():
            rep.err(f"meta.{k} missing")
    if meta.get("sensitivity") != "public":
        rep.err("meta.sensitivity must be 'public' — this repo is public")
    if meta.get("update_mode") not in UPDATE_MODES:
        rep.err(f"meta.update_mode must be one of {sorted(UPDATE_MODES)}")
    if meta.get("retrieved") and not RE_ISO_DATE.match(str(meta["retrieved"])):
        rep.err("meta.retrieved must be YYYY-MM-DD")
    expected_id = "-".join(folder.relative_to(DATASETS).parts)
    if meta.get("id") and meta["id"] != expected_id:
        rep.warn(f"meta.id '{meta['id']}' ≠ folder-derived '{expected_id}'")
    return meta


def check_spec(path: Path, headers: list[str], rep: Report) -> dict:
    if not path.exists():
        rep.err("spec.json missing"); return {}
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        rep.err(f"spec.json invalid JSON: {e}"); return {}
    for k in SPEC_REQUIRED:
        if not str(spec.get(k, "")).strip():
            rep.err(f"spec.{k} missing")
    unknown = set(spec) - SPEC_ALLOWED
    if unknown: rep.err(f"spec has unknown keys {sorted(unknown)} (push_chart.py rejects them)")
    if spec.get("type") and spec["type"] not in SPEC_TYPES:
        rep.err(f"spec.type '{spec['type']}' not a known Datawrapper type")
    if spec.get("data_file") and spec["data_file"] != "data.csv":
        rep.err("spec.data_file must be 'data.csv'")
    for series in (spec.get("colors") or {}):
        if headers and series not in headers:
            rep.err(f"spec.colors key '{series}' not a CSV header")
    return spec


def discover(selected: list[str]) -> list[Path]:
    if selected:
        return [Path(s).resolve() for s in selected]
    return sorted(p.parent for p in DATASETS.rglob("data.csv")
                  if "_template" not in p.parts)


# ---------- catalog ----------

def build_catalog(entries: list[tuple[Path, dict, dict]]) -> str:
    cfg = json.loads((ROOT / "repo.config.json").read_text(encoding="utf-8"))
    base = f"https://raw.githubusercontent.com/{cfg['owner']}/{cfg['repo']}/{cfg['branch']}"
    out = ["# Dataset catalog", "",
           "_Generated by `scripts/validate.py` — do not edit by hand._", "",
           "| Course | Lecture | Chart title | Mode | DW chart | Raw CSV URL |",
           "|---|---|---|---|---|---|"]
    for folder, meta, spec in entries:
        rel = folder.relative_to(ROOT).as_posix()
        cid = meta.get("datawrapper_chart_id") or "—"
        out.append(f"| {meta.get('course','')} | {meta.get('lecture','')} | "
                   f"{spec.get('title','')} | {meta.get('update_mode','')} | {cid} | "
                   f"`{base}/{rel}/data.csv` |")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="*")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--check-catalog", action="store_true")
    args = ap.parse_args()

    folders = discover(args.folders)
    if not folders:
        print("No datasets found."); return 0

    failed, entries = 0, []
    for folder in folders:
        rep = Report(folder.relative_to(ROOT).as_posix())
        if args.fix and (folder / "data.csv").exists():
            for c in fix_csv(folder / "data.csv"):
                print(f"  fixed  {rep.name}: {c}")
        headers = check_csv(folder / "data.csv", rep)
        meta = check_meta(folder / "meta.json", folder, rep)
        spec = check_spec(folder / "spec.json", headers, rep)
        entries.append((folder, meta, spec))
        status = "FAIL" if rep.errors else "ok  "
        print(f"[{status}] {rep.name}")
        for e in rep.errors: print(f"         ✗ {e}")
        for w in rep.warnings: print(f"         ! {w}")
        failed += bool(rep.errors)

    if not args.folders:
        catalog = build_catalog(entries)
        if args.check_catalog:
            current = CATALOG.read_text(encoding="utf-8") if CATALOG.exists() else ""
            if current != catalog:
                print("✗ CATALOG.md is stale — run scripts/validate.py locally and commit")
                failed += 1
        else:
            CATALOG.write_text(catalog, encoding="utf-8")

    print("\nAll checks passed." if not failed else f"\n{failed} check(s) failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
