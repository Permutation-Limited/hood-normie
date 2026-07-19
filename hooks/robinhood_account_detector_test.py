import unittest

from hooks.robinhood_account_detector import contains_account_number


class RobinhoodAccountNumberDetectorTest(unittest.TestCase):
    def test_flags_account_number_in_example_config(self):
        result = contains_account_number(
            "examples/rebalance/config.example.yaml",
            '  - "716715529"',
        )
        self.assertTrue(result)

    def test_ignores_numbers_outside_example_config(self):
        result = contains_account_number("config.yaml", '  - "716715529"')
        self.assertFalse(result)

    def test_ignores_non_account_numeric_values(self):
        result = contains_account_number(
            "examples/rebalance/config.example.yaml",
            "target_amount: 238412.25",
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
