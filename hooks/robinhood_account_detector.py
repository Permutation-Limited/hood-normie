"""Account-number policy for the public example config."""

import re

ACCOUNT_NUMBER = re.compile(r"(?<![\d.])\d{9,}(?![\d.])")


def contains_account_number(filename: str, line: str) -> bool:
    return (
        filename.endswith("examples/rebalance/config.example.yaml")
        and ACCOUNT_NUMBER.search(line) is not None
    )
