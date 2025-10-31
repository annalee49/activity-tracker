import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks
import matplotlib.pyplot as plt

# ---- 1. Define IMU binary data structure ----
log_dtype = np.dtype([
    ('timestamp', np.uint32),  # 4 bytes
    ('ax_raw', np.int16),
    ('ay_raw', np.int16),
    ('az_raw', np.int16),
    ('gx_raw', np.int16),
    ('gy_raw', np.int16),
    ('gz_raw', np.int16),
])

# ---- 2. Load binary IMU file ----
filename = '/Users/annalee/Documents/BME390/testing files/imu_data_10_27_arm_raise.bin'
data = np.fromfile(filename, dtype=log_dtype)

if len(data) == 0:
    raise ValueError("No IMU data found. Make sure the .bin file exists and contains samples.")

df = pd.DataFrame(data)

# ---- 3. Convert raw values to physical units ----
df['ax_g'] = df['ax_raw'] / 16384.0
df['ay_g'] = df['ay_raw'] / 16384.0
df['az_g'] = df['az_raw'] / 16384.0
df['gx_dps'] = df['gx_raw'] / 131.0
df['gy_dps'] = df['gy_raw'] / 131.0
df['gz_dps'] = df['gz_raw'] / 131.0

# ---- 4. Compute magnitudes ----
df['accel_mag'] = np.sqrt(df['ax_g']**2 + df['ay_g']**2 + df['az_g']**2)
df['gyro_mag'] = np.sqrt(df['gx_dps']**2 + df['gy_dps']**2 + df['gz_dps']**2)
accel_mag = df['accel_mag']

plt.figure(figsize=(12, 4))
plt.plot(accel_mag - np.mean(accel_mag), color='brown', linewidth=1.0)
plt.xlabel('Sample Index / Time')
plt.ylabel('Acceleration Magnitude (g)')
plt.title('Longitudinal waveform of raw acceleration')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

from scipy.signal import find_peaks
import numpy as np
import matplotlib.pyplot as plt

# ---- Parameters ----
signal = df['accel_mag'].to_numpy()
multiplier = 0.33           # threshold multiplier for peak amplitude (adjust 0.8–1.5)
min_peak_distance = 5       # minimum distance between distinct peaks (samples)
burst_gap = 25              # max spacing (samples) between peaks to count as one burst

# ---- Step 1. Detect all peaks ----
mean_val = np.mean(signal)
std_val = np.std(signal)
amp_threshold = mean_val + (1 + multiplier) * std_val

peaks, properties = find_peaks(signal, height=amp_threshold, distance=min_peak_distance)

# ---- Step 2. Group nearby peaks into bursts ----
burst_indices = []   # list of (start_idx, end_idx)
current_burst = [peaks[0]] if len(peaks) > 0 else []

for i in range(1, len(peaks)):
    if peaks[i] - peaks[i - 1] <= burst_gap:
        current_burst.append(peaks[i])
    else:
        burst_indices.append(current_burst)
        current_burst = [peaks[i]]
if current_burst:
    burst_indices.append(current_burst)

# ---- Step 3. Classify bursts vs single peaks ----
burst_list = [b for b in burst_indices if len(b) > 1]
single_peaks = [b[0] for b in burst_indices if len(b) == 1]

print(f"Detected {len(peaks)} peaks total.")
print(f"→ {len(burst_list)} bursts (clusters of peaks)")
print(f"→ {len(single_peaks)} isolated peaks")
print(f"Amplitude threshold = {amp_threshold:.3f}")

# ---- Step 4. Plot results ----
plt.figure(figsize=(12, 4))
plt.plot(signal, color='brown', linewidth=1.0, label='Raw Acceleration')

# Plot single peaks (red) and bursts (green clusters)
plt.scatter(single_peaks, signal[single_peaks], color='red', s=50, label='Single Peaks')
for burst in burst_list:
    plt.scatter(burst, signal[burst], color='green', s=40, label='Burst Peaks' if burst == burst_list[0] else "")

plt.hlines(amp_threshold, 0, len(signal), color='blue', linestyle='--', alpha=0.5, label='Amplitude Threshold')
plt.title('Burst vs Single Peak Detection in Raw Acceleration')
plt.xlabel('Sample Index / Time')
plt.ylabel('Acceleration Magnitude (g)')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.3)
plt.tight_layout()
plt.show()


# ---- 5. Low-pass filter to smooth signals ----
def butter_lowpass_filter(data, cutoff, fs, order=4):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data)

fs = 50.0  # sampling frequency (Hz)
filtered_accel = butter_lowpass_filter(df['accel_mag'], cutoff=3.0, fs=fs)
filtered_gyro = butter_lowpass_filter(df['gyro_mag'], cutoff=3.0, fs=fs)

# ---- 6. Normalize and combine accel + gyro signals ----
gyro_scaled = (filtered_gyro / np.max(filtered_gyro)) * np.mean(filtered_accel)
activity_index = 0.7 * filtered_accel + 0.3 * gyro_scaled

# ---- 7. Detect activity bursts ----
mean_ai = np.mean(activity_index)
std_ai = np.std(activity_index)
threshold_ai = mean_ai + 1.5 * std_ai  # adjust multiplier if needed

# Find peaks representing strong activity bursts
peaks, _ = find_peaks(activity_index, height=threshold_ai, distance=int(fs * 1.0))

# Binary mask for activity above threshold
activity_mask = activity_index > threshold_ai

# Identify contiguous high-activity regions
activity_periods = []
start = None
for i in range(len(activity_mask)):
    if activity_mask[i] and start is None:
        start = i
    elif not activity_mask[i] and start is not None:
        if i - start > fs * 0.3:  # must last at least 0.3 s
            activity_periods.append((start, i))
        start = None
if start is not None:
    activity_periods.append((start, len(activity_mask)))

# ---- 8. Summary ----
print(f"Detected {len(activity_periods)} activity bursts (combined accel + gyro):")
for i, (s, e) in enumerate(activity_periods, 1):
    print(f"  Burst {i}: samples {s}-{e}, duration {(e - s)/fs:.2f} s")

# ---- 9. Cluster-style filtered signal visualization ----
t = df['timestamp'].to_numpy() - df['timestamp'].iloc[0]

plt.figure(figsize=(12, 5))

# Plot the filtered combined activity signal (no raw lines or threshold)
plt.plot(t, activity_index, color='steelblue', linewidth=1.2, label='Filtered Activity Signal')

plt.title("Filtered Activity Signal (Clusters of Motion)", fontsize=14)
plt.xlabel("Time (ms)")
plt.ylabel("Amplitude (normalized)")
plt.grid(True, linestyle='--', alpha=0.3)
plt.legend()
plt.tight_layout()
plt.show()
