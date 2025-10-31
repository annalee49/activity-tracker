import serial as serial
import time
from datetime import datetime

# when you are running this code, run it in the same folder as the ino file:
# python3 export.py

# Change to your actual ESP32 serial port
PORT = "/dev/tty.usbserial-1420"  # e.g., /dev/tty.usbserial-1410 or COM3
BAUD = 115200

# Output file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
outfile = f"imu_data_{timestamp}.csv"

with serial.Serial(PORT, BAUD, timeout=2) as ser:
    print(f"Connected to {PORT}")
    time.sleep(2)

    # Send export command
    ser.write(b"EXPORT\n")
    print("Requesting CSV data...")

    with open(outfile, "w") as f:
        # Read until end marker
        started = False
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if "--- CSV EXPORT START ---" in line:
                started = True
                continue
            elif "--- CSV EXPORT END ---" in line:
                break
            elif started:
                f.write(line + "\n")

    print(f"✅ CSV saved as {outfile}")
