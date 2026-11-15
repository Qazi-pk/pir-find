import numpy as np
import pandas as pd
import pytest

from pir_find import check_formula, core, describe_table, fit_table

RNG = lambda: np.random.default_rng(0)


def _lens(n=800):
    r = RNG()
    u, v = r.uniform(1, 5, n), r.uniform(1, 5, n)
    return pd.DataFrame({"u": u, "v": v, "f": u * v / (u + v)})


def _pendulum(n=800):
    r = RNG()
    L, g = r.uniform(0.2, 2, n), r.uniform(9, 10, n)
    T = 2 * np.pi * np.sqrt(L / g)
    return pd.DataFrame({"L": L, "g": g, "T": T * (1 + 0.01 * r.normal(size=n))})


def test_lens_exact_law():
    res = fit_table(_lens(), "f")
    assert res["law_found"] and res["r2_heldout_rows"] > 0.999999
    assert res["formula"] and res["fallback_model"] is None


def test_noisy_pendulum_law_found_with_high_heldout_r2():
    res = fit_table(_pendulum(), "T")
    assert res["law_found"] and res["r2_heldout_rows"] > 0.98


def test_pure_noise_says_no_law():
    r = RNG()
    df = pd.DataFrame(r.uniform(1, 5, (600, 3)), columns=["a", "b", "c"])
    df["y"] = r.normal(0, 1, 600)
    res = fit_table(df, "y")
    assert not res["law_found"] and res["formula"] is None and "No simple law" in res["note"]


def test_constant_column_and_few_rows_warn():
    df = _lens(60)
    df["k"] = 3.0
    res = fit_table(df, "f")
    assert any("constant" in w for w in res["warnings"])
    assert any("few rows" in w for w in res["warnings"])


def test_errors_are_plain_messages():
    with pytest.raises(ValueError, match="not found"):
        fit_table(_lens(), "nope")
    with pytest.raises(ValueError, match="at least"):
        fit_table(_lens(10), "f")
    df = _lens()
    df["s"] = "text"
    with pytest.raises(ValueError, match="non-numeric"):
        fit_table(df, "f")


def test_describe_flags_problems():
    df = _lens(50)
    df["k"] = 1.0
    d = describe_table(df)
    assert any("constant" in p for p in d["problems"]) and any("few rows" in p for p in d["problems"])


def test_check_formula_exact_and_wrong():
    df = _lens()
    good = check_formula(df, "f", "u*v/(u+v)")
    assert good["r2"] > 0.999999999 and good["rows_undefined"] == 0
    bad = check_formula(df, "f", "u + v")
    assert bad["r2"] < 0.5


def test_check_formula_domain_warning_and_unused_inputs():
    df = _lens()
    df["f"] = df["u"]
    res = check_formula(df, "f", "log(u - 3)")
    assert res["rows_undefined"] > 0 and any("undefined" in w for w in res["warnings"])
    assert res["inputs_unused"] == ["v"]


@pytest.mark.parametrize("bad", ["__import__('os').system('ls')", "u.__class__", "open('x')", "u; v", "lambda: 1", "eval(u)"])
def test_check_formula_rejects_unsafe_input(bad):
    with pytest.raises(ValueError):
        check_formula(_lens(), "f", bad)


def test_find_formula_child_process_and_timeout():
    res = core.find_formula(_lens(300), "f", timeout=240)
    assert res["law_found"]
    with pytest.raises(TimeoutError):
        core.find_formula(_lens(300), "f", timeout=0.01)
