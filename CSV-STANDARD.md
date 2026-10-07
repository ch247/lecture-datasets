# CSV Standard — lecture-datasets

Enforced by `scripts/validate.py` (✔ = automated check, ○ = manual review).

## 1. File
| Rule | Check |
|---|---|
| File name is `data.csv` | ✔ |
| Encoding UTF-8 **without BOM** | ✔ |
| Delimiter **comma** (`,`) — not semicolon | ✔ |
| Decimal separator **dot** (`1234.5`) | ✔ |
| Line endings LF, no trailing empty rows | ✔ |
| ≤ 5 MB (lecture charts should be far smaller) | ✔ |

> **German Excel trap:** "CSV UTF-8" in a German-locale Excel exports `;` + `,`-decimals.
> Either export and run `python scripts/validate.py --fix` (converts `;`/`,` → `,`/`.`), or save via Python/Power Query.

## 2. Shape
| Rule | Check |
|---|---|
| Exactly one header row; every header non-empty and unique | ✔ |
| Every row has the same number of columns as the header | ✔ |
| Column 1 = labels (categories or dates); columns 2..n = one series each | ○ |
| No totals rows, subtotals, merged headers or footnotes inside the table | ○ |
| Missing values are **empty cells** — not `n/a`, `-`, `0` | ✔ (flags `n/a`, `-`, `NA`, `null`) |
| Sort order deliberate (by value for rankings, natural order for time/scales) | ○ |

## 3. Values
| Rule | Check |
|---|---|
| Numbers unformatted: no thousands separators, no `€`, `%`, `Mio`, `bn` in cells | ✔ |
| Units live in the header or `spec.json` (`intro`, `number_append`) | ○ |
| Dates ISO: `2026-03-31`, `2026-03`, `2026`, or `2026-Q1` | ✔ (flags `31.03.2026`, `03/31/2026`) |
| Percentages as numbers: `12.5` with `number_append: "%"` (not `0.125` mixed with `12.5`) | ○ |

## 4. Headers
Headers become legend and tooltip labels → write them for the audience:
`Deutsche Bank`, `Net interest income` — not `db_val_2026`.

## 5. Metadata (`meta.json`)
Required: `id`, `course`, `lecture`, `source_name`, `source_url`, `license`, `retrieved`, `sensitivity`, `update_mode`.
- `sensitivity` must be `"public"` — anything else fails validation.
- `update_mode`: `"static"` (paste/upload) or `"linked"` (raw URL in Datawrapper).
- `retrieved`: ISO date the data was pulled from the source.

## 6. Spec (`spec.json`)
Must validate against the datawrapper-charts skill schema. Minimum: `title` (action title), `type`, `data_file: "data.csv"`, `source_name`.
