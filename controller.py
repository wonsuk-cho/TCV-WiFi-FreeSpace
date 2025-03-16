# controller.py
"""
Controller module for the IoT Project.
Coordinates background tasks:
  - Running tcpdump to detect Wi-Fi probe requests.
  - Capturing the live webcam feed.
  - Processing frames and updating global variables.
"""

import cv2
import re
import threading
import time
import pexpect
from collections import deque

from settings import TCPDUMP_CONFIG, WEBCAM_CONFIG, VISUALIZATION_CONFIG, DEBUG, SCAN_RADIUS_METERS
from model import calculate_difference, rssi_to_distance
from view import display_signals  # For debugging if needed

import os
from mqtt_setup import publish_log

# File to store trusted device MAC addresses
trusted_devices_file = "trusted_devices.txt"

# Global dictionary to hold trusted devices.
# Key: MAC address; Value: Trusted name (empty string if no name is set)
trusted_devices = {}

# Global variable to indicate if Secure Location is enabled.
secure_location_enabled = False

# ---------------- GLOBAL VARIABLES ----------------
detected_devices = set()  # Unique detected device MAC addresses
device_counts = deque(maxlen=VISUALIZATION_CONFIG['max_data_points'])
wifi_strengths = deque(maxlen=VISUALIZATION_CONFIG['max_data_points'])

frame = None             # Current webcam frame
baseline_image = None    # Baseline frame for image comparison
stop_threads = False     # Control flag for safely stopping threads

# Global dictionary to hold detailed info for each device
# Key: MAC address; Value: dict with 'mac', 'signal', 'last_seen', 'vendor'
devices_info = {}

# Allowed MAC address prefixes (for filtering)
allowed_prefixes = {
    "94:9b:2c",  # Samsung
    "b8:50:01",  # Apple
    "6e:5d:06",  # Huawei
    "b6:6a:f3",  # Xiaomi
    "62:05:5a",  # OPPO
    "fa:62:37",  # OnePlus
    "26:09:a8",  # Motorola
    "b6:77:d5"   # Additional allowed prefix
}

# Mapping of MAC prefix to Vendor
VENDOR_MAP = {
    "94:9b:2c": "Samsung Electronics",
    "b8:50:01": "Apple, Inc.",
    "6e:5d:06": "Huawei Technologies",
    "b6:6a:f3": "Xiaomi Communications",
    "62:05:5a": "OPPO Electronics",
    "fa:62:37": "OnePlus Technology",
    "26:09:a8": "Motorola Mobility",
    "b6:77:d5": "Won Suk CHO"
}

printed_devices = set()

def load_trusted_devices():
    """Loads trusted devices from trusted_devices.txt into the global trusted_devices dict.
    If the file does not exist, it is created."""
    global trusted_devices
    if not os.path.exists(trusted_devices_file):
        with open(trusted_devices_file, "w") as f:
            pass  # Create an empty file
    with open(trusted_devices_file, "r") as f:
        lines = f.readlines()
    trusted_devices = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",", 1)
        if len(parts) == 2:
            mac, name = parts[0].strip(), parts[1].strip()
        else:
            mac, name = parts[0].strip(), ""
        trusted_devices[mac] = name

load_trusted_devices()

def add_trusted_device(mac, name):
    """Adds a MAC address with a trusted name to the trusted_devices dict and appends it to trusted_devices.txt."""
    global trusted_devices
    if mac not in trusted_devices:
        trusted_devices[mac] = name
        with open(trusted_devices_file, "a") as f:
            f.write(f"{mac},{name}\n")

def run_tcpdump():
    """
    Runs tcpdump in a separate thread to capture Wi-Fi probe requests.
    Updates global devices_info (and signal deques for plotting).
    """
    password = TCPDUMP_CONFIG['password']
    interface = TCPDUMP_CONFIG['interface']
    tcpdump_filter = TCPDUMP_CONFIG['filter']
    buffer_size = TCPDUMP_CONFIG['buffer_size']
    
    try:
        if DEBUG:
            print("[DEBUG] Starting tcpdump thread...")
        # Use -e -vvv so that the output contains MAC addresses and signal info
        cmd = f"sudo tcpdump -I -e -vvv -i {interface} -n -s {buffer_size} {tcpdump_filter}"
        child = pexpect.spawn(cmd, timeout=None)
        
        index = child.expect(["Password:", pexpect.EOF], timeout=5)
        if index == 0:
            if DEBUG:
                print("[DEBUG] Sending password for tcpdump...")
            child.sendline(password)
        
        if DEBUG:
            print("[DEBUG] tcpdump running...")
        
        while not stop_threads:
            try:
                line = child.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                if DEBUG:
                    print(f"[DEBUG] tcpdump output: {line}")
                
                mac_match = re.search(r"SA:([0-9a-fA-F:]+)", line)
                signal_match = re.search(r'(-\d+)dBm signal', line)
                
                if mac_match and signal_match:
                    mac_address = mac_match.group(1).lower()
                    mac_prefix = mac_address[:8]
                    
                    # # Filter based on allowed prefixes
                    # if mac_prefix not in allowed_prefixes:
                    #     continue
                    
                    signal_value = int(signal_match.group(1))
                    current_time = time.time()
                    
                    # Only print if this device hasn't been printed before
                    # NOT TRUSTED DEVICES
                    if secure_location_enabled and (mac_address not in trusted_devices):
                        # if mac_address not in printed_devices:
                        message = (f"[NOT TRUSTED] MAC: {mac_address}, Vendor: {VENDOR_MAP.get(mac_prefix, 'Unknown')}, "
                                    f"Signal: {signal_value} dBm, Time: {time.ctime(current_time)}")
                        print(message)
                        publish_log(message)
                        printed_devices.add(mac_address)
                            
                    # Only print if this device hasn't been printed before
                    # TRUSTED DEVICES
                    if secure_location_enabled and (mac_address in trusted_devices):
                        # if mac_address not in printed_devices:
                        trusted_name = trusted_devices.get(mac_address, "Unknown")
                        message = (f"[TRUSTED] MAC: {mac_address}, Name: {trusted_name}, Vendor: {VENDOR_MAP.get(mac_prefix, 'Unknown')}, "
                                    f"Signal: {signal_value} dBm, Time: {time.ctime(current_time)}")
                        print(message)
                        publish_log(message)
                        printed_devices.add(mac_address)
                    
                    # Update devices_info with this device's data (unique by MAC)
                    devices_info[mac_address] = {
                        "mac": mac_address,
                        "signal": signal_value,
                        "last_seen": current_time,
                        "vendor": VENDOR_MAP.get(mac_prefix, "Unknown")
                    }
                    
                    # Also update global sets/deques for plotting if needed.
                    detected_devices.add(mac_address)
                    device_counts.append(len(detected_devices))
                    wifi_strengths.append(signal_value)
            except pexpect.exceptions.TIMEOUT:
                if DEBUG:
                    print("[ERROR] tcpdump timeout.")
                continue
            except Exception as e:
                if DEBUG:
                    print(f"[ERROR] Exception in tcpdump thread: {e}")
                break
    except pexpect.exceptions.EOF:
        if DEBUG:
            print("[ERROR] tcpdump EOF encountered.")
    except Exception as e:
        if DEBUG:
            print(f"[ERROR] Exception starting tcpdump: {e}")

def webcam_feed():
    """
    Continuously captures frames from the webcam and updates the global 'frame' variable.
    """
    global frame, stop_threads
    if DEBUG:
        print("[DEBUG] Starting webcam feed thread...")
    cap = cv2.VideoCapture(WEBCAM_CONFIG['device_index'])
    while not stop_threads:
        ret, new_frame = cap.read()
        if ret:
            frame = cv2.resize(new_frame, (WEBCAM_CONFIG['frame_width'], WEBCAM_CONFIG['frame_height']))
        else:
            if DEBUG:
                print("[ERROR] Failed to capture webcam frame.")
    cap.release()
    if DEBUG:
        print("[DEBUG] Webcam feed thread terminated.")

if __name__ == '__main__':
    pass
