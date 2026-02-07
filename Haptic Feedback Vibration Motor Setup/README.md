##

## The "Full Phase" Component List

1.  **Raspberry Pi 5**
2.  **Waveshare UPS Module 3S** (I2C Address: `0x41`)
3.  **PCA9685 PWM Driver** (I2C Address: `0x40`)
4.  **MP1584EN Buck Converter** (Set to **3.3V** output)
5.  **2x ULN2803A ICs** (One for motors 1-8, one for motor 9)
6.  **9x Coin Vibration Motors**

---

### **Step 1: Calibrate the Buck Converter (Critical)**
Before wiring anything else, you must set the voltage:
1.  Connect **UPS 5V** to MP1584EN **IN+**.
2.  Connect **UPS GND** to MP1584EN **IN-**.
3.  Use a multimeter on the **OUT+ / OUT-** pins.
4.  Turn the tiny screw until the output is **exactly 3.3V**.
5.  **Disconnect it.** Do not touch the screw again.

---

### **Step 2: Wiring Diagram (The Master Plan)**

#### **A. I2C Logic Connections**
This allows the Pi to talk to the UPS and the Motor Driver at the same time.
*   **UPS SDA** $\rightarrow$ **PCA9685 SDA** $\rightarrow$ **Pi SDA** (Pin 3)
*   **UPS SCL** $\rightarrow$ **PCA9685 SCL** $\rightarrow$ **Pi SCL** (Pin 5)
*   **UPS GND** $\rightarrow$ **PCA9685 GND** $\rightarrow$ **Pi GND** (Pin 6)
*   **UPS 3V3** $\rightarrow$ **PCA9685 VCC** (This powers the chip logic)

#### **B. Motor Power (The Buck Converter Rail)**
This provides the heavy current needed to vibrate the motors.
*   **Buck Converter OUT (+3.3V)** $\rightarrow$ **9x Motor Red Wires** AND **ULN2803A Pin 10** (on both chips).
*   **Buck Converter OUT (GND)** $\rightarrow$ **ULN2803A Pin 9** (on both chips) AND **Pi GND** (Common Ground).

#### **C. PWM & Driver Wiring**
*   **PCA9685 Output Channels 0-7** $\rightarrow$ **ULN2803A (Chip 1) Pins 1-8**.
*   **PCA9685 Output Channel 8** $\rightarrow$ **ULN2803A (Chip 2) Pin 1**.
*   **ULN2803A (Chip 1) Pins 11-18** $\rightarrow$ **Motors 1-8 Blue/Black Wires**.
*   **ULN2803A (Chip 2) Pin 18** $\rightarrow$ **Motor 9 Blue/Black Wire**.

---

### **Step 3: Verification Checklist**
*   [ ] **Common Ground:** Are the grounds of the Pi, UPS, Buck Converter, and ULN2803A all tied together? (Yes, they must be).
*   [ ] **Voltage Check:** Is the Buck Converter definitely outputting 3.3V? (If it's 5V, you will damage the motors).
*   [ ] **Flyback Protection:** Is Pin 10 of the ULN2803A connected to the 3.3V output of the Buck Converter? (This prevents the "kickback" from destroying the circuit).

---

### **Step 4: The Python Control Script**

This script uses the `adafruit-circuitpython-pca9685` library. Since you have hardware-regulated 3.3V now, you can safely use **100% duty cycle** for maximum vibration.

```python
import time
import board
import busio
from adafruit_pca9685 import PCA9685

# Initialize I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Initialize PCA9685 (Address 0x40)
# Note: Waveshare UPS remains at 0x41, so no conflict occurs.
pca = PCA9685(i2c)
pca.frequency = 60 # Standard frequency for vibration motors

def set_vibration(motor_id, power):
    """
    motor_id: 0-8
    power: 0.0 to 1.0 (0% to 100%)
    """
    if motor_id < 0 or motor_id > 8:
        return
    
    # 65535 is the max 16-bit duty cycle for PCA9685
    duty = int(power * 65535)
    pca.channels[motor_id].duty_cycle = duty

# --- EXAMPLE USAGE ---
print("Vibrating Motor 9 (Channel 8) at 50%...")
set_vibration(8, 0.5)
time.sleep(2)

print("Stopping all motors...")
for i in range(9):
    set_vibration(i, 0)

pca.deinit()
```

---
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
---
For a haptic obstacle-avoidance wearable on the forearm, your goal shifts from "powering a motor" to **"tactile communication."** To make it feel like a phone—subtle, crisp, and professional—you need to focus on **Pulse Timing** and **Duty Cycle Mapping.**

### 1. Tuning the "Phone-Like" Feel
Since you are using 3V motors on a 3.3V regulated line, 100% power is quite aggressive. For a subtle "skin-tap" on the forearm:

*   **Intensity:** Use a **50% to 70% duty cycle**. This makes the vibration "softer" and quieter.
*   **Duration:** 
    *   **Short Click (0.1s):** Feels like a phone button press.
    *   **Medium Alert (0.3s):** Feels like a text message notification.
    *   **Long Warning (0.6s+):** Used for "Critical Danger."

### 2. The Python "Haptic Pulse" Code
For obstacle avoidance, your code cannot "stop" while it vibrates. You need a **non-blocking** way to pulse the motors so the Pi can keep reading distance sensors (like ultrasonic or LiDAR).

```python
import time
import threading
from adafruit_pca9685 import PCA9685
# ... (initialize pca as before) ...

def vibrate_pulse(channel, intensity=0.6, duration=0.3):
    """
    Sends a timed pulse without stopping the rest of your code.
    intensity: 0.0 to 1.0 (0.6 is recommended for subtle feel)
    duration: seconds to stay on
    """
    def run():
        # Turn ON
        pca.channels[channel].duty_cycle = int(intensity * 65535)
        time.sleep(duration)
        # Turn OFF
        pca.channels[channel].duty_cycle = 0
    
    # Run in a background thread so the sensor loop doesn't wait
    threading.Thread(target=run).start()

# --- Use case: Distance Mapping ---
# distance = get_sensor_data() 
# if distance < 20: # 20cm
#     vibrate_pulse(8, intensity=0.7, duration=0.5) # Strong/Long for close
# elif distance < 50: # 50cm
#     vibrate_pulse(8, intensity=0.5, duration=0.2) # Soft/Short for far
```

### 3. Obstacle Avoidance Mapping
Since you have 9 motors, you can create a **spatial map** on the forearm:
*   **Motor 0-2:** Left side obstacles.
*   **Motor 3-5:** Center obstacles.
*   **Motor 6-8:** Right side obstacles.
*   **Pulse Speed:** The closer the object, the faster the "Beep-Beep" rhythm of the vibration (just like a car's parking sensor).

### 4. Wearable Design (Making it Small)
To keep it compact on the forearm, do not put the Raspberry Pi 5 on the arm. It is too heavy and hot.

*   **Split the Build:**
    *   **The Hub:** Put the Pi 5 and UPS in a small fanny pack or bicep pouch.
    *   **The Sleeve:** Place only the **9 motors** and the **ULN2803A chips** on the forearm sleeve. 
    *   **The Connection:** Use a thin 10-wire ribbon cable (or a modified HDMI/VGA cable) to connect the "Hub" to the "Sleeve."
*   **Motor Mounting:** Use **medical-grade double-sided tape** or sew small pockets into a compression sleeve (like a sports arm-warmer).
*   **Wiring:** Solder the motors directly to a small piece of **stripboard** (perfboard) where the ULN2803A sits. This will be much flatter than using a breadboard.

### 5. Wearable Dos and Don'ts
*   **DO** use a **soft backing** (felt or thin foam) between the motor and the skin. Direct plastic-to-skin vibration can feel "sharp" or irritating after 10 minutes.
*   **DO** use **Heat Shrink tubing** on all motor solder joints. Movement from your arm will eventually snap thin motor wires if they aren't reinforced.
*   **DON'T** let the wires cross without insulation. Your arm's sweat is conductive enough to cause "ghost vibrations" if wires are exposed.
*   **DON'T** put the Buck Converter on the arm. It gets warm. Keep it in the bicep pouch where airflow is better.

### Summary for your Haptic Guide:
1.  **Hardware:** Regulated 3.3V (Buck Converter) $\rightarrow$ ULN2803A $\rightarrow$ Coin Motor.
2.  **Logic:** PCA9685 sends 60Hz PWM.
3.  **Haptics:** Map 50-70% intensity for 0.1s to 0.3s pulses to mimic a modern smartphone.
4.  **Ergonomics:** Move the Pi/UPS to the bicep/waist; keep only the motors and small driver chips on the forearm.
