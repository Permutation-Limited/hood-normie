"""Dependency-free terminal styling shared by command-line examples."""

import os


class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def apply(self, value: object, *codes: str) -> str:
        text = str(value)
        return f"{''.join(codes)}{text}{self.RESET}" if self.enabled else text


def color_enabled(mode: str, stream: object) -> bool:
    if mode == "always":
        return True
    if mode == "never" or os.environ.get("NO_COLOR") is not None:
        return False
    return bool(getattr(stream, "isatty", lambda: False)())
