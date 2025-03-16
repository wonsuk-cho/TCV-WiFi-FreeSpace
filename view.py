# view.py
"""
View module for the IoT Project.
Contains helper functions for visualization (if needed for debugging).
Note: The unified GUI in main_gui.py now handles the live feed and plot.
"""

import matplotlib.pyplot as plt
from settings import VISUALIZATION_CONFIG, DEBUG

def display_signals(signals):
    """
    Display the list of Wi-Fi signals (for debugging purposes).
    """
    if DEBUG:
        print("Devices within specified range:")
    if not signals:
        if DEBUG:
            print("No devices found within the specified range.")
    for signal in signals:
        if DEBUG:
            print(f"- {signal.get('ssid')} (RSSI: {signal.get('rssi')})")

# No standalone test code.
if __name__ == '__main__':
    pass
