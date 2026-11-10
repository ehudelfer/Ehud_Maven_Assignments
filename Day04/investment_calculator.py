import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def calculate_investment(
    starting_budget: float,
    years: int,
    monthly_investment: float,
    annual_interest_rate: float,
) -> tuple[float, list[float], float, float]:
    """Calculate compound investment growth over time.

    Assumes monthly contributions are added at the end of each month.

    Returns:
        tuple containing:
        - final_budget (float)
        - yearly_budgets (list[float])
        - total_contributions (float)
        - total_interest_earned (float)
    """
    if starting_budget < 0:
        raise ValueError("Starting budget cannot be negative.")
    if years <= 0:
        raise ValueError("Investment duration must be at least 1 year.")
    if monthly_investment < 0:
        raise ValueError("Monthly contribution cannot be negative.")
    if annual_interest_rate < 0:
        raise ValueError("Annual interest rate cannot be negative.")

    monthly_interest_rate = annual_interest_rate / 100 / 12
    budget = starting_budget
    yearly_budgets = []

    for _ in range(years):
        for _ in range(12):
            budget *= 1 + monthly_interest_rate
            budget += monthly_investment
        yearly_budgets.append(budget)

    total_contributions = starting_budget + (monthly_investment * 12 * years)
    total_interest_earned = budget - total_contributions

    return budget, yearly_budgets, total_contributions, total_interest_earned


def show_budget_graph(
    starting_budget: float,
    years: int,
    monthly_investment: float,
    yearly_budgets: list[float],
) -> None:
    """Plot total principal invested vs compound portfolio growth over time."""
    years_list = list(range(years + 1))
    invested_budgets = [
        starting_budget + (monthly_investment * 12 * year) for year in years_list
    ]

    plt.figure(figsize=(10, 6))
    plt.plot(
        years_list,
        invested_budgets,
        label="Total Principal Invested",
        linestyle="--",
        color="#1f77b4",
        linewidth=2,
    )
    plt.plot(
        years_list,
        [starting_budget, *yearly_budgets],
        label="Portfolio Value (with Interest)",
        color="#2ca02c",
        linewidth=2.5,
    )

    plt.title("Compound Investment Growth Over Time", fontsize=14, fontweight="bold")
    plt.xlabel("Year", fontsize=11)
    plt.ylabel("Portfolio Value ($)", fontsize=11)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(fontsize=10)

    # Format Y-axis with currency symbols
    formatter = ticker.StrMethodFormatter("${x:,.0f}")
    plt.gca().yaxis.set_major_formatter(formatter)

    plt.tight_layout()
    plt.show()


def main() -> None:
    print("==================================================")
    print("      🌱 Compound Investment Growth Simulator     ")
    print("==================================================\n")

    try:
        starting_budget = float(input("Initial principal ($): "))
        years = int(input("Investment horizon (years): "))
        monthly_investment = float(input("Monthly contribution ($): "))
        annual_interest_rate = float(input("Expected annual return (%): "))

        (
            final_budget,
            yearly_budgets,
            total_contributions,
            total_interest_earned,
        ) = calculate_investment(
            starting_budget,
            years,
            monthly_investment,
            annual_interest_rate,
        )

    except ValueError as error:
        print(f"\n❌ Invalid input: {error}")
        return

    print("\n--------------------------------------------------")
    print("                Year-End Portfolio                ")
    print("--------------------------------------------------")
    for year, budget in enumerate(yearly_budgets, start=1):
        print(f"Year {year:2d}: ${budget:,.2f}")

    print("\n--------------------------------------------------")
    print("                Investment Summary                ")
    print("--------------------------------------------------")
    print(f"Total Principal Invested: ${total_contributions:,.2f}")
    print(f"Total Interest Earned:   ${total_interest_earned:,.2f}")
    print(f"Final Portfolio Value:   ${final_budget:,.2f}")
    print("--------------------------------------------------")
    print("✨ 'Compound interest is the eighth wonder of the world.")
    print("   He who understands it, earns it.' — Albert Einstein\n")

    show_budget_graph(
        starting_budget,
        years,
        monthly_investment,
        yearly_budgets,
    )


if __name__ == "__main__":
    main()