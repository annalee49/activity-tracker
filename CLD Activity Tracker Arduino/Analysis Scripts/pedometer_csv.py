import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks
import matplotlib.pyplot as plt

# ---- 1. Filtering function ----
def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low, high = lowcut / nyq, highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data)

# ---- 2. Load IMU CSV data ----
filename_csv = '/Users/annalee/Documents/BME390/testing files/test_bluetooth_11_18.csv'
df = pd.read_csv(filename_csv)

print(df.head())

# ---- 3. Convert raw sensor data to physical units ----
df["ax_g"] = df["ax"] / 16384.0
df["ay_g"] = df["ay"] / 16384.0
df["az_g"] = df["az"] / 16384.0

df["gx_dps"] = df["gx"] / 131.0
df["gy_dps"] = df["gy"] / 131.0
df["gz_dps"] = df["gz"] / 131.0

# ---- 4. Compute magnitudes ----
df["accel_mag"] = np.sqrt(df["ax_g"]**2 + df["ay_g"]**2 + df["az_g"]**2)
df["gyro_mag"]  = np.sqrt(df["gx_dps"]**2 + df["gy_dps"]**2 + df["gz_dps"]**2)
accel_mag = df["accel_mag"]

# ---- 5. Prepare time base ----
fs = 40  # Hz — adjust to your actual sampling rate
t = (df["timestamp"] - df["timestamp"].iloc[0]) / 1000  # convert ms → s
print(t)

plt.figure(figsize=(12, 6))
plt.plot(t, accel_mag, color="steelblue", linewidth=1.0, label="Raw Accelerometer Data")
plt.title("Raw Accelerometer Data", fontsize=14)
plt.xlabel("Time (s)")
plt.ylabel("Accelerometer Magnitude (g)")
plt.xlim(0, t.max() + 1)
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()

# ---- 6. Filter both signals ----
a_filt = butter_bandpass_filter(df["accel_mag"], 0.2, 1.5, fs)
g_filt = butter_bandpass_filter(df["gyro_mag"], 0.2, 1.5, fs)

# ---- 7. Combine into unified "activity index" ----
activity_index = 0.7 * a_filt + 0.3 * (g_filt / np.max(g_filt)) * np.mean(a_filt)

height_threshold = np.percentile(a_filt, 85)
prominence_threshold = height_threshold / 2
distance_threshold = int(1 * fs)

# ---- 8. Peak detection: one per oscillation (positive crests only) ----
peaks, props = find_peaks(
    a_filt,
    height=height_threshold,
    prominence=prominence_threshold,
    distance=distance_threshold
)

print(f"Detected {len(peaks)} candidate motion peaks")

# ---- 9. Gait Confirmation Filter ----
MIN_CONSECUTIVE_STEPS = 3
MAX_STEP_INTERVAL_S = 6

final_peaks = []

if len(peaks) > 0:
    peak_times = t.iloc[peaks].values
    time_diffs = np.diff(peak_times)
    current_group = [peaks[0]]
    
    for i in range(len(time_diffs)):
        if time_diffs[i] <= MAX_STEP_INTERVAL_S:
            current_group.append(peaks[i+1])
        else:
            if len(current_group) >= MIN_CONSECUTIVE_STEPS:
                final_peaks.extend(current_group)
            current_group = [peaks[i+1]]
    
    if len(current_group) >= MIN_CONSECUTIVE_STEPS:
        final_peaks.extend(current_group)

step_count = len(final_peaks) * 2
print(f"✅ Detected {step_count} steps (after gait confirmation)")

# ---- 10. Visualization ----
plt.figure(figsize=(12, 6))
plt.plot(t, a_filt, color="steelblue", linewidth=1.0, label="Activity Index (Accel+Gyro)")
plt.scatter(t[final_peaks], activity_index[final_peaks], color='red', s=50, zorder=3, label='Detected Peaks')

plt.title("Filtered Accelerometer Data With Steps", fontsize=14)
plt.xlabel("Time (s)")
plt.ylabel("Magnitude of Accelerometer Data (g)")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()
