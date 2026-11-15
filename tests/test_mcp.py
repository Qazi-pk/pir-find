import numpy as np
import pandas as pd
import pytest

pytest.importorskip("mcp")
from pir_find.mcp_server import build


def test_mcp_tools_registered():
    import asyncio
    names = {t.name for t in asyncio.run(build().list_tools())}
    assert names == {"describe_table", "find_formula", "check_formula"}
