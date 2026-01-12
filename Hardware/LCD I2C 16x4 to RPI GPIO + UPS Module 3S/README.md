# RPi5 AI Power Station Monitor

This project provides a real-time system dashboard for a **Raspberry Pi 5** equipped with a **Hailo-8 AI HAT+** and a **Waveshare UPS Module 3S**, displaying critical data on a **16x4 I2C LCD**.

## 🚀 Features
- **Accurate Memory Monitoring**: Uses `(Used/Total)` formula to match the RPi Task Manager.
- **Battery Fuel Gauge**: Calculated for 3S Li-ion configurations (9.0V - 12.6V).
- **Thermal Tracking**: Real-time SoC temperature monitoring.
- **Flicker-Free UI**: Uses cursor positioning instead of screen clearing for smooth updates.

---

## 🛠 Hardware Setup

### Wiring Diagram
The UPS and LCD share the I2C bus. Since power is provided via **USB-C from the UPS to the Pi**, the 5V GPIO pin from the UPS is omitted to prevent back-powering issues.

| Signal | RPi 5 Pin | Waveshare UPS 3S | 16x4 LCD (PCF8574) |
| :--- | :--- | :--- | :--- |
| **5V Power** | Pin 2 or 4 | -- | VCC |
| **Ground** | Pin 6 | GND (Pin 5/6) | GND |
| **I2C SDA** | Pin 3 | SDA (Pin 2) | SDA |
| **I2C SCL** | Pin 5 | SCL (Pin 1) | SCL |

---

## ⚙️ Software Installation

### 1. Enable I2C
```bash
sudo raspi-config
# Interface Options -> I2C -> Yes -> Finish -> Reboot
```

### 2. Install Dependencies
Compatible with Raspberry Pi OS (Bookworm).
```bash
sudo apt update
sudo apt install python3-smbus i2c-tools python3-pip -y
pip install psutil RPLCD smbus2 --break-system-packages
```

### 3. Verify Addresses
```bash
i2cdetect -y 1
```
*Expected: `41` (UPS) and `27` or `3f` (LCD).*

---

## 💻 The Monitoring Script (`monitor.py`)

```python
import smbus2 as smbus
import time
import psutil
from RPLCD.i2c import CharLCD

# Configuration
LCD_ADDR = 0x27  # Change to 0x3F if required
UPS_ADDR = 0x41 
lcd = CharLCD('PCF8574', LCD_ADDR, port=1, cols=16, rows=4)

class INA219:
    def __init__(self, addr):
        self.bus = smbus.SMBus(1)
        self.addr = addr
        self.calibrate()

    def calibrate(self):
        try:
            self.bus.write_i2c_block_data(self.addr, 0x05, [0x10, 0x00]) # 32V/2A
            self.bus.write_i2c_block_data(self.addr, 0x00, [0x39, 0x9F])
        except: pass

    def get_voltage(self):
        try:
            raw = self.bus.read_i2c_block_data(self.addr, 0x02, 2)
            return ((raw[0] << 8) | raw[1] >> 3) * 0.004
        except: return 0.0

def get_stats():
    mem = psutil.virtual_memory()
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
        temp = float(f.read()) / 1000.0
    return temp, psutil.cpu_percent(), (mem.used / mem.total) * 100

ups = INA219(UPS_ADDR)

try:
    while True:
        v = ups.get_voltage()
        t, cpu, mem = get_stats()
        batt = min(max(((v - 9.0) / 3.6) * 100, 0), 100)

        lcd.cursor_pos = (0, 0); lcd.write_string(f"BATT:  {batt:5.1f}%".ljust(16))
        lcd.cursor_pos = (1, 0); lcd.write_string(f"TEMP:  {t:5.1f} C".ljust(16))
        lcd.cursor_pos = (2, 0); lcd.write_string(f"MEM:   {mem:5.1f}%".ljust(16))
        lcd.cursor_pos = (3, 0); lcd.write_string(f"CPU:   {cpu:5.1f}%".ljust(16))
        time.sleep(2)
except KeyboardInterrupt:
    lcd.clear()
```

---

## 🛠 Troubleshooting
- **No Text on LCD:** Adjust the blue potentiometer (contrast screw) on the back of the I2C backpack.
- **I2C Errors:** Double-check SDA/SCL wiring. Ensure the UPS **BOOT** button has been pressed to activate the battery output.
- **Memory Inaccuracy:** This script uses `Used/Total`. If it still differs from your UI, verify if your UI is including "Shared" memory.

---

## 🔄 Autostart on Boot
To run the script automatically at startup:
1. Run `crontab -e`.
2. Add this line at the bottom:
   `@reboot /usr/bin/python3 /home/pi/monitor.py &`


Here is the corrected, **fail-proof guide** tailored specifically for your **Raspberry Pi 5**. 

The main reason your previous attempt failed was a mismatch in the **username** (using `pi` instead of `raspberrypi`) and a **directory error** (status 200). This guide fixes those specific issues.

---

### Step 1: Secure the Python Script
First, ensure your script is in the right place and has the right permissions.
1.  **Move/Save your file** to the main home directory:
    *   The file must be at: `/home/raspberrypi/smart_monitor.py`
2.  **Give it "Execute" permissions:**
    ```bash
    chmod +x /home/raspberrypi/smart_monitor.py
    ```

---

### Step 2: Ensure Libraries are Global
Since the background service runs in a different environment than your terminal, you must install the libraries so the **system** can see them:
```bash
sudo pip install psutil RPLCD smbus2 --break-system-packages
```

---

### Step 3: Create the Corrected Service File
We will now create the service file with the exact paths required by the Raspberry Pi 5.

1.  **Open the editor:**
    ```bash
    sudo nano /etc/systemd/system/lcd_monitor.service
    ```
2.  **Paste this exact code:**
    ```ini
    [Unit]
    Description=Raspberry Pi 5 LCD Monitor
    # Wait for the system to be fully ready
    After=multi-user.target
    # Wait specifically for the I2C hardware to be initialized
    After=i2c-dev.target

    [Service]
    # Corrected username for Pi 5
    User=raspberrypi
    Group=raspberrypi
    WorkingDirectory=/home/raspberrypi
    # Direct path to python3 and the script
    ExecStart=/usr/bin/python3 /home/raspberrypi/smart_monitor.py
    # If the script crashes, wait 10 seconds and restart automatically
    Restart=always
    RestartSec=10
    # Capture errors in the system log
    StandardOutput=inherit
    StandardError=inherit

    [Install]
    WantedBy=multi-user.target
    ```
3.  **Save and Exit:** Press **Ctrl+O**, then **Enter**, then **Ctrl+X**.

---

### Step 4: Fix Permissions for the I2C Bus
The service needs permission to talk to the SDA/SCL pins without you being logged in.
```bash
sudo usermod -a -G i2c raspberrypi
```

---

### Step 5: "The Activation" (Compile/Register)
This is the process to tell the Pi to load your new configuration.

1.  **Reload the system daemon:**
    ```bash
    sudo systemctl daemon-reload
    ```
2.  **Enable the service (This sets it to run on BOOT):**
    ```bash
    sudo systemctl enable lcd_monitor.service
    ```
3.  **Start the service (This runs it NOW):**
    ```bash
    sudo systemctl start lcd_monitor.service
    ```

---

### Step 6: Verify it is working
Check the status to ensure it says **Active (running)** in green text:
```bash
sudo systemctl status lcd_monitor.service
```

**If you see errors:**
If it still won't start, run this to see the live Python error log:
```bash
journalctl -u lcd_monitor.service -f
```

---

### Summary Checklist for Success:
*   **Path:** Your script is definitely at `/home/raspberrypi/smart_monitor.py`.
*   **Username:** Every mention of `pi` has been changed to `raspberrypi`.
*   **Libraries:** You used `--break-system-packages` so the service can find `RPLCD`.
*   **Hardware:** Your **Waveshare UPS** and **LCD** are connected to the GPIO.

**Now, when you flip the UPS battery switch, the Pi 5 will boot and your LCD will automatically turn on with your Battery and CPU stats within 15-20 seconds!**
