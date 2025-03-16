# main_gui.py
"""
MVP for the IoT Project with a unified GUI.
Layout:
- Top: Live camera feed.
- Middle: Table listing available Wi-Fi devices.
- Bottom: Settings panel (to adjust SCAN_RADIUS_METERS, DEFAULT_TX_POWER, PATH_LOSS_EXPONENT)
         and Control panel with detection method checkboxes and control buttons.
Detection Methods:
    • Frame Differencing
    • Background Subtraction
    • Contour Detection
    • Structural Similarity Index (SSIM)
Users can enable/disable each detection method via checkboxes.
An average of the enabled detection results is computed and overlaid on the live feed.
The device table updates dynamically, removing devices that haven’t been seen recently.
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2
import threading
import time

import settings  # so we can update its variables dynamically
from settings import DEBUG, VISUALIZATION_CONFIG
from model import calculate_difference
import controller  # Uses run_tcpdump, webcam_feed, and global variables
from mqtt_setup import publish_log

# Global variable for PhotoImage to prevent garbage collection
photo = None

# Timeout (in seconds) to consider a device “lost”
DEVICE_TIMEOUT = 5.0

# Global variable for the print interval in milliseconds (default 3000 ms = 3 seconds)
print_interval_ms = 3000

CAMERA_LOG_INTERVAL = 1000 #ms

# ================= DETECTION METHOD FUNCTIONS =================
def detect_frame_differencing(baseline, current):
    diff = cv2.absdiff(baseline, current)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    changed_pixels = cv2.countNonZero(thresh)
    total_pixels = thresh.shape[0] * thresh.shape[1]
    diff_percent = (changed_pixels / total_pixels) * 100
    return diff_percent, thresh

def detect_background_subtraction(baseline, current):
    diff = cv2.absdiff(baseline, current)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    changed_pixels = cv2.countNonZero(cleaned)
    total_pixels = cleaned.shape[0] * cleaned.shape[1]
    diff_percent = (changed_pixels / total_pixels) * 100
    return diff_percent, cleaned

def detect_contour_detection(baseline, current):
    diff = cv2.absdiff(baseline, current)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour_img = current.copy()
    cv2.drawContours(contour_img, contours, -1, (0, 255, 0), 2)
    total_area = current.shape[0] * current.shape[1]
    contour_area = sum(cv2.contourArea(c) for c in contours)
    diff_percent = (contour_area / total_area) * 100
    return diff_percent, contour_img, contours

def detect_ssim(baseline, current):
    diff_percent, binary_diff, ssim_diff = calculate_difference(baseline, current)
    return diff_percent, binary_diff, ssim_diff

# ================= GUI UPDATE FUNCTIONS =================
def update_device_table():
    """
    Updates the Treeview table with the current devices from controller.devices_info.
    Devices not seen within DEVICE_TIMEOUT seconds are removed.
    """
    current_time = time.time()
    # Clear existing rows
    for row in device_table.get_children():
        device_table.delete(row)
    keys_to_remove = []
    for mac, info in list(controller.devices_info.items()):
        age = current_time - info["last_seen"]
        if age > DEVICE_TIMEOUT:
            keys_to_remove.append(mac)
        else:
            device_table.insert("", "end", values=(
                info["mac"],
                info["vendor"],
                info["signal"],
                f"{age:.1f}"
            ))
    for mac in keys_to_remove:
        del controller.devices_info[mac]
    # Schedule next table update (every 5 seconds)
    root.after(5000, update_device_table)

def update_gui():
    """
    Periodically update the GUI:
      - Refresh the live camera feed.
      - If a baseline is captured, run the enabled detection methods and overlay the results.
      - Compute and overlay the average difference from enabled methods.
    """
    global photo
    if controller.frame is not None:
        display_frame = controller.frame.copy()
        
        if controller.baseline_image is not None:
            detection_results = {}
            y_offset = 30

            if var_frame_diff.get():
                diff_fd, _ = detect_frame_differencing(controller.baseline_image, display_frame)
                detection_results["Frame Diff"] = diff_fd

            if var_background_sub.get():
                diff_bs, _ = detect_background_subtraction(controller.baseline_image, display_frame)
                detection_results["Background Sub"] = diff_bs

            if var_contour.get():
                diff_contour, contour_img, _ = detect_contour_detection(controller.baseline_image, display_frame)
                detection_results["Contour"] = diff_contour
                display_frame = contour_img

            if var_ssim.get():
                diff_ssim, _, _ = detect_ssim(controller.baseline_image, display_frame)
                detection_results["SSIM"] = diff_ssim

            # Overlay individual detection results
            for i, (method, diff_val) in enumerate(detection_results.items()):
                cv2.putText(display_frame, f"{method}: {diff_val:.2f}%", (20, y_offset + i * 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
            # Compute and overlay the average difference if any method is enabled
            if detection_results:
                average_diff = sum(detection_results.values()) / len(detection_results)
                cv2.putText(display_frame, f"Average: {average_diff:.2f}%", (20, y_offset + len(detection_results) * 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2, cv2.LINE_AA)
        
        # Convert BGR (OpenCV) to RGB (Tkinter)
        cv_img = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(cv_img)
        photo = ImageTk.PhotoImage(image=img)
        live_feed_label.config(image=photo)
    
    root.after(100, update_gui)

def capture_baseline():
    """
    Capture the current frame as the baseline image.
    """
    if controller.frame is not None:
        controller.baseline_image = controller.frame.copy()
        if DEBUG:
            print("[DEBUG] Baseline image captured via GUI.")

def close_program():
    """
    Signal background threads to stop and close the GUI.
    """
    controller.stop_threads = True
    root.destroy()
    if DEBUG:
        print("[DEBUG] Program is closing.")

def print_detection_results():
    """
    Every 3 seconds, this function prints to the terminal the results from the free space detection methods.
    It prints the individual detection percentages for:
      • Frame Differencing
      • Background Subtraction
      • Contour Detection
      • SSIM
    Only the enabled methods are computed; disabled methods are marked as DISABLED.
    Finally, it prints the mean of the enabled methods (or indicates if all are disabled).
    """
    if controller.baseline_image is not None and controller.frame is not None:
        # Copy the current frame for processing
        current_frame = controller.frame.copy()
        detection_results = {}
        output_lines = []
        output_lines.append("=== Free Space Detection Results ===")
        
        # Frame Differencing
        if var_frame_diff.get():
            diff_fd, _ = detect_frame_differencing(controller.baseline_image, current_frame)
            detection_results["Frame Differencing"] = diff_fd
            output_lines.append(f"Frame Differencing: {diff_fd:.2f}%")
        else:
            output_lines.append("Frame Differencing: DISABLED")
        
        # Background Subtraction
        if var_background_sub.get():
            diff_bs, _ = detect_background_subtraction(controller.baseline_image, current_frame)
            detection_results["Background Subtraction"] = diff_bs
            output_lines.append(f"Background Subtraction: {diff_bs:.2f}%")
        else:
            output_lines.append("Background Subtraction: DISABLED")
        
        # Contour Detection
        if var_contour.get():
            diff_contour, _, _ = detect_contour_detection(controller.baseline_image, current_frame)
            detection_results["Contour Detection"] = diff_contour
            output_lines.append(f"Contour Detection: {diff_contour:.2f}%")
        else:
            output_lines.append("Contour Detection: DISABLED")
        
        # SSIM
        if var_ssim.get():
            diff_ssim, _, _ = detect_ssim(controller.baseline_image, current_frame)
            detection_results["SSIM"] = diff_ssim
            output_lines.append(f"SSIM: {diff_ssim:.2f}%")
        else:
            output_lines.append("SSIM: DISABLED")
        
        # Compute the mean of enabled methods (if any are enabled)
        if detection_results:
            mean_value = sum(detection_results.values()) / len(detection_results)
            output_lines.append(f"Mean of Enabled Methods: {mean_value:.2f}%")
        else:
            output_lines.append("Mean of Enabled Methods: N/A (all methods disabled)")
    else:
        output_lines = ["Baseline image or current frame not available for detection."]
    
    # Create a single log message
    log_message = "\n".join(output_lines)
    # print(log_message)  # Optionally print to terminal as well
    publish_log(log_message)  # Publish the log message via MQTT

    # Schedule the next print after 3000 milliseconds (3 seconds)
    root.after(CAMERA_LOG_INTERVAL, print_detection_results)

# ================= MAIN WINDOW SETUP =================
root = tk.Tk()
root.title("IoT Project Dashboard")

# --- Live Camera Feed Frame ---
live_feed_frame = tk.Frame(root)
live_feed_frame.pack(side="top", fill="both", expand=True)
live_feed_label = tk.Label(live_feed_frame)
live_feed_label.pack()

# --- Table Frame for Available Wi-Fi Devices ---
# --- Table Frame for Available Wi-Fi Devices ---
table_frame = tk.Frame(root)
table_frame.pack(side="top", fill="both", expand=True)
# Add an extra column "Trusted" to display if a device is trusted.
device_table = ttk.Treeview(table_frame, columns=("MAC", "VendorName", "Signal", "LastSeen", "Trusted"), show="headings")
device_table.heading("MAC", text="MAC")
device_table.heading("VendorName", text="Vendor/Name")
device_table.heading("Signal", text="Signal (dBm)")
device_table.heading("LastSeen", text="Last Seen (s ago)")
device_table.heading("Trusted", text="Trusted")
device_table.pack(fill="both", expand=True)

# --- Settings Panel ---
settings_frame = tk.Frame(root)
settings_frame.pack(side="bottom", fill="x", pady=5)

label_scan_radius = tk.Label(settings_frame, text="Scan Radius (m):")
label_scan_radius.grid(row=0, column=0, padx=5, pady=2, sticky="e")
entry_scan_radius = tk.Entry(settings_frame, width=10)
entry_scan_radius.grid(row=0, column=1, padx=5, pady=2)
entry_scan_radius.insert(0, str(settings.SCAN_RADIUS_METERS))

label_tx_power = tk.Label(settings_frame, text="Default Tx Power (dBm):")
label_tx_power.grid(row=0, column=2, padx=5, pady=2, sticky="e")
entry_tx_power = tk.Entry(settings_frame, width=10)
entry_tx_power.grid(row=0, column=3, padx=5, pady=2)
entry_tx_power.insert(0, str(settings.DEFAULT_TX_POWER))

label_path_loss = tk.Label(settings_frame, text="Path Loss Exponent:")
label_path_loss.grid(row=0, column=4, padx=5, pady=2, sticky="e")
entry_path_loss = tk.Entry(settings_frame, width=10)
entry_path_loss.grid(row=0, column=5, padx=5, pady=2)
entry_path_loss.insert(0, str(settings.PATH_LOSS_EXPONENT))

def update_settings():
    try:
        new_scan_radius = float(entry_scan_radius.get())
        new_tx_power = float(entry_tx_power.get())
        new_path_loss = float(entry_path_loss.get())
        settings.SCAN_RADIUS_METERS = new_scan_radius
        settings.DEFAULT_TX_POWER = new_tx_power
        settings.PATH_LOSS_EXPONENT = new_path_loss
        print("[DEBUG] Updated settings:", new_scan_radius, new_tx_power, new_path_loss)
    except Exception as e:
        print("[ERROR] Invalid settings input:", e)

update_button = tk.Button(settings_frame, text="Update Settings", command=update_settings)
update_button.grid(row=0, column=6, padx=5, pady=2)

def update_device_table():
    """
    Updates the Treeview table with the current devices from controller.devices_info.
    Devices not seen within DEVICE_TIMEOUT seconds are removed.
    """
    current_time = time.time()
    # Clear existing rows
    for row in device_table.get_children():
        device_table.delete(row)
    keys_to_remove = []
    for mac, info in list(controller.devices_info.items()):
        age = current_time - info["last_seen"]
        if age > DEVICE_TIMEOUT:
            keys_to_remove.append(mac)
        else:
            # If device is trusted, display its trusted name; otherwise, show vendor.
            if mac in controller.trusted_devices and controller.trusted_devices[mac]:
                vendor_name = controller.trusted_devices[mac]
            else:
                vendor_name = info["vendor"]
            trusted_status = "Yes" if mac in controller.trusted_devices else "No"
            device_table.insert("", "end", values=(
                info["mac"],
                vendor_name,
                info["signal"],
                f"{age:.1f}",
                trusted_status
            ))
    for mac in keys_to_remove:
        del controller.devices_info[mac]
    # Schedule next table update (every 5 seconds)
    root.after(5000, update_device_table)

def on_device_double_click(event):
    selected_item = device_table.selection()
    if selected_item:
        values = device_table.item(selected_item[0], "values")
        mac = values[0]
        trusted_status = values[4]
        if trusted_status == "No":
            # Create a pop-up window
            popup = tk.Toplevel(root)
            popup.title("Add Trusted Device")
            label = tk.Label(popup, text=f"Enter a name for device {mac}:")
            label.pack(pady=10, padx=10)
            name_entry = tk.Entry(popup)
            name_entry.pack(pady=5, padx=10)
            def add_and_close():
                name = name_entry.get().strip()
                if name:  # Only add if a name was provided
                    controller.add_trusted_device(mac, name)
                    update_device_table()  # Refresh the table to update the trusted status
                popup.destroy()
            add_button = tk.Button(popup, text="Add as Trusted", command=add_and_close)
            add_button.pack(pady=5)
            cancel_button = tk.Button(popup, text="Cancel", command=popup.destroy)
            cancel_button.pack(pady=5)
            
def update_secure_location():
    # Update the global flag in the controller module.
    controller.secure_location_enabled = var_secure_location.get()
    print("[DEBUG] Secure Location Enabled:", controller.secure_location_enabled)
            
# Bind double-click to the table
device_table.bind("<Double-1>", on_device_double_click)

# --- Control Panel for Detection Methods and Program Control ---
control_frame = tk.Frame(root)
control_frame.pack(side="bottom", fill="x", pady=10)

detection_frame = tk.Frame(control_frame)
detection_frame.pack(side="top", fill="x", pady=5)

# Existing detection method checkboxes...
var_frame_diff     = tk.BooleanVar(value=True)
var_background_sub = tk.BooleanVar(value=True)
var_contour        = tk.BooleanVar(value=True)
var_ssim           = tk.BooleanVar(value=True)

cb_frame_diff     = tk.Checkbutton(detection_frame, text="Frame Differencing", variable=var_frame_diff)
cb_background_sub = tk.Checkbutton(detection_frame, text="Background Subtraction", variable=var_background_sub)
cb_contour        = tk.Checkbutton(detection_frame, text="Contour Detection", variable=var_contour)
cb_ssim           = tk.Checkbutton(detection_frame, text="SSIM", variable=var_ssim)
cb_frame_diff.pack(side="left", padx=5)
cb_background_sub.pack(side="left", padx=5)
cb_contour.pack(side="left", padx=5)
cb_ssim.pack(side="left", padx=5)

# --- Add the Secure Location Checkbox (auto-enabled) ---
var_secure_location = tk.BooleanVar(value=True)
secure_checkbox = tk.Checkbutton(control_frame, text="Secure Location", variable=var_secure_location, command=update_secure_location)
secure_checkbox.pack(side="left", padx=5)
# Immediately update the secure location flag on startup
update_secure_location()

button_frame = tk.Frame(control_frame)
button_frame.pack(side="bottom", fill="x", pady=5)
baseline_button = tk.Button(button_frame, text="Capture Baseline", command=capture_baseline)
baseline_button.pack(side="left", padx=10)
close_button = tk.Button(button_frame, text="Close Program", command=close_program)
close_button.pack(side="right", padx=10)

# ================= BACKGROUND THREADS =================
def start_background_threads():
    tcpdump_thread = threading.Thread(target=controller.run_tcpdump, daemon=True)
    webcam_thread = threading.Thread(target=controller.webcam_feed, daemon=True)
    tcpdump_thread.start()
    webcam_thread.start()
    if DEBUG:
        print("[DEBUG] Background threads started.")

start_background_threads()
update_gui()
update_device_table()  # Start updating the device table periodically
print_detection_results()  # Start printing detection results every 3 seconds
root.mainloop()
