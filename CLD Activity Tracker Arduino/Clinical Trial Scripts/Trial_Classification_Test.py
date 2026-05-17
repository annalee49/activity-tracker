import pandas as pd
import numpy as np
from scipy.signal import welch
from scipy.stats import entropy

def calculate_spectral_entropy(signal, sf=40):
    freqs, psd = welch(signal, sf, nperseg=len(signal))
    # Avoid division by zero if signal is completely flat
    if np.sum(psd) == 0:
        return 0
    psd_norm = psd / np.sum(psd)
    return entropy(psd_norm)

def calculate_spectral_energy(signal):
    fft_vals = np.fft.fft(signal)
    return np.sum(np.abs(fft_vals)**2) / len(signal)

def load_and_sync_data(wrist_path, ankle_path, tolerance_ms=15):
    print("Loading and fuzzy-synchronizing sensor data...")
    df_wrist = pd.read_csv(wrist_path)
    df_ankle = pd.read_csv(ankle_path)
    
    df_wrist = df_wrist.sort_values('timestamp')
    df_ankle = df_ankle.sort_values('timestamp')
    
    # Update this: Exclude both 'timestamp' AND 'Time(s)' from getting prefixes
    excluded_cols = ['timestamp', 'Time(s)']
    
    wrist_cols = {col: f"wrist_{col}" for col in df_wrist.columns if col not in excluded_cols}
    df_wrist = df_wrist.rename(columns=wrist_cols)
    
    ankle_cols = {col: f"ankle_{col}" for col in df_ankle.columns if col not in excluded_cols}
    df_ankle = df_ankle.rename(columns=ankle_cols)
    
    # fuzzy join
    df_synced = pd.merge_asof(
        df_wrist, 
        df_ankle, 
        on='timestamp', 
        direction='nearest', 
        tolerance=tolerance_ms
    )
    
    # We may end up with 'Time(s)_x' and 'Time(s)_y' if they exist in both.
    # If so, we'll keep the wrist version as the primary reference.
    if 'Time(s)_x' in df_synced.columns:
        df_synced = df_synced.rename(columns={'Time(s)_x': 'Time(s)'})
    
    df_synced = df_synced.dropna().reset_index(drop=True)
    return df_synced

def extract_features(wrist_path, ankle_path, output_path):
    # 1. Load and align the two separate files
    df = load_and_sync_data(wrist_path, ankle_path)
    
    if len(df) == 0:
        print("Error: No matching timestamps found between the two files. Check your data.")
        return None
    print("Converting raw data to standard units (g and deg/s)...")

    # Accelerometer: Convert raw LSB to units of 'g' (gravity)
    accel_scale_factor = 16384.0 
    for prefix in ['wrist', 'ankle']:
        for axis in ['ax', 'ay', 'az']:
            df[f'{prefix}_{axis}'] = df[f'{prefix}_{axis}'] / accel_scale_factor

    # Gyroscope: Convert raw LSB to degrees per second (°/s)
    # Note: 131.0 is the standard for +/- 250 deg/s. 
    # (If your sensor is set to +/- 500 deg/s, change this to 65.5)
    gyro_scale_factor = 131.0 
    for prefix in ['wrist', 'ankle']:
        for axis in ['gx', 'gy', 'gz']:
            df[f'{prefix}_{axis}'] = df[f'{prefix}_{axis}'] / gyro_scale_factor
            
    # 2. Calculate Magnitudes
    df['wrist_accel_mag'] = np.sqrt(df['wrist_ax']**2 + df['wrist_ay']**2 + df['wrist_az']**2)
    df['wrist_gyro_mag'] = np.sqrt(df['wrist_gx']**2 + df['wrist_gy']**2 + df['wrist_gz']**2)
    df['ankle_accel_mag'] = np.sqrt(df['ankle_ax']**2 + df['ankle_ay']**2 + df['ankle_az']**2)
    df['ankle_gyro_mag'] = np.sqrt(df['ankle_gx']**2 + df['ankle_gy']**2 + df['ankle_gz']**2)
    
    # 3. Calculate Jerks (Derivative of Magnitude)
    dt = 0.025 # 40Hz
    for prefix in ['wrist', 'ankle']:
        df[f'{prefix}_accel_jerk'] = df[f'{prefix}_accel_mag'].diff() / dt
        df[f'{prefix}_gyro_jerk'] = df[f'{prefix}_gyro_mag'].diff() / dt
    
    df = df.fillna(0) # Fill first row NaNs
    
    # 4. Sliding Window Setup
    window_size = 200 # 200 = 5 seconds at 40Hz
    step_size = 100  # 50% overlap
    features_list = []
    
    print("Extracting features in sliding windows...")
    for start in range(0, len(df) - window_size + 1, step_size):
        window = df.iloc[start:start + window_size]
        feat = {'window_start_Time(s)': window['Time(s)'].iloc[0]}
        
        # We extract the single-limb features for BOTH wrist and ankle, 
        # as you will want to let the ML model decide which limb is more important for which exercise.
        for limb in ['wrist', 'ankle']:
            # SMA (Sum of absolute values of axes divided by window size)
            feat[f'{limb}_SMA'] = (np.sum(np.abs(window[f'{limb}_ax'])) + 
                                   np.sum(np.abs(window[f'{limb}_ay'])) + 
                                   np.sum(np.abs(window[f'{limb}_az']))) / window_size
            
            # Mean of Accel Magnitude (Overall posture)
            feat[f'{limb}_accel_mag_mean'] = window[f'{limb}_accel_mag'].mean()
            
            # RMS of Accel Magnitude (Overall power)
            feat[f'{limb}_accel_mag_rms'] = np.sqrt(np.mean(window[f'{limb}_accel_mag']**2))
            
            # Standard Deviation of Accel Magnitude (Movement intensity)
            feat[f'{limb}_accel_mag_std'] = window[f'{limb}_accel_mag'].std()
            
            # Standard Deviation of Angular Accel Magnitude (Rotational intensity)
            feat[f'{limb}_gyro_mag_std'] = window[f'{limb}_gyro_mag'].std()
            
            # Standard Deviation of Jerk (Smoothness/hesitation)
            feat[f'{limb}_accel_jerk_std'] = window[f'{limb}_accel_jerk'].std()
            feat[f'{limb}_gyro_jerk_std'] = window[f'{limb}_gyro_jerk'].std()
            
            # Spectral Features
            feat[f'{limb}_accel_mag_entropy'] = calculate_spectral_entropy(window[f'{limb}_accel_mag'].values, sf=40)
            feat[f'{limb}_accel_mag_energy'] = calculate_spectral_energy(window[f'{limb}_accel_mag'].values)

        # 5. CROSS-SENSOR FEATURES (The ones that require perfectly synced files)
        # We calculate the Pearson correlation coefficient between the upper and lower body
        
        # If standard deviation is 0 (perfectly flat line), correlation returns NaN. We catch this safely.
        if window['wrist_accel_mag'].std() == 0 or window['ankle_accel_mag'].std() == 0:
            feat['cross_corr_accel_mag'] = 0.0
        else:
            feat['cross_corr_accel_mag'] = np.corrcoef(window['wrist_accel_mag'], window['ankle_accel_mag'])[0, 1]
            
        if window['wrist_gyro_mag'].std() == 0 or window['ankle_gyro_mag'].std() == 0:
            feat['cross_corr_gyro_mag'] = 0.0
        else:
            feat['cross_corr_gyro_mag'] = np.corrcoef(window['wrist_gyro_mag'], window['ankle_gyro_mag'])[0, 1]

        features_list.append(feat)

    features_df = pd.DataFrame(features_list)
    features_df.to_csv(output_path, index=False)
    print(f"Success! Saved feature table to {output_path}")
    return features_df

# === Execution ===
# Update these with your actual filenames
wrist_file = "C:\CLD Activity Tracker Arduino\Clinical Trial Data\Patient 15\pt15wrist_data.csv"
ankle_file = "C:\CLD Activity Tracker Arduino\Clinical Trial Data\Patient 15\pt15ankle_data.csv"
output_file = 'patient15_extracted_features_5S.csv'

extract_features(wrist_file, ankle_file, output_file)