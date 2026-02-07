# Haptic Feedback 9 Motors Conceptual Guide
---
## The "Full Phase" Component List

1.  **Raspberry Pi 5**
2.  **Waveshare UPS Module 3S** (I2C Address: `0x41`)
3.  **PCA9685 PWM Driver** (I2C Address: `0x40`)
4.  **MP1584EN Buck Converter** (Set to **3.3V** output)
5.  **2x ULN2803A ICs** (One for motors 1-8, one for motor 9)
6.  **9x Coin Vibration Motors**

---
This section provides the "Engineering Context." Understanding **why** we use these specific parts will help you troubleshoot and expand your project in the future.

### 1. The "Why" (Design Logic)

*   **Why PCA9685? (The Brain):**
    The Raspberry Pi 5 is powerful, but generating 9 precise PWM signals takes up CPU resources and can be jittery if the OS is busy. The PCA9685 "set and forget" logic means you tell it the speed once via I2C, and the chip handles the pulsing perfectly while the Pi moves on to other tasks.
*   **Why ULN2803A? (The Muscle):**
    Think of this as a row of 8 high-power light switches. The PCA9685 logic signal is too weak to move a motor (it's like trying to start a car with a watch battery). The ULN2803A uses the small PCA9685 signal to "flip the switch" on the high-current 3.3V line.
*   **Why the MP1584EN? (The Safety Valve):**
    If you used a simple resistor to drop 5V to 3V, it would get incredibly hot. A Buck Converter is a "Switching Regulator"—it converts voltage efficiently with very little heat. It ensures that even if the UPS battery is fully charged (12.6V) or nearly empty, your motors always see exactly 3.3V.

---

### 2. The "Dos" (Best Practices)

*   **DO Calibrate Before Connecting:** Always use a multimeter to set the Buck Converter to 3.3V *before* the motors are attached. If the screw is turned the wrong way, it could output 5V or more and instantly burn out your 9 motors.
*   **DO Use a Common Ground:** Ensure every single component (Pi, UPS, PCA9685, ULN2803, Buck Converter) shares a single "Ground" connection. In electronics, voltage is "potential difference"; if they don't share a ground, they don't speak the same language.
*   **DO Stress Test Heat:** After running the motors for 5 minutes, touch the ULN2803A chips and the Buck Converter. They should be warm, but not painful. If they are painful to touch, you have a short circuit or are pulling too much current.
*   **DO Implement "Graceful Shutdown":** In your Python code, always use a `try...except` block to ensure that if the program crashes, all motors are turned **OFF**. (See Developer Notes).

---

### 3. The "Don'ts" (Safety Warnings)

*   **DON'T Power Motors from the Pi's 3.3V Pin:** The Pi's onboard 3.3V regulator is meant for sensors (milliamps). Drawing 1A for 9 motors will cause the Pi 5 to undergo a "brown-out" reset or permanently damage the internal PMIC (Power Management IC).
*   **DON'T Skip the "Pin 10" Connection:** On the ULN2803A, Pin 10 is the "COM" (Common Free-wheeling Diode) pin. Motors are "inductive loads"—when they stop, they throw a spike of high voltage back into the wire. Pin 10 catches this spike and sends it safely back to the power supply.
*   **DON'T "Hot-Swap":** Do not plug or unplug motors or the PCA9685 while the UPS is turned on. Inductive sparks during plugging can kill the I2C pins on your Raspberry Pi 5.

---

### 4. Developer Notes (Pro-Tips)

#### **The I2C Address Map**
Your system has a "Map." If you ever add more sensors, keep this in mind:
*   `0x40`: PCA9685 (Default)
*   `0x41`: Waveshare UPS (Fixed)
*   `0x70`: PCA9685 "All Call" (A special address to talk to all PWM drivers at once).

#### **PWM Frequency Tuning**
Vibration motors have a "resonant frequency." 
*   If you set the `pca.frequency` too high (e.g., 1000Hz), the motor might just hum and not vibrate well.
*   If you set it too low (e.g., 20Hz), the vibration will feel "choppy."
*   **Sweet Spot:** **60Hz to 200Hz** usually provides the smoothest intensity control for coin motors.

#### **Python Error Handling Template**
Always use this structure to prevent the motors from getting "stuck" in the ON position if your script fails:

```python
try:
    # Your motor logic here
    while True:
        set_vibration(0, 1.0)
except KeyboardInterrupt:
    print("User stopped the script")
finally:
    # This runs NO MATTER WHAT (even on errors)
    for i in range(16): # Clear all 16 channels of the PCA9685
        pca.channels[i].duty_cycle = 0
    pca.deinit()
    print("Motors safely deactivated.")
```

#### **Wire Gauge**
Since 9 motors can pull ~1A, don't use the very thinnest "jumper wires" for the main power line (the one coming out of the Buck Converter). Use a slightly thicker wire for the **Main +3.3V Rail** and the **Main Ground** to prevent voltage drop.

---
Okay, here is the complete and detailed wiring diagram guide, formatted for a GitHub README.md, for your Haptic Feedback Forearm Sleeve.

This guide assumes you are building the "Full Phase" setup with the PCA9685, ULN2803A, and MP1584EN all on the arm, connected by a 4-wire umbilical to the Raspberry Pi and Waveshare UPS at the waist.

---

# Haptic Feedback Forearm Sleeve: Wiring Guide

This document details the wiring for a 9-motor haptic feedback forearm sleeve, designed for obstacle avoidance. The system is split into two modules: a **Waist Pouch** (housing the Raspberry Pi 5 and Waveshare UPS) and a **Forearm Sleeve** (housing the haptic drive electronics and motors).

---

## 1. System Overview

### **A. Waist Pouch Module**
*   **Components:**
    *   Raspberry Pi 5
    *   Waveshare UPS Module 3S (I2C address: `0x41`)
*   **Function:** Provides power to the entire system and acts as the central processing unit and I2C master.

### **B. Forearm Sleeve Module**
*   **Components:**
    *   MP1584EN Buck Converter (set to 3.3V output)
    *   PCA9685 PWM Driver (I2C address: `0x40`)
    *   2x ULN2803A Darlington Transistor Arrays (DIP-18 package)
    *   5x7cm FR4 Universal Protoboard
    *   9x 1027 Mobile Phone Flat Vibration Motors
*   **Function:** Receives power and I2C commands, drives the 9 vibration motors with precise PWM signals.

### **C. The "Umbilical Cord"**
*   A flexible 4-wire cable connecting the Waist Pouch to the Forearm Sleeve.
*   **Wires:** +5V, GND, SDA (I2C Data), SCL (I2C Clock)

---

## 2. Component Pinouts & Details

### **A. Raspberry Pi 5 GPIO Pinout (Waist Pouch Side)**
| Pin # | Function |
| :---- | :------- |
| 1     | 3.3V     |
| 2     | 5V       |
| 3     | SDA (I2C) |
| 5     | SCL (I2C) |
| 6     | GND      |

### **B. Waveshare UPS Module 3S Header (Waist Pouch Side)**
*   Connects directly to the Raspberry Pi 5 GPIO pins for power and I2C communication.
*   **Important:** Ensure the UPS is configured to provide power to the Pi.

### **C. MP1584EN Buck Converter (Forearm Sleeve Side)**
*   **Input:** `IN+` (5V), `IN-` (GND)
*   **Output:** `OUT+` (Regulated 3.3V), `OUT-` (GND)
*   **Calibration:** MUST be set to **3.3V** output using a multimeter before connecting any other components.

### **D. PCA9685 PWM Driver (Forearm Sleeve Side)**
*   **Power:** `VCC` (3.3V Logic Power), `GND`
*   **I2C:** `SDA`, `SCL`
*   **Outputs:** `LED0` through `LED15` (PWM signals for motors)

### **E. ULN2803A Darlington Array (Forearm Sleeve Side)**
*   **Inputs:** Pin 1 through Pin 8 (Receives PWM signals)
*   **GND:** Pin 9
*   **COM:** Pin 10 (Connect to Motor Power Rail for Flyback Diode Protection)
*   **Outputs:** Pin 11 through Pin 18 (Switches motor negative to ground)

### **F. 1027 Coin Vibration Motors**
*   Two small wires (typically Red for Positive, Blue/Black for Negative).

---

## 3. Wiring Diagram: Step-by-Step Guide

This guide details connections to the **5x7cm FR4 Universal Protoboard** in the Forearm Sleeve.

### **Step 0: Buck Converter Calibration (CRITICAL!)**
1.  Connect the **+5V** and **GND** from your Waveshare UPS (or a separate 5V source) to the **`IN+`** and **`IN-`** of the MP1584EN Buck Converter.
2.  Power on the UPS.
3.  Using a multimeter, measure the voltage between **`OUT+`** and **`OUT-`**.
4.  Carefully adjust the small potentiometer screw on the Buck Converter until the output reads **3.3V**.
5.  Power off the UPS. **Do NOT adjust the screw again.**

### **Step 1: Umbilical Cord Connections (Waist Pouch to Forearm Sleeve)**

| Umbilical Wire Color | Connects To (Waist Pouch) | Connects To (Forearm Sleeve Module) | AWG | Type |
| :------------------- | :------------------------ | :---------------------------------- | :-- | :--- |
| **Red (5V)**         | UPS 5V Pin (or Pi 5V Pin)  | MP1584EN `IN+`                      | 22  | Stranded |
| **Black (GND)**      | UPS GND Pin (or Pi GND Pin) | MP1584EN `IN-`                      | 22  | Stranded |
| **Yellow (SDA)**     | Pi SDA (Pin 3)            | PCA9685 `SDA`                       | 22  | Stranded |
| **Blue (SCL)**       | Pi SCL (Pin 5)            | PCA9685 `SCL`                       | 22  | Stranded |

### **Step 2: Forearm Sleeve Module: Power Rails on Perfboard**

Establish a central 3.3V power rail and a common ground rail on your perfboard.

1.  **3.3V Power Rail:** Solder a bare (or stripped) 22 AWG stranded wire along a row of holes on your perfboard.
    *   Connect **MP1584EN `OUT+`** to this `3.3V Power Rail`.
    *   Connect **PCA9685 `VCC`** to this `3.3V Power Rail`.
    *   Connect **ULN2803A (Chip 1) Pin 10 (`COM`)** to this `3.3V Power Rail`.
    *   Connect **ULN2803A (Chip 2) Pin 10 (`COM`)** to this `3.3V Power Rail`.
    *   **All 9 Red Motor Wires** will eventually connect to this `3.3V Power Rail`.
2.  **Ground Rail:** Solder a bare (or stripped) 22 AWG stranded wire along another row of holes on your perfboard (parallel to the 3.3V rail).
    *   Connect **MP1584EN `OUT-`** to this `GND Rail`.
    *   Connect **PCA9685 `GND`** to this `GND Rail`.
    *   Connect **ULN2803A (Chip 1) Pin 9 (`GND`)** to this `GND Rail`.
    *   Connect **ULN2803A (Chip 2) Pin 9 (`GND`)** to this `GND Rail`.
    *   Ensure the **Umbilical Black (GND) wire** is also connected to this `GND Rail`.

### **Step 3: Forearm Sleeve Module: PCA9685 to ULN2803A Logic Connections**

Use **28 AWG Stranded Silicone Wire** for these connections to ensure flexibility and ease of wiring on the perfboard.

*   **PCA9685 `LED0` Output** $\rightarrow$ **ULN2803A (Chip 1) Pin 1**
*   **PCA9685 `LED1` Output** $\rightarrow$ **ULN2803A (Chip 1) Pin 2**
*   **PCA9685 `LED2` Output** $\rightarrow$ **ULN2803A (Chip 1) Pin 3**
*   **PCA9685 `LED3` Output** $\rightarrow$ **ULN2803A (Chip 1) Pin 4**
*   **PCA9685 `LED4` Output** $\rightarrow$ **ULN2803A (Chip 1) Pin 5**
*   **PCA9685 `LED5` Output** $\rightarrow$ **ULN2803A (Chip 1) Pin 6**
*   **PCA9685 `LED6` Output** $\rightarrow$ **ULN2803A (Chip 1) Pin 7**
*   **PCA9685 `LED7` Output** $\rightarrow$ **ULN2803A (Chip 1) Pin 8**

*   **PCA9685 `LED8` Output** $\rightarrow$ **ULN2803A (Chip 2) Pin 1**

    *(Note: You only need one channel on the second ULN2803A chip for your 9th motor.)*

### **Step 4: Forearm Sleeve Module: Motor Connections**

Use **28 AWG Stranded Silicone Wire** for flexibility and comfort. Label your wires (M1-M9) at both ends before soldering.

*   **All 9 Motor Red Wires** $\rightarrow$ Connect to the **3.3V Power Rail** on the perfboard.

*   **Motor 1 Black Wire** $\rightarrow$ **ULN2803A (Chip 1) Pin 18**
*   **Motor 2 Black Wire** $\rightarrow$ **ULN2803A (Chip 1) Pin 17**
*   **Motor 3 Black Wire** $\rightarrow$ **ULN2803A (Chip 1) Pin 16**
*   **Motor 4 Black Wire** $\rightarrow$ **ULN2803A (Chip 1) Pin 15**
*   **Motor 5 Black Wire** $\rightarrow$ **ULN2803A (Chip 1) Pin 14**
*   **Motor 6 Black Wire** $\rightarrow$ **ULN2803A (Chip 1) Pin 13**
*   **Motor 7 Black Wire** $\rightarrow$ **ULN2803A (Chip 1) Pin 12**
*   **Motor 8 Black Wire** $\rightarrow$ **ULN2803A (Chip 1) Pin 11**

*   **Motor 9 Black Wire** $\rightarrow$ **ULN2803A (Chip 2) Pin 18**

    *(Note: ULN2803A outputs are typically mirrored to inputs, so Pin 1 maps to Pin 18, Pin 2 to 17, etc.)*

---

## 4. Final Construction & Durability Tips

*   **IC Sockets:** Use DIP-18 IC Sockets for the ULN2803A chips to prevent damage during soldering and allow for easy replacement.
*   **Strain Relief:**
    *   Anchor the Umbilical Cord securely to the perfboard (e.g., with hot glue or a zip-tie) where it connects to prevent stress on solder joints.
    *   Use hot glue or heat shrink at the point where motor wires connect to the motors to protect the fragile leads.
*   **Insulation:** Apply Nano Tape to the bottom of the perfboard to cover sharp solder points, protecting your skin and preventing short circuits.
*   **Compactness:** Stack components using double-sided foam tape or Nano Tape (PCA9685 on ULN2803A sockets, MP1584EN nearby) to minimize the footprint on your arm.
*   **Wire Management:** Keep internal wires short and tidy. For external motor wires, use the "S-curve" technique to allow for arm movement.
---
---
For a haptic obstacle-avoidance wearable on the forearm, your goal shifts from "powering a motor" to **"tactile communication."** To make it feel like a phone—subtle, crisp, and professional—you need to focus on **Pulse Timing** and **Duty Cycle Mapping.**

### 1. Tuning the "Phone-Like" Feel
Since you are using 3V motors on a 3.3V regulated line, 100% power is quite aggressive. For a subtle "skin-tap" on the forearm:

*   **Intensity:** Use a **50% to 70% duty cycle**. This makes the vibration "softer" and quieter.
*   **Duration:** 
    *   **Short Click (0.1s):** Feels like a phone button press.
    *   **Medium Alert (0.3s):** Feels like a text message notification.
    *   **Long Warning (0.6s+):** Used for "Critical Danger."

### 2. Obstacle Avoidance Mapping
Since you have 9 motors, you can create a **spatial map** on the forearm:
*   **Motor 0-2:** Left side obstacles.
*   **Motor 3-5:** Center obstacles.
*   **Motor 6-8:** Right side obstacles.
*   **Pulse Speed:** The closer the object, the faster the "Beep-Beep" rhythm of the vibration (just like a car's parking sensor).

### 3. Wearable Design (Making it Small)
To keep it compact on the forearm, do not put the Raspberry Pi 5 on the arm. It is too heavy and hot.

*   **Split the Build:**
    *   **The Hub:** Put the Pi 5 and UPS in a small fanny pack or bicep pouch.
    *   **The Sleeve:** Place only the **9 motors** and the **ULN2803A chips** on the forearm sleeve. 
    *   **The Connection:** Use a thin 10-wire ribbon cable (or a modified HDMI/VGA cable) to connect the "Hub" to the "Sleeve."
*   **Motor Mounting:** Use **medical-grade double-sided tape** or sew small pockets into a compression sleeve (like a sports arm-warmer).
*   **Wiring:** Solder the motors directly to a small piece of **stripboard** (perfboard) where the ULN2803A sits. This will be much flatter than using a breadboard.

### 4. Wearable Dos and Don'ts
*   **DO** use a **soft backing** (felt or thin foam) between the motor and the skin. Direct plastic-to-skin vibration can feel "sharp" or irritating after 10 minutes.
*   **DO** use **Heat Shrink tubing** on all motor solder joints. Movement from your arm will eventually snap thin motor wires if they aren't reinforced.
*   **DON'T** let the wires cross without insulation. Your arm's sweat is conductive enough to cause "ghost vibrations" if wires are exposed.
*   **DON'T** put the Buck Converter on the arm. It gets warm. Keep it in the bicep pouch where airflow is better.

---
---
### The Haptic Precision GUI

```python
import tkinter as tk
from tkinter import messagebox
import board
import busio
from adafruit_pca9685 import PCA9685

# --- PCA9685 Hardware Initialization ---
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c)
    pca.frequency = 60
    # Ensure all channels are 0 on startup
    for i in range(16):
        pca.channels[i].duty_cycle = 0
except Exception as e:
    print(f"Hardware Error: {e}")
    # We will continue so the GUI can be viewed even without hardware
    pca = None

class HapticControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Haptic Forearm Sleeve Tester")
        self.root.geometry("800x850") # Wide enough for the sliders
        self.root.configure(bg="#2c3e50") # Professional dark blue background

        # Motor state tracking
        self.motor_on = [False] * 9
        self.intensity_values = [50.0] * 9  # Default slider position
        self.buttons = []
        self.sliders = []

        self.setup_ui()

    def setup_ui(self):
        # Header
        title = tk.Label(self.root, text="Haptic Feedback Intensity Controller", 
                         font=("Helvetica", 20, "bold"), bg="#2c3e50", fg="#ecf0f1")
        title.pack(pady=20)

        subtitle = tk.Label(self.root, text="Buttons correspond to PCA9685 Channels 0-8", 
                            font=("Helvetica", 10), bg="#2c3e50", fg="#bdc3c7")
        subtitle.pack(pady=0)

        # Main container for the motor rows
        container = tk.Frame(self.root, bg="#2c3e50")
        container.pack(pady=10, padx=30, fill="both", expand=True)

        for i in range(9):
            row = tk.Frame(container, bg="#34495e", pady=10, padx=15, highlightbackground="#2c3e50", highlightthickness=2)
            row.pack(fill="x", pady=2)

            # 1. Motor Number Label
            lbl = tk.Label(row, text=f"CH {i}", font=("Courier", 14, "bold"), 
                           bg="#34495e", fg="#f1c40f", width=5)
            lbl.pack(side="left")

            # 2. ON/OFF Button
            btn = tk.Button(row, text="OFF", font=("Helvetica", 11, "bold"), 
                            width=8, bg="#e74c3c", fg="white", activebackground="#c0392b",
                            command=lambda m=i: self.toggle_motor(m))
            btn.pack(side="left", padx=20)
            self.buttons.append(btn)

            # 3. Horizontal Intensity Slider
            # tickinterval=10 adds the 0, 10, 20... labels
            # length=450 makes the bar wide
            slider = tk.Scale(row, from_=0, to=100, orient="horizontal", 
                              length=450, tickinterval=10, resolution=1,
                              bg="#34495e", fg="#ecf0f1", highlightthickness=0,
                              troughcolor="#95a5a6", activebackground="#3498db",
                              font=("Helvetica", 8),
                              command=lambda val, m=i: self.update_intensity(m, val))
            slider.set(50)
            slider.pack(side="right")
            self.sliders.append(slider)

        # Emergency Stop Button
        stop_btn = tk.Button(self.root, text="ALL MOTORS EMERGENCY STOP", 
                             font=("Helvetica", 14, "bold"), bg="#c0392b", fg="white",
                             pady=15, command=self.emergency_stop)
        stop_btn.pack(side="bottom", fill="x", padx=50, pady=30)

    def toggle_motor(self, m):
        self.motor_on[m] = not self.motor_on[m]
        
        if self.motor_on[m]:
            self.buttons[m].config(text="ON", bg="#2ecc71") # Green
            self.apply_pwm(m)
        else:
            self.buttons[m].config(text="OFF", bg="#e74c3c") # Red
            if pca:
                pca.channels[m].duty_cycle = 0

    def update_intensity(self, m, val):
        self.intensity_values[m] = float(val)
        # If the motor is currently toggled ON, update the vibration immediately
        if self.motor_on[m]:
            self.apply_pwm(m)

    def apply_pwm(self, m):
        if not pca: return
        
        percentage = self.intensity_values[m]
        # Convert 0-100% to 16-bit 0-65535
        duty = int((percentage / 100.0) * 65535)
        pca.channels[m].duty_cycle = duty

    def emergency_stop(self):
        for i in range(9):
            self.motor_on[i] = False
            self.buttons[i].config(text="OFF", bg="#e74c3c")
            if pca:
                pca.channels[i].duty_cycle = 0

    def on_closing(self):
        self.emergency_stop()
        if pca:
            pca.deinit()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HapticControlApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
```

### Key Features of this Design:

1.  **Safety First:**
    *   All motors are initialized to `duty_cycle = 0` the moment the script runs.
    *   All buttons start in the **RED "OFF"** state.
    *   The **Emergency Stop** button at the bottom provides a one-click way to kill all power to the arm.

2.  **PCA-Channel Mapping:**
    *   The labels clearly say **CH 0** to **CH 8**. This corresponds exactly to the yellow signal pins on your PCA9685 board. 
    *   If you plug a motor into PCA Pin 0, use the first slider.

3.  **High-Visibility Slider:**
    *   **`length=450`**: This stretches the slider so you have very fine control over the intensity.
    *   **`tickinterval=10`**: This automatically adds the **0, 10, 20... 100** markings beneath the bar.
    *   **Live Updates:** If a button is "ON," moving the slider will change the vibration intensity instantly without needing to turn it off and on again.

4.  **The "60Hz" Logic:**
    *   The code sets `pca.frequency = 60`.
    *   This ensures your Makerlab motors receive 60 pulses per second. 
    *   At the **10%** mark on the slider, the motor is "on" for 10% of that 1/60th of a second and "off" for 90%. This gives you that perfect weak vibration feel you wanted.

### How to use it for your project:
*   **Test 1 (Individual):** Turn on CH 0 and find the "Minimum Start" value. (The percentage where the motor first starts moving). 
*   **Test 2 (Interference):** Turn on CH 0 at 100% and CH 1 at 0%. Touch Motor 1 to see if it is vibrating accidentally (which would mean a short circuit on your board).
*   **Test 3 (Heat):** Turn on all 9 motors at 50% for 2 minutes. Feel the **Buck Converter** and the **ULN2803A** chips. If they are very hot, you know you need more airflow in your sleeve!
