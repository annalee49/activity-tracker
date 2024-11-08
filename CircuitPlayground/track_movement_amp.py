import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Read and clean the data
df = pd.read_csv('Winnie_11_06_Noise.txt', delimiter=',')
for col in df.columns:
    df[col] = df[col].astype(str).str.replace('[()]', '', regex=True).astype(float)

# Calculate the L2 norm (amplitude)
num_rows = df.shape[0]
norm = np.zeros(num_rows)
for i in range(num_rows):
    norm[i] = np.linalg.norm(np.array([df.iloc[i, 0], df.iloc[i, 1], df.iloc[i, 2]]))

# Define a threshold for large amplitudes at the 35th percentile
amplitude_threshold = np.percentile(norm, 90)

# Identify high-amplitude regions based on the threshold
high_amplitude_regions = norm > amplitude_threshold

# Apply a minimum gap to merge nearby high-amplitude regions
min_gap = 20  # Adjust based on your data resolution and needs

# Detect start and end points of each high amplitude region, merging gaps
activity_periods = []
start = None
for i in range(1, len(high_amplitude_regions)):
    if high_amplitude_regions[i] and not high_amplitude_regions[i - 1]:  # Start of a region
        start = i
    elif not high_amplitude_regions[i] and high_amplitude_regions[i - 1]:  # End of a region
        if start is not None:
            end = i
            # Check if the gap is smaller than min_gap to merge
            if activity_periods and start - activity_periods[-1][1] <= min_gap:
                # Merge with the previous region
                activity_periods[-1] = (activity_periods[-1][0], end)
            else:
                # Add as a new activity period
                activity_periods.append((start, end))
            start = None

# Edge case: if the high-amplitude region goes to the end
if start is not None:
    activity_periods.append((start, len(norm) - 1))

# Select the two largest merged activity periods
activity_periods = sorted(activity_periods, key=lambda x: np.sum(norm[x[0]:x[1]]), reverse=True)[:2]

# Identify inactivity periods as the gaps between activity periods
inactivity_periods = []
if activity_periods[0][0] > 0:
    inactivity_periods.append((0, activity_periods[0][0]))
for i in range(1, len(activity_periods)):
    inactivity_periods.append((activity_periods[i-1][1], activity_periods[i][0]))
if activity_periods[-1][1] < len(norm):
    inactivity_periods.append((activity_periods[-1][1], len(norm) - 1))

# Plot the raw data with highlighted activity and inactivity periods
plt.figure(figsize=(12, 6))
plt.plot(norm, label='Raw Data Norm', color='blue', alpha=0.7)

# Shade the selected high-amplitude periods (activity) in green
for (start, end) in activity_periods:
    plt.axvspan(start, end, color='green', alpha=0.3, label='Activity' if start == activity_periods[0][0] else "")

# Shade the inactivity periods in pink
for (start, end) in inactivity_periods:
    plt.axvspan(start, end, color='pink', alpha=0.3, label='Inactivity' if start == inactivity_periods[0][0] else "")

# Label the plot
plt.xlabel('Time')
plt.ylabel('Amplitude')
plt.title('Signal with High-Amplitude Activity and Inactivity Periods Highlighted')
plt.legend(loc='upper right')
plt.tight_layout()
plt.show()