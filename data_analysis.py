#!/usr/bin/env python3
"""
Subscriber that receives MQTT messages, processes the message data, and writes to two CSV files:
    1. free_space_detection.csv – Contains free space computation results.
    2. wifi_detection.csv – Contains Wi‑Fi detection details.
The incoming MQTT messages are expected to have the following format:
    
=== Free Space Detection Results ===
Frame Differencing: 32.96%
Background Subtraction: 24.29%
Contour Detection: 32.87%
SSIM: 30.01%
Mean of Enabled Methods: 30.03%
[NOT TRUSTED] MAC: 4c:23:1a:05:bd:d4, Vendor: Unknown, Signal: -69 dBm, Time: Sat Mar 15 18:47:03 2025
[NOT TRUSTED] MAC: 66:97:d8:9a:e3:7d, Vendor: Unknown, Signal: -72 dBm, Time: Sat Mar 15 18:47:03 2025

Each message is parsed into its two sections, and the resulting data is appended to the CSV files.
"""

import paho.mqtt.client as mqtt
import os
import csv
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from statsmodels.tsa.arima.model import ARIMA

# ================= MQTT SETTINGS =================
MQTT_BROKER = 'localhost'
MQTT_PORT = 1883
MQTT_TOPIC = 'iot/detection'

# ================= CSV FILE NAMES =================
FREE_SPACE_CSV = "free_space_detection.csv"
WIFI_CSV = "wifi_detection.csv"

# ================= DEBUG SETTING =================
DEBUG = False  # Set to True to enable debug prints

# Update interval in milliseconds
UPDATE_INTERVAL = 10

class DataAnalysisGUI:
    def __init__(self, master):
        self.master = master
        master.title("Data Analysis & Live Visualization")
        master.geometry("1200x800")  # Adjust window size as needed
        
        # Create a Notebook for multiple tabs
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill="both", expand=True)
        
        # Create four tabs
        self.tab1 = ttk.Frame(self.notebook)  # Wi-Fi Signal Strength
        self.tab2 = ttk.Frame(self.notebook)  # Free Space Trend
        self.tab3 = ttk.Frame(self.notebook)  # Device Count
        self.tab4 = ttk.Frame(self.notebook)  # Trusted vs Untrusted
        self.notebook.add(self.tab1, text="Wi-Fi Signal Strength")
        self.notebook.add(self.tab2, text="Free Space Trend")
        self.notebook.add(self.tab3, text="Device Count")
        self.notebook.add(self.tab4, text="Trusted vs Untrusted")
        
        # ----------------- Tab 1: Wi-Fi Signal Strength Over Time -----------------
        self.fig1 = Figure(figsize=(5, 4), dpi=100)
        self.ax1 = self.fig1.add_subplot(111)
        self.fig1.subplots_adjust(right=0.8)
        self.canvas1 = FigureCanvasTkAgg(self.fig1, master=self.tab1)
        self.canvas1.get_tk_widget().pack(fill="both", expand=True)
        # self.fig1.tight_layout()
        
        # ----------------- Tab 2: Free Space Detection Trend -----------------
        self.fig2 = Figure(figsize=(5, 4), dpi=100)
        self.ax2 = self.fig2.add_subplot(111)
        self.canvas2 = FigureCanvasTkAgg(self.fig2, master=self.tab2)
        self.canvas2.get_tk_widget().pack(fill="both", expand=True)
        
        # ----------------- Tab 3: Device Count Over Time -----------------
        self.fig3 = Figure(figsize=(5, 4), dpi=100)
        self.ax3 = self.fig3.add_subplot(111)
        self.canvas3 = FigureCanvasTkAgg(self.fig3, master=self.tab3)
        self.canvas3.get_tk_widget().pack(fill="both", expand=True)
        
        # ----------------- Tab 4: Trusted vs Untrusted Devices -----------------
        self.fig4 = Figure(figsize=(5, 4), dpi=100)
        self.ax4 = self.fig4.add_subplot(111)
        self.canvas4 = FigureCanvasTkAgg(self.fig4, master=self.tab4)
        self.canvas4.get_tk_widget().pack(fill="both", expand=True)
        
        # Exit button at the bottom of the window
        exit_button = tk.Button(master, text="Exit", command=master.quit)
        exit_button.pack(side="bottom", pady=5)
        
        # Start updating plots
        self.update_plots()
    
    def update_plots(self):
        """Reads CSV files and updates the four plots."""
        # Clear all axes
        self.ax1.clear()
        self.ax2.clear()
        self.ax3.clear()
        self.ax4.clear()
        
        # -------------- Tab 1: Wi-Fi Signal Strength Over Time --------------
        try:
            if os.path.exists(WIFI_CSV):
                wifi_df = pd.read_csv(WIFI_CSV, parse_dates=["timestamp"])
                if not wifi_df.empty:
                    # Group by MAC address and plot each line
                    # Group by MAC address and plot each line
                    for mac, group in wifi_df.groupby("mac"):
                        group = group.sort_values("timestamp")

                        # Check if the device is trusted
                        trusted_name = group["trusted_name"].iloc[0] if group["status"].iloc[0] == "TRUSTED" and group["trusted_name"].iloc[0] else None
                        
                        if trusted_name:
                            # Use a thick red line for trusted devices and display their names in the legend
                            self.ax1.scatter(group["timestamp"], group["signal"], label=f"{trusted_name} (Trusted)", s=50, color="green", alpha=0.9)
                        else:
                            # Normal plot for untrusted devices
                            self.ax1.scatter(group["timestamp"], group["signal"], label=mac, s=20, alpha=0.7)
                    self.ax1.set_title("Wi-Fi Signal Strength Over Time")
                    self.ax1.set_xlabel("Time")
                    self.ax1.set_ylabel("Signal (dBm)")
                    self.ax1.legend(
                        fontsize='small',
                        bbox_to_anchor=(1.02, 1),  # Position outside plot
                        loc='upper left',
                        borderaxespad=0,
                        title="Devices"
                    )
                else:
                    self.ax1.text(0.5, 0.5, "No Wi-Fi Data", ha="center", va="center")
            else:
                self.ax1.text(0.5, 0.5, "Wi-Fi CSV Not Found", ha="center", va="center")
        except Exception as e:
            if DEBUG:
                print("[DEBUG] Error in Tab 1:", e)
            self.ax1.text(0.5, 0.5, "Error loading Wi-Fi data", ha="center", va="center")
        
        # -------------- Tab 2: Free Space Detection Trend --------------
        try:
            if os.path.exists(FREE_SPACE_CSV):
                free_df = pd.read_csv(FREE_SPACE_CSV, parse_dates=["timestamp"])
                if not free_df.empty:
                    free_df = free_df.sort_values("timestamp")
                    self.forecast_free_space()
                    self.canvas2.draw()
                    self.ax2.set_title("Free Space Detection Trend")
                    self.ax2.set_xlabel("Time")
                    self.ax2.set_ylabel("Mean Detection (%)")
                else:
                    self.ax2.text(0.5, 0.5, "No Free Space Data", ha="center", va="center")
            else:
                self.ax2.text(0.5, 0.5, "Free Space CSV Not Found", ha="center", va="center")
        except Exception as e:
            if DEBUG:
                print("[DEBUG] Error in Tab 2:", e)
            self.ax2.text(0.5, 0.5, "Error loading Free Space data", ha="center", va="center")
        
        # -------------- Tab 3: Device Count Over Time --------------
        try:
            if os.path.exists(WIFI_CSV):
                wifi_df = pd.read_csv(WIFI_CSV, parse_dates=["timestamp"])
                if not wifi_df.empty:
                    # Group data into 5-second intervals
                    wifi_df["time_bucket"] = wifi_df["timestamp"].dt.floor("s")
                    count_series = wifi_df.groupby("time_bucket").size().sort_index()

                    if not count_series.empty:
                        # self.ax3.bar(count_series.index, count_series.values,
                        #     width=0.00005,  # ~5 seconds in days
                        #     color="blue", alpha=0.7,
                        #     label="Device Count", align="center")
                        # self.ax3.set_title("Device Count Over Time")
                        # self.ax3.set_xlabel("Time")
                        # self.ax3.set_ylabel("Count")
                        # self.ax3.legend()
                        self.ax3.plot(
                            count_series.index,
                            count_series.values,
                            marker='o',         # Optional: puts a dot at each data point
                            linestyle='-',      # Connect dots with a line
                            color='blue',
                            alpha=0.7,
                            label="Device Count"
                        )
                        # Improve X-axis readability
                        self.ax3.xaxis.set_major_locator(plt.MaxNLocator(nbins=10))
                        self.ax3.tick_params(axis="x", rotation=45)
                    else:
                        self.ax3.text(0.5, 0.5, "No Device Data", ha="center", va="center")
            else:
                self.ax3.text(0.5, 0.5, "Wi-Fi CSV Not Found", ha="center", va="center")
        except Exception as e:
            if DEBUG:
                print("[DEBUG] Error in Tab 3:", e)
            self.ax3.text(0.5, 0.5, "Error loading Device Count data", ha="center", va="center")

        # -------------- Tab 4: Trusted vs Untrusted Devices (Pie Chart) --------------
        try:
            if os.path.exists(WIFI_CSV):
                wifi_df = pd.read_csv(WIFI_CSV)
                if not wifi_df.empty:
                    # Count trusted and not trusted devices based on the status column
                    trusted_count = wifi_df[wifi_df["status"].str.contains("TRUSTED", case=False)].shape[0]
                    not_trusted_count = wifi_df[wifi_df["status"].str.contains("NOT TRUSTED", case=False)].shape[0]
                    counts = [trusted_count, not_trusted_count]
                    labels = ["Trusted", "Not Trusted"]
                    self.ax4.pie(counts, labels=labels, autopct='%1.1f%%', startangle=90)
                    self.ax4.set_title("Trusted vs Untrusted Devices")
                else:
                    self.ax4.text(0.5, 0.5, "No Wi-Fi Data", ha="center", va="center")
            else:
                self.ax4.text(0.5, 0.5, "Wi-Fi CSV Not Found", ha="center", va="center")
        except Exception as e:
            if DEBUG:
                print("[DEBUG] Error in Tab 4:", e)
            self.ax4.text(0.5, 0.5, "Error loading Pie Chart data", ha="center", va="center")
        
        # Redraw all canvases
        self.canvas1.draw()
        self.canvas2.draw()
        self.canvas3.draw()
        self.canvas4.draw()
        
        # Schedule the next update
        self.master.after(UPDATE_INTERVAL, self.update_plots)
        
    def forecast_free_space(self):
        """
        Reads past free space detection data and applies ARIMA to forecast future occupancy levels.
        """
        try:
            if os.path.exists(FREE_SPACE_CSV):
                free_df = pd.read_csv(FREE_SPACE_CSV, parse_dates=["timestamp"])
                free_df["timestamp"] = pd.to_datetime(free_df["timestamp"])
                if not free_df.empty:
                    free_df = free_df.sort_values("timestamp")

                    # Ensure enough data points for ARIMA
                    if len(free_df) > 10:
                    # if len(free_df) > 10 and free_df["mean"].notna().sum() > 10:
                        # Fit ARIMA model (Auto-Regressive=2, Differencing=1, Moving Average=2)
                        model = ARIMA(free_df["mean"], order=(3, 2, 3), enforce_stationarity=False, enforce_invertibility=False)
                        model_fit = model.fit()

                        # Forecast next 5 intervals
                        forecast_steps = 100
                        forecast = model_fit.forecast(steps=forecast_steps)

                        # Generate future timestamps
                        last_timestamp = free_df["timestamp"].iloc[-1]
                        future_timestamps = pd.date_range(last_timestamp, periods=forecast_steps + 1, freq="s")[1:]

                        # Plot actual data
                        self.ax2.plot(free_df["timestamp"], free_df["mean"], linestyle="-", color="black", label="Actual")

                        # Plot forecasted data
                        self.ax2.plot(future_timestamps, forecast, linestyle="--", color="red", label="Forecast")

                        self.ax2.set_title("Free Space Detection Trend (with Forecast)")
                        self.ax2.set_xlabel("Time")
                        self.ax2.set_ylabel("Mean Occupancy (%)")
                        self.ax2.legend()
                        
                    else:
                        self.ax2.text(0.5, 0.5, "Not enough data for forecasting", ha="center", va="center")
                        
        except Exception as e:
            if DEBUG:
                print("[DEBUG] Error in forecasting free space:", e)
            self.ax2.text(0.5, 0.5, "Error loading forecast data", ha="center", va="center")

# ================= HELPER FUNCTIONS =================
def parse_free_space_detection(lines):
    """
    Parses free space detection lines and extracts detection percentages.
    Returns a dictionary with keys:
      - frame_differencing
      - background_subtraction
      - contour_detection
      - ssim
      - mean
    """
    result = {}
    for line in lines:
        if "Frame Differencing:" in line:
            match = re.search(r"Frame Differencing:\s*([\d.]+)%", line)
            if match:
                result["frame_differencing"] = float(match.group(1))
        elif "Background Subtraction:" in line:
            match = re.search(r"Background Subtraction:\s*([\d.]+)%", line)
            if match:
                result["background_subtraction"] = float(match.group(1))
        elif "Contour Detection:" in line:
            match = re.search(r"Contour Detection:\s*([\d.]+)%", line)
            if match:
                result["contour_detection"] = float(match.group(1))
        elif "SSIM:" in line:
            match = re.search(r"SSIM:\s*([\d.]+)%", line)
            if match:
                result["ssim"] = float(match.group(1))
        elif "Mean of Enabled Methods:" in line:
            match = re.search(r"Mean of Enabled Methods:\s*([\d.]+)%", line)
            if match:
                result["mean"] = float(match.group(1))
    if DEBUG:
        print("[DEBUG] Parsed free space detection data:", result)
    return result

def parse_wifi_detection(lines):
    """
    Parses Wi-Fi detection lines and extracts device details.
    Returns a list of dictionaries, each with keys:
      - timestamp, mac, vendor, trusted_name, signal, status
    """
    wifi_list = []
    for line in lines:
        # Process only lines that start with '[' and contain "MAC:"
        if line.startswith("[") and "MAC:" in line:
            status_match = re.match(r"\[(.*?)\]", line)
            mac_match = re.search(r"MAC:\s*([0-9a-fA-F:]+)", line)
            vendor_match = re.search(r"Vendor:\s*([^,]+)", line)
            signal_match = re.search(r"Signal:\s*([-\d]+)\s*dBm", line)
            time_match = re.search(r"Time:\s*(.*)", line)
            
            if status_match and mac_match and vendor_match and signal_match and time_match:
                status = status_match.group(1).strip()
                mac = mac_match.group(1).strip()
                vendor = vendor_match.group(1).strip()
                signal = int(signal_match.group(1).strip())
                time_str = time_match.group(1).strip()
                
                # Parse time format e.g., "Sat Mar 15 18:47:03 2025"
                try:
                    timestamp = datetime.strptime(time_str, "%a %b %d %H:%M:%S %Y")
                    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    if DEBUG:
                        print(f"[DEBUG] Failed to parse time '{time_str}': {e}")
                    timestamp_str = time_str
                
                # If the device is TRUSTED, try to capture the trusted name (e.g., "Name: John Doe")
                trusted_name = ""
                if "TRUSTED" in status.upper():
                    name_match = re.search(r"Name:\s*([^,]+)", line)
                    if name_match:
                        trusted_name = name_match.group(1).strip()
                
                wifi_list.append({
                    "timestamp": timestamp_str,
                    "mac": mac,
                    "vendor": vendor,
                    "trusted_name": trusted_name,
                    "signal": signal,
                    "status": status
                })
    if DEBUG:
        print("[DEBUG] Parsed Wi-Fi detection data:", wifi_list)
    return wifi_list

def append_free_space_csv(free_space_data, timestamp):
    """
    Appends a row of free space detection data to FREE_SPACE_CSV.
    CSV Columns: timestamp, frame_differencing, background_subtraction,
                 contour_detection, ssim, mean
    """
    file_exists = os.path.exists(FREE_SPACE_CSV)
    with open(FREE_SPACE_CSV, "a", newline="") as csvfile:
        fieldnames = ["timestamp", "frame_differencing", "background_subtraction", 
                      "contour_detection", "ssim", "mean"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        row = {"timestamp": timestamp}
        row.update(free_space_data)
        writer.writerow(row)
    if DEBUG:
        print(f"[DEBUG] Appended free space detection data to {FREE_SPACE_CSV}")

def append_wifi_csv(wifi_data):
    """
    Appends rows of Wi-Fi detection data to WIFI_CSV.
    CSV Columns: timestamp, mac, vendor, trusted_name, signal, status
    """
    file_exists = os.path.exists(WIFI_CSV)
    with open(WIFI_CSV, "a", newline="") as csvfile:
        fieldnames = ["timestamp", "mac", "vendor", "trusted_name", "signal", "status"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for entry in wifi_data:
            writer.writerow(entry)
    if DEBUG:
        print(f"[DEBUG] Appended Wi-Fi detection data to {WIFI_CSV}")

def process_and_write_data(raw_text):
    """
    Processes the raw MQTT message text by splitting it into free space and Wi-Fi sections,
    then appends the extracted data to their respective CSV files.
    """
    lines = raw_text.splitlines()
    if DEBUG:
        print("[DEBUG] Processing raw text message.")
    free_space_lines = []
    wifi_lines = []
    free_space_section = False
    wifi_section = False

    for line in lines:
        line = line.strip()
        # Start free space detection section if header is detected
        if line.startswith("===") and "Free Space Detection Results" in line:
            free_space_section = True
            wifi_section = False
            continue
        # Lines starting with '[' and containing "MAC:" indicate Wi-Fi messages
        if line.startswith("[") and "MAC:" in line:
            wifi_section = True
            free_space_section = False
        if free_space_section:
            free_space_lines.append(line)
        if wifi_section:
            wifi_lines.append(line)
    
    free_space_data = parse_free_space_detection(free_space_lines)
    wifi_data = parse_wifi_detection(wifi_lines)
    
    # Use timestamp from first Wi-Fi detection if available; otherwise, use current time.
    if wifi_data:
        timestamp = wifi_data[0]["timestamp"]
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    append_free_space_csv(free_space_data, timestamp)
    append_wifi_csv(wifi_data)
    
    if DEBUG:
        print("[DEBUG] Finished processing and writing data.")

# ================= MQTT CALLBACKS =================
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[DEBUG] Subscriber connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    print(f"[DEBUG] Subscribed to topic: {MQTT_TOPIC}")

def on_message(client, userdata, msg):
    # Decode the incoming MQTT message payload.
    message = msg.payload.decode()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[DEBUG] Message received at {timestamp}:")
    print(message)
    # Process the raw message text to extract and save the data.
    process_and_write_data(message)

def start_subscriber():
    """
    Initializes and starts the MQTT subscriber client.
    """
    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="DataSubscriber") 
    subscriber.on_connect = on_connect
    subscriber.on_message = on_message

    print("[DEBUG] Subscriber connecting to broker...")
    subscriber.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    subscriber.loop_forever()

# ================= MAIN EXECUTION =================
def main():
    root = tk.Tk()
    app = DataAnalysisGUI(root)
    root.mainloop()

if __name__ == "__main__":
    import threading

    # Start the MQTT subscriber in a background daemon thread
    subscriber_thread = threading.Thread(target=start_subscriber, daemon=True)
    subscriber_thread.start()

    # Start the GUI main loop (this runs in the main thread)
    main()
