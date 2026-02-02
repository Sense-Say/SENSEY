##
https://github.com/hailo-ai/hailo-apps/blob/main/doc/user_guide/installation.md#raspberry-pi-installation
##


## Raspberry Pi Installation

These instructions are for setting up a Raspberry Pi 5 with a Hailo AI accelerator.

### Hardware Setup for RPi

1.  **Required Hardware**:
    *   Raspberry Pi 5 (8GB recommended) with Active Cooler.
    *   A Hailo accelerator:
        *   **Raspberry Pi AI Kit**: M.2 HAT + Hailo-8L/Hailo-8 Module.
        *   **Raspberry Pi AI HAT+**: A board with an integrated Hailo accelerator (13 or 26 TOPs).
    *   A 27W USB-C Power Supply.

2.  **Assembly**:
    *   **For AI Kit**: Follow the [Raspberry Pi's official AI Kit Guide](https://www.raspberrypi.com/documentation/accessories/ai-kit.html#ai-kit).
        *   Ensure a thermal pad is placed between the M.2 module and the HAT.
        *   Ensure the GPIO header is connected for stable operation.
    *   **For AI HAT+**: Follow the [Raspberry Pi's official AI HAT+ Guide](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html#ai-hat-plus).
        *   Ensure the GPIO header is connected for stable operation.

### Software Setup for RPi

1.  **Install Raspberry Pi OS**:
    *   Use the Raspberry Pi Imager to install the latest version of Raspberry Pi OS from [here](https://www.raspberrypi.com/software/).

2.  **Install Hailo Software**:
    *   The official Raspberry Pi AI stack includes the Hailo firmware and runtime. Follow the [Raspberry Pi's official AI Software Guide](https://www.raspberrypi.com/documentation/computers/ai.html#getting-started).

3.  **Enable PCIe Gen3 for Optimal Performance**:
    *   This is required for the M.2 HAT to achieve full performance. The AI HAT+ should configure this automatically if the GPIO is connected.
    *   Open the configuration tool: `sudo raspi-config`
    *   Go to `6 Advanced Options` -> `A8 PCIe Speed`.
    *   Choose `Yes` to enable PCIe Gen 3 mode.
    *   Reboot the Raspberry Pi: `sudo reboot`.

### Verification for RPi

1.  **Check if the Hailo chip is recognized**:
    ```bash
    hailortcli fw-control identify
    ```
    This should show your board details (e.g., Board Name: Hailo-8). If not, see the troubleshooting section.

2.  **Check GStreamer plugins**:
    *   Verify `hailotools`: `gst-inspect-1.0 hailotools`
    *   Verify `hailo` (inference element): `gst-inspect-1.0 hailo`
    *   If a plugin is not found, you may need to clear the GStreamer cache: `rm ~/.cache/gstreamer-1.0/registry.aarch64.bin` and reboot.

---


### Installation in Docker

After installing the prerequisites, proceed with the standard installation:

```bash
# Clone the repository (if not already done)
git clone https://github.com/hailo-ai/hailo-apps.git
cd hailo-apps

# Run the automated installation script
sudo ./install.sh
```

> **Note:** The Hailo "Suite Docker" already has HailoRT and TAPPAS Core pre-installed. The `install.sh` script will detect this and skip those components.

---

## Post-Installation Verification

After running any of the installation methods, you can verify that everything is working correctly.

1.  **Activate your environment**
    ```bash
    source venv_hailo_apps/bin/activate
    # or simply run the helper each session
    source setup_env.sh
    ```
2.  **Check installed Hailo packages**
    ```bash
    pip list | grep hailo
    # You should see packages like hailort, hailo-tappas-core, and hailo-apps.

    apt list | grep hailo
    # This shows all installed Hailo-related system packages.
    ```
3.  **Verify the Hailo device connection**
    ```bash
    hailortcli fw-control identify
    ```
4.  **Run a demo application**
    ```bash
    hailo-detect-simple
    ```
    A video window with live detections should appear.

<details>
<summary><b>Troubleshooting Tips</b></summary>

*   **PCIe Issues (RPi)**: If `lspci | grep Hailo` shows no device, check your M.2 HAT or AI HAT+ connections, power supply, and ensure PCIe is enabled in `raspi-config`.
*   **Driver Issues (RPi)**: If you see driver errors, ensure your kernel is up to date (`sudo apt update && sudo apt full-upgrade`).
*   **`DEVICE_IN_USE()` Error**: This means the Hailo device is being used by another process. Run the cleanup script: `./scripts/kill_first_hailo.sh`.
*   **GStreamer `cannot allocate memory in static TLS block` (RPi)**: This is a known issue. Add `export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1` to your `~/.bashrc` file and reboot.
*   **Emoji Display Issues (RPi)**: If emoji icons (❌, ✅, etc.) are not displaying correctly in terminal output, install the Noto Color Emoji font:
    ```bash
    sudo apt-get update
    sudo apt-get install fonts-noto-color-emoji
    fc-cache -f -v
    ```
    After installation, restart your terminal or log out and back in. If emojis still don't display, ensure your locale supports UTF-8:
    ```bash
    export LANG=en_US.UTF-8
    export LC_ALL=en_US.UTF-8
    ```

</details>

---

## Uninstallation

To remove the environment and downloaded resources:

```bash
# Deactivate the virtual environment if active
deactivate

# Delete project files and logs
sudo rm -rf venv_hailo_apps/ resources/ hailort.log hailo_apps.egg-info
```
To uninstall system packages, use `apt remove`.
