import numpy as np
import pandas as pd
import math

# 1. Define the structure in numpy, matching the ESP32
# 'L' = unsigned long (4 bytes)
# 'h' = signed int16 (2 bytes)
log_dtype = np.dtype([
    ('timestamp', np.uint32),  # 4-byte unsigned long
    ('ax_raw', np.int16),      # 2-byte signed int
    ('ay_raw', np.int16),
    ('az_raw', np.int16),
    ('gx_raw', np.int16),
    ('gy_raw', np.int16),
    ('gz_raw', np.int16),
])

# 2. Load the raw binary file into a numpy array
filename = 'imu_data.csv' # Your binary data file
data = np.fromfile(filename, dtype=log_dtype)

# 3. Convert the whole thing to a pandas DataFrame
df = pd.DataFrame(data)

# 4. Now, do all your conversions in Python (this is very fast)
df['ax_g'] = df['ax_raw'] / 16384.0
df['ay_g'] = df['ay_raw'] / 16384.0
df['az_g'] = df['az_raw'] / 16384.0

df['gx_dps'] = df['gx_raw'] / 131.0
df['gy_dps'] = df['gy_raw'] / 131.0
df['gz_dps'] = df['gz_raw'] / 131.0

# You are now ready for analysis!
print(df.head())