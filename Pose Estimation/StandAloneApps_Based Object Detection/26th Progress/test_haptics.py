import asyncio
from bleak import BleakScanner, BleakClient

# The name you defined in your ESP32 MicroPython code
DEVICE_NAME = "SENSEY-HAPTIC"
# Standard Nordic UART Service UUID (used by BLEUART)
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E" # To send data to ESP32

async def run_haptic_test():
    print(f"🔎 Scanning for {DEVICE_NAME}...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME)
    
    if not device:
        print(f"❌ Could not find {DEVICE_NAME}. Is it powered on?")
        return

    print(f"✅ Found {device.name} [{device.address}]. Connecting...")
    
    async with BleakClient(device) as client:
        print("🔗 Connected! Cycling through motors...")

        # Test sequence: Pin 0 to 5
        for pin in range(6):
            # Format: "pin:intensity"
            # Intensity 512 = Pulsing (Warning)
            # Intensity 1023 = Solid (Critical)
            msg = f"{pin}:512\n" 
            print(f"📳 Testing Motor on Pin {pin} (Pulsing)")
            await client.write_gatt_char(UART_TX_CHAR_UUID, msg.encode())
            await asyncio.sleep(2)
            
            # Stop the motor
            await client.write_gatt_char(UART_TX_CHAR_UUID, f"{pin}:0\n".encode())
            await asyncio.sleep(0.5)

        print("🛑 Sending STOP command to all motors...")
        await client.write_gatt_char(UART_TX_CHAR_UUID, b"STOP:0\n")
        print("🏁 Test Complete.")

if __name__ == "__main__":
    try:
        asyncio.run(run_haptic_test())
    except Exception as e:
        print(f"🔴 Error: {e}")