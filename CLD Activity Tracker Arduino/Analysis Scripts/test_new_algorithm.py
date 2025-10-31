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

# ---- 2. Load IMU binary data ----
log_dtype = np.dtype([
    ('timestamp', np.uint32),
    ('ax_raw', np.int16),
    ('ay_raw', np.int16),
    ('az_raw', np.int16),
    ('gx_raw', np.int16),
    ('gy_raw', np.int16),
    ('gz_raw', np.int16),
])

filename = '/Users/annalee/Documents/BME390/testing files/imu_data_10_27_adam_walk.bin'
data = np.fromfile(filename, dtype=log_dtype)

if len(data) == 0:
    raise ValueError("No IMU data found in file.")

# Convert to DataFrame for convenience
df = pd.DataFrame(data)
print(df.head())

# ---- 3. Convert raw sensor data to physical units ----
df["ax_g"] = df["ax_raw"] / 16384.0
df["ay_g"] = df["ay_raw"] / 16384.0
df["az_g"] = df["az_raw"] / 16384.0

df["gx_dps"] = df["gx_raw"] / 131.0
df["gy_dps"] = df["gy_raw"] / 131.0
df["gz_dps"] = df["gz_raw"] / 131.0

# ---- 4. Compute magnitudes ----
df["accel_mag"] = np.sqrt(df["ax_g"]**2 + df["ay_g"]**2 + df["az_g"]**2)
df["gyro_mag"]  = np.sqrt(df["gx_dps"]**2 + df["gy_dps"]**2 + df["gz_dps"]**2)
accel_mag = df["accel_mag"]

# ---- 5. Prepare time base ----
fs = 50  # Hz — adjust to your actual sampling rate
t = (df["timestamp"] - df["timestamp"].iloc[0]) / 1000.0  # convert ms → s

plt.figure(figsize=(12, 6))
plt.plot(t, accel_mag, color="steelblue", linewidth=1.0, label="Raw Accelerometer Data")
plt.title("Raw Accelerometer Data", fontsize=14)
plt.xlabel("Time (s)")
plt.ylabel("Accelerometer Magnitude")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()


# ---- 6. Filter both signals ----
a_filt = butter_bandpass_filter(df["accel_mag"], 0.3, 5.0, fs)
g_filt = butter_bandpass_filter(df["gyro_mag"], 0.3, 5.0, fs)

# ---- 7. Combine into unified "activity index" ----
activity_index = 0.7 * a_filt + 0.3 * (g_filt / np.max(g_filt)) * np.mean(a_filt)

# ---- 8. Peak detection: one per oscillation (positive crests only) ----
# Focus only on the positive lobes (top of each sine)
peaks, props = find_peaks(
    activity_index,
    prominence=np.std(activity_index) * 0.8,  # require noticeable amplitude
    distance=int(fs * 0.3)                    # at least ~300 ms apart
)

# Optional: visualize prominence threshold
print(f"Detected {len(peaks)} candidate motion peaks")

# ---- 9. Group nearby peaks into repetitions ----
rep_gap = int(fs * 0.6)  # consider any peaks within 0.6 s part of same rep
rep_indices = []
if len(peaks) > 0:
    current = [peaks[0]]
    for i in range(1, len(peaks)):
        if peaks[i] - peaks[i-1] <= rep_gap:
            current.append(peaks[i])
        else:
            rep_indices.append(current)
            current = [peaks[i]]
    rep_indices.append(current)

rep_count = len(rep_indices)
print(f"✅ Detected {rep_count} repetitions")

# ---- 10. Visualization ----
plt.figure(figsize=(12, 6))
plt.plot(t, activity_index, color="steelblue", linewidth=1.0, label="Activity Index (Accel+Gyro)")
#plt.scatter(t[peaks], activity_index[peaks], color='red', s=50, zorder=3, label='Detected Peaks')

plt.title("Detected Repetitions from Activity Index Peaks", fontsize=14)
plt.xlabel("Time (s)")
plt.ylabel("Activity Index (a.u.)")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()
