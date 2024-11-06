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
    while ble.connected:
        # Read acceleration values using the Circuit Playground library
        x, y, z = cp.acceleration
        data = f"({x}, {y}, {z})\n"  # Format the data as a tuple string

        # Send data over UART BLE service
        uart.write(data.encode("utf-8"))
        print((x, y, z))  # Print to console in the exact same format as your basic script

        time.sleep(0.1)
