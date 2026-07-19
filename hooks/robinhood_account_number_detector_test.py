import unittest

from hooks.robinhood_account_number_detector import contains_account_number


class RobinhoodAccountNumberDetectorTest(unittest.TestCase):
    def test_yaml_inline_list(self):
        self.assertTrue(contains_account_number(
            'robinhood_account_numbers: ["907314682"]',
        ))

    def test_yaml_block_list(self):
        self.assertTrue(contains_account_number(
            'robinhood_account_numbers:\n  - "907314682"\n',
        ))

    def test_python_assignment(self):
        self.assertTrue(contains_account_number(
            'robinhood_account_numbers = ["907314682"]',
        ))

    def test_ignores_unrelated_numbers(self):
        self.assertFalse(contains_account_number('target_amount: 238412.25'))

    def test_allows_empty_account_list(self):
        self.assertFalse(contains_account_number('robinhood_account_numbers: []'))


if __name__ == "__main__":
    unittest.main()
