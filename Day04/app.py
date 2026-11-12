from flask import Flask, render_template, request

if __package__:
    from .investment_calculator import calculate_investment
else:
    from investment_calculator import calculate_investment

app = Flask(__name__)

FIELDS = ("starting_budget", "years", "monthly_investment", "annual_interest_rate")
MAX_WEB_YEARS = 1000


@app.route("/", methods=["GET", "POST"])
def index():
    form = {}
    result = None
    error = None

    if request.method == "POST":
        form = {name: request.form.get(name, "").strip() for name in FIELDS}
        try:
            start = float(form["starting_budget"])
            years = int(form["years"])
            monthly = float(form["monthly_investment"])
            annual_rate = float(form["annual_interest_rate"])
        except ValueError:
            error = "Please enter valid numbers (years must be a whole number)."
        else:
            try:
                if years > MAX_WEB_YEARS:
                    raise ValueError(f"Investment duration cannot exceed {MAX_WEB_YEARS} years.")
                final, yearly, contributions, interest = calculate_investment(
                    start, years, monthly, annual_rate
                )
            except ValueError as exc:
                error = str(exc)
            else:
                result = {
                    "final": final,
                    "contributions": contributions,
                    "interest": interest,
                    "rows": list(enumerate(yearly, start=1)),
                    "labels": list(range(years + 1)),
                    "portfolio": [round(v, 2) for v in [start, *yearly]],
                    "invested": [
                        round(start + monthly * 12 * y, 2)
                        for y in range(years + 1)
                    ],
                }

    return render_template(
        "index.html", form=form, result=result, error=error, max_years=MAX_WEB_YEARS
    )


if __name__ == "__main__":
    app.run()
