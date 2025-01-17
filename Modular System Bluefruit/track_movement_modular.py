# Import necessary libraries
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.signal import butter, filtfilt

# Bandpass filter function
def butter_bandpass_filter(data, lowcut, highcut, fs):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(4, [low, high], btype='band')
    return filtfilt(b, a, data)

# Zero crossing rate function
def zero_crossing_rate(data, window_size):
    zero_crossings = np.diff(np.sign(data)) != 0
    return np.convolve(zero_crossings, np.ones(window_size), mode='same') / window_size

# Define a function to process a single dataset
def process_dataset(filename, lowcut, highcut, sampling_rate, zcr_threshold_percentile, window_size):
    # Read dataset
    df = pd.read_csv(filename, delimiter=',')
    # Current cleaning logic in the first code
    for col in df.columns:
        df[col] = df[col].astype(str).str.replace('[()]', '', regex=True).astype(float)


    # Calculate L2 norm
    norm = np.linalg.norm(df.values, axis=1)

    # Apply bandpass filter
    filtered_data = butter_bandpass_filter(norm, lowcut, highcut, sampling_rate)

    # Clip data
    clipped_data = np.clip(filtered_data, -2, 2)

    # Calculate ZCR
    zcr = zero_crossing_rate(clipped_data, window_size)
    zcr_threshold = np.percentile(zcr, zcr_threshold_percentile)
    activity = zcr > zcr_threshold

    # Extract activity periods
    activity_periods = []
    start = None
    for i in range(1, len(activity)):
        if activity[i] and not activity[i - 1]:
            start = i
        elif not activity[i] and activity[i - 1] and start is not None:
            activity_periods.append((start, i))
            start = None
    if start is not None:
        activity_periods.append((start, len(activity) - 1))

    # Merge close activity periods
    merged_activity_periods = []
    if activity_periods:
        prev_start, prev_end = activity_periods[0]
        for start, end in activity_periods[1:]:
            if start - prev_end <= 100:
                prev_end = end
            else:
                merged_activity_periods.append((prev_start, prev_end))
                prev_start, prev_end = start, end
        merged_activity_periods.append((prev_start, prev_end))

    return merged_activity_periods

# Merge two datasets' activity periods
def merge_activity_periods(activity_periods1, activity_periods2):
    all_periods = sorted(activity_periods1 + activity_periods2, key=lambda x: x[0])
    merged_periods = []
    if all_periods:
        prev_start, prev_end = all_periods[0]
        for start, end in all_periods[1:]:
            if start <= prev_end:
                prev_end = max(prev_end, end)
            else:
                merged_periods.append((prev_start, prev_end))
                prev_start, prev_end = start, end
        merged_periods.append((prev_start, prev_end))
    return merged_periods

# Main parameters
lowcut = 0.01
highcut = 7
sampling_rate = 40.0
zcr_threshold_percentile = 40
window_size = 200

# Process datasets
file1 = 'CIRCUITPYc67c_short_decimal_acceleration_data_20250116_145104.txt'  # Replace with your actual file path
file2 = 'CIRCUITPYb48a_short_decimal_acceleration_data_20250116_145101.txt'  # Replace with your actual file path
activity_periods1 = process_dataset(file1, lowcut, highcut, sampling_rate, zcr_threshold_percentile, window_size)
activity_periods2 = process_dataset(file2, lowcut, highcut, sampling_rate, zcr_threshold_percentile, window_size)

# Merge activity periods
merged_activity_periods = merge_activity_periods(activity_periods1, activity_periods2)

# Calculate total activity duration
total_activity_time = sum(end - start for start, end in merged_activity_periods)

# Output results
print("Merged Activity Periods:")
for start, end in merged_activity_periods:
    print(f"Start: {start}, End: {end}")

print(f"\nTotal Activity Time: {total_activity_time} seconds")

# Plot the merged activity periods
plt.figure(figsize=(12, 6))
for (start, end) in merged_activity_periods:
    plt.axvspan(start, end, color='green', alpha=0.3, label='Merged Activity')
plt.title('Merged Activity Periods from Two Datasets')
plt.xlabel('Time')
plt.ylabel('Activity Indicator')
plt.tight_layout()
plt.show()
