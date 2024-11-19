import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.signal import butter, filtfilt
import os

def butter_bandpass_filter(data, lowcut, highcut, fs):
    nyquist = 0.5 * fs  # Nyquist frequency
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(4, [low, high], btype='band')
    y = filtfilt(b, a, data)
    return y

def zero_crossing_rate(data, window_size):
    zero_crossings = np.diff(np.sign(data)) != 0
    zcr = np.convolve(zero_crossings, np.ones(window_size), mode='same') / window_size
    return zcr

# Parameters for the bandpass filter
lowcut = 0.01  # Hz
highcut = 4  # Hz

# Read and clean the data
df = pd.read_csv('acceleration_data_time_2.txt', delimiter=',', header=None, names=['time', 'x', 'y', 'z'])

# Separate timestamps and acceleration data
timestamps = df['time'].values  # Assuming 'time' is the correct column name for timestamps
accel_data = df[['x', 'y', 'z']].values  # Assuming 'x', 'y', 'z' are the column names for acceleration data

# Calculate L2 norm
norm = np.linalg.norm(accel_data, axis=1)

# Plot the original norm
plt.figure()
plt.plot(timestamps, norm)
plt.xlabel('Time (s)')
plt.ylabel('L2 Norm')
plt.title('L2 Norm of Signal')

# Apply bandpass filter
# Assuming a sampling rate of 40 Hz for filtering purposes (adjust as needed based on your data characteristics)
filtered_data = butter_bandpass_filter(norm, lowcut, highcut, 40.0)

# Plot filtered data against timestamps
plt.figure()
plt.plot(timestamps, filtered_data)
plt.xlabel('Time (s)')
plt.ylabel('L2 Norm')
plt.title('L2 Norm of Filtered Signal')

# Set amplitude threshold (e.g., 90th percentile)
amplitude_threshold = np.percentile(norm, 95)
high_amplitude_regions = norm > amplitude_threshold

# Apply clipping
clipping_plus = 2
clipping_minus = -2
clipped_data = np.clip(filtered_data, clipping_minus, clipping_plus)

# Calculate ZCR with a sliding window
window_size = 200
zcr = zero_crossing_rate(clipped_data, window_size)

# Define ZCR threshold for activity detection
zcr_threshold = np.percentile(zcr, 40)
zcr_activity = zcr > zcr_threshold
# Ensure both arrays are of the same length
min_length = min(len(zcr_activity), len(high_amplitude_regions))
zcr_activity = zcr_activity[:min_length]
high_amplitude_regions = high_amplitude_regions[:min_length]

# Combine conditions: activity if both ZCR and amplitude thresholds are met
combined_activity = zcr_activity & high_amplitude_regions

# Identify activity periods
activity_periods = []
start = None
for i in range(1, len(combined_activity)):
    if combined_activity[i] and not combined_activity[i - 1]:  # Start of activity
        start = i
    elif not combined_activity[i] and combined_activity[i - 1]:  # End of activity
        if start is not None:
            end = i
            activity_periods.append((start, end))
            start = None

# Handle edge cases
if start is not None:
    activity_periods.append((start, len(combined_activity) - 1))


# Merge close activity periods directly within activity_periods list
min_gap = 100
merged_activity_periods = []  # Temporary list for merged periods

# Initialize with the first activity period
prev_start, prev_end = activity_periods[0]

for start, end in activity_periods[1:]:
    # Check if the gap between the current start and previous end is less than or equal to min_gap
    if start - prev_end <= min_gap:
        # Extend the previous end to the current end
        prev_end = end
    else:
        # Add the merged period to the list and update prev_start and prev_end
        merged_activity_periods.append((prev_start, prev_end))
        prev_start, prev_end = start, end

# Add the last merged period
merged_activity_periods.append((prev_start, prev_end))

# Update activity_periods to reflect the merged periods
activity_periods = merged_activity_periods

# Identify inactivity periods based on the merged activity periods
inactivity_periods = []
if activity_periods[0][0] > 0:
    inactivity_periods.append((0, activity_periods[0][0]))
for i in range(1, len(activity_periods)):
    inactivity_periods.append((activity_periods[i - 1][1], activity_periods[i][0]))
if activity_periods[-1][1] < len(combined_activity):
    inactivity_periods.append((activity_periods[-1][1], len(combined_activity) - 1))

# Calculate total exercise time based on timestamps
total_exercise_time = 0  # In seconds
for start, end in activity_periods:
    duration_seconds = df['time'].iloc[end] - df['time'].iloc[start]
    print(f"Activity Period - Start: {df['time'].iloc[start]:.2f} s, End: {df['time'].iloc[end]:.2f} s, Duration (s): {duration_seconds:.2f}")
    total_exercise_time += duration_seconds

print(f"Total exercise time: {total_exercise_time:.2f} seconds")

# Plotting
plt.figure(figsize=(12, 6))
plt.plot(clipped_data, label='Clipped Data', alpha=0.7)
for (start, end) in activity_periods:
    plt.axvspan(start, end, color='green', alpha=0.3, label='Activity')
for (start, end) in inactivity_periods:
    plt.axvspan(start, end, color='red', alpha=0.1, label='Inactivity')
plt.xlabel('Time')
plt.ylabel('Amplitude')
plt.title(f'Signal with Combined Activity and Inactivity Periods')
plt.legend(loc='upper right')
plt.tight_layout()
plt.show()

# Output
print("Merged Activity Periods:")
for (start, end) in activity_periods:
    print(f"Start: {start}, End: {end}")

print("\nInactivity Periods:")
for (start, end) in inactivity_periods:
    print(f"Start: {start}, End: {end}")
