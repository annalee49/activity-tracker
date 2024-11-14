# SPDX-License-Identifier: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
from adafruit_circuitplayground import cp
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

# Initialize BLE
ble = BLERadio()
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

print("Waiting for connection...")

while True:
    # Start BLE advertisement
    ble.start_advertising(advertisement)
    while not ble.connected:
        pass

    print("Connected")
    start_time = time.monotonic()  # Record initial time
    while ble.connected:
        # Read acceleration values using the Circuit Playground library
        x, y, z = cp.acceleration
        # Calculate the elapsed time since the start of the connection
        elapsed_time = time.monotonic() - start_time
        # Format the output as a comma-separated string for easier parsing
        data = f"{elapsed_time:.2f},{x},{y},{z}\n"  # CSV-style output

        # Send data over UART BLE service
        uart.write(data.encode("utf-8"))
        print(data)  # Print data for debugging/monitoring

        time.sleep(0.1)
