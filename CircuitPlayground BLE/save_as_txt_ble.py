import asyncio
from bleak import BleakClient, BleakScanner

# Replace "Your_Device_Name" with the exact name of your Circuit Playground Bluefruit
KNOWN_DEVICE_NAME = "CIRCUITPYb48a"  
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"  # Nordic UART Service UUID
UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # RX characteristic for reading data

async def run():
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

        def handle_rx(_, data):
            text = data.decode("utf-8")
            print(f"Received: {text}")
            with open("acceleration_data.txt", "a") as file:
                file.write(text)

        await client.start_notify(UART_RX_CHAR_UUID, handle_rx)

        print("Receiving data. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1)

asyncio.run(run())
