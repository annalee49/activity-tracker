import asyncio
import time
from bleak import BleakClient, BleakScanner

# Replace "Your_Device_Name" with the exact name of your Circuit Playground Bluefruit
KNOWN_DEVICE_NAME = "CIRCUITPYb48a"
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"  # Nordic UART Service UUID
UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # RX characteristic for reading data

# Global variables
file = None
file_open = False  # Track if the file is open
data_buffer = ""  # Buffer to accumulate parts of the data

# Function to create a new file with a timestamp
def create_new_file():
    patient_name = 'Andre_cane'
    timestamp = time.strftime("%Y%m%d_%H%M%S")  # Use timestamp for unique file names
    filename = f"acceleration_data_{patient_name}_{timestamp}.txt"
    return open(filename, "a")  # Open file in append mode to not overwrite

# Function to process received data
def handle_data(characteristic, data):
    global file, file_open, data_buffer
    data_str = data.decode("utf-8")

    print(f"Received data: {data_str}")  # Debugging: Check if data is being received

    # Skip button press/release data, don't write it to the file
    if "BUTTON_" in data_str:
        print(f"Skipping BUTTON data: {data_str}")  # Debugging: Show skipped button data
        # Handle button press/release to open/close the file
        if "PRESSED" in data_str:
            if not file_open:
                try:
                    file = create_new_file()
                    file_open = True
                    print(f"File opened: {file.name}")
                except Exception as e:
                    print(f"Error opening file: {e}")
            else:
                try:
                    file.close()
                    file_open = False
                    print(f"File saved and closed: {file.name}")
                except Exception as e:
                    print(f"Error closing file: {e}")
                    file_open = False
                    file = None  # Reset file reference
        return  # Skip processing button data

    # Accumulate all incoming data into the buffer
    data_buffer += data_str.strip()  # Strip any extra spaces or newlines

    # Process complete data in the format (elapsed_time, x, y, z)
    while "(" in data_buffer and ")" in data_buffer:
        # Look for a complete data segment enclosed in parentheses
        start_idx = data_buffer.find("(")
        end_idx = data_buffer.find(")")

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            # Extract the data inside the parentheses
            segment = data_buffer[start_idx + 1:end_idx]
            try:
                elapsed_time, x, y, z = map(float, segment.split(","))
                print(f"Parsed Data: elapsed_time={elapsed_time}, x={x}, y={y}, z={z}")

                # Write the complete data to the file if it's open
                if file_open:
                    try:
                        file.write(f"{elapsed_time:.2f},{x:.2f},{y:.2f},{z:.2f}\n")
                        print(f"Data written to file: {elapsed_time:.2f},{x:.2f},{y:.2f},{z:.2f}")
                    except Exception as e:
                        print(f"Error writing data: {e}")
            except ValueError as e:
                print(f"Error parsing data segment: {segment} - {e}")

            # Remove the processed segment from the buffer
            data_buffer = data_buffer[end_idx + 1:]
        else:
            # Wait for more data if the message is incomplete
            break


async def run():
    global file, file_open
    print("Scanning for devices...")
    devices = await BleakScanner.discover()
    cplay_device = None

    # Look for the specific known device
    for device in devices:
        if device.name == KNOWN_DEVICE_NAME:  # Exact match with known name
            cplay_device = device
            break

    if not cplay_device:
        print(f"No device found with the name '{KNOWN_DEVICE_NAME}'.")
        return

    print(f"Connecting to {cplay_device.name}...")
    async with BleakClient(cplay_device.address) as client:
        print(f"Connected to {cplay_device.name}")

        # Open the file at the start since the device is already in "ON" state
        if not file_open:
            try:
                file = create_new_file()
                file_open = True
                print(f"File opened for data collection: {file.name}")
            except Exception as e:
                print(f"Error opening file: {e}")

        # Subscribe to the RX characteristic to receive data
        await client.start_notify(UART_RX_CHAR_UUID, handle_data)

        # Keep the connection alive and listen for data
        try:
            while True:
                await asyncio.sleep(1)  # Keep the connection open and listen
        except KeyboardInterrupt:
            print("Disconnected.")
            # Close the file when the program ends (optional)
            if file:
                file.close()
                print(f"File saved: {file.name}")
            await client.stop_notify(UART_RX_CHAR_UUID)

# Run the asyncio event loop
asyncio.run(run())
