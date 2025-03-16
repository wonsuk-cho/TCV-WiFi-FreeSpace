# settings.py
"""
Global configuration file for the IoT Project.
Contains all the important settings and global variables.
"""

# ---------------- SYSTEM CONFIGURATION ----------------
SYSTEM = {
    'os': 'macOS',
    'machine': 'Macbook Pro 14 M1 Pro',
    'ram': '16GB',
    'python_version': '3.13.1'
}

# ---------------- TCPDUMP CONFIGURATION ----------------
TCPDUMP_CONFIG = {
    'interface': 'en0',               # Network interface to listen on
    'filter': 'type mgt subtype probe-req',  # tcpdump filter for probe requests
    'buffer_size': 256,               # Buffer size for tcpdump capture
    'password': 'yourmacpassword',             # Replace with your actual password
}

# ---------------- WEBCAM CONFIGURATION ----------------
WEBCAM_CONFIG = {
    'device_index': 0,     # Default webcam device index
    'frame_width': 854,    # Width to resize the webcam feed
    'frame_height': 480,   # Height to resize the webcam feed
}

# ---------------- VISUALIZATION CONFIGURATION ----------------
VISUALIZATION_CONFIG = {
    'plot_update_interval': 0.5,  # Time (in seconds) between plot updates
    'max_data_points': 30,        # Maximum number of data points for live plotting
}

# ---------------- DEBUG SETTINGS ----------------
DEBUG = False  # Set to True to enable debug prints

SCAN_RADIUS_METERS = 0.1
DEFAULT_TX_POWER = -30
PATH_LOSS_EXPONENT = 2.0

def print_test_settings():
    """
    Prints out the current global settings for debugging.
    """
    if DEBUG:
        print("----- System Settings -----")
        for key, value in SYSTEM.items():
            print(f"{key}: {value}")
        print("\n----- TCPDump Configuration -----")
        for key, value in TCPDUMP_CONFIG.items():
            print(f"{key}: {value}")
        print("\n----- Webcam Configuration -----")
        for key, value in WEBCAM_CONFIG.items():
            print(f"{key}: {value}")
        print("\n----- Visualization Configuration -----")
        for key, value in VISUALIZATION_CONFIG.items():
            print(f"{key}: {value}")

if __name__ == '__main__':
    print_test_settings()
