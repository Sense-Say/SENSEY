vcgencmd pmic_read_adc EXT5V_V
or
vcgencmd pmic_read_adc             ## to see current/voltage

https://www.youtube.com/watch?v=lEZccWuOXuo


To increase the total USB current from 600mA to 1600mA do the following:
Open Terminal and type: sudo nano /boot/firmware/config.txt

Add this to the file: usb_max_current_enable=1

To force the Raspberry Pi 5 to think it is using a 5A power supply even if it is not using the 27W USB-C supply do the following:
Open Terminal and type: sudo -E rpi-eeprom-config --edit 

Add this to the file (allowable options at 3000 or 5000): PSU_MAX_CURRENT=5000
 
