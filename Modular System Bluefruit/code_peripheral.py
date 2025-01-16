import time
from adafruit_circuitplayground import cp  # For LEDs and acceleration
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

# Initialize BLE
ble = BLERadio()
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

print("Peripheral initialized. Always advertising and sending data.")

# Helper function to set the green LED state
def set_led_state(is_on):
    """Turn the green LED on or off."""
    cp.pixels.fill((0, 0, 0))  # Turn off all LEDs first
    if is_on:
        cp.pixels[0] = (0, 255, 0)  # Green for active

# Set green LED to always on
set_led_state(True)

# Always start advertising
ble.start_advertising(advertisement)

while True:
    # Check for connections
    while not ble.connected:
        # Wait until a connection is established
        time.sleep(0.1)

    print("Connected to Central.")

    # Send acceleration data continuously
    while ble.connected:
        # Read acceleration values
        x, y, z = cp.acceleration
        current_time = time.monotonic()

        # Format the data as <timestamp>,<x>,<y>,<z>
        data = f"{current_time:.2f},{x:.4f},{y:.4f},{z:.4f}"
        uart.write(data.encode("utf-8"))
        print(f"Sent: {data}")

        # Small delay to prevent spamming
        time.sleep(0.1)

    print("Disconnected from Central.")
    # Resume advertising when disconnected
    ble.start_advertising(advertisement)
