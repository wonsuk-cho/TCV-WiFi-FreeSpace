# model.py
"""
Model module for the IoT Project.
Contains functions for image processing and empty space detection.
"""

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from settings import DEFAULT_TX_POWER, PATH_LOSS_EXPONENT, DEBUG

def rssi_to_distance(rssi, tx_power=DEFAULT_TX_POWER, path_loss_exponent=PATH_LOSS_EXPONENT):
    """
    Estimate distance (in meters) based on RSSI using the log-distance path loss model.
    """
    distance = 10 ** ((tx_power - rssi) / (10 * path_loss_exponent))
    if DEBUG:
        print(f"[DEBUG] rssi_to_distance() -> rssi: {rssi}, tx_power: {tx_power}, "
              f"exponent: {path_loss_exponent}, estimated distance: {distance:.2f}m")
    return distance

def calculate_difference(baseline, current, threshold_value=50):
    """
    Calculate the difference between the baseline image and the current frame using SSIM.
    Returns:
        diff_percent (float): Percentage difference.
        binary_diff (np.ndarray): Binary image after thresholding.
        ssim_diff (np.ndarray): Scaled diff image from SSIM computation.
    """
    # Convert images to grayscale
    baseline_gray = cv2.cvtColor(baseline, cv2.COLOR_BGR2GRAY)
    current_gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    
    # Compute SSIM and diff image
    score, diff = ssim(baseline_gray, current_gray, full=True)
    ssim_diff = (diff * 255).astype("uint8")
    
    # Apply thresholding
    _, binary_diff = cv2.threshold(ssim_diff, threshold_value, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    
    changed_pixels = cv2.countNonZero(binary_diff)
    total_pixels = binary_diff.shape[0] * binary_diff.shape[1]
    diff_percent = (changed_pixels / total_pixels) * 100

    if DEBUG:
        print(f"[DEBUG] SSIM Score: {score:.4f}")
        print(f"[DEBUG] Changed Pixels: {changed_pixels}, Total Pixels: {total_pixels}")
        print(f"[DEBUG] Difference Percentage: {diff_percent:.2f}%")
    
    return diff_percent, binary_diff, ssim_diff

if __name__ == '__main__':
    pass
