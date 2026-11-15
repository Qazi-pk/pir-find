"""Core of pir-find: no web or MCP code here. Everything returns plain dicts (JSON-safe)."""
import multiprocessing as mp
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

MAX_BYTES = 5 * 1024 * 1024    # file size limit
MAX_ROWS = 20_000              # larger tables are subsampled (seeded)
MAX_FEATURES = 8               # PIR searches products and powers; keep inputs small
HOLDOUT = 0.25                 # share of rows held out for the reported accuracy
MIN_ROWS = 20
FEW_ROWS = 200                 # below this, warn
DEFAULT_TIMEOUT = 300          # seconds for one find_formula call
FALLBACKS = ("linear_fallback", "mean_fallback")   # PIR 3.7 safeguard outcomes
ALLOWED_FUNCS = {"exp": "exp", "log": "log", "ln": "log", "sqrt": "sqrt", "sin": "sin", "cos": "cos",
                 "tan": "tan", "asin": "asin", "arcsin": "asin", "acos": "acos", "arccos": "acos",
                 "atan": "atan", "arctan": "atan", "tanh": "tanh", "Abs": "Abs", "abs": "Abs", "pi": "pi", "E": "E"}


def _version():
    import physics_engine
    return physics_engine.__version__


def load_table(path, max_bytes=MAX_BYTES):
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"file not found: {path}")
    if p.stat().st_size > max_bytes:
        raise ValueError(f"file larger than {max_bytes // (1024 * 1024)} MB")
    try:
        return pd.read_csv(p)
    except Exception as e:
        raise ValueError(f"could not read CSV: {e}")


def _readable(expr_str, digits=6):
    """Round floats to `digits` significant figures; integers stay integers."""
    import sympy as sp
    names = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", expr_str)) - set(ALLOWED_FUNCS)
    try:
        e = sp.sympify(expr_str, locals={n: sp.Symbol(n) for n in names})
        e = e.xreplace({n: sp.Float(n, digits) for n in e.atoms(sp.Float)})
        e = e.xreplace({n: sp.Integer(int(n)) for n in e.atoms(sp.Float) if float(n) == int(float(n))})
        return str(e)
    except Exception:
        return expr_str


def _r2(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    v = float(np.var(y))
    return float(1 - np.mean((y - p) ** 2) / v) if v > 0 else float("nan")


def _numeric(df):
    num = df.apply(pd.to_numeric, errors="coerce")
    return num.replace([np.inf, -np.inf], np.nan)


def describe_table(df):
    """Columns, row counts, missing values, ranges and problems found, before any fitting."""
    num = _numeric(df)
    cols, problems = [], []
    for c in df.columns:
        s = num[c]
        ok = int(s.notna().sum())
        entry = {"name": str(c), "numeric": bool(ok > 0), "rows_numeric": ok, "rows_missing": int(len(df) - ok)}
        if ok:
            entry.update(min=float(s.min()), max=float(s.max()), constant=bool(s.nunique() <= 1))
            if entry["constant"]:
                problems.append(f"column '{c}' is constant")
        else:
            problems.append(f"column '{c}' has no numeric values")
        cols.append(entry)
    complete = int(num.dropna().shape[0])
    if complete < MIN_ROWS:
        problems.append(f"only {complete} complete numeric rows (need at least {MIN_ROWS})")
    elif complete < FEW_ROWS:
        problems.append(f"few rows ({complete}); a formula found from so few rows is weak evidence")
    if len(df.columns) - 1 > MAX_FEATURES:
        problems.append(f"{len(df.columns) - 1} possible inputs; at most {MAX_FEATURES} are allowed")
    return {"rows": int(len(df)), "complete_numeric_rows": complete, "columns": cols, "problems": problems}


def fit_table(df, target, seed=0):
    """Validate the table, fit PIR on 75% of rows, report accuracy on the other 25%."""
    from physics_engine.sklearn_adapter import PIRRegressor
    if target not in df.columns:
        raise ValueError(f"target column '{target}' not found; columns are {list(df.columns)}")
    num = _numeric(df)
    feats = [c for c in num.columns if c != target]
    bad = [c for c in feats + [target] if num[c].isna().all()]
    if bad:
        raise ValueError(f"non-numeric columns: {bad}")
    if not feats:
        raise ValueError("need at least one input column besides the target")
    if len(feats) > MAX_FEATURES:
        raise ValueError(f"at most {MAX_FEATURES} input columns (got {len(feats)})")
    num = num[feats + [target]].dropna()
    dropped = int(len(df) - len(num))
    if len(num) < MIN_ROWS:
        raise ValueError(f"need at least {MIN_ROWS} complete numeric rows (got {len(num)})")
    subsampled = len(num) > MAX_ROWS
    if subsampled:
        num = num.sample(MAX_ROWS, random_state=seed)
    perm = np.random.default_rng(seed).permutation(len(num))
    cut = int((1 - HOLDOUT) * len(num))
    tr, te = num.iloc[perm[:cut]], num.iloc[perm[cut:]]

    warnings = []
    constant = [c for c in feats if num[c].nunique() <= 1]
    if constant:
        warnings.append(f"constant input column(s) {constant} carry no information")
    if len(num) < FEW_ROWS:
        warnings.append(f"few rows ({len(num)}); treat any formula as weak evidence")
    if subsampled:
        warnings.append(f"table has more than {MAX_ROWS} rows; a seeded random sample of {MAX_ROWS} was used")

    t0 = time.time()
    m = PIRRegressor(gates="all", safeguard=True, separability=True, noise_tolerant=True,
                     random_state=seed).fit(tr[feats], tr[target].values)
    secs = time.time() - t0
    p_tr, p_te = m.predict(tr[feats]), m.predict(te[feats])
    source = getattr(m, "final_source_", "engine")
    law_found = source not in FALLBACKS
    r2_te = _r2(te[target], p_te)
    if law_found and np.isfinite(r2_te) and r2_te < 0.9:
        warnings.append("held-out R2 is below 0.9: the formula explains the data only partly")
    return {
        "law_found": law_found,
        "formula": _readable(m.model()) if law_found else None,
        "formula_full_precision": m.model() if law_found else None,
        "fallback_model": None if law_found else _readable(m.model()),
        "target": target,
        "inputs": feats,
        "found_by": source,
        "r2_heldout_rows": r2_te,
        "r2_fit_rows": _r2(tr[target], p_tr),
        "rows_used": int(len(num)),
        "rows_dropped_missing": dropped,
        "heldout_share": HOLDOUT,
        "fit_seconds": round(secs, 2),
        "pir_engine": _version(),
        "warnings": warnings,
        "note": ("Candidate formula, not a proven law. Held-out R2 is the honest accuracy. PIR does not use "
                 "units: check the formula for dimensional sense yourself." if law_found else
                 "No simple law found: PIR's formulas fitted worse than a straight line, so the fallback is a "
                 "linear model or the average. This is an honest answer, not an error, and it does not prove "
                 "that no law exists (high noise, many inputs or sums of many terms are hard for PIR)."),
    }


def _worker(q, df, target, seed):
    try:
        q.put(("ok", fit_table(df, target, seed)))
    except Exception as e:   # reported to the caller as a message, never a crash
        q.put(("err", f"{type(e).__name__}: {e}"))


def find_formula(df, target, seed=0, timeout=DEFAULT_TIMEOUT):
    """fit_table in a child process with a hard time limit."""
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_worker, args=(q, df, target, seed), daemon=True)
    p.start()
    try:
        kind, val = q.get(timeout=timeout)
    except Exception:
        p.terminate()
        p.join(5)
        raise TimeoutError(f"no answer within {timeout} s: the table is too large or too hard for PIR; "
                           "try fewer input columns or fewer rows")
    p.join(5)
    if kind == "err":
        raise ValueError(val.split(": ", 1)[-1])
    return val


_TOKEN = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+|\*\*|[-+*/^(),]|\s+")


def _safe_parse(formula, columns):
    """Parse with sympy only after a whitelist check: names must be columns or known functions."""
    import sympy as sp
    s = formula.strip()
    if not s or len(s) > 500:
        raise ValueError("formula is empty or too long")
    pos = 0
    names = set()
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if not m:
            raise ValueError(f"unexpected character {s[pos]!r} in formula")
        tok = m.group(0)
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", tok):
            names.add(tok)
        pos = m.end()
    unknown = [n for n in names if n not in columns and n not in ALLOWED_FUNCS]
    if unknown:
        raise ValueError(f"unknown name(s) {sorted(unknown)}; allowed: the column names and {sorted(ALLOWED_FUNCS)}")
    loc = {n: sp.Symbol(n) for n in names if n in columns}
    for n in names:
        if n not in loc:
            loc[n] = getattr(sp, ALLOWED_FUNCS[n])
    return sp.sympify(s.replace("^", "**"), locals=loc), [sp.Symbol(c) for c in columns if c in names]


def check_formula(df, target, formula):
    """Evaluate a candidate formula on the table. Never fits anything."""
    import sympy as sp
    if target not in df.columns:
        raise ValueError(f"target column '{target}' not found; columns are {list(df.columns)}")
    num = _numeric(df).dropna()
    cols = [c for c in num.columns if c != target]
    expr, syms = _safe_parse(formula, set(map(str, num.columns)))
    fn = sp.lambdify(syms, expr, modules="numpy")
    with np.errstate(all="ignore"):
        pred = np.broadcast_to(np.asarray(fn(*[num[str(s)].values for s in syms]), dtype=complex), (len(num),))
    y = num[target].values
    complex_rows = int(np.sum(np.abs(pred.imag) > 1e-12))
    pred = pred.real
    nonfinite = int(np.sum(~np.isfinite(pred)))
    ok = np.isfinite(pred)
    warnings = []
    if nonfinite:
        warnings.append(f"formula is undefined or infinite on {nonfinite} of {len(num)} rows "
                        "(for example log or sqrt of a negative number, or division by zero)")
    if complex_rows:
        warnings.append(f"formula gives complex values on {complex_rows} rows")
    if target in {str(s) for s in syms}:
        warnings.append("the formula uses the target column itself")
    used_unknown = [c for c in cols if c not in {str(s) for s in syms}]
    out = {"formula": str(expr), "rows_checked": int(len(num)), "rows_undefined": nonfinite,
           "inputs_used": [str(s) for s in syms], "inputs_unused": used_unknown, "warnings": warnings}
    if ok.sum() >= 2:
        err = np.abs(pred[ok] - y[ok])
        scale = float(np.max(np.abs(y[ok]))) or 1.0
        out.update(r2=_r2(y[ok], pred[ok]), max_abs_error=float(err.max()),
                   max_error_share_of_range=float(err.max() / scale))
    else:
        out.update(r2=None, max_abs_error=None, max_error_share_of_range=None)
    out["note"] = ("This evaluates the formula on all rows; nothing was fitted, so R2 here is not a held-out "
                   "score. A good R2 does not prove the formula is a law: check it against domain knowledge.")
    return out
