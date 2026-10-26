# Day 02: Michaelis–Menten Kinetics Calculator

This program calculates the reaction velocity ($v$) of an enzyme-catalyzed reaction using **Michaelis–Menten kinetics**.

## Overview & Formula

The Michaelis–Menten equation models how the rate of an enzymatic reaction depends on the concentration of a substrate:

$$v = \frac{V_{\max} \cdot [S]}{K_m + [S]}$$

Where:
* **$V_{\max}$**: Maximum reaction velocity achievable at saturating substrate concentration.
* **$[S]$**: Substrate concentration.
* **$K_m$**: Michaelis constant (the substrate concentration at which the reaction velocity is half of $V_{\max}$).
* **$v$**: Calculated reaction velocity.

---

## Files

* `michaelis_menten.py`: Python script containing the calculator program.

---
## Example
   # Michaelis-Menten Kinetics Calculator
Enter maximum reaction velocity (Vmax): 100
Enter substrate concentration ([S]): 5
Enter Michaelis constant (Km): 15

# Result
Vmax: 100.0
[S]:  5.0
Km:   15.0
Reaction Velocity (v): 25.0000  
