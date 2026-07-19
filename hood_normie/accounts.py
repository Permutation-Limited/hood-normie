"""Parse and select accounts from Robinhood MCP responses."""

from typing import Any


def select_account(payload: Any) -> str:
    accounts = account_records(payload)
    numbered = [(account, account_number(account)) for account in accounts]
    selectable = [(account, number) for account, number in numbered if number is not None]
    if len(selectable) == 1:
        return str(selectable[0][1])

    lines = ["could not select a Robinhood account automatically."]
    if numbered:
        lines.append("Available accounts:")
        for account, number in numbered:
            shown_number = str(number) if number is not None else "(number unavailable)"
            lines.append(f"  - {account_name(account)}: {shown_number}")
    else:
        lines.append("Available accounts: none returned")
    if selectable:
        lines.append("Pass one of the numbers above with --account NUMBER.")
    else:
        lines.append(
            "Robinhood returned no recognized account-number field; "
            "available account fields are shown below."
        )
        for account in accounts:
            lines.append(f"  - {account_name(account)} fields: {', '.join(sorted(account))}")
    raise SystemExit("\n".join(lines))


def account_records(payload: Any) -> list[dict[str, Any]]:
    """Extract account objects through common MCP response wrappers."""
    wrappers = {"accounts", "results", "items", "data"}
    identifier_fields = {
        "account_number", "accountNumber", "number", "account_id", "accountId",
        "nickname", "display_name", "displayName", "account_type", "accountType",
    }
    found: list[dict[str, Any]] = []

    def visit(value: Any, inside_wrapper: bool = False) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item, inside_wrapper)
        elif isinstance(value, dict):
            if inside_wrapper and identifier_fields.intersection(value):
                found.append(value)
                return
            for key, item in value.items():
                if key in wrappers:
                    visit(item, True)

    visit(payload, isinstance(payload, list))
    if not found and isinstance(payload, dict) and identifier_fields.intersection(payload):
        found.append(payload)
    return found


def account_number(account: dict[str, Any]) -> Any:
    return first(
        account, "account_number", "accountNumber", "number",
        "brokerage_account_number", "brokerageAccountNumber",
    )


def account_name(account: dict[str, Any]) -> str:
    value = first(
        account, "nickname", "display_name", "displayName", "name",
        "account_type", "accountType", "type",
    )
    return str(value) if value is not None else "Unnamed account"


def first(record: dict[str, Any], *keys: str) -> Any:
    return next((record[key] for key in keys if record.get(key) is not None), None)
