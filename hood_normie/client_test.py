import unittest

from hood_normie.accounts import account_label, account_summary
from hood_normie.client import RobinhoodClient, normalize_account, normalize_quotes


class FakeMcp:
    """Answers the tool calls fetch_holdings makes, without a network."""

    def __init__(self, accounts, portfolios, positions, quotes):
        self.accounts = accounts
        self.portfolios = portfolios
        self.positions = positions
        self.quotes = quotes
        self.quoted_symbols = None

    def connect(self):
        pass

    def call_tool(self, name, arguments=None):
        arguments = arguments or {}
        if name == "get_accounts":
            return self.accounts
        if name == "get_portfolio":
            return self.portfolios[arguments["account_number"]]
        if name == "get_equity_positions":
            return self.positions[arguments["account_number"]]
        if name == "get_equity_quotes":
            self.quoted_symbols = list(arguments["symbols"])
            return self.quotes
        raise AssertionError(f"unexpected tool {name}")


def fake_client(mcp):
    client = RobinhoodClient("token")
    client.mcp = mcp
    return client


class ClientNormalizationTest(unittest.TestCase):
    def test_normalizes_nested_portfolio_positions_and_quotes(self):
        result = normalize_account(
            {"data": {"total_value": "1000", "cash": "100"}},
            {"data": {"positions": [{"symbol": "VTI", "quantity": "2"}]}},
            {"data": {"quotes": [{"symbol": "VTI", "last_trade_price": "250"}]}},
        )
        self.assertEqual(result["net_liquidation_value"], "1000")
        self.assertEqual(result["cash"], "100")
        self.assertEqual(result["positions"], [
            {"symbol": "VTI", "quantity": "2", "price": "250"}
        ])

    def test_normalizes_quote_map(self):
        self.assertEqual(
            normalize_quotes([{"symbol": "BND", "price": {"amount": "72.50"}}]),
            {"BND": "72.50"},
        )


class AccountSummaryTest(unittest.TestCase):
    def test_builds_descriptive_account_label(self):
        self.assertEqual(
            account_label("ABC123", {
                "brokerageAccountType": "Roth IRA",
                "nickname": "Retirement",
            }),
            "Roth IRA · Retirement · ABC123",
        )

    def test_label_falls_back_to_the_number_alone(self):
        self.assertEqual(account_label("ABC123", None), "ABC123")
        self.assertEqual(account_label("ABC123", {}), "ABC123")

    def test_summarizes_field_name_variants(self):
        self.assertEqual(
            account_summary({
                "taxStatus": "Individual", "accountType": "cash",
                "accountNumber": "ABC123", "displayName": "Main",
            }),
            {"tax_status": "Individual", "account_type": "cash",
             "account_number": "ABC123", "nickname": "Main"},
        )

    def test_missing_and_non_scalar_fields_are_none(self):
        self.assertEqual(
            account_summary({"accountNumber": "ABC123", "nickname": {"a": 1}}),
            {"tax_status": None, "account_type": None,
             "account_number": "ABC123", "nickname": None},
        )


class FetchHoldingsTest(unittest.TestCase):
    def mcp(self):
        return FakeMcp(
            accounts={"accounts": [
                {"account_number": "111", "tax_status": "Individual",
                 "nickname": "Main"},
                {"account_number": "222", "retirement_account_type": "Roth IRA"},
            ]},
            portfolios={
                "111": {"total_value": "1500", "cash": "500"},
                "222": {"total_value": "700", "cash": "700"},
            },
            positions={
                "111": {"positions": [{"symbol": "VTI", "quantity": "4"}]},
                "222": {"positions": []},
            },
            quotes={"quotes": [{"symbol": "VTI", "price": "250"}]},
        )

    def test_lists_every_account_with_a_label(self):
        holdings = fake_client(self.mcp()).fetch_holdings()
        self.assertEqual([item["label"] for item in holdings],
                         ["Individual · Main · 111", "Roth IRA · 222"])
        self.assertEqual(holdings[0]["positions"],
                         [{"symbol": "VTI", "quantity": "4", "price": "250"}])
        self.assertEqual(holdings[0]["cash"], "500")
        self.assertEqual(holdings[1]["positions"], [])

    def test_selects_only_the_requested_accounts(self):
        holdings = fake_client(self.mcp()).fetch_holdings(["222"])
        self.assertEqual([item["account_number"] for item in holdings], ["222"])

    def test_quotes_are_requested_once_for_every_held_symbol(self):
        mcp = self.mcp()
        fake_client(mcp).fetch_holdings()
        self.assertEqual(mcp.quoted_symbols, ["VTI"])

    def test_no_numbered_account_is_an_error(self):
        mcp = self.mcp()
        mcp.accounts = {"accounts": [{"nickname": "Unnumbered"}]}
        with self.assertRaises(ValueError):
            fake_client(mcp).fetch_holdings()


if __name__ == "__main__":
    unittest.main()
