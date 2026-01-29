
# Raspberry Pi 5 Active Cooler: 100% Speed at Boot Configuration Guide

This guide details how to configure the Official Raspberry Pi 5 Active Cooler to run at its maximum (100%) speed immediately upon boot, overriding the default temperature-controlled behavior. This setup is ideal for scenarios requiring continuous, maximum cooling, such as sustained AI workloads (Object Detection, Pose Estimation) in enclosed or wearable environments.

**Note:** Running the fan at 100% constantly will increase noise and slightly reduce battery life compared to temperature-controlled operation.

---

## **1. Prerequisites**

*   **Raspberry Pi 5:** With Raspberry Pi OS (Bookworm or newer) installed.
*   **Official Raspberry Pi 5 Active Cooler:** Correctly installed and plugged into the 4-pin fan header on your Raspberry Pi 5.
*   **Terminal Access:** Access to your Raspberry Pi's command line (via SSH or direct keyboard/monitor).

---

## **2. Modifying the `config.txt` File**

The fan's behavior is controlled via parameters in the `config.txt` file, which is located in a new path for Raspberry Pi OS Bookworm and later.

1.  **Open the `config.txt` file:**
    In your Raspberry Pi's terminal, use the `nano` editor to open the configuration file:

    ```bash
    sudo nano /boot/firmware/config.txt
    ```

2.  **Add/Modify Fan Parameters:**
    Scroll to the very bottom of the file. You will add or modify the lines within or directly after the `[all]` section to ensure these settings apply to your Pi 5.

    Add the following lines:

    ```ini
    # Custom settings for Raspberry Pi 5 Active Cooler: 100% speed from boot
    dtoverlay=rpi-5-fan        # Ensures the fan overlay is active
    dtparam=fan_temp0=1        # Sets the first fan stage to activate at 0.001°C (effectively always on)
    dtparam=fan_temp0_speed=100 # Sets the fan speed for stage 0 to 100%
    ```

    **Explanation of Parameters:**
    *   `dtoverlay=rpi-5-fan`: This line enables the fan control overlay, which is necessary for the Pi to manage the active cooler. It's usually present, but ensuring it's uncommented is good practice.
    *   `dtparam=fan_temp0=1`: This defines the temperature (in millicelcius, 1 = 0.001°C) at which the first fan speed stage (`N=0`) should activate. By setting it to such a low value, the fan will effectively be "on" from the moment the system can activate it.
    *   `dtparam=fan_temp0_speed=100`: This sets the fan speed for the first stage (`N=0`) to 100%. Combined with `fan_temp0=1`, this ensures the fan runs at maximum speed whenever the Pi is powered on.

3.  **Save and Exit:**
    *   Press `Ctrl+X` to exit.
    *   Press `Y` to confirm saving the changes.
    *   Press `Enter` to confirm the filename (`/boot/firmware/config.txt`).

---

## **3. Reboot Your Raspberry Pi**

For the changes to take effect, you must reboot your Raspberry Pi:

```bash
sudo reboot
```

---

## **4. Verification**

After rebooting, the Official Raspberry Pi 5 Active Cooler should immediately spin up to its maximum speed (8000 RPM / 1.09 CFM, as per its specifications) as soon as the Pi powers on.

You can verify the CPU temperature by running:

```bash
vcgencmd measure_temp
```

While the fan might not *sound* or *feel* as powerful as larger fans, its 1.09 CFM max airflow is optimized for direct CPU cooling. Combined with your external enclosure fans (axial intake and blower exhaust), this setup provides robust and continuous thermal management for your intensive AI applications.

---

**Further Reading:**
*   Raspberry Pi Documentation on `config.txt` and `dtparam`: [http://rptl.io/configtxt](http://rptl.io/configtxt) (Search for `rpi-5-fan` within this document for detailed overlay options.)
