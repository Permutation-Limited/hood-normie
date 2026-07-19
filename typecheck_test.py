"""Repository-wide static type-check test."""

from pathlib import Path
import sys

from mypy import api


def main() -> int:
    workspace = Path(__file__).resolve().parent
    roots = [workspace / name for name in ("examples", "hood_normie", "hooks")]
    sources = [path for root in roots for path in root.rglob("*.py")]
    production = [str(path) for path in sources if not path.name.endswith("_test.py")]
    tests = [str(path) for path in sources if path.name.endswith("_test.py")]

    stdout, stderr, production_status = api.run([
        "--strict",
        "--show-error-codes",
        "--no-error-summary",
        *production,
    ])
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    stdout, stderr, test_status = api.run([
        "--check-untyped-defs",
        "--show-error-codes",
        "--no-error-summary",
        *tests,
    ])
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return production_status or test_status


if __name__ == "__main__":
    raise SystemExit(main())
