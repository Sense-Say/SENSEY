import bluetooth
from ble_uart_peripheral import BLEUART
from machine import Pin, PWM
import time

PIN_IDS = [0, 1, 2, 3, 4, 5]
haptics = {}
target_intensity = {str(p): 0 for p in PIN_IDS} # Stores the level (0-1023)

# 🚀 Timing logic for independent pulsing
for pid in PIN_IDS:
    Pin(pid, Pin.OUT).value(0)
    haptics[str(pid)] = PWM(Pin(pid), freq=1000)
    haptics[str(pid)].duty(0)

# BLE Setup
name = "SENSEY-HAPTIC"
ble = bluetooth.BLE()
uart = BLEUART(ble, name=name)

def handle_rx():
    try:
        msg = uart.read().decode().strip()
        if ":" in msg:
            pin_id, val = msg.split(":")
            if pin_id in target_intensity:
                target_intensity[pin_id] = int(val)
            elif pin_id == "STOP":
                for k in target_intensity: target_intensity[k] = 0
    except: pass

print(f"📡 {name} Active with Pulse Logic.")

last_toggle = time.ticks_ms()
pulse_state = True # ON or OFF

while True:
    if uart.any(): handle_rx()
    
    current_time = time.ticks_ms()
    
    # 🚀 DYNAMIC PULSE CALCULATOR
    # We create a 500ms global clock loop
    if time.ticks_diff(current_time, last_toggle) > 250:
        pulse_state = not pulse_state
        last_toggle = current_time

    for pid, intensity in target_intensity.items():
        if intensity == 0:
            haptics[pid].duty(0)
        elif intensity > 1000:
            # 🛑 CRITICAL: Always ON
            haptics[pid].duty(intensity)
        else:
            # 💓 WARNING: Pulsing
            # Only turn on during the 'ON' phase of the clock
            if pulse_state:
                haptics[pid].duty(intensity)
            else:
                haptics[pid].duty(0)

    time.sleep(0.01)