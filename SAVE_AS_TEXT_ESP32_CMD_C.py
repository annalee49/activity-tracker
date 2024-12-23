##############

# Reads BLE IMU data from the ESP32C3 Devkit 1 device
    # Automatically generates new files - new unqiue file names are produced by a time marker: day-month-year_hour-minute-second
    # Saves text files with timestamp, x,y,z accelerometer data like for the Bluefruit
        #timestamp starts at 0 and increments each time a notification is received (time is in seconds)

    # For future: could find a way to automatically detect ESP32 Adress?

##############


import asyncio
from bleak import BleakClient, BleakScanner
import time
import struct
import os

ESP32_ADDRESS = "40:4C:CA:8C:60:5A"  # Put your ESP32's address here

STANDARD_SERVICE_UUIDS = {
    "00001800-0000-1000-8000-00805f9b34fb",  # Generic Access Service
    "00001801-0000-1000-8000-00805f9b34fb",  # Generic Attribute Service
    "00001811-0000-1000-8000-00805f9b34fb",  # Alert Notification Service
    
}

# List to hold the discovered services and characteristics
discovered_services = {}
# Last time a notification was received
start_time = None
last_notification_time = time.time()

# File path (CHANGE PATIENT_NAME)
patient_name = 'name'

time_stamp = time.strftime("%d-%b-%Y_%H-%M-%S")  # Timestamp: day-month-year_hour-minute-second
filename = f"acceleration_data_{patient_name}_{time_stamp}.txt"

file_path = os.path.join(os.getcwd(), filename)

def parse_accel_data(data):
    """
    Parse the received data from the ESP32.

    Parameters
    ----------
    data : bytearray
        The data received from the ESP32.

    Returns
    -------
    tuple
        A tuple containing the acceleration values in m/s^2 (x, y, z) and the gyroscope values in deg/s (x, y, z).

    Notes
    -----
    The data format is assumed to be 6 bytes (2 for each axis) in the order of x, y, z for both the accelerometer and gyroscope.
    You may need to adjust the code based on the actual data format of your sensor.
    """
    flags = data[0]
    accel_x, accel_y, accel_z = struct.unpack('<3f', data)  # '<' for little-endian, 'f' for float
  
    return accel_x, accel_y, accel_z #, gyro_x, gyro_y, gyro_z

# Function to handle the incoming notifications
def notification_handler(sender: int, data: bytearray):
    """
    This function will be called when data is received as a notification.
    """
    global start_time
    global last_notification_time

    if start_time is None:
        start_time = time.time()

     # Calculate the relative time
    current_time = time.time()
    relative_time = float((current_time - start_time))  # Convert to milliseconds

    last_notification_time = time.time()  # Update the last received notification time

    accel_x, accel_y, accel_z = parse_accel_data(data)
    formatted_data = f"Accel: X: {accel_x:.4f} m/s², Y: {accel_y:.4f} m/s², Z: {accel_z:.4f} m/s²\n"
    #saved_data= [accel_x, accel_y ,accel_z, timestamp]
    timestamp = int(last_notification_time * 1000)  # Convert to milliseconds
    
    # For monitoring purposes - print recieved data
    print(f"Notification : {formatted_data.strip()}", "Relative time: ", relative_time)
    
    # write to file 
    with open(file_path, "a", encoding="utf-8") as file:
        file.write(f"{relative_time},{accel_x},{accel_y},{accel_z}\n")



async def discover_services_and_characteristics(address):
    async with BleakClient(address) as client:
        print(f"Connected to {address}")

        # Check if the client is connected
        if not client.is_connected:
            print("Failed to connect to the device.")
            return
       
        # Retrieve all the services
        services = await client.get_services()
        for service in services:
            service_uuid = service.uuid
            # Filter out standard services
            if service_uuid not in STANDARD_SERVICE_UUIDS:
                print(f"Found custom service: {service_uuid}")
                discovered_services[service_uuid] = []
                
                for char in service.characteristics:
                    char_uuid = char.uuid
                    char_props = char.properties
                    # Save only characteristics that support notifications or indications
                    if "notify" in char_props:
                        discovered_services[service_uuid].append(char_uuid)
                        print(f"  Found characteristic: {char_uuid}, Properties: {char_props}")
                    

    # Print saved custom services and characteristics
    print("\nCustom Services and Characteristics found:")
    for service_uuid, characteristics in discovered_services.items():
        print(f"Service UUID: {service_uuid}")
        for char_uuid in characteristics:
            print(f"  Characteristic UUID: {char_uuid}")


async def connect_and_subscribe():
    """
    Connect to the ESP32, subscribe to notifications, and save received data.
    """
    # Discover services and characteristics first
    await discover_services_and_characteristics(ESP32_ADDRESS)

    async with BleakClient(ESP32_ADDRESS) as client:
        print(f"Connected to {ESP32_ADDRESS}")

        # Check if we are connected
        if not client.is_connected:
            print("Failed to connect to the device.")
            return
        
        # Subscribe to notifications for each characteristic
        for service_uuid, characteristics in discovered_services.items():
            for char_uuid in characteristics:
                print(f"Subscribing to notifications for characteristic: {char_uuid}")
                await client.start_notify(char_uuid, notification_handler)
        
        # Keep the connection alive and listen for notifications
        #
        #
        #
        #
        await asyncio.sleep(30)  # Listen for 30 seconds, adjust as needed
        #
        #
        #
        #

        # Upon connecting, keep connection alive until cmd C
        try:
            while True:
                await asyncio.sleep(1)  # Prevent busy-waiting
        except KeyboardInterrupt:
            print("\nStopping notifications and exiting...")
            
        # Stop notifications when done
            for service_uuid, characteristics in discovered_services.items():
                for char_uuid in characteristics:
                    await client.stop_notify(char_uuid)
                print(f"Disconnected: Unsubscribed from {char_uuid}")

       
 
async def scan_and_connect():
    devices = await BleakScanner.discover()
    for device in devices:
        if device.name and "blecsc_sensor" in device.name.lower():
            print(f"Found ESP32: {device.name}, Address: {device.address}")
            await connect_and_subscribe()

if __name__ == "__main__":
    asyncio.run(scan_and_connect())
