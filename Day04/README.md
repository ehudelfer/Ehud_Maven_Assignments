# Investment calculator

## How it works

Enter an initial amount, investment duration, monthly contribution, and expected
annual return. Each month, the calculator applies one twelfth of the annual
return to the current balance, then adds the monthly contribution. It displays
the balance at the end of each year, the total amount invested, the interest
earned, and the final balance, alongside a chart comparing investment growth
with contributions.

The result is an estimate based on a constant return; it does not account for
fees, taxes, inflation, or changes in market returns.

## Running the web app

Install the dependencies and start the web app from the repository root:

```powershell
python -m pip install -r Day04\requirements.txt
python Day04\app.py
```

Open http://127.0.0.1:5000. The Flask development server is intended for local
development, not production hosting. The chart loads Chart.js from a CDN and
requires an internet connection; the results and table work without it.

The calculator compounds monthly, adding contributions at the end of each
month. Inputs must be non-negative and finite, and the duration must be a
positive whole number. The web form additionally limits the duration to 1000
years to keep requests and rendered pages bounded.

Run the tests from the repository root:

```powershell
python Day04\test_investment_app.py
```

The tests cover the Flask app and both the Day03 and Day04 calculator copies.
