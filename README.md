# pir-find

Find a closed-form formula in a table of numbers with [PIR](https://github.com/Qazi-pk/physics-engine) (symbolic regression, MIT), and check a candidate formula. Command line and MCP server. Your data stays on your computer: no uploads, no network calls, no telemetry.

**Status: 0.1.0.dev0, not released.** PIR 3.10.0 inside.

## Install (Python 3.10+, needs `git`)
Not on PyPI yet, so install from GitHub:
```
pip install "git+https://github.com/Qazi-pk/pir-find.git"            # command line
pip install "pir-find[mcp] @ git+https://github.com/Qazi-pk/pir-find.git"   # plus the MCP server
```
Or from a clone: `pip install .` / `pip install ".[mcp]"`.

## Command line
```
pir-find data.csv --describe                      # columns, ranges, problems
pir-find data.csv --target y                      # find a formula for column y (all other columns are inputs)
pir-find data.csv --target y --check "a*b/(a+b)"  # evaluate a candidate formula, no fitting
pir-find data.csv --target y --json
```
Limits: 5 MB, 8 input columns, 20,000 rows (larger tables are sampled), 300 s per search.

## MCP server (Claude Code, Claude desktop, Cursor, Cline)
Claude Code: `claude mcp add pir-find -- pir-find-mcp`

With `uv` installed, no separate install is needed:
`claude mcp add pir-find -- uvx --from "pir-find[mcp] @ git+https://github.com/Qazi-pk/pir-find.git" pir-find-mcp`

Claude desktop / others (config file, after `pip install`):
```json
{ "mcpServers": { "pir-find": { "command": "pir-find-mcp" } } }
```
Tools: `describe_table(path)`, `find_formula(path, target)`, `check_formula(path, target, formula)`.

## How to read the answer
- `law_found: true` means PIR returned a formula that beat a straight-line fit. It is a **candidate formula, not a proven law**; the honest accuracy is `r2_heldout_rows` (rows not used in fitting).
- `law_found: false` means **no simple law found**; the fallback is a linear model or the average. That does not prove no law exists.
- PIR does not use units: check the formula for dimensional sense yourself.
- PIR loses accuracy above about 1% noise, with many inputs, or for sums of many terms.
- `check_formula` only evaluates; it never fits. A good R2 there is not a held-out score.

## Test
```
pip install ".[test,mcp]" && pytest
```
Licence: MIT. Cite PIR: DOI 10.5281/zenodo.23460310.
