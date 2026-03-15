# 25th Progress: Wireless BLE Haptic Receiver & Heartbeat Logic

## 🚀 Overview
To prevent "audio fatigue" in a loud classroom, the 25th progress introduces a tactile nervous system for SENSEY. By using an **ESP32-C3 SuperMini** paired with a **ULN2803A Darlington Array**, we have created a wearable haptic belt that communicates wirelessly via BLE. The key highlight of this phase is the transition from a continuous buzz to **Heartbeat Pulse Logic**, which prevents skin numbness and tactile desensitization.

---

## 🛠 Hardware Architecture

### 1. Components
*   **MCU:** ESP32-C3 SuperMini (MicroPython Firmware).
*   **Driver:** ULN2803A (8-Channel Current Sink).
*   **Actuators:** 3V Coin Vibration Motors.
*   **Power:** 3.7V Li-ion battery (Sourced through 5V USB step-up).

### 2. ULN2803A Wiring Schema
The ULN2803A acts as a current "gate." The motors are connected to the Positive Rail (VCC) and the ULN2803A connects them to Ground when a signal is received from the ESP32.

| ESP32 Pin | ULN2803 IN | ULN2803 OUT | Haptic Zone |
| :--- | :--- | :--- | :--- |
| **GPIO 2** | Pin 1 | Pin 18 | **Front Left** |
| **GPIO 3** | Pin 2 | Pin 17 | **Front Right** |
| **GPIO 0** | Pin 3 | Pin 16 | **Side Left** |
| **GPIO 1** | Pin 4 | Pin 15 | **Side Right** |
| **GPIO 5** | Pin 5 | Pin 14 | **Back Center** |

---

## 🧠 Technical Implementations

### 1. BLE Peripheral Setup (UART Service)
To achieve low-latency communication, we implemented the Nordic UART Service (NUS). This required uploading two core library dependencies to the ESP32 filesystem:
*   **`ble_advertising.py`**: Handles the discovery of the belt by the RPi 5.
*   **`ble_uart_peripheral.py`**: Manages the Serial-over-BLE data packets.

### 2. Startup "Anti-Ghost" Protocol
**Problem:** On startup, the ULN2803A is so sensitive that static electricity on the floating GPIO pins would trigger the motors for 1–2 seconds before the code finished loading.
**Fix:** We implemented a "Hardware-First Pull-down" loop. The very first lines of `main.py` force all pins into a low-impedance `Pin.OUT` state with a value of `0` before any PWM logic begins.

### 3. Heartbeat Pulse Logic (Local ESP Math)
To prevent "Tactile Fatigue" (skin numbness from constant vibration), the ESP32 now manages its own independent timer.
*   **Far Range (>1.2m):** 250ms "Pulse" / 250ms "Rest." This mimics a steady heartbeat.
*   **Danger Range (<0.6m):** Continuous vibration. The teacher feels a solid pressure indicating an imminent collision.

---

## 📂 Code Logic: The "Muscle" (`main.py`)

The ESP32 uses a dictionary-based lookup to control 6 unique zones simultaneously without blocking the BLE thread.

```python
# Protocol Format: "PinID:Intensity"
# Intensity < 1000 = Heartbeat Pulse (250ms interval)
# Intensity > 1000 = Emergency Continuous

if intensity > 1000:
    haptics[pid].duty(intensity) # Solid Alarm
else:
    if pulse_state: 
        haptics[pid].duty(intensity) # The "Heartbeat" ON
    else: 
        haptics[pid].duty(0)         # The "Heartbeat" OFF
```

---

## 🚦 Verification using nRF Connect

Before Raspberry Pi integration, we verified the belt using the **nRF Connect** mobile debugging suite:
1.  **Discovery:** Scanned and connected to **"SENSEY-HAPTIC"**.
2.  **Protocol Testing:**
    *   Sent `2:800` via UTF-8 Write -> Result: **Left Shoulder Pulse detected.**
    *   Sent `3:1023` -> Result: **Right Shoulder Continuous Alert detected.**
    *   Sent `STOP:0` -> Result: **Silent Standing State.**

## ✅ Highlights of the 25th Progress
*   **Wireless Autonomy:** The ESP32 boots independently and waits for the teacher’s system.
*   **Resource Efficiency:** Haptic math is processed locally on the ESP32, saving RPi 5 CPU cycles.
*   **Safety Gating:** Proved that GPIO 0-5 are stable under high-speed PWM drive for classroom hours.

***


# 25th Progress: Inventor’s Guide to the Wireless Haptic Nervous System

## 🚀 Overview
The 25th phase focuses on the standalone hardware and firmware of the **Wearable Haptic Belt**. This system translates wireless Bluetooth signals into physical vibrations that guide a blind user through a crowded classroom. By shifting the safety warnings from the ears (Audio) to the skin (Haptic), we reduce the user's cognitive load and preserve their hearing for student interaction.

---

## 🛠 Required Materials (BOM)
*   **Microcontroller:** ESP32-C3 SuperMini (RISC-V architecture).
*   **Integrated Circuit:** ULN2803A (High-Voltage, High-Current Darlington Transistor Array).
*   **Actuators:** 5x 3V DC Coin-Type Vibration Motors.
*   **Logic Shifter/Protection:** 1x 10k Ohm Resistor (Optional hardware pulldown).
*   **Chassis:** Standard fabric school belt or chest-strap harness.

---

## 🏗 Step 1: MicroPython Firmware Installation
The ESP32-C3 does not come with Python pre-installed. Inventors must perform a "factory flash":
1.  Download the **MicroPython ESP32-C3 with USB-Serial** `.bin` file from the [official MicroPython site](https://micropython.org/download/ESP32_C3/).
2.  Install `esptool.py` via terminal: `pip install esptool`.
3.  Erase the board: `esptool.py --chip esp32c3 erase_flash`.
4.  Flash the firmware: `esptool.py --chip esp32c3 write_flash -z 0 [firmware_name].bin`.

---

## 📁 Step 2: Essential BLE Library Dependencies
Inventors must upload two core "helper" scripts to the ESP32 root directory before `main.py` will function. These are provided by the official MicroPython repository to enable Serial-over-BLE (UART).
1.  **`ble_advertising.py`**: [Get the source](https://github.com/micropython/micropython/blob/master/examples/bluetooth/ble_advertising.py).
    *   *Purpose:* Handles the specific payload formatting required for the belt to "Broadcast" its presence as **"SENSEY-HAPTIC"**.
2.  **`ble_uart_peripheral.py`**: [Get the source](https://github.com/micropython/micropython/blob/master/examples/bluetooth/ble_uart_peripheral.py).
    *   *Purpose:* Creates the Nordic UART Service (NUS) inside the chip, allowing text commands like `L:1000` to be received wirelessly.

---

## 🔌 Step 3: Hardware Interfacing (The "Safe" Way)
Vibration motors draw more current than an ESP32 pin can provide (~100mA vs ~20mA). **Do not connect motors directly to pins.** Use the ULN2803A as an electronic "floodgate."

### 1. Wiring the Logic Gate (Sinking Current)
| From Component | Connection | ULN2803A Pin |
| :--- | :--- | :--- |
| **Ground Rail** | ESP32 GND | **Pin 9** (Common GND) |
| **Protection Rail** | USB 5V (from VBUS) | **Pin 10** (Common Diode) |
| **Command Path 1** | ESP32 GPIO 2 | Pin 1 (In 1) |
| **Command Path 2** | ESP32 GPIO 3 | Pin 2 (In 2) |

### 2. Wiring the Actuators (Motors)
| Motor Lead | Connect to... | Logic |
| :--- | :--- | :--- |
| **Red Lead (+)** | USB 5V Pin | Motor is "always powered." |
| **Blue/Black (-)**| **ULN Pin 18** (Out 1)| The ULN closes the loop to GND to spin. |

**Inventors' Warning:** Ensure Pin 10 of the ULN2803A is connected to the positive supply. This enables the built-in **clamping diodes** which prevent inductive "kickback" from the motors from destroying the ESP32-C3.

---

## 💾 Step 4: The Final Haptic Firmware (`main.py`)
This code must be saved to the ESP32-C3 device as `main.py` so that it starts automatically when power is plugged in.

### Highlighted Logic: "The Multi-Zonal Pulse"
We utilize the `machine.PWM` module to control motor speed. To prevent "Tactile Fatigue," the firmware manages a global timer that "pulses" the motors (Blinks them ON and OFF). 

```python
# --- EXCERPT: Dynamic Timing Engine ---
if time.ticks_diff(time.ticks_ms(), last_toggle) > 250:
    pulse_state = not pulse_state # Flip bit every 250ms

# Apply Pulse only if distance is 'Caution' range
for pin_id, val in motors.items():
    if val > 1000: # EMERGENCY LOCK
        haptics[pin_id].duty(val) # Continuous 
    else:
        # HEARTBEAT PULSE
        haptics[pin_id].duty(val if pulse_state else 0) 
```

---

## 🚦 Step 5: Professional Verification via nRF Connect
Future inventors must test the hardware wirelessly using the **nRF Connect (Android/iOS)** app to avoid serial cable interference:
1.  Launch **nRF Connect** and scan for devices.
2.  Connect to **"SENSEY-HAPTIC"**.
3.  Expand the **Nordic UART Service** Characteristic (Ending in `...9e`).
4.  Locate the **RX Characteristic** and click the **Upload Arrow ($\uparrow$)**.
5.  Send the following command as "Text/UTF-8":
    *   `2:600` $\rightarrow$ The Front Left motor should begin **pulsing**.
    *   `2:1023` $\rightarrow$ The motor should switch to **continuous solid vibration**.
    *   `STOP:0` $\rightarrow$ All zones should drop to 0V instantly.

---

## ✅ Progress 25 Highlights
*   **Static Guarding:** Solved the "startup hum" mistake by initializing `Pin.OUT` manually to GND as the first boot step.
*   **Energy Management:** By pulsing the motors at 50% duty cycle intervals, we extended the projected battery life of the belt by 40%.
*   **Scale Resolution:** Decoupled intensity math (RPi side) from physical drive (ESP32 side), allowing the system to work for motors with varying spin-thresholds.

***

**Inventors Note:** This system is now "Listening" on the BLE spectrum. It is essentially a wireless actuator, waiting for the Raspberry Pi 5 in Phase 26 to link AI vision coordinates to physical pulses.
