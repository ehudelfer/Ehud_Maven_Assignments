"""Tests for the investment calculator and its Flask interface."""

import importlib.util
import math
import io
import unittest
from pathlib import Path
from unittest.mock import patch

import app as web_app
import investment_calculator as day04_calculator


day03_path = Path(__file__).resolve().parent.parent / "Day03" / "investment_calculator.py"
spec = importlib.util.spec_from_file_location("day03_investment_calculator", day03_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load calculator from {day03_path}")
day03_calculator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(day03_calculator)
CALCULATORS = (day03_calculator, day04_calculator)


class CalculatorTests(unittest.TestCase):
    def test_zero_interest_and_yearly_balances(self):
        for calculator in CALCULATORS:
            with self.subTest(calculator=calculator.__name__):
                final, yearly, contributions, interest = calculator.calculate_investment(
                    1000, 2, 100, 0
                )
                self.assertEqual(yearly, [2200, 3400])
                self.assertEqual((final, contributions, interest), (3400, 3400, 0))

    def test_compounding_and_end_of_month_contributions(self):
        rate = 0.12 / 12
        expected = 1000 * (1 + rate) ** 12 + 100 * ((1 + rate) ** 12 - 1) / rate
        for calculator in CALCULATORS:
            with self.subTest(calculator=calculator.__name__):
                final, yearly, contributions, interest = calculator.calculate_investment(
                    1000, 1, 100, 12
                )
                self.assertAlmostEqual(final, expected)
                self.assertEqual(yearly, [final])
                self.assertEqual(contributions, 2200)
                self.assertAlmostEqual(interest, final - 2200)

    def test_invalid_inputs(self):
        cases = [
            ((-1, 1, 0, 0), "Starting budget"),
            ((0, 0, 0, 0), "duration"),
            ((0, -1, 0, 0), "duration"),
            ((0, 1.5, 0, 0), "whole number"),
            ((0, True, 0, 0), "whole number"),
            ((0, 1, -1, 0), "Monthly contribution"),
            ((0, 1, 0, -1), "Annual interest rate"),
            ((math.nan, 1, 0, 0), "finite"),
            ((0, 1, math.inf, 0), "finite"),
            ((0, 1, 0, math.nan), "finite"),
            ((0, 1, 0, math.inf), "finite"),
            ((0, 1, 1e308, 0), "too large"),
            ((10 ** 400, 1, 0, 0), "too large"),
            ((1e308, 1, 0, 1000), "too large"),
        ]
        for calculator in CALCULATORS:
            for args, message in cases:
                with self.subTest(calculator=calculator.__name__, args=args):
                    with self.assertRaisesRegex(ValueError, message):
                        calculator.calculate_investment(*args)

    def test_graph_uses_starting_balance_and_yearly_values(self):
        for calculator in CALCULATORS:
            with self.subTest(calculator=calculator.__name__):
                with patch.object(calculator.plt, "show"):
                    calculator.show_budget_graph(1000, 2, 100, [2300, 3700])
                    axes = calculator.plt.gca()
                    self.assertEqual(list(axes.lines[0].get_ydata()), [1000, 2200, 3400])
                    self.assertEqual(list(axes.lines[1].get_ydata()), [1000, 2300, 3700])
                    calculator.plt.close(axes.figure)

    def test_command_line_reports_summary_and_invalid_input(self):
        for calculator in CALCULATORS:
            with self.subTest(calculator=calculator.__name__):
                with patch("builtins.input", side_effect=["1000", "1", "100", "0"]):
                    with patch("sys.stdout", new_callable=io.StringIO) as output:
                        with patch.object(calculator, "show_budget_graph") as graph:
                            calculator.main()
                self.assertIn("Final Portfolio Value:   $2,200.00", output.getvalue())
                graph.assert_called_once_with(1000, 1, 100, [2200])

                with patch("builtins.input", side_effect=["nan", "1", "0", "0"]):
                    with patch("sys.stdout", new_callable=io.StringIO) as output:
                        calculator.main()
                self.assertIn("finite", output.getvalue())


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.client = web_app.app.test_client()
        self.values = {
            "starting_budget": "1000",
            "years": "2",
            "monthly_investment": "100",
            "annual_interest_rate": "0",
        }

    def test_get_displays_form(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="starting_budget"', response.data)
        self.assertNotIn(b"Final Portfolio Value", response.data)

    def test_valid_post_displays_summary_table_and_chart_data(self):
        response = self.client.post("/", data=self.values)
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Final Portfolio Value", text)
        self.assertIn("$3,400.00", text)
        self.assertIn("$2,200.00", text)
        self.assertIn("$0.00", text)
        self.assertIn("labels: [0, 1, 2]", text)
        self.assertIn("[1000.0, 2200.0, 3400.0]", text)

    def test_invalid_posts_report_error_and_preserve_values(self):
        cases = [
            ({"starting_budget": ""}, "valid numbers"),
            ({"years": "1.5"}, "valid numbers"),
            ({"years": "0"}, "at least 1 year"),
            ({"starting_budget": "-2"}, "cannot be negative"),
            ({"annual_interest_rate": "nan"}, "finite"),
            ({"monthly_investment": "inf"}, "finite"),
            ({"starting_budget": "1e999"}, "finite"),
            ({"starting_budget": "1e308", "annual_interest_rate": "1000"}, "too large"),
            ({"years": "1001"}, "1000 years"),
        ]
        for changed, message in cases:
            with self.subTest(changed=changed):
                response = self.client.post("/", data={**self.values, **changed})
                text = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(message, text)
                self.assertNotIn("Final Portfolio Value", text)
                for value in changed.values():
                    if value:
                        self.assertIn(f'value="{value}"', text)

    def test_web_duration_limit_accepts_boundary(self):
        response = self.client.post("/", data={**self.values, "years": "1000"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Final Portfolio Value", response.data)

    def test_debug_mode_is_disabled_by_default(self):
        self.assertFalse(web_app.app.debug)


if __name__ == "__main__":
    unittest.main()
