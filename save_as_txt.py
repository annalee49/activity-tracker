import serial
import time

# Adjust the port to match your setup (e.g., 'COM3' on Windows or '/dev/ttyUSB0' on Linux/Mac)
ser = serial.Serial('/dev/tty.usbmodem1401', 9600, timeout=1)

# Open the text file on your computer
with open("acceleration_data.txt", "w") as f:
    while True:
        try:
            # Read a line of serial data and decode it
            line = ser.readline().decode('utf-8').strip()
            
            # If there is data, write it to the text file
            if line:
                print(line)  # Also print to the console
                f.write(line + "\n")
                f.flush()  # Ensure it writes immediately
        except KeyboardInterrupt:
            print("Stopping...")
            break

# Close the serial connection
ser.close()
