import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.signal import butter, filtfilt

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
lowcut = 0.1  # Hz
highcut = 3.5  # Hz
sampling_rate = 30.0  # Hz

# read in acceleration file of interest
df = pd.read_csv('acceleration_data_Winnie1.txt', delimiter=',')
#clean data 
for col in df.columns:
    df[col] = df[col].astype(str).str.replace('[()]', '', regex=True).astype(float)

#initliazing norm df
num_rows = df.shape[0]
norm = np.zeros(num_rows)

#calculating the L-2 norm for all data points
for i in range(num_rows):
    norm[i] = np.linalg.norm(np.array([df.iloc[i,0],df.iloc[i,1],df.iloc[i,2]]))

# filter after calculating the L-2 norm
filtered_data = butter_bandpass_filter(norm,lowcut,highcut,sampling_rate)

# Set a clipping threshold
clipping_plus =2
clipping_minus = -2

# Clip the peaks
clipped_data = np.clip(filtered_data, clipping_minus, clipping_plus)

# set window size and run the zero crossing function on the clipped data
# window size is directly related to sensivity (ie. increasing the window size will also increase the sensivitiy of the code to small fluctuations in the dataset)
# this window size will likely have to be fine tuned based on the findings in the data
window_size = 200  
zcr = zero_crossing_rate(clipped_data, window_size)

# zcr threshold -> determined by the sensivity that is needed in the data
# this determines what is considered activity vs. inactivity 
zcr_threshold = np.percentile(zcr, 40) 

# activity regions are defined 
activity = zcr > zcr_threshold
# Identify activity periods
activity_periods = []
start = None

#tracking the time when activity starts / finishes based on the indicies 
for i in range(1, len(activity)):
    if activity[i] and not activity[i - 1]:  # Start of activity
        start = i
    elif not activity[i] and activity[i - 1] and start is not None:  # End of activity
        activity_periods.append((start, i))
        start = None

# edge case: when activity lasts until the end of the signal 
if start is not None:
    activity_periods.append((start, len(activity) - 1))

# edge case: inactivity at start of the signal 
merged_activity_periods = []
if activity[0] == False:
    # if the signal starts inactive, add inactivity period from the start to the first activity
    first_activity_start = activity_periods[0][0] if activity_periods else len(activity)
    inactivity_periods = [(0, first_activity_start)]
else:
    inactivity_periods = []

# merging the gaps between the activity periods that are within a minimum gap 
min_gap = 100 # chosen based on empirical data 
prev_start, prev_end = activity_periods[0]

for start, end in activity_periods[1:]:
    if start - prev_end <= min_gap:
        prev_end = end  
    else:
        merged_activity_periods.append((prev_start, prev_end)) 
        prev_start, prev_end = start, end

# add the last merged period
merged_activity_periods.append((prev_start, prev_end))

# identify inactivity periods between merged activity periods
inactivity_periods += [
    (merged_activity_periods[i - 1][1], merged_activity_periods[i][0])
    for i in range(1, len(merged_activity_periods))
]

# edge case: inactivity after the last activity period
if merged_activity_periods[-1][1] < len(clipped_data):
    inactivity_periods.append((merged_activity_periods[-1][1], len(clipped_data)))


# plot the clipped data with shaded activity and inactivity regions
plt.figure(figsize=(12, 6))
plt.plot(clipped_data, label='Clipped Data', alpha=0.7)

# shade merged activity regions
for (start, end) in merged_activity_periods:
    plt.axvspan(start, end, color='green', alpha=0.3, label='Activity')

# shade inactivity regions
for (start, end) in inactivity_periods:
    plt.axvspan(start, end, color='red', alpha=0.1, label='Inactivity')

plt.xlabel('Time')
plt.ylabel('Amplitude')
plt.title('Signal with Merged Activity and Inactivity Regions (ZCR-Based)')
plt.legend(loc='upper right')

# Show the plot
plt.tight_layout()
plt.show()

# Output the merged activity and inactivity periods
print("Merged Activity Periods:")
for (start, end) in merged_activity_periods:
    print(f"Start: {start}, End: {end}")

print("\nInactivity Periods:")
for (start, end) in inactivity_periods:
    print(f"Start: {start}, End: {end}")
