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
from hood_normie.oauth import OAuthError
from webapp import demo
from webapp.api import report_json
from webapp.server import INDEX, make_handler


def _ignore_demo(build):
    """Adapt a zero-argument fake builder to the handler's build(demo) contract."""
    return lambda demo: build()


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

    def test_demo_report_is_flagged_in_the_payload(self):
        payload = report_json(demo.build_demo_report(), demo=True)
        self.assertTrue(payload["demo"])
        self.assertFalse(report_json(sample_report())["demo"])


class ServerTest(unittest.TestCase):
    def serve(self, build):
        build = _ignore_demo(build)
        root = tempfile.mkdtemp()
        with open(os.path.join(root, INDEX), "w", encoding="utf-8") as stream:
            stream.write("<!doctype html><div id=root></div>")
        os.mkdir(os.path.join(root, "assets"))
        with open(os.path.join(root, "assets", "app.js"), "w", encoding="utf-8") as s:
            s.write("console.log(1)")
        # A file the bundle must never expose, next to but outside the root.
        with open(os.path.join(root, "..", "outside.txt"), "w", encoding="utf-8") as s:
            s.write("secret")
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root, build))
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
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root, build))
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

    def test_unknown_api_endpoint_is_json_not_the_shell(self):
        base = self.serve(sample_report)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get(f"{base}/api/nope")
        self.assertEqual(caught.exception.code, 404)
        self.assertIn("unknown endpoint", json.loads(caught.exception.read())["error"])


if __name__ == "__main__":
    unittest.main()
