from decimal import Decimal
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from examples.rebalance.core import ClassTarget, Portfolio, Position
from examples.rebalance.report import (
    AccountHoldings, PortfolioReport, Report,
)
from hood_normie.accounts import account_records
from hood_normie.client import LabeledAccount
from hood_normie.oauth import OAuthError
from hood_normie.types import JsonObject, JsonValue
from webapp import demo
from webapp.api import accounts_json, holdings_json, report_json
from webapp.server import INDEX, make_handler


def _ignore_demo(build):
    """Adapt a zero-argument fake builder to the handler's build(demo) contract."""
    return lambda demo: build()


SAMPLE_ACCOUNT_RECORDS: list[JsonObject] = [
    {"accountNumber": "111", "taxStatus": "Individual", "accountType": "margin",
     "nickname": "Main"},
]

# The same records inside the wrapper a live `get_accounts` response uses.
SAMPLE_ACCOUNTS: JsonValue = {
    "accounts": [dict(account) for account in SAMPLE_ACCOUNT_RECORDS],
}

SAMPLE_HOLDINGS: list[LabeledAccount] = [{
    "label": "Individual · Main · 111",
    "account_number": "111",
    "net_liquidation_value": "2050",
    "cash": "1000",
    "positions": [
        {"symbol": "VTI", "quantity": "10", "price": "100"},
        {"symbol": "BND", "quantity": "2", "price": "25"},
    ],
}]


def sample_report():
    portfolio = Portfolio(
        name="taxable",
        targets=(ClassTarget("stocks", Decimal("1.0")),),
        account_numbers=("111",),
        target_cash=Decimal("-200"),
        minimum_trade=Decimal("5"),
    )
    account = AccountHoldings(
        label="111", kind="robinhood",
        positions={
            "VTI": Position("VTI", Decimal("10"), Decimal("100")),
            "MYSTERY": Position("MYSTERY", Decimal("2"), Decimal("25")),
        },
        cash=Decimal("1000"),
    )
    item = PortfolioReport(
        portfolio=portfolio,
        accounts=(account,),
        positions=account.positions,
        recommendations=(),
    )
    return Report(asset_classes={"VTI": "stocks"}, portfolios=(item,))


class ApiJsonTest(unittest.TestCase):
    def test_money_is_serialized_as_exact_decimal_strings(self):
        payload = report_json(sample_report())
        account = payload["portfolios"][0]["accounts"][0]
        self.assertEqual(account["cash"], "1000")
        self.assertEqual(account["total_value"], "2050")
        position = account["positions"][1]
        self.assertEqual(position["symbol"], "VTI")
        self.assertEqual(position["market_value"], "1000")
        self.assertIsInstance(position["market_value"], str)

    def test_unclassified_positions_are_reported_separately(self):
        payload = report_json(sample_report())
        portfolio = payload["portfolios"][0]
        self.assertEqual([item["symbol"] for item in portfolio["unclassified"]],
                         ["MYSTERY"])
        self.assertIsNone(portfolio["unclassified"][0]["asset_class"])

    def test_grand_total_sums_portfolios(self):
        self.assertEqual(report_json(sample_report())["grand_total"], "2050")


class AccountsJsonTest(unittest.TestCase):
    def test_summarizes_each_account(self):
        payload = accounts_json(SAMPLE_ACCOUNT_RECORDS)
        self.assertFalse(payload["demo"])
        self.assertEqual(payload["accounts"], [{
            "tax_status": "Individual", "account_type": "margin",
            "account_number": "111", "nickname": "Main",
        }])

    def test_absent_fields_are_null(self):
        payload = accounts_json([{"account_number": "222"}])
        self.assertIsNone(payload["accounts"][0]["nickname"])
        self.assertEqual(payload["accounts"][0]["account_number"], "222")


class HoldingsJsonTest(unittest.TestCase):
    def test_marks_positions_and_sorts_them_by_symbol(self):
        account = holdings_json(SAMPLE_HOLDINGS)["accounts"][0]
        self.assertEqual([item["symbol"] for item in account["positions"]],
                         ["BND", "VTI"])
        self.assertEqual(account["positions"][0]["market_value"], "50")
        self.assertEqual(account["positions"][1]["market_value"], "1000")

    def test_total_is_marked_positions_plus_cash(self):
        payload = holdings_json(SAMPLE_HOLDINGS)
        self.assertEqual(payload["accounts"][0]["cash"], "1000")
        self.assertEqual(payload["accounts"][0]["total_value"], "2050")
        self.assertEqual(payload["grand_total"], "2050")

    def test_money_stays_an_exact_decimal_string(self):
        holdings: list[LabeledAccount] = [{
            **SAMPLE_HOLDINGS[0], "cash": "0.10",
            "positions": [{"symbol": "VTI", "quantity": "3", "price": "0.20"}],
        }]
        account = holdings_json(holdings)["accounts"][0]
        self.assertEqual(account["positions"][0]["market_value"], "0.60")
        self.assertEqual(account["total_value"], "0.70")

    def test_demo_flag_travels_with_the_payload(self):
        self.assertTrue(holdings_json(SAMPLE_HOLDINGS, demo=True)["demo"])
        self.assertTrue(accounts_json([], demo=True)["demo"])


class DemoTest(unittest.TestCase):
    def test_builds_a_report_without_network_or_token(self):
        report = demo.build_demo_report()
        self.assertEqual([item.portfolio.name for item in report.portfolios],
                         ["Demo Taxable", "Demo Retirement"])
        self.assertGreater(report.grand_total, Decimal(0))

    def test_every_demo_holding_is_quoted(self):
        held = {symbol for holdings in demo.HOLDINGS.values()
                for symbol, _ in holdings}
        self.assertEqual(held - set(demo.PRICES), set())

    def test_demo_shows_an_unclassified_holding(self):
        report = demo.build_demo_report()
        taxable = report.portfolios[0]
        self.assertEqual([item.symbol for item in taxable.unclassified(
            report.asset_classes)], ["MEME"])

    def test_undeclared_class_is_sold_off_in_the_ira(self):
        report = demo.build_demo_report()
        plan = {item.asset_class: item for item in report.portfolios[1].recommendations}
        self.assertEqual(plan["alternatives"].target_value, Decimal("0.00"))
        self.assertEqual(plan["alternatives"].action, "SELL")

    def test_demo_accounts_match_the_demo_holdings(self):
        records = account_records(demo.demo_accounts())
        numbers = {account["account_number"] for account in records}
        self.assertEqual(numbers, set(demo.HOLDINGS))

    def test_demo_holdings_are_labeled_and_marked(self):
        payload = holdings_json(demo.demo_holdings(), demo=True)
        labels = [account["label"] for account in payload["accounts"]]
        self.assertEqual(labels, ["Individual · Demo Brokerage · DEMO-TAXABLE",
                                  "Roth IRA · Demo Retirement · DEMO-IRA"])
        self.assertGreater(Decimal(payload["grand_total"]), Decimal(0))

    def test_demo_report_is_flagged_in_the_payload(self):
        payload = report_json(demo.build_demo_report(), demo=True)
        self.assertTrue(payload["demo"])
        self.assertFalse(report_json(sample_report())["demo"])


class ServerTest(unittest.TestCase):
    def serve(self, build, accounts=None, holdings=None):
        build = _ignore_demo(build)
        accounts = _ignore_demo(accounts or (lambda: SAMPLE_ACCOUNTS))
        holdings = _ignore_demo(holdings or (lambda: SAMPLE_HOLDINGS))
        root = tempfile.mkdtemp()
        with open(os.path.join(root, INDEX), "w", encoding="utf-8") as stream:
            stream.write("<!doctype html><div id=root></div>")
        os.mkdir(os.path.join(root, "assets"))
        with open(os.path.join(root, "assets", "app.js"), "w", encoding="utf-8") as s:
            s.write("console.log(1)")
        # A file the bundle must never expose, next to but outside the root.
        with open(os.path.join(root, "..", "outside.txt"), "w", encoding="utf-8") as s:
            s.write("secret")
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(root, build, accounts, holdings)
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def get(self, url):
        with urllib.request.urlopen(url) as response:
            return response.status, response.read().decode(), dict(response.headers)

    def test_serves_the_report_as_json(self):
        base = self.serve(sample_report)
        status, body, headers = self.get(f"{base}/api/rebalance")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["portfolios"][0]["name"], "taxable")
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_serves_the_account_list_as_json(self):
        base = self.serve(sample_report)
        status, body, _ = self.get(f"{base}/api/accounts")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["accounts"][0]["account_number"], "111")
        self.assertEqual(payload["accounts"][0]["tax_status"], "Individual")

    def test_serves_holdings_as_json(self):
        base = self.serve(sample_report)
        status, body, _ = self.get(f"{base}/api/holdings")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["accounts"][0]["label"], "Individual · Main · 111")
        self.assertEqual(payload["accounts"][0]["total_value"], "2050")

    def test_holdings_errors_report_reauthentication(self):
        def holdings():
            raise OAuthError("token expired")

        base = self.serve(sample_report, holdings=holdings)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get(f"{base}/api/holdings")
        self.assertEqual(caught.exception.code, 401)

    def test_config_errors_become_client_errors(self):
        def build():
            raise ValueError("portfolio names must be unique")

        base = self.serve(build)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get(f"{base}/api/rebalance")
        self.assertEqual(caught.exception.code, 400)
        self.assertIn("must be unique", json.loads(caught.exception.read())["error"])

    def test_missing_config_points_at_the_example_and_demo_mode(self):
        def build():
            raise FileNotFoundError(2, "No such file", "/repo/config.yaml")

        base = self.serve(build)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get(f"{base}/api/rebalance")
        self.assertEqual(caught.exception.code, 400)
        message = json.loads(caught.exception.read())["error"]
        self.assertIn("/repo/config.yaml", message)
        self.assertIn("Demo", message)

    def test_expired_token_asks_for_reauthentication(self):
        def build():
            raise OAuthError("token expired")

        base = self.serve(build)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get(f"{base}/api/rebalance")
        self.assertEqual(caught.exception.code, 401)
        self.assertIn("authenticate", json.loads(caught.exception.read())["error"])

    def test_serves_static_assets(self):
        base = self.serve(sample_report)
        status, body, headers = self.get(f"{base}/assets/app.js")
        self.assertEqual(status, 200)
        self.assertEqual(body, "console.log(1)")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_client_side_route_falls_back_to_the_app_shell(self):
        base = self.serve(sample_report)
        status, body, _ = self.get(f"{base}/rebalance")
        self.assertEqual(status, 200)
        self.assertIn("id=root", body)

    def test_missing_asset_is_not_masked_by_the_shell(self):
        base = self.serve(sample_report)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get(f"{base}/assets/missing.js")
        self.assertEqual(caught.exception.code, 404)

    def test_refuses_to_traverse_out_of_the_static_root(self):
        base = self.serve(sample_report)
        for path in ("/../outside.txt", "/%2e%2e/outside.txt", "/assets/../../outside.txt"):
            with self.subTest(path=path):
                try:
                    status, body, _ = self.get(base + path)
                except urllib.error.HTTPError as error:
                    self.assertEqual(error.code, 404)
                else:
                    self.assertNotIn("secret", body)

    def test_demo_param_selects_the_demo_builder(self):
        seen: list[bool] = []

        def build(demo):
            seen.append(demo)
            return sample_report()

        root = tempfile.mkdtemp()
        with open(os.path.join(root, INDEX), "w", encoding="utf-8") as stream:
            stream.write("<!doctype html><div id=root></div>")
        handler = make_handler(root, build, _ignore_demo(lambda: SAMPLE_ACCOUNTS),
                               _ignore_demo(lambda: SAMPLE_HOLDINGS))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_address[1]}"

        for query, expected in (("", False), ("?demo=1", True), ("?demo=true", True),
                                ("?demo=0", False), ("?demo=maybe", False)):
            with self.subTest(query=query):
                _, body, _ = self.get(f"{base}/api/rebalance{query}")
                self.assertEqual(seen[-1], expected)
                self.assertEqual(json.loads(body)["demo"], expected)

    def test_demo_param_reaches_every_endpoint(self):
        seen: list[tuple[str, bool]] = []

        def accounts(demo):
            seen.append(("accounts", demo))
            return SAMPLE_ACCOUNTS

        def holdings(demo):
            seen.append(("holdings", demo))
            return SAMPLE_HOLDINGS

        root = tempfile.mkdtemp()
        with open(os.path.join(root, INDEX), "w", encoding="utf-8") as stream:
            stream.write("<!doctype html><div id=root></div>")
        handler = make_handler(root, _ignore_demo(sample_report), accounts, holdings)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_address[1]}"

        for path in ("accounts", "holdings"):
            for query, expected in (("", False), ("?demo=1", True)):
                with self.subTest(path=path, query=query):
                    _, body, _ = self.get(f"{base}/api/{path}{query}")
                    self.assertEqual(seen[-1], (path, expected))
                    self.assertEqual(json.loads(body)["demo"], expected)

    def test_unknown_api_endpoint_is_json_not_the_shell(self):
        base = self.serve(sample_report)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get(f"{base}/api/nope")
        self.assertEqual(caught.exception.code, 404)
        self.assertIn("unknown endpoint", json.loads(caught.exception.read())["error"])


if __name__ == "__main__":
    unittest.main()
