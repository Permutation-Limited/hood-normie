"""Run detect-secrets with this repository's custom detectors enabled."""

import os
import sys

from detect_secrets.pre_commit_hook import main
from hooks.robinhood_account_detector import contains_account_number


if __name__ == "__main__":
    violations = []
    for filename in sys.argv[1:]:
        if filename.startswith("-") or not os.path.isfile(filename):
            continue
        with open(filename, encoding="utf-8") as stream:
            if any(contains_account_number(filename, line) for line in stream):
                violations.append(filename)
    if violations:
        for filename in violations:
            print(f"Robinhood account number found: {filename}", file=sys.stderr)
        sys.exit(1)
    sys.exit(main(sys.argv[1:]))
