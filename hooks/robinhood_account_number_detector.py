"""Reject Robinhood account numbers from files passed by pre-commit."""

import re
import sys


ACCOUNT_NUMBER = re.compile(
    r"(?im)\b(?:robinhood_)?account_numbers?\b\s*[:=]\s*"
    r"(?:\[\s*|\n\s*-\s*)?[\"']?(\d{9,})"
)


def contains_account_number(content: str) -> bool:
    return ACCOUNT_NUMBER.search(content) is not None


def main(filenames: list[str]) -> int:
    violations = []
    for filename in filenames:
        try:
            with open(filename, encoding="utf-8") as stream:
                if contains_account_number(stream.read()):
                    violations.append(filename)
        except (OSError, UnicodeDecodeError):
            continue
    for filename in violations:
        print(f"Robinhood account number found: {filename}", file=sys.stderr)
    return bool(violations)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
