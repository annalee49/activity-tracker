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
# !!! UPDATE THIS to the path of your downloaded CSV file !!!
filename = r"C:\Users\wjcol\Downloads\imu_data.csv"

try:
    df = pd.read_csv(filename)
except FileNotFoundError:
    raise FileNotFoundError(f"Error: The file '{filename}' was not found.")
except Exception as e:
    raise Exception(f"Error reading CSV: {e}")


if len(df) == 0:
    raise ValueError("No IMU data found in file.")

print(f"Loaded {len(df)} rows from {filename}")
print(df.head())

# Find large negative jumps in the timestamp, which indicate a rollover
diffs = np.diff(df["timestamp"].astype(np.int64))
rollover_indices = np.where(diffs < -100000)[0]  # Find jumps > 100k ms
print(rollover_indices)
if len(rollover_indices) > 0:
    first_rollover = rollover_indices[0]
    print(f"WARNING: Timestamp rollover detected at index {first_rollover}.")
    print(f"Truncating data to only use the first {first_rollover} samples.")
    df = df.iloc[:first_rollover] # Keep only the data BEFORE the rollover

# ---- 3. Convert raw sensor data to physical units ----
# NOTE: We now use 'ax', 'ay', etc. (from CSV) instead of 'ax_raw', 'ay_raw'
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
fs = 40  # Hz — This should match your ESP32 logInterval (1000ms / 25ms = 40Hz)
# fs = 20
t = (df["timestamp"] - df["timestamp"].iloc[0]) / 1000 # convert ms → s
print(t)

# Plot raw data
plt.figure(figsize=(12, 6))
plt.plot(t, accel_mag, color="steelblue", linewidth=1.0, label="Raw Accelerometer Data")
plt.title("Raw Accelerometer Data", fontsize=14)
plt.xlabel("Time (s)")
plt.ylabel("Accelerometer Magnitude (g)") # Changed unit to 'g'
print(f"Plotting t from 0 to {t.max():.2f} seconds")
plt.xlim(0, t.max() + 1) # Force the x-axis to match t-data
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()


# ---- 6. Filter both signals ----
# Note: Frequencies 0.2Hz to 1.5Hz are very slow, typical for walking/steps
# You may need to adjust these if you are analyzing faster motions.
a_filt = butter_bandpass_filter(df["accel_mag"], 0.2, 1.5, fs)
g_filt = butter_bandpass_filter(df["gyro_mag"], 0.2, 1.5, fs)

# ---- 7. Thresholds for peak detection ----
# These thresholds may need tuning for 40Hz data
# height_threshold = np.percentile(a_filt, 90) # 20Hz threshold
height_threshold = np.percentile(a_filt, 85) # 40Hz threshold
prominence_threshold = height_threshold / 2
distance_threshold = int(1 * fs) # Allow 1 peak per second

# ---- 8. Peak detection: one per oscillation (positive crests only) ----
peaks, props = find_peaks(
    a_filt,
    height=height_threshold,
    prominence=prominence_threshold,
    distance=distance_threshold
)

# Print number of peaks detected
print(f"Detected {len(peaks)} candidate motion peaks")

# ---- 9. Gait Confirmation Filter ----
# Only count peaks that are part of a continuous "walk" (gait).
# This filters out isolated, random peaks.

MIN_CONSECUTIVE_STEPS = 3  # Must take this many steps in a row to count
MAX_STEP_INTERVAL_S = 6  # Max time allowed between 2 steps (in seconds)

final_peaks = [] # This will store the *indices* of confirmed steps

if len(peaks) > 0:
    # Get the times of all candidate peaks
    peak_times = t.iloc[peaks].values
    
    # Calculate time difference between consecutive peaks
    time_diffs = np.diff(peak_times)
    
    # 'current_group' will store the indices of peaks in a potential walk
    current_group = [peaks[0]] 
    
    for i in range(len(time_diffs)):
        # Check if the time gap is small enough to be part of the same walk
        if time_diffs[i] <= MAX_STEP_INTERVAL_S:
            # This step is part of the current group
            current_group.append(peaks[i+1])
        else:
            # This step is too far. The group is broken.
            # Check if the group we *just* finished is valid.
            if len(current_group) >= MIN_CONSECUTIVE_STEPS:
                final_peaks.extend(current_group) # Add them to the final list
            
            # Start a new group with the current peak
            current_group = [peaks[i+1]]
    
    # At the end of the loop, check the very last group
    if len(current_group) >= MIN_CONSECUTIVE_STEPS:
        final_peaks.extend(current_group)

# The step_count is the total number of peaks in all valid groups
step_count = len(final_peaks)
# Note: The original script multiplied by 2. This is likely incorrect.
# find_peaks finds one peak per step. The count should be len(final_peaks).
# I have removed the '*2'.
print(f"✅ Detected {step_count} steps (after gait confirmation)")

# ---- 10. Visualization ----
plt.figure(figsize=(12, 6))
plt.plot(t, a_filt, color="steelblue", linewidth=1.0, label="Filtered Accelerometer Signal")
plt.scatter(t.iloc[final_peaks], a_filt[final_peaks], color='red', s=50, zorder=3, label='Detected Steps')

plt.title("Filtered Accelerometer Data With Steps", fontsize=14)
plt.xlabel("Time (s)")
plt.ylabel("Filtered Accelerometer Magnitude (g)") # Changed unit to 'g'
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()