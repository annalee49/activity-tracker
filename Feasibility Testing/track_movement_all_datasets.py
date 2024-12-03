import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.signal import butter, filtfilt
import os
import re


def butter_bandpass_filter(data, lowcut, highcut, fs):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(4, [low, high], btype='band')
    return filtfilt(b, a, data)


def zero_crossing_rate(data, window_size):
    zero_crossings = np.diff(np.sign(data)) != 0
    zcr = np.convolve(zero_crossings, np.ones(window_size), mode='same') / window_size
    return zcr


# Parameters for the bandpass filter
lowcut = 0.01  # Hz
highcut = 4  # Hz
fs = 40.0  # Sampling rate, adjust if needed

# Loop through all .txt files in the current directory
for filename in os.listdir('.'):  # Use '.' for the current directory
    if filename.endswith('.txt'):
        filepath = os.path.join('.', filename)  # Path to the file

        # Extract metadata from filename
        match = re.search(r'acceleration_data_(\w+?)_(.+?)_\d{8}_\d{6}\.txt', filename)
        if not match:
            print(f"Skipping file with unexpected format: {filename}")
            continue

        person_name = match.group(1)
        activity_phrase = match.group(2)

        # Read the TXT file directly into a DataFrame
        df = pd.read_csv(
            filepath, 
            delimiter=',', 
            header=None, 
            names=['time', 'x', 'y', 'z'], 
            engine='python'
        )

        # Remove parentheses and convert to numeric
        df = df.replace({r'[()]': ''}, regex=True).astype(float)

        # Separate timestamps and acceleration data
        timestamps = df['time'].values
        accel_data = df[['x', 'y', 'z']].values

        # Calculate L2 norm
        norm = np.linalg.norm(accel_data, axis=1)

        # Apply bandpass filter
        filtered_data = butter_bandpass_filter(norm, lowcut, highcut, fs)

        # Set amplitude threshold
        amplitude_threshold = np.percentile(norm, 95)
        high_amplitude_regions = norm > amplitude_threshold

        # Apply clipping
        clipping_plus = 2
        clipping_minus = -2
        clipped_data = np.clip(filtered_data, clipping_minus, clipping_plus)

        # Calculate ZCR with a sliding window
        window_size = 200
        zcr = zero_crossing_rate(clipped_data, window_size)

        # Define ZCR threshold
        zcr_threshold = np.percentile(zcr, 40)
        zcr_activity = zcr > zcr_threshold

        # Combine conditions
        min_length = min(len(zcr_activity), len(high_amplitude_regions))
        combined_activity = (zcr_activity[:min_length] & high_amplitude_regions[:min_length])

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
        merged_activity_periods = []  # Temporary list for merged periods

        # Initialize with the first activity period
        if activity_periods:
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

        # Identify inactivity periods
        inactivity_periods = []
        if merged_activity_periods:
            if merged_activity_periods[0][0] > 0:
                inactivity_periods.append((0, merged_activity_periods[0][0]))
            for i in range(1, len(merged_activity_periods)):
                inactivity_periods.append((merged_activity_periods[i - 1][1], merged_activity_periods[i][0]))
            if merged_activity_periods[-1][1] < len(combined_activity):
                inactivity_periods.append((merged_activity_periods[-1][1], len(combined_activity) - 1))

        # Calculate total exercise time
        total_exercise_time = 0
        print(f"\nActivity Times for {filename}:")
        for start, end in merged_activity_periods:
            duration_seconds = df['time'].iloc[end] - df['time'].iloc[start]
            print(f"Start: {df['time'].iloc[start]:.2f}s, End: {df['time'].iloc[end]:.2f}s, Duration: {duration_seconds:.2f}s")
            total_exercise_time += duration_seconds

        print(f"Total exercise time: {total_exercise_time:.2f} seconds")

        # Plotting
        plt.figure(figsize=(12, 6))
        plt.plot(clipped_data, label='Clipped Data', alpha=0.7)
        for (start, end) in merged_activity_periods:
            plt.axvspan(start, end, color='green', alpha=0.3, label='Activity')
        for (start, end) in inactivity_periods:
            plt.axvspan(start, end, color='red', alpha=0.1, label='Inactivity')
        plt.xlabel('Time')
        plt.ylabel('Amplitude')
        plt.title(f'Signal with Combined Activity and Inactivity Periods - {person_name.capitalize()} - {activity_phrase}')
        plt.legend(loc='upper right')
        plt.tight_layout()

        # Save figure with title as filename
        save_path = f"{person_name.capitalize()}_{activity_phrase}.png"
        plt.savefig(save_path)
        plt.close()

        print(f"Processed and saved figure for {filename}")
