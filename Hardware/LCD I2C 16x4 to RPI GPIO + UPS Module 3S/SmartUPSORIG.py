import smbus2 as smbus
import time
import psutil
from RPLCD.i2c import CharLCD

# ==========================================
# CONFIGURATION
# ==========================================
I2C_BUS = 1
UPS_ADDR = 0x41 
LCD_ADDR = 0x27 
LCD_COLS = 16
LCD_ROWS = 4

# Initialize LCD
lcd = CharLCD('PCF8574', LCD_ADDR, port=1, cols=LCD_COLS, rows=LCD_ROWS)

class INA219:
    def __init__(self, addr):
        self.bus = smbus.SMBus(I2C_BUS)
        self.addr = addr
        self.calibrate()

    def calibrate(self):
        # 32V / 2A Calibration from your SmartUPS code
        try:
            self.bus.write_i2c_block_data(self.addr, 0x05, [0x10, 0x00])
            self.bus.write_i2c_block_data(self.addr, 0x00, [0x39, 0x9F])
        except: pass

    def get_voltage(self):
        try:
            data = self.bus.read_i2c_block_data(self.addr, 0x02, 2)
            raw = (data[0] << 8) | data[1]
            return (raw >> 3) * 0.004
        except: return 0.0

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return float(f.read()) / 1000.0
    except: return 0.0

# ==========================================
# ACCURATE MEMORY CALCULATION
# ==========================================
def get_accurate_mem_percent():
    mem = psutil.virtual_memory()
    # Task Manager Style: (Used / Total) * 100
    # This ignores Buffers/Cache to give you the "App Usage" percentage
    used_mb = mem.used / (1024**2)
    total_mb = mem.total / (1024**2)
    percentage = (mem.used / mem.total) * 100
    return percentage, used_mb

# ==========================================
# MAIN LOOP
# ==========================================
ups = INA219(UPS_ADDR)

try:
    while True:
        # 1. Gather Metrics
        v = ups.get_voltage()
        cpu_t = get_cpu_temp()
        cpu_u = psutil.cpu_percent()
        mem_p, mem_used = get_accurate_mem_percent()
        
        # 2. Battery % (9V-12.6V Logic)
        batt_p = min(max(((v - 9.0) / 3.6) * 100, 0), 100)

        # 3. Format Strings for 16-Char LCD
        # Line 1: Battery
        line1 = f"BATTERY :{batt_p:5.1f}%".ljust(16)
        # Line 2: Temp
        line2 = f"CPU TEMP:{cpu_t:5.1f}C".ljust(16)
        # Line 3: Accurate Memory (Formula: Used/Total)
        line4 = f"RAM USE  :{mem_p:5.1f}%".ljust(16)
        # Line 4: CPU Usage
        line3 = f"CPU USE :{cpu_u:5.1f}%".ljust(16)

        # 4. Push to LCD
        lcd.cursor_pos = (0, 0); lcd.write_string(line1)
        lcd.cursor_pos = (1, 0); lcd.write_string(line2)
        lcd.cursor_pos = (2, 0); lcd.write_string(line3)
        lcd.cursor_pos = (3, 0); lcd.write_string(line4)

        time.sleep(2)

except KeyboardInterrupt:
    lcd.clear()
    lcd.write_string("Monitor Stopped")