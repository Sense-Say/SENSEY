
# 📚 Control Systems: Time Response Crash Course
**Status:** 🚨 Emergency Exam Prep
**Goal:** Ace the 10 AM Exam
**Format:** Plain Text / Calculator-Friendly

---

## 1. The Big Picture
**Total Response** = **Transient** (Initial startup wiggles) + **Steady-State** (Final resting value).

*   **Poles (X):** Determine **STABILITY** and **SHAPE** (how much it wiggles).
*   **Zeros (O):** Determine **AMPLITUDE** (how high it goes).

---

## 2. First-Order Systems
**Look for:** A denominator with just `s` (no `s^2`).
**Standard Form:**
```text
G(s) = b / (s + b)
```

### 📝 Formulas (Sample Problem 1)
If `G(s) = 50 / (s + 50)`, then **b = 50**.

| Specification | Symbol | Formula | Calculator Example (b=50) |
| :--- | :--- | :--- | :--- |
| **Time Constant** | **Tc** | `1 / b` | 1 / 50 = **0.02s** |
| **Rise Time** | **Tr** | `2.2 / b` | 2.2 / 50 = **0.044s** |
| **Settling Time** | **Ts** | `4 / b` | 4 / 50 = **0.08s** |

> **⚠️ Watch Out:** If given `10 / (5s + 10)`, divide top and bottom by 5 first to isolate `s`.
> Result: `2 / (s + 2)`. Here, **b = 2**.

---

## 3. Second-Order Systems (The Main Event)
**Look for:** An `s^2` in the denominator.
**Standard Form:**
```text
          ωn^2
G(s) = -----------------------
       s^2 + 2ζωn*s + ωn^2
```

### 🔍 How to Identify Variables (Sample Problem 2)
Given: `G(s) = 16 / (s^2 + 8s + 16)`

1.  **Find ωn (Natural Frequency):**
    *   Look at the **Last Number** (16).
    *   `ωn = sqrt(16) = 4`
2.  **Find ζ (Damping Ratio):**
    *   Look at the **Middle Number** (8s).
    *   Formula: `2 * ζ * ωn = 8`
    *   `2 * ζ * (4) = 8`
    *   `8ζ = 8`  →  **ζ = 1**

### 🚦 The 4 Types of Responses
| Damping Ratio (ζ) | Type | What it does |
| :--- | :--- | :--- |
| **ζ = 0** | **Undamped** | Oscillates forever (Sine wave). |
| **0 < ζ < 1** | **Underdamped** | Wiggles then stops. (**Most Common Exam Question**) |
| **ζ = 1** | **Critically Damped** | Fast rise, NO overshoot. |
| **ζ > 1** | **Overdamped** | Slow rise, sluggish. |

---

## 4. Underdamped Formulas (0 < ζ < 1)
These are the most important formulas for the exam.

### A. The Frequencies
*   **ωn (Natural Freq):** The hypotenuse length.
*   **ωd (Damped Freq):** The actual ringing frequency.
    ```text
    ωd = ωn * sqrt(1 - ζ^2)
    ```
*   **σ (Sigma/Attenuation):** The decay rate (Real part).
    ```text
    σ = ζ * ωn
    ```

### B. Performance Specs (Calculator Ready)

#### 1. Percent Overshoot (%OS)
How much does it jump over the limit?
```text
%OS = e^( -(ζ * π) / sqrt(1 - ζ^2) ) * 100
```
*Note: `e` is Euler's number (shift+ln on calculator).*

#### 2. Finding ζ from %OS (The Reverse Formula)
If the problem gives you %OS and asks for Damping Ratio:
```text
      -ln(%OS / 100)
ζ = ------------------------------------
    sqrt( π^2 + (ln(%OS / 100))^2 )
```

#### 3. Settling Time (Ts) - The "2% Criterion"
How long to stop wiggling?
```text
Ts = 4 / (ζ * ωn)
```
*Tip: This uses the REAL part of the pole.*

#### 4. Peak Time (Tp)
Time to hit the highest point.
```text
Tp = π / (ωd)
```
*Expanded:* `Tp = π / (ωn * sqrt(1 - ζ^2))`

---

## 5. Visualizing the S-Plane (Sample Problem 3)
If given a graph with a "Pole" marked as an **X**:
*   **Horizontal distance:** magnitude of `ζ * ωn` (Real part)
*   **Vertical height:** magnitude of `ωd` (Imaginary part)
*   **Distance to origin (Hypotenuse):** `ωn`
*   **Angle θ:** `cos(θ) = ζ`

---

## 6. Mechanical Systems (Mass-Spring-Damper)
**Sample Problem 4 & 5**

**Transfer Function:**
```text
          1
G(s) = ----------------
       Js^2 + Ds + K
```
**Step 1:** Divide everything by **J** to clean up `s^2`.
```text
       1/J
-------------------------
s^2 + (D/J)s + (K/J)
```

**Step 2:** Match coefficients:
*   `ωn^2 = K / J`
*   `2 * ζ * ωn = D / J`

---

## 7. Strategy for "Unity Feedback" (Sample Prob 9)
If you see a block diagram with a feedback loop (negative feedback):

**Step 1: Simplify the block.**
Formula: `T(s) = G(s) / (1 + G(s))`

**Shortcut:**
If `G(s) = Num / Den`
Then `T(s) = Num / (Den + Num)`

**Example:**
*   G(s) = `225 / (s^2 + 12s)`
*   T(s) = `225 / (s^2 + 12s + 225)`
*   Now, `ωn^2 = 225` and `2ζωn = 12`. Solve normally.

---

## ⚡ Quick Cheat Sheet (Write this down!)

| Variable | Definition | How to find |
| :--- | :--- | :--- |
| **ωn** | Natural Freq | `sqrt(Last Number)` |
| **ζ** | Damping Ratio | `(Middle Number) / (2 * ωn)` |
| **Tp** | Peak Time | `3.1416 / Imaginary_Part` |
| **Ts** | Settling Time | `4 / Real_Part` |
| **%OS** | Overshoot | Depends ONLY on **ζ** |

**Good luck! You've got this.**