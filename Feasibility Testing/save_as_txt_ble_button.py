import asyncio
import time
from bleak import BleakClient, BleakScanner

# Replace "Your_Device_Name" with the exact name of your Circuit Playground Bluefruit
# KNOWN_DEVICE_NAME = "CIRCUITPYb48a"
KNOWN_DEVICE_NAME = "CIRCUITPYc67c"
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"  # Nordic UART Service UUID
UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # RX characteristic for reading data

# Global variables
file = None
file_open = False  # Track if the file is open
data_buffer = ""  # Buffer to accumulate parts of the data

# Function to create a new file with a timestamp
def create_new_file():
    patient_name = input("Enter the patient's name: ").strip().replace(" ", "_")
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

    # Process complete data (timestamp, x, y, z)
    while "," in data_buffer:
        # Look for a full data segment (timestamp,x,y,z)
        parts = data_buffer.split(",", 3)  # Limit to 4 parts (timestamp, x, y, z)
        
        print(f"Buffer: {data_buffer}")  # Debugging: See the accumulated buffer
        
        if len(parts) == 4:
            timestamp, x, y, z = parts
            print(f"Acceleration Data: {timestamp}, {x}, {y}, {z}")  # Debugging: Confirm data parsing

            # Write the complete data to the file if it's open
            if file_open:
                try:
                    file.write(f"{timestamp},{x},{y},{z}\n")
                    print(f"Data written to file: {timestamp},{x},{y},{z}")  # Debugging: Check if data is written
                except Exception as e:
                    print(f"Error writing data: {e}")

            # Reset the buffer to remove the processed data
            data_buffer = ""
        else:
            # Wait for more data if we don't have a complete message yet
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
