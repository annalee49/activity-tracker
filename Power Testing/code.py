import time
import board  # Import board to access pin constants
from adafruit_circuitplayground import cp
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

# Initialize BLE
ble = BLERadio()
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

# Helper function to set LED state
def set_led_state(is_on):
    if is_on:
        cp.pixels.fill((0, 0, 0))  # Turn off all LEDs first
        cp.pixels[0] = (0, 255, 0)  # Green for "on"
    else:
        cp.pixels.fill((0, 0, 0))  # Turn off all LEDs first
        cp.pixels[1] = (255, 0, 0)  # Red for "off"

# Initial state
ble_enabled = False
set_led_state(ble_enabled)
print("System initialized. Press button A to toggle BLE connection...")

button_a_previous = False  # Track previous state of button A

# Buffer settings
DATA_BUFFER = []
BUFFER_SIZE = 10  # Number of readings per burst
TRANSMISSION_INTERVAL = 60  # Time in seconds (1 minute)
last_transmission_time = time.monotonic()

while True:
    # Detect button press state change (button release)
    if cp.button_a and not button_a_previous:
        ble_enabled = not ble_enabled  # Toggle BLE state
        if ble_enabled:
            print("Button A pressed. Starting BLE advertisement...")
            set_led_state(True)  # Show "on" state (green LED)
            ble.start_advertising(advertisement)
        else:
            print("Button A pressed. Stopping BLE advertisement...")
            ble.stop_advertising()
            set_led_state(False)  # Show "off" state (red LED)

    # Send button state over BLE if changed
    if cp.button_a != button_a_previous:
        button_state = "PRESSED" if cp.button_a else "RELEASED"
        uart.write(f"BUTTON_{button_state}\n".encode("utf-8"))
        print(f"Button A state: {button_state}")

    # Collect acceleration data if BLE is enabled
    if ble_enabled:
        x, y, z = cp.acceleration
        DATA_BUFFER.append((x, y, z))

        # Send data every 60 seconds (1 minute) or when the buffer reaches its limit
        if (time.monotonic() - last_transmission_time) >= TRANSMISSION_INTERVAL:
            if DATA_BUFFER:  # Ensure there is data to send
                # Convert buffer to a string format
                data_str = ";".join([f"({x:.2f},{y:.2f},{z:.2f})" for x, y, z in DATA_BUFFER])

                # Send over BLE
                uart.write((data_str + "\n").encode("utf-8"))
                print(f"Sending Burst: {data_str}")  # Print for debugging

                # Clear buffer and reset transmission timer
                DATA_BUFFER.clear()
            last_transmission_time = time.monotonic()  # Reset the timer

    # Update button state
    button_a_previous = cp.button_a

    # Small delay for debouncing
    time.sleep(0.1)
