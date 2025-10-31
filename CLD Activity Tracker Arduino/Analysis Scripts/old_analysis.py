import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt
from scipy.ndimage import uniform_filter1d
import os

# ---------------------------------------------
# Bandpass filter
# ---------------------------------------------
def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    if low <= 0 or high >= 1 or low >= high:
        raise ValueError(f"Invalid cutoff frequencies: low={lowcut}, high={highcut}, fs={fs}")
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data)

# ---------------------------------------------
# Zero Crossing Rate
# ---------------------------------------------
def zero_crossing_rate(data, window_size):
    zero_crossings = np.diff(np.sign(data)) != 0
    zcr = np.convolve(zero_crossings, np.ones(window_size), mode='same') / window_size
    return zcr

# ---------------------------------------------
# Parameters
# ---------------------------------------------
lowcut = 0.3  # Hz, adjust as needed
highcut = 8.0 # Hz
fs = 50.0     # Sampling rate, adjust to match your data
window_size = 200  # for ZCR
amplitude_percentile = 95
zcr_percentile = 40
clipping_limits = (-2, 2)
min_gap_samples = 100

# ---------------------------------------------
# Load CSV data (exported from your binary IMU file)
# ---------------------------------------------
filename_csv = '/Users/annalee/Documents/BME390/testing files/imu_data_10_27_arm_raise.csv'
df = pd.read_csv(filename_csv)

# Compute acceleration magnitude
accel_mag = np.sqrt(df["ax_g"]**2 + df["ay_g"]**2 + df["az_g"]**2)

# Apply bandpass filter
filtered = butter_bandpass_filter(accel_mag, lowcut, highcut, fs)

# Clip filtered data
clipped = np.clip(filtered, clipping_limits[0], clipping_limits[1])

# Compute ZCR
zcr = zero_crossing_rate(clipped, window_size)

# Thresholds
amp_thresh = np.percentile(accel_mag, amplitude_percentile)

high_amp = accel_mag > amp_thresh

# Define ZCR threshold
zcr_threshold = np.percentile(zcr, 40)
zcr_activity = zcr > zcr_threshold

# Make sure both arrays are the same length before combining
min_len = min(len(high_amp), len(zcr_activity))
combined_activity = high_amp[:min_len] & zcr_activity[:min_len]

# Identify activity periods
activity_periods = []
start = None
for i in range(1, len(combined_activity)):
    if combined_activity[i] and not combined_activity[i-1]:
        start = i
    elif not combined_activity[i] and combined_activity[i-1]:
        if start is not None:
            activity_periods.append((start, i))
            start = None
if start is not None:
    activity_periods.append((start, len(combined_activity)-1))

# Merge close activity periods
merged_periods = []
if activity_periods:
    prev_start, prev_end = activity_periods[0]
    for start, end in activity_periods[1:]:
        if start - prev_end <= min_gap_samples:
            prev_end = end
        else:
            merged_periods.append((prev_start, prev_end))
            prev_start, prev_end = start, end
    merged_periods.append((prev_start, prev_end))

# Identify inactivity periods
inactivity_periods = []
if merged_periods:
    if merged_periods[0][0] > 0:
        inactivity_periods.append((0, merged_periods[0][0]))
    for i in range(1, len(merged_periods)):
        inactivity_periods.append((merged_periods[i-1][1], merged_periods[i][0]))
    if merged_periods[-1][1] < len(combined_activity):
        inactivity_periods.append((merged_periods[-1][1], len(combined_activity)-1))

# ---------------------------------------------
# Print results
# ---------------------------------------------
total_exercise_time = 0
print("\nActivity Times:")
for start, end in merged_periods:
    duration = df['timestamp'].iloc[end] - df['timestamp'].iloc[start]
    print(f"Start: {df['timestamp'].iloc[start]} ms, End: {df['timestamp'].iloc[end]} ms, Duration: {duration} ms")
    total_exercise_time += duration
print(f"Total exercise time: {total_exercise_time} ms")

# ---------------------------------------------
# Plot results
# ---------------------------------------------
plt.figure(figsize=(12, 6))
plt.plot(clipped, label='Clipped Filtered Signal', alpha=0.7)
for start, end in merged_periods:
    plt.axvspan(start, end, color='green', alpha=0.3, label='Activity')
for start, end in inactivity_periods:
    plt.axvspan(start, end, color='red', alpha=0.1, label='Inactivity')
plt.xlabel('Sample Index')
plt.ylabel('Amplitude')
plt.title('Activity and Inactivity Periods')
plt.legend(loc='upper right')
plt.tight_layout()
plt.show()

from scipy.signal import find_peaks

# -------------------------------
# Create DataFrame for processed signal
# -------------------------------
processed_df = pd.DataFrame({
    'time': df['time'].iloc[:len(clipped_data)],
    'clipped_filtered_accel': clipped_data
})

# -------------------------------
# Detect peaks in the processed signal
# -------------------------------
# You can adjust parameters like 'distance' or 'prominence' to suit your data
peak_indices, properties = find_peaks(clipped_data, prominence=0.5, distance=int(0.5 * fs))

print(f"Number of peaks detected: {len(peak_indices)}")

# Add peak information to DataFrame
processed_df['is_peak'] = 0
processed_df.loc[peak_indices, 'is_peak'] = 1

# Optional: save the processed dataset with peaks
processed_df.to_csv('processed_signal_with_peaks.csv', index=False)
print("Processed signal with peaks saved to 'processed_signal_with_peaks.csv'.")

# -------------------------------
# Optional: quick plot
# -------------------------------
plt.figure(figsize=(12, 4))
plt.plot(processed_df['time'], processed_df['clipped_filtered_accel'], label='Clipped Filtered Signal')
plt.scatter(processed_df['time'].iloc[peak_indices], processed_df['clipped_filtered_accel'].iloc[peak_indices],
            color='red', label='Peaks')
plt.xlabel('Time')
plt.ylabel('Amplitude')
plt.title('Processed Signal with Peaks')
plt.legend()
plt.tight_layout()
plt.show()
