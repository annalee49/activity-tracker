#code developed by Grace Hooper - last updated on 11/7/24
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
lowcut = 0.01 # Hz
highcut = 4  # Hz
sampling_rate = 40.0  # Hz

# Read and clean the data
df = pd.read_csv('acceleration_data_Andre_11_7_24_Noise.txt', delimiter=',')
# df = pd.read_csv('Grace_11_06_Noise.txt', delimiter=',')
for col in df.columns:
    df[col] = df[col].astype(str).str.replace('[()]', '', regex=True).astype(float)

# Calculate L2 norm
num_rows = df.shape[0]
norm = np.zeros(num_rows)
for i in range(num_rows):
    norm[i] = np.linalg.norm(np.array([df.iloc[i, 0], df.iloc[i, 1], df.iloc[i, 2]]))

# Plot the original norm
plt.figure()
plt.plot(norm)
plt.xlabel('Time')
plt.ylabel('L2 Norm')
plt.title('L2 Norm of Signal')

# Apply bandpass filter
filtered_data = butter_bandpass_filter(norm, lowcut, highcut, sampling_rate)

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

# Merge close activity periods
min_gap = 100
merged_activity_periods = []
prev_start, prev_end = activity_periods[0]
for start, end in activity_periods[1:]:
    if start - prev_end <= min_gap:
        prev_end = end
    else:
        merged_activity_periods.append((prev_start, prev_end))
        prev_start, prev_end = start, end
merged_activity_periods.append((prev_start, prev_end))

# Identify inactivity periods
inactivity_periods = []
if merged_activity_periods[0][0] > 0:
    inactivity_periods.append((0, merged_activity_periods[0][0]))
for i in range(1, len(merged_activity_periods)):
    inactivity_periods.append((merged_activity_periods[i - 1][1], merged_activity_periods[i][0]))
if merged_activity_periods[-1][1] < len(combined_activity):
    inactivity_periods.append((merged_activity_periods[-1][1], len(combined_activity) - 1))


filename = os.path.basename('Andre_11_7_24_Noise.txt')  # Replace with your variable if using dynamic filenames

# Plotting
plt.figure(figsize=(12, 6))
plt.plot(clipped_data, label='Clipped Data', alpha=0.7)
for (start, end) in merged_activity_periods:
    plt.axvspan(start, end, color='green', alpha=0.3, label='Activity')
for (start, end) in inactivity_periods:
    plt.axvspan(start, end, color='red', alpha=0.1, label='Inactivity')
plt.xlabel('Time')
plt.ylabel('Amplitude')
plt.title(f'Signal with Combined Activity and Inactivity Periods - {filename}')
plt.legend(loc='upper right')
plt.tight_layout()
plt.show()

# Output
print("Merged Activity Periods:")
for (start, end) in merged_activity_periods:
    print(f"Start: {start}, End: {end}")

print("\nInactivity Periods:")
for (start, end) in inactivity_periods:
    print(f"Start: {start}, End: {end}")
