import pandas as pd
import numpy as np

def extract_features(file_path, output_path):
    # 1. Load the data
    print(f"Loading data from {file_path}...")
    df = pd.read_csv(file_path)

    # 2. Preprocessing: Calculate Vector Magnitudes and Jerk
    # Magnitudes are orientation-independent, capturing overall force/rotation
    df['accel_mag'] = np.sqrt(df['ax']**2 + df['ay']**2 + df['az']**2)
    df['gyro_mag'] = np.sqrt(df['gx']**2 + df['gy']**2 + df['gz']**2)

    # Calculate Jerk (derivative of acceleration magnitude with respect to time)
    # At 40Hz, the time step (dt) is 1/40 = 0.025 seconds
    dt = 0.025
    df['jerk_mag'] = df['accel_mag'].diff() / dt
    df['jerk_mag'] = df['jerk_mag'].fillna(0) # Handle the first NaN value

    # 3. Sliding Window Setup
    window_size = 200  # 5 seconds at 40Hz
    step_size = 100    # 2.5 seconds (50% overlap)

    features_list = []

    # 4. Extract Features per Window
    print("Extracting features...")
    for start in range(0, len(df) - window_size + 1, step_size):
        window = df.iloc[start:start + window_size]
        
        # Dictionary to hold features for this specific window
        window_features = {}
        
        # Keep track of the window's starting timestamp for reference
        window_features['window_start_Time(s)'] = window['Time(s)'].iloc[0]
        
        # --- Base Axes Features ---
        # Mean captures the gravitational pull/postural orientation
        # Standard Deviation (std) captures the dynamic movement intensity
        # Interquartile Range (IQR) captures the bounded range, ignoring momentary sensor noise
        for axis in ['ax', 'ay', 'az', 'gx', 'gy', 'gz']:
            window_features[f'{axis}_mean'] = window[axis].mean()
            window_features[f'{axis}_std'] = window[axis].std()
            window_features[f'{axis}_iqr'] = np.percentile(window[axis], 75) - np.percentile(window[axis], 25)
            
        # --- Magnitude Features ---
        window_features['accel_mag_mean'] = window['accel_mag'].mean()
        window_features['accel_mag_std'] = window['accel_mag'].std()
        window_features['gyro_mag_mean'] = window['gyro_mag'].mean()
        window_features['gyro_mag_std'] = window['gyro_mag'].std()
        
        # --- Movement Quality Feature ---
        # High standard deviation in jerk indicates rough, hesitant, or uncoordinated movement
        window_features['jerk_mag_std'] = window['jerk_mag'].std()
        
        features_list.append(window_features)

    # 5. Create the final feature table
    features_df = pd.DataFrame(features_list)

    # 6. Save to a new CSV
    features_df.to_csv(output_path, index=False)
    print(f"Success! Extracted {len(features_df.columns)} features across {len(features_df)} windows.")
    print(f"Saved feature table to {output_path}")
    
    return features_df

# Execute the pipeline on the provided file
input_filename = 'Example data.xlsx - Sheet1.csv'
output_filename = 'extracted_features_windowed.csv'

# Uncomment the line below to run the extraction when executing the script locally
# final_table = extract_features(input_filename, output_filename)