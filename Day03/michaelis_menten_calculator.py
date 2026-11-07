import numpy as np

def main():
    print("--- Michaelis-Menten Kinetics Calculator (using SciPy/NumPy) ---")

    v_max = float(input("Enter maximum reaction velocity (Vmax): "))
    substrate_conc = float(input("Enter substrate concentration ([S]): "))
    km = float(input("Enter Michaelis constant (Km): "))

    # Using NumPy vector evaluation (standard in PyPI packages like SciPy)
    s = np.array([substrate_conc], dtype=float)
    velocity = float((v_max * s) / (km + s))

    print(f"\nCalculated Reaction Velocity (v): {velocity:.4f}")

if __name__ == "__main__":
    main()