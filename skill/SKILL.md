---
name: scientific-analysis
description: Analyse a lab or simulation data table: describe it, fit or test, and look for a checkable closed-form formula with pir-find. Use for physics/engineering data tables, "find the formula", or checking a formula against data.
---

# Scientific analysis with pir-find

1. **Describe first.** Call `describe_table` on the CSV. Fix problems it lists (non-numeric columns, constant columns, too few rows) before anything else. Ask which column is the target if unclear.
2. **Look at the data.** Plot target against each input; say what you see (trend, scatter, outliers).
3. **Find a formula.** Call `find_formula`. Report `law_found` first.
   - If false: say "no simple law found" plainly, report the fallback, and suggest more rows, fewer inputs, or a plain fit. Never present the fallback as a law.
   - If true: give the formula, `found_by`, and the **held-out** R2. Call it a candidate formula, not a proven law.
4. **Check it.** Call `check_formula` on the formula, then reason about units and limits (does it behave sensibly at extremes? are dimensions consistent? PIR does not check units).
5. **Report** method, result, accuracy and limits in plain language. State what was checked and how.

**Teacher mode** (when the user is a student or asks for hints): do not give the final formula; give the next step, ask the student to predict, then call the tools together and compare.
