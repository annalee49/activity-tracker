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

filename = r"C:\CLD Activity Tracker Arduino\Data\11_3_25_Will_walking_ankle_80_steps_20Hz.bin"
data = np.fromfile(filename, dtype=log_dtype)

if len(data) == 0:
    raise ValueError("No IMU data found in file.")

# Convert to DataFrame for convenience
df = pd.DataFrame(data)
print(df.head())

# --- ADD THIS SNIPPET TO FIX ROLLOVER ---
# Find large negative jumps in the timestamp, which indicate a rollover
diffs = np.diff(df["timestamp"].astype(np.int64))
rollover_indices = np.where(diffs < -100000)[0]  # Find jumps > 1ook ms
print(rollover_indices)
if len(rollover_indices) > 0:
    first_rollover = rollover_indices[0]
    print(f"WARNING: Timestamp rollover detected at index {first_rollover}.")
    print(f"Truncating data to only use the first {first_rollover} samples.")
    df = df.iloc[:first_rollover] # Keep only the data BEFORE the rollover
# --- END SNIPPET ---

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
fs = 20 
# fs = 40  
# Hz — adjust to your actual sampling rate
t = (df["timestamp"] - df["timestamp"].iloc[0]) / 1000 # convert ms → s
print(t)

plt.figure(figsize=(12, 6))
plt.plot(t, accel_mag, color="steelblue", linewidth=1.0, label="Raw Accelerometer Data")
plt.title("Raw Accelerometer Data", fontsize=14)
plt.xlabel("Time (s)")
plt.ylabel("Accelerometer Magnitude (m/s^2)")
print(f"Plotting t from 0 to {t.max():.2f} seconds")
plt.xlim(0, t.max() + 1) # Force the x-axis to match your (correct) t-data
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()


# ---- 6. Filter both signals ----
a_filt = butter_bandpass_filter(df["accel_mag"], 0.2, 1.5, fs)
g_filt = butter_bandpass_filter(df["gyro_mag"], 0.2, 1.5, fs)

# ---- 7. Combine into unified "activity index" ----
# activity_index = 0.7 * a_filt + 0.3 * (g_filt / np.max(g_filt)) * np.mean(a_filt)

height_threshold = np.percentile(a_filt, 90)
# height_threshold = np.percentile(a_filt, 85)
prominence_threshold = height_threshold/2
distance_threshold = int(1*fs)
# ---- 8. Peak detection: one per oscillation (positive crests only) ----
# Focus only on the positive lobes (top of each sine)
peaks, props = find_peaks(
    a_filt,
    height= height_threshold,
    prominence=prominence_threshold,  # require noticeable amplitude
    distance= distance_threshold                   # at least ~300 ms apart
)

# Optional: visualize prominence threshold
print(f"Detected {len(peaks)} candidate motion peaks")

# ---- 9. Gait Confirmation Filter (NEW STEP) ----
# Only count peaks that are part of a continuous "walk" (gait).
# This filters out isolated, random peaks.

MIN_CONSECUTIVE_STEPS = 3  # Must take this many steps in a row to count
MAX_STEP_INTERVAL_S = 6  # Max time allowed between steps (in seconds)

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
step_count = len(final_peaks)*2
print(f"✅ Detected {step_count} steps (after gait confirmation)")

# # ---- 9. Group nearby peaks into repetitions ----
# rep_gap = int(fs * 0.6)  # consider any peaks within 0.6 s part of same rep
# rep_indices = []
# if len(peaks) > 0:
#     current = [peaks[0]]
#     for i in range(1, len(peaks)):
#         if peaks[i] - peaks[i-1] <= rep_gap:
#             current.append(peaks[i])
#         else:
#             rep_indices.append(current)
#             current = [peaks[i]]
#     rep_indices.append(current)

# step_count = len(peaks)*2
# print(f"✅ Detected {step_count} steps")
# ---- 10. Visualization ----
plt.figure(figsize=(12, 6))
plt.plot(t, a_filt, color="steelblue", linewidth=1.0, label="Filtered Accelerometer Signal")
plt.scatter(t[final_peaks], a_filt[final_peaks], color='red', s=50, zorder=3, label='Detected Steps')

plt.title("Filtered Accelerometer Data With Steps", fontsize=14)
plt.xlabel("Time (s)")
plt.ylabel("Magnitude of Accelerometer Data (m/s^2)")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()
