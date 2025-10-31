import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks
import matplotlib.pyplot as plt

# ---- 1. Define IMU binary data structure ----
log_dtype = np.dtype([
    ('timestamp', np.uint32),  # 4 bytes
    ('ax_raw', np.int16),      # 2 bytes
    ('ay_raw', np.int16),
    ('az_raw', np.int16),
    ('gx_raw', np.int16),
    ('gy_raw', np.int16),
    ('gz_raw', np.int16),
])

# ---- 2. Load binary IMU file ----
filename = '/Users/annalee/Documents/BME390/testing files/imu_data_10_27_adam_walk.bin'  # your .bin file from ESP32
data = np.fromfile(filename, dtype=log_dtype)

if len(data) == 0:
    raise ValueError("No IMU data found. Make sure imu_data.bin exists and contains binary samples.")

df = pd.DataFrame(data)

# ---- 3. Convert raw values to physical units ----
df['ax_g'] = df['ax_raw'] / 16384.0
df['ay_g'] = df['ay_raw'] / 16384.0
df['az_g'] = df['az_raw'] / 16384.0
df['gx_dps'] = df['gx_raw'] / 131.0
df['gy_dps'] = df['gy_raw'] / 131.0
df['gz_dps'] = df['gz_raw'] / 131.0

# ---- 4. Compute acceleration magnitude ----
accel_mag = np.sqrt(df['ax_g']**2 + df['ay_g']**2 + df['az_g']**2)
df['accel_mag'] = accel_mag

print(df.head())

plt.figure(figsize=(12, 4))
plt.plot(accel_mag - np.mean(accel_mag), color='brown', linewidth=1.0)
plt.xlabel('Sample Index / Time')
plt.ylabel('Acceleration Magnitude (g)')
plt.title('Longitudinal waveform of raw acceleration')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()


# ---- 5. Low-pass filter to smooth acceleration magnitude ----
def butter_lowpass_filter(data, cutoff, fs, order=4):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data)

# Sampling rate (Hz)
fs = 50.0  

# Apply low-pass filter (cutoff ~3 Hz for human motion)
filtered_accel = butter_lowpass_filter(df['accel_mag'], cutoff=3.0, fs=fs)


# ---- 6. Detect bursts of activity ----
# Compute dynamic threshold based on noise level
mean_level = np.mean(filtered_accel)
std_level = np.std(filtered_accel)
threshold = mean_level + 0.3* std_level   # adjust multiplier (1.2–2.0) to tune sensitivity

# Find peaks (bursts)
peaks, _ = find_peaks(filtered_accel, height=threshold, distance=int(fs*1.0))  # ≥1s apart

# Label bursts as contiguous high-activity periods
activity_mask = filtered_accel > threshold

# Identify contiguous regions above threshold
activity_periods = []
start = None
for i in range(len(activity_mask)):
    if activity_mask[i] and start is None:
        start = i
    elif not activity_mask[i] and start is not None:
        if i - start > fs * 0.3:  # at least 0.3 seconds long
            activity_periods.append((start, i))
        start = None
if start is not None:
    activity_periods.append((start, len(activity_mask)))

# ---- 7. Print summary ----
print(f"Detected {len(activity_periods)} bursts of activity")
for i, (s, e) in enumerate(activity_periods, 1):
    print(f"  Burst {i}: samples {s}-{e} ({(e - s)/fs:.2f}s)")

# ---- 8. Plot results ----
t = df['timestamp'].to_numpy() - df['timestamp'].iloc[0]

plt.figure(figsize=(12, 6))
plt.plot(t, filtered_accel, 'k-', linewidth=1.0, label='Filtered Accel Magnitude')
plt.hlines(threshold, t[0], t[-1], colors='blue', linestyles='--', label='Threshold')

# Mark detected bursts
for (s, e) in activity_periods:
    plt.axvspan(t[s], t[e], color='orange', alpha=0.3)
plt.scatter(t[peaks], filtered_accel[peaks], color='red', s=30, zorder=3, label='Detected Peaks')

plt.title("Detected Activity Bursts (Low-Pass Filtered Signal)")
plt.xlabel("Time (ms)")
plt.ylabel("Acceleration Magnitude (g)")
plt.grid(True, linestyle='--', alpha=0.4)
plt.legend()
plt.tight_layout()
plt.show()
