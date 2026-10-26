def calculate_michaelis_menten(v_max: float, substrate_conc: float, km: float) -> float:
    """
    Calculates the reaction velocity (v) using the Michaelis-Menten equation:
    v = (Vmax * [S]) / (Km + [S])
    """
    return (v_max * substrate_conc) / (km + substrate_conc)


def main():
    print("--- Michaelis-Menten Kinetics Calculator ---")
    
    try:
        # Prompting user for inputs
        v_max = float(input("Enter maximum reaction velocity (Vmax): "))
        substrate_conc = float(input("Enter substrate concentration ([S]): "))
        km = float(input("Enter Michaelis constant (Km): "))

        # Input validation
        if v_max < 0 or substrate_conc < 0 or km < 0:
            print("\nError: Concentrations and rates must be non-negative values.")
            return
        
        if km + substrate_conc == 0:
            print("\nError: (Km + [S]) cannot equal zero (division by zero).")
            return

        # Perform calculation
        velocity = calculate_michaelis_menten(v_max, substrate_conc, km)

        # Output result
        print("\n--- Results ---")
        print(f"Vmax: {v_max}")
        print(f"[S]:  {substrate_conc}")
        print(f"Km:   {km}")
        print(f"Reaction Velocity (v): {velocity:.4f}")

    except ValueError:
        print("\nError: Please enter valid numerical values.")

if __name__ == "__main__":
    main()