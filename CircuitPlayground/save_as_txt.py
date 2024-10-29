#This file is dependent on collecting data from the CircuitPlayground using Mu and closing the serial connection there (while the code is still running) to ensure proper data transfer. Note that files names should be updated each time to reflect the type of data that is being transferred.  

import serial
import time

# Adjust the port to match your setup (e.g., 'COM3' on Windows or '/dev/ttyUSB0' on Linux/Mac)
ser = serial.Serial('/dev/tty.usbmodem1401', 9600, timeout=1)

# Open the text file on your computer --> update file name to prevent overwriting 
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
