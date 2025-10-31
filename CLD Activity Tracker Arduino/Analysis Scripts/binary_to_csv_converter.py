import struct
import math
import csv

input_file = "/Users/annalee/Documents/BME390/imu_data_10_26.bin"
output_file = "/Users/annalee/Documents/BME390/imu_data_10_26.csv"

# Define the binary record format
record_struct = struct.Struct("<Lhhhhhh")  # matches LogEntry: unsigned long + 6 int16

with open(input_file, "rb") as f, open(output_file, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["timestamp(ms)", "ax(g)", "ay(g)", "az(g)", "gx(dps)", "gy(dps)", "gz(dps)", "roll(deg)", "pitch(deg)"])
    
    while True:
        chunk = f.read(record_struct.size)
        if not chunk:
            break
        timestamp, ax, ay, az, gx, gy, gz = record_struct.unpack(chunk)
        ax_g, ay_g, az_g = ax/16384.0, ay/16384.0, az/16384.0
        gx_dps, gy_dps, gz_dps = gx/131.0, gy/131.0, gz/131.0
        roll = math.degrees(math.atan2(ay_g, az_g))
        pitch = math.degrees(math.atan2(-ax_g, math.sqrt(ay_g**2 + az_g**2)))
        writer.writerow([timestamp, ax_g, ay_g, az_g, gx_dps, gy_dps, gz_dps, roll, pitch])

print(f"✅ Converted {input_file} → {output_file}")
