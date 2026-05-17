import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import glob
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, ConfusionMatrixDisplay


import glob
import os

# 1. Load multiple datasets
# Using 'r' before the string handles the backslashes correctly in Windows
# The '**' and recursive=True allow it to look into all Patient folders
data_path = r"C:\CLD Activity Tracker Arduino\Clinical Trial Data"
file_pattern = os.path.join(data_path, "**", "*_Final_Dataset.csv")
all_files = glob.glob(file_pattern, recursive=True)

print(f"Found {len(all_files)} files: {all_files}")

# Read each file and add a column to keep track of which patient it came from
# This is helpful if you want to analyze patient-specific performance later
df_list = []
for filename in all_files:
    temp_df = pd.read_csv(filename)
    # Optional: Extract patient ID from folder name/filename
    temp_df['source_file'] = os.path.basename(filename) 
    df_list.append(temp_df)

# Combine all dataframes into one
df = pd.concat(df_list, axis=0, ignore_index=True)

print(f"Combined dataset shape: {df.shape}")

# 2. Data Cleaning: Drop rows where 'exercise_type' is missing
data = df.dropna(subset=['exercise_type']).copy()

# 4. Define Features and Target
X = data.drop(columns=['window_start_Time(s)', 'exercise_type', 'source_file'])
y = data['exercise_type']

# 5. Train/Test Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=0, stratify=y
)

# 6. Feature Scaling (Standardization)
# We scale AFTER splitting to prevent information from the test set leaking into the training set
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# --- RANDOM FOREST CLASSIFIER ---
print("Tuning Random Forest...")
rf_param_grid = {
    'max_depth': range(2, 12, 2),
    'n_estimators': range(10, 110, 10)
}

rf_grid = GridSearchCV(
    RandomForestClassifier(random_state=0),
    param_grid=rf_param_grid,
    cv=5,
    return_train_score=True
)
# Make sure to train on the scaled data
rf_grid.fit(X_train_scaled, y_train)

best_rf = rf_grid.best_estimator_
print(f"Best RF Params: {rf_grid.best_params_}")
print(f"RF Test Accuracy: {best_rf.score(X_test_scaled, y_test):.3f}")

# Plot and save Random Forest Confusion Matrix
fig, ax = plt.subplots(figsize=(12, 10))
ConfusionMatrixDisplay.from_estimator(best_rf, X_test_scaled, y_test, ax=ax, cmap='Blues', xticks_rotation=45)
plt.setp(ax.get_xticklabels(), rotation=45, ha='right', rotation_mode='anchor')
plt.title('Random Forest - Confusion Matrix')
plt.tight_layout()
plt.show()

import seaborn as sns
import matplotlib.pyplot as plt

# 1. Choose a subset of data (e.g., just 4 categories)
subset_labels = ['Rest', 'March', 'Shoulder Blade Squeeze', 'Calf and Hamstring Stretch']
plot_data = data[data['exercise_type'].isin(subset_labels)]

# 2. Choose a few features to compare
features = ['ankle_accel_mag_energy', 'wrist_accel_mag_energy', 'cross_corr_accel_mag', 'ankle_accel_mag_entropy']

# 3. Create the plot
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
axes = axes.flatten()

for i, col in enumerate(features):
    sns.boxplot(x='exercise_type', y=col, data=plot_data, ax=axes[i], palette='Set2')
    axes[i].set_title(f'Comparison of {col}')
    plt.setp(axes[i].get_xticklabels(), rotation=30, ha='right')

plt.tight_layout()
plt.show()

# --- GRADIENT BOOSTING CLASSIFIER ---
print("\nTuning Gradient Boosting...")
gb_param_grid = {
    'learning_rate': [0.05, 0.1, 0.2],
    'n_estimators': range(10, 110, 20),
    'max_depth': range(2, 6, 1)
}

gb_grid = GridSearchCV(
    GradientBoostingClassifier(random_state=0),
    param_grid=gb_param_grid,
    cv=5,
    return_train_score=True
)
# Make sure to train on the scaled data
gb_grid.fit(X_train_scaled, y_train)

best_gb = gb_grid.best_estimator_
print(f"Best GB Params: {gb_grid.best_params_}")
print(f"GB Test Accuracy: {best_gb.score(X_test_scaled, y_test):.3f}")

# Plot Gradient Boosting Confusion Matrix
fig, ax = plt.subplots(figsize=(12, 10))
ConfusionMatrixDisplay.from_estimator(best_gb, X_test_scaled, y_test, ax=ax, cmap='Greens', xticks_rotation=45)
plt.setp(ax.get_xticklabels(), rotation=45, ha='right', rotation_mode='anchor')
plt.title('Gradient Boosting - Confusion Matrix')
plt.tight_layout()
plt.show()
