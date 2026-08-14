"""Parse and select accounts from Robinhood MCP responses."""

from typing import TypedDict

from hood_normie.types import JsonObject, JsonValue, is_json_value


TAX_STATUS_FIELDS = (
    "tax_status", "taxStatus", "tax_type", "taxType",
    "retirement_account_type", "retirementAccountType",
    "brokerage_account_type", "brokerageAccountType",
)
ACCOUNT_TYPE_FIELDS = ("account_type", "accountType", "type")
NICKNAME_FIELDS = ("nickname", "display_name", "displayName", "name")


class AccountSummary(TypedDict):
    """The identifying fields the CLI table and the web API both present.

    A field is None when Robinhood omitted it or returned something that is not
    a scalar; each renderer decides how to say "unavailable".
    """

    tax_status: str | None
    account_type: str | None
    account_number: str | None
    nickname: str | None


def select_account(payload: object) -> str:
    if not is_json_value(payload):
        raise ValueError("account payload is not valid JSON data")
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


def account_records(payload: object) -> list[JsonObject]:
    """Extract account objects through common MCP response wrappers."""
    if not is_json_value(payload):
        raise ValueError("account payload is not valid JSON data")
    wrappers = {"accounts", "results", "items", "data"}
    identifier_fields = {
        "account_number", "accountNumber", "number", "account_id", "accountId",
        "brokerage_account_number", "brokerageAccountNumber", "nickname",
        "display_name", "displayName", "account_type", "accountType", "type",
        "tax_status", "taxStatus", "tax_type", "taxType",
        "retirement_account_type", "retirementAccountType",
        "brokerage_account_type", "brokerageAccountType",
    }
    found: list[JsonObject] = []

    def visit(value: JsonValue, inside_wrapper: bool = False) -> None:
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


def account_number(account: JsonObject) -> str | int | float | None:
    value = first(
        account, "account_number", "accountNumber", "number",
        "brokerage_account_number", "brokerageAccountNumber",
    )
    return value if isinstance(value, (str, int, float)) and not isinstance(value, bool) else None


def account_name(account: JsonObject) -> str:
    value = first(
        account, "nickname", "display_name", "displayName", "name",
        "account_type", "accountType", "type",
    )
    return str(value) if value is not None else "Unnamed account"


def account_summary(account: JsonObject) -> AccountSummary:
    """Pull the fields that identify an account, across MCP naming variants."""
    return {
        "tax_status": text(first(account, *TAX_STATUS_FIELDS)),
        "account_type": text(first(account, *ACCOUNT_TYPE_FIELDS)),
        "account_number": text(account_number(account)),
        "nickname": text(first(account, *NICKNAME_FIELDS)),
    }


def account_label(number: str, account: JsonObject | None) -> str:
    """A human-readable heading for one account's holdings."""
    if account is None:
        return number
    summary = account_summary(account)
    parts = [value for value in (summary["tax_status"], summary["nickname"]) if value]
    parts.append(number)
    return " · ".join(parts)


def text(value: object) -> str | None:
    """Render a scalar field, or None for a missing or non-scalar one."""
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    return str(value)


def first(record: JsonObject, *keys: str) -> JsonValue:
    return next((record[key] for key in keys if record.get(key) is not None), None)
