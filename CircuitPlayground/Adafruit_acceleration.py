import time
from adafruit_circuitplayground import cp

print("Sending accelerometer data over serial...")

while True:
    try:
        # Read the acceleration values
        x, y, z = cp.acceleration

        # Print them to the serial monitor (sent to the computer)
        print(f"{x}, {y}, {z}")

        # Wait before the next reading
        time.sleep(0.1)

    except KeyboardInterrupt:
        print("Logging stopped.")
        break
