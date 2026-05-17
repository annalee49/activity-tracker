import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks
import matplotlib.pyplot as plt

def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low, high = lowcut / nyq, highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data)

# ---- Load and Segment Data ----
filename = "C:\CLD Activity Tracker Arduino\Clinical Trial Data\Patient 15\pt15ankle_data.csv"
df = pd.read_csv(filename)

# UPDATE THESE: Define your exercise window
START_S = 40202.526
END_S = 40382.958
df = df[(df['Time(s)'] >= START_S) & (df['Time(s)'] <= END_S)].copy()

if len(df) < 10:
    print("Warning: Segment too short for filtering.")

# ---- Processing ----
fs = 40  # 40Hz
df["ax_g"] = df["ax"] / 16384.0
df["ay_g"] = df["ay"] / 16384.0
df["az_g"] = df["az"] / 16384.0
df["accel_mag"] = np.sqrt(df["ax_g"]**2 + df["ay_g"]**2 + df["az_g"]**2)

# Normalizing time to start at 0 for the segment
t = df["Time(s)"] - df["Time(s)"].iloc[0]

# ---- Filtering & Peak Detection ----
a_filt = butter_bandpass_filter(df["accel_mag"], 0.2, 1.5, fs)
height_threshold = np.percentile(a_filt, 85)
distance_threshold = int(0.8 * fs)
prominence_threshold = height_threshold / 2
peaks, _ = find_peaks(a_filt, 
                      height=height_threshold, 
                      prominence = prominence_threshold, 
                      distance=distance_threshold)

# ---- Gait Confirmation ----
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

step_count = len(final_peaks)*2
print(f"✅ Detected {step_count} steps (after gait confirmation)")

# ---- Visualization ----
plt.plot(t, a_filt, label="Filtered Signal")
plt.scatter(t.iloc[final_peaks], a_filt[final_peaks], color='red', label="Steps")
plt.title("Filtered Accelerometer Data")
plt.xlabel("Time (s)")
plt.ylabel("Accelerometer Magnitude")
plt.legend()
plt.show()