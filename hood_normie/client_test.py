import unittest

from hood_normie.client import normalize_account, normalize_quotes


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


if __name__ == "__main__":
    unittest.main()
