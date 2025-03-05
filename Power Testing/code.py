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

# **Fixed burst interval (store 30 seconds of data before sending)**
BURST_INTERVAL = 30  # Time before sending all data (in seconds)
SAMPLE_RATE = 0.1  # Sample every 0.3s
BUFFER_SIZE = int(BURST_INTERVAL / SAMPLE_RATE)  # 100 data points for 30s at 0.3s intervals
data_buffer = [""] * BUFFER_SIZE  # Pre-allocate buffer space
buffer_index = 0  # Circular buffer index
start_time = time.monotonic()  # Reference time

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

    # Store acceleration data in the circular buffer
    if ble_enabled:
        x, y, z = cp.acceleration
        timestamp = time.monotonic() - start_time  # **Relative timestamp**
        data_buffer[buffer_index] = f"{timestamp:.2f},{x:.2f},{y:.2f},{z:.2f}"
        buffer_index = (buffer_index + 1) % BUFFER_SIZE  # Circular buffer behavior

    # Check if BURST_INTERVAL has passed
    if ble_enabled and (time.monotonic() - start_time >= BURST_INTERVAL):
        # Send each line **individually** over BLE to ensure newline separation
        for line in data_buffer:
            if line:  # Ensure we don't send empty lines
                uart.write((line + "\n").encode("utf-8"))
                time.sleep(0.05)  # Small delay to prevent BLE congestion

        print(f"Sent {BUFFER_SIZE} data points in burst.")

        # Reset buffer for the next cycle
        data_buffer = [""] * BUFFER_SIZE  # Clear buffer
        buffer_index = 0
        start_time = time.monotonic()  # Reset reference time

    # Update button state
    button_a_previous = cp.button_a

    # Small delay for sampling rate
    time.sleep(SAMPLE_RATE)
