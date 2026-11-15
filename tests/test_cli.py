import json

import numpy as np
import pandas as pd

from pir_find.cli import main


def test_cli_describe_check_and_errors(tmp_path, capsys):
    r = np.random.default_rng(0)
    u, v = r.uniform(1, 5, 300), r.uniform(1, 5, 300)
    p = tmp_path / "d.csv"
    pd.DataFrame({"u": u, "v": v, "f": u * v / (u + v)}).to_csv(p, index=False)
    assert main([str(p), "--describe", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["rows"] == 300
    assert main([str(p), "--target", "f", "--check", "u*v/(u+v)", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["r2"] > 0.999999
    assert main([str(tmp_path / "missing.csv"), "--describe"]) == 2
    assert "file not found" in capsys.readouterr().err
