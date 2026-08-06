#!/bin/bash

# 1. CLEANUP: Force kill any leftover processes from a crashed session
# This ensures that when you boot up, the camera/Hailo isn't already "locked"
pkill -9 -f sensey_mode_controller.py
pkill -9 -f oakd_blind_runner.py
pkill -9 -f arecord

# Wait for desktop and audio hardware to stabilize
sleep 5

# Force video display to use XCB
export QT_QPA_PLATFORM=xcb
export DISPLAY=:0

# Run the Master Controller script
# We use quotes to handle the space in "MASTER CONTROL"
cd "/home/raspberrypi/MASTER CONTROL"
/home/raspberrypi/hailo-apps/venv_hailo_apps/bin/python3 "/home/raspberrypi/MASTER CONTROL/sensey_mode_controller.py"

# Keep window open if crash happens
exec bash
