import time
from adafruit_ble import BLERadio
from adafruit_ble.services.nordic import UARTService

# Initialize BLE
ble = BLERadio()

print("Central initialized.")

while True:
    connected_peripheral = None

    # Scan for peripherals
    for entry in ble.start_scan(timeout=5):
        if UARTService in entry.services:
            print(f"Found Peripheral: {entry.address}")
            connected_peripheral = entry
            break

    ble.stop_scan()

    # Connect to the peripheral and synchronize time
    if connected_peripheral:
        with ble.connect(connected_peripheral) as connection:
            print("Connected to Peripheral.")
            uart = connection[UARTService]

            # Synchronize time
            sync_time = time.monotonic()
            sync_message = f"SYNC,{sync_time:.2f}"
            uart.write(sync_message.encode("utf-8"))
            print(f"Sent: {sync_message}")

            while connection.connected:
                # Collect central data
                central_time = time.monotonic()
                cx, cy, cz = cp.acceleration

                # Collect peripheral data
                if uart.in_waiting:
                    peripheral_data = uart.read(uart.in_waiting).decode("utf-8").strip()
                    px_time, px, py, pz = map(float, peripheral_data.split(","))

                    # Create unified dataset
                    combined_data = f"{px_time:.2f},{cx:.4f},{cy:.4f},{cz:.4f},{px:.4f},{py:.4f},{pz:.4f}"
                    print(f"Unified Data: {combined_data}")

                time.sleep(0.1)
    else:
        # Central operates independently
        central_time = time.monotonic()
        cx, cy, cz = cp.acceleration
        independent_data = f"{central_time:.2f},{cx:.4f},{cy:.4f},{cz:.4f},N/A,N/A,N/A"
        print(f"Central Data: {independent_data}")
        time.sleep(0.1)
