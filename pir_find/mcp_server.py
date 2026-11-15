"""MCP server (stdio) exposing three tools: describe_table, find_formula, check_formula.
Runs on the user's computer and reads local file paths; no network calls, no telemetry."""
from .core import check_formula as _check, describe_table as _describe, find_formula as _find, load_table


def build():
    try:                                   # mcp >= 2
        from mcp.server.mcpserver import MCPServer as _Server
    except ImportError:                    # mcp 1.x
        from mcp.server.fastmcp import FastMCP as _Server
    mcp = _Server("pir-find")

    @mcp.tool()
    def describe_table(path: str) -> dict:
        """Describe a local CSV file: columns, ranges, missing values and problems. Use before find_formula."""
        return _describe(load_table(path))

    @mcp.tool()
    def find_formula(path: str, target: str, timeout_seconds: int = 300) -> dict:
        """Search a local CSV for a closed-form formula explaining the `target` column (all other columns are
        inputs) with PIR. Returns the formula, held-out R2, which stage found it, warnings, or law_found=false
        ('no simple law found'). Report law_found=false plainly; a result is a candidate formula, not a proven law."""
        return _find(load_table(path), target, 0, max(10, min(int(timeout_seconds), 900)))

    @mcp.tool()
    def check_formula(path: str, target: str, formula: str) -> dict:
        """Evaluate a candidate formula (column names, + - * / ** , exp log sqrt sin cos tan, pi) on a local CSV.
        Nothing is fitted. Reports R2, worst error, rows where the formula is undefined and unused columns."""
        return _check(load_table(path), target, formula)

    return mcp


def main():
    build().run()


if __name__ == "__main__":
    main()
