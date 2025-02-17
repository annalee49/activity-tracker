import asyncio
import time
from bleak import BleakClient, BleakScanner

# Known device names
KNOWN_DEVICE_NAMES = ["CIRCUITPYb48a", "CIRCUITPYc67c"]
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"  # Nordic UART Service UUID
UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # RX characteristic for reading data

# Global dictionaries to manage files and states
files = {}
file_open = {}
transmission_active = {}
patient_names = {}

# Prompt for the patient name for each new connection
def get_patient_name(device_name):
    patient_name = input(f"Enter the patient's name for {device_name}: ").strip().replace(" ", "_")
    patient_names[device_name] = patient_name
    return patient_name

# Create a new file for a device with a timestamp
def create_new_file(device_name):
    patient_name = patient_names.get(device_name) or get_patient_name(device_name)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{device_name}_{patient_name}_acceleration_data_{timestamp}.txt"
    return open(filename, "a")

# Process received data
def handle_data(device_name):
    def inner_handle(characteristic, data):
        global files, file_open, transmission_active
        data_str = data.decode("utf-8").strip()
        
        # Debugging: Show received data
        print(f"{device_name} Received data: {data_str}")

        # Handle button press events
        if "BUTTON_" in data_str:
            if "PRESSED" in data_str:
                if transmission_active.get(device_name, False):
                    # Stop transmission and close the file
                    try:
                        files[device_name].close()
                        file_open[device_name] = False
                        transmission_active[device_name] = False
                        print(f"File closed for {device_name}: {files[device_name].name}")
                    except Exception as e:
                        print(f"Error closing file for {device_name}: {e}")
                else:
                    # Prompt for patient name and open a new file
                    try:
                        patient_names[device_name] = get_patient_name(device_name)
                        files[device_name] = create_new_file(device_name)
                        file_open[device_name] = True
                        transmission_active[device_name] = True
                        print(f"New file opened for {device_name}: {files[device_name].name}")
                    except Exception as e:
                        print(f"Error opening new file for {device_name}: {e}")
            return

        # Write data to the file if transmission is active
        if transmission_active.get(device_name, False):
            try:
                # Timestamp synced to the computer's time
                timestamp = time.strftime("%H:%M:%S")
                files[device_name].write(f"{timestamp},{data_str}\n")
                print(f"Data written for {device_name}: {timestamp},{data_str}")
            except Exception as e:
                print(f"Error writing data for {device_name}: {e}")

    return inner_handle

# Connect to a single device
async def connect_to_device(device):
    device_name = device.name
    try:
        async with BleakClient(device.address) as client:
            print(f"Connected to {device_name}")

            # Prompt for patient name and open the initial file
            patient_names[device_name] = get_patient_name(device_name)
            files[device_name] = create_new_file(device_name)
            file_open[device_name] = True
            transmission_active[device_name] = True
            print(f"Initial file opened for {device_name}: {files[device_name].name}")

            # Subscribe to notifications
            await client.start_notify(UART_RX_CHAR_UUID, handle_data(device_name))

            # Keep the connection alive
            while True:
                await asyncio.sleep(1)

    except Exception as e:
        print(f"Failed to connect to {device_name}: {e}")
    finally:
        # Ensure the file is closed
        if file_open.get(device_name, False):
            try:
                files[device_name].close()
                print(f"File closed for {device_name}: {files[device_name].name}")
            except Exception as e:
                print(f"Error closing file for {device_name}: {e}")
            file_open[device_name] = False
            transmission_active[device_name] = False

# Main function
async def run():
    print("Scanning for devices...")
    devices = await BleakScanner.discover()

    # Find target devices
    target_devices = [device for device in devices if device.name in KNOWN_DEVICE_NAMES]
    if not target_devices:
        print(f"No devices found with names: {KNOWN_DEVICE_NAMES}")
        return

    # Create tasks to connect to each device
    tasks = [connect_to_device(device) for device in target_devices]

    # Run all tasks concurrently
    await asyncio.gather(*tasks)

# Run the asyncio event loop
if __name__ == "__main__":
    asyncio.run(run())
