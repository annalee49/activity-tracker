import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, find_peaks, hilbert

# -------------------------------
# Bandpass filter function
# -------------------------------
def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    if not 0 < low < 1 or not 0 < high < 1:
        raise ValueError(f"Invalid cutoff frequencies: low={low}, high={high}, fs={fs}")
    b, a = butter(order, [low, high], btype='band')
    y = filtfilt(b, a, data)
    return y
# -------------------------------
# Load CSV
# -------------------------------
filename_csv = '/Users/annalee/Documents/BME390/testing files/imu_data_10_27_arm_raise.csv'
df = pd.read_csv(filename_csv)

# Sampling rate (Hz) -- approximate from timestamps
fs = 1000 / np.median(np.diff(df['timestamp']))  # timestamps in ms

# -------------------------------
# Optional filtering
# -------------------------------
# Set low/high cutoffs in Hz (adjust as needed)
lowcut = 0.1
highcut = 1.5

accel_filtered = butter_bandpass_filter(df['accel_mag'], lowcut, highcut, fs)
gyro_filtered = butter_bandpass_filter(df['gyro_mag'], lowcut, highcut, fs)

# -------------------------------
# Optional Hilbert envelope
# -------------------------------
accel_envelope = np.abs(hilbert(accel_filtered))
gyro_envelope = np.abs(hilbert(gyro_filtered))

# -------------------------------
# Peak detection
# -------------------------------
# Adjust these to detect more/fewer peaks
accel_peaks, _ = find_peaks(accel_envelope, height=0.8, distance=20)
gyro_peaks, _  = find_peaks(gyro_envelope, height=20, distance=20)

# -------------------------------
# Plot results
# -------------------------------
plt.figure(figsize=(12,5))
plt.plot(df['timestamp'], df['accel_mag'], label='Accel Mag Raw', alpha=0.5)
plt.plot(df['timestamp'], accel_filtered, label='Accel Mag Filtered')
plt.plot(df['timestamp'], accel_envelope, label='Accel Envelope', linestyle='--')
plt.plot(df['timestamp'][accel_peaks], accel_envelope[accel_peaks], 'rx', label='Accel Peaks')
plt.xlabel('Timestamp (ms)')
plt.ylabel('Accel Magnitude')
plt.title('Acceleration Magnitude and Peaks')
plt.legend()
plt.show()

plt.figure(figsize=(12,5))
plt.plot(df['timestamp'], df['gyro_mag'], label='Gyro Mag Raw', alpha=0.5)
plt.plot(df['timestamp'], gyro_filtered, label='Gyro Mag Filtered')
plt.plot(df['timestamp'], gyro_envelope, label='Gyro Envelope', linestyle='--')
plt.plot(df['timestamp'][gyro_peaks], gyro_envelope[gyro_peaks], 'rx', label='Gyro Peaks')
plt.xlabel('Timestamp (ms)')
plt.ylabel('Gyro Magnitude')
plt.title('Gyroscope Magnitude and Peaks')
plt.legend()
plt.show()

# -------------------------------
# Print peak counts
# -------------------------------
print(f"Accel peaks detected: {len(accel_peaks)}")
print(f"Gyro peaks detected: {len(gyro_peaks)}")
