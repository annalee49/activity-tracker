import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks, hilbert
from scipy.ndimage import uniform_filter1d
import matplotlib.pyplot as plt

# ---------------------------------------------
# Bandpass filter helper
# ---------------------------------------------
def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low, high = lowcut / nyq, highcut / nyq
    if low <= 0 or high >= 1 or low >= high:
        raise ValueError(f"Invalid cutoff frequencies: low={lowcut}, high={highcut}, fs={fs}")
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data)

# -------------------------------
# Input / Output
# -------------------------------
filename_bin = '/Users/annalee/Documents/BME390/testing files/imu_data_10_27_adam_walk.bin'
filename_csv = '/Users/annalee/Documents/BME390/testing files/imu_data_10_27_adam_walk.csv'

# -------------------------------
# Define binary structure
# -------------------------------
log_dtype = np.dtype([
    ('timestamp', np.uint32),
    ('ax_raw', np.int16),
    ('ay_raw', np.int16),
    ('az_raw', np.int16),
    ('gx_raw', np.int16),
    ('gy_raw', np.int16),
    ('gz_raw', np.int16),
])

# -------------------------------
# Read binary file
# -------------------------------
data = np.fromfile(filename_bin, dtype=log_dtype)
if len(data) == 0:
    raise ValueError("No IMU data found in file.")

df = pd.DataFrame(data)

# -------------------------------
# Convert raw values to physical units
# -------------------------------
df["ax_g"] = df["ax_raw"] / 16384.0
df["ay_g"] = df["ay_raw"] / 16384.0
df["az_g"] = df["az_raw"] / 16384.0

df["gx_dps"] = df["gx_raw"] / 131.0
df["gy_dps"] = df["gy_raw"] / 131.0
df["gz_dps"] = df["gz_raw"] / 131.0

# -------------------------------
# Compute vector magnitudes
# -------------------------------
df["accel_mag"] = np.sqrt(df["ax_g"]**2 + df["ay_g"]**2 + df["az_g"]**2)
df["gyro_mag"]  = np.sqrt(df["gx_dps"]**2 + df["gy_dps"]**2 + df["gz_dps"]**2)

# ---------------------------------------------
# Time base
# ---------------------------------------------
fs = 50  # Hz (replace with actual sample rate)
t = (df["timestamp"] - df["timestamp"].iloc[0]) / 1000.0  # convert ms → s

# ---------------------------------------------
# Bandpass filter both accel and gyro
# ---------------------------------------------
lowcut, highcut = 0.3, 8.0  # motion-relevant band
a_filt = butter_bandpass_filter(df["accel_mag"], lowcut, highcut, fs)
g_filt = butter_bandpass_filter(df["gyro_mag"], lowcut, highcut, fs)

# ---------------------------------------------
# Combine signals into a unified "activity index"
# ---------------------------------------------
a_norm = a_filt / np.max(np.abs(a_filt))
g_norm = g_filt / np.max(np.abs(g_filt))
activity_index = 0.9 * a_norm + 0.1 * g_norm

# ---------------------------------------------
# Detect peaks in activity index
# ---------------------------------------------
sig = activity_index.astype(float)
sig_zero = sig - np.mean(sig)

# Smooth signal to reduce noise
sig_smooth = uniform_filter1d(sig_zero, size=5)

# Hilbert envelope
analytic = hilbert(sig_smooth)
envelope = np.abs(analytic)
env_med, env_std = np.median(envelope), np.std(envelope)

# Adaptive peak detection
prom_mult = 0.1
height_mult = 0.2
min_distance_samples = int(0.5 * fs)  # minimum samples between peaks
peaks = []

for attempt in range(6):
    prominence = env_std * prom_mult
    height = env_med + env_std * height_mult
    peaks_candidate, props = find_peaks(sig_smooth, prominence=prominence, height=height, distance=min_distance_samples)
    if len(peaks_candidate) >= 3 and len(peaks_candidate) < len(sig) / 2:
        peaks = peaks_candidate
        used_prom, used_height = prominence, height
        break
    prom_mult *= 0.1
    height_mult *= 0.2
    peaks, used_prom, used_height = peaks_candidate, prominence, height

print(f"Detected peaks: {len(peaks)} (prom={used_prom:.4f}, height={used_height:.4f})")

# Peak times and values
peak_times = t[peaks]
peak_values = sig[peaks]
print("Peak times (s):", peak_times)
print("Peak values:", peak_values)

# ---------------------------------------------
# Plot activity index with detected peaks
# ---------------------------------------------
plt.figure(figsize=(12, 4))
plt.plot(t, sig, color='tab:blue', lw=1.1, label='Activity Index')
plt.plot(t, envelope, color='orange', lw=0.8, alpha=0.8, label='Hilbert Envelope')
plt.scatter(peak_times, peak_values, color='red', s=60, zorder=4, label='Detected Peaks')
plt.title(f"Detected Peaks: {len(peaks)}")
plt.xlabel('Time (s)')
plt.ylabel('Activity Index')
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()
