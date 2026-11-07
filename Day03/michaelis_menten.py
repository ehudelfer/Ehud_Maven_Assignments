def calculate_michaelis_menten(v_max: float, substrate_conc: float, km: float) -> float:
    """
    Calculates the reaction velocity (v) using the Michaelis-Menten equation:
    v = (Vmax * [S]) / (Km + [S])
    """
    return (v_max * substrate_conc) / (km + substrate_conc)


def get_positive_float(prompt: str) -> float:
    """Prompts the user repeatedly until a valid non-negative float is entered."""
    while True:
        try:
            val = float(input(prompt))
            if val < 0:
                print("Error: Value cannot be negative. Please try again.")
                continue
            return val
        except ValueError:
            print("Error: Invalid input. Please enter a numerical value.")


def main():
    print("--- Michaelis-Menten Kinetics Calculator ---")

    while True:
        v_max = get_positive_float("Enter maximum reaction velocity (Vmax): ")
        substrate_conc = get_positive_float("Enter substrate concentration ([S]): ")
        km = get_positive_float("Enter Michaelis constant (Km): ")

        # Check for division by zero (e.g., if both Km and [S] are 0)
        if km + substrate_conc == 0:
            print("\nError: Both Km and [S] cannot be zero (division by zero). Please try again.\n")
            continue

        velocity = calculate_michaelis_menten(v_max, substrate_conc, km)

        print("\n--- Results ---")
        print(f"Vmax:                  {v_max}")
        print(f"[S]:                   {substrate_conc}")
        print(f"Km:                    {km}")
        print(f"Reaction Velocity (v): {velocity:.4f}\n")

        # Ask user if they want to calculate again
        again = input("Do another calculation? (y/n): ").strip().lower()
        if again != 'y':
            print("Goodbye!")
            break


if __name__ == "__main__":
    main()