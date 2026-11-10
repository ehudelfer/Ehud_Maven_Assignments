from flask import Flask, render_template, request

from investment_calculator import calculate_investment

app = Flask(__name__)

FIELDS = {
    "starting_budget": float,
    "years": int,
    "monthly_investment": float,
    "annual_interest_rate": float,
}


@app.route("/", methods=["GET", "POST"])
def index():
    form = {}
    result = None
    error = None

    if request.method == "POST":
        form = {name: request.form.get(name, "").strip() for name in FIELDS}
        try:
            values = {name: cast(form[name]) for name, cast in FIELDS.items()}
            final, yearly, contributions, interest = calculate_investment(**values)
            start = values["starting_budget"]
            monthly = values["monthly_investment"]
            result = {
                "final": final,
                "contributions": contributions,
                "interest": interest,
                "rows": list(enumerate(yearly, start=1)),
                "labels": list(range(values["years"] + 1)),
                "portfolio": [round(v, 2) for v in [start, *yearly]],
                "invested": [
                    round(start + monthly * 12 * y, 2)
                    for y in range(values["years"] + 1)
                ],
            }
        except ValueError as exc:
            error = str(exc)
            if "invalid literal" in error or "could not convert" in error:
                error = "Please enter valid numbers (years must be a whole number)."

    return render_template("index.html", form=form, result=result, error=error)


if __name__ == "__main__":
    app.run(debug=True)
