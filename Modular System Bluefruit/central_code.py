import time
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
from adafruit_circuitplayground import cp  # For button, LEDs, and acceleration

# Initialize BLE
ble = BLERadio()
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

print("Central initialized. Press Button A to toggle modes. Press Button B to toggle BLE connection.")

# State variables
scanning_enabled = False  # Start in central-only mode
ble_enabled = False  # Start with BLE off
button_a_previous = False  # Previous state of Button A
button_b_previous = False  # Previous state of Button B

# Helper function to set LEDs based on states
def set_led_state(ble_on, mode):
    """Set individual LEDs based on BLE state and mode."""
    cp.pixels.fill((0, 0, 0))  # Turn off all LEDs first
    if ble_on:
        cp.pixels[0] = (0, 255, 0)  # Green for BLE enabled
    else:
        cp.pixels[1] = (255, 0, 0)  # Red for BLE disabled

    if mode == "scanning":
        cp.pixels[2] = (0, 0, 255)  # Blue for scanning
    elif mode == "central":
        cp.pixels[3] = (255, 255, 0)  # Yellow for central-only mode

# Initialize in BLE off and central-only mode
set_led_state(ble_enabled, "central")

while True:
    # Detect Button A press to toggle between modes
    if cp.button_a and not button_a_previous:
        if ble_enabled:  # Only allow mode switching if BLE is on
            scanning_enabled = not scanning_enabled

            # Toggle between scanning and advertising
            if scanning_enabled:
                ble.stop_advertising()  # Stop advertising when scanning
                print("Peripheral scanning enabled.")
                set_led_state(ble_enabled, "scanning")
            else:
                ble.start_advertising(advertisement)  # Start advertising in central-only mode
                print("Central-only mode enabled and advertising.")
                set_led_state(ble_enabled, "central")
        else:
            print("Enable BLE first to toggle modes.")

    # Detect Button B press to toggle BLE connection
    if cp.button_b and not button_b_previous:
        ble_enabled = not ble_enabled

        # Start or stop BLE advertising
        if ble_enabled:
            print("Button B pressed. Starting BLE advertisement...")
            ble.start_advertising(advertisement)
        else:
            print("Button B pressed. Stopping BLE advertisement...")
            ble.stop_advertising()

        # Update LED state
        set_led_state(ble_enabled, "scanning" if scanning_enabled else "central")

        # Send Button B state over BLE
        button_b_state = "PRESSED" if cp.button_b else "RELEASED"
        uart.write(f"BUTTON_B_{button_b_state}\n".encode("utf-8"))
        print(f"Button B state: {button_b_state}")

    # Update button states
    button_a_previous = cp.button_a
    button_b_previous = cp.button_b

    if scanning_enabled and ble_enabled:
        # Peripheral scanning mode
        print("Scanning for peripherals...")
        for adv in ble.start_scan(ProvideServicesAdvertisement, timeout=2):
            if UARTService in adv.services:
                print(f"Found Peripheral: {adv.address}")
                with ble.connect(adv) as connection:
                    print("Connected to Peripheral.")
                    uart_peripheral = connection[UARTService]

                    # Synchronize time
                    sync_time = time.monotonic()
                    sync_message = f"SYNC,{sync_time:.2f}"
                    uart_peripheral.write(sync_message.encode("utf-8"))
                    print(f"Sent: {sync_message}")

                    # Process peripheral data while scanning is enabled
                    while connection.connected and scanning_enabled:
                        central_time = time.monotonic()
                        cx, cy, cz = cp.acceleration
                        print(f"Central Acceleration: {central_time:.2f},{cx:.4f},{cy:.4f},{cz:.4f}")

                        if uart_peripheral.in_waiting:
                            peripheral_data = uart_peripheral.read(uart_peripheral.in_waiting).decode("utf-8").strip()
                            print(f"Peripheral Data: {peripheral_data}")

                        time.sleep(0.2)

                print("Disconnected from Peripheral.")
        ble.stop_scan()

    elif ble_enabled:
        # Central-only mode: Advertise and send acceleration data
        central_time = time.monotonic()
        cx, cy, cz = cp.acceleration
        central_data = f"{central_time:.2f},{cx:.4f},{cy:.4f},{cz:.4f}"
        uart.write(central_data.encode("utf-8"))
        print(f"Central Only Data Sent: {central_data}")
        time.sleep(0.1)
