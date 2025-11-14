import time
import sys
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


import platform
if platform.system() == 'Windows':
    port = 'COM12'
else:
    # Linux (Raspberry Pi)
    port = '/dev/ttyUSB0'
print(f"Using port: {port}")

# Create the client
client = ModbusSerialClient(
    port=port,
    baudrate=115200,
    parity='N',
    stopbits=1,
    bytesize=8,
    timeout=0.007,  # Increased timeout for Raspberry Pi
    
)

test_slave_id = 3
# Try connecting to the client
if not client.connect():
    print("Failed to connect! Check your port and permissions.")
    print("For Raspberry Pi, try: sudo chmod 666 /dev/ttyUSB0")
    sys.exit(1)
else:
    print("Successfully connected to Modbus device")

total_start = time.perf_counter()


try:
    for i in range(100):
        print(f"\n--- Round {i+1} ---")
        try:
            # Write single coil (address 9)
            write_single_coil_result = client.write_coil(address=9, value=True if i%2 == 0 else False, slave=test_slave_id)
            if write_single_coil_result.isError():
                print(f"Error write_single coil:", write_single_coil_result)
                break
            else:
                print(f"Successfully write_single coil: {True if i%2 == 0 else False}")

            # Read single coil (address 0)
            read_single_coil_result = client.read_coils(address=9, count=1, slave=test_slave_id)
            if not read_single_coil_result.isError():
                print(f"Single coil status: {read_single_coil_result.bits[0]}")
            else:
                print(f"Error reading single coil:", read_single_coil_result)
                break

            # Write Multiple coils 
            write_multiple_coils_result = client.write_coils(address=0, values=[False if i%2 == 0 else True, True if i%2 == 0 else False], slave=test_slave_id)
            if write_multiple_coils_result.isError():
                print(f"Error write_multiple coil:", write_multiple_coils_result)
                break
            else:
                print(f"Successfully write_multiple coils")
            
            # Read Multiple coils 
            read_coils_result = client.read_coils(address=0, count=2, slave=test_slave_id)
            if read_coils_result.isError():
                print(f"Error reading Multiple coils:", read_coils_result)
                break
            else:
                print(f"Successfully read Multiple coils: {read_coils_result.bits[:2]}")

            # Read input registers (address 0, count 2)
            read_input_result = client.read_input_registers(address=0, count=2, slave=test_slave_id)
            if not read_input_result.isError():
                print(f"Input registers values: {read_input_result.registers}")
            else:
                print(f"Error reading input registers:", read_input_result)
                break

            # Write single holding register (address 0, value 100)
            write_single_reg_result = client.write_register(address=0, value=100+i, slave=test_slave_id)
            if write_single_reg_result.isError():
                print(f"Error writing single holding register:", write_single_reg_result)
                break
            else:
                print(f"Successfully wrote single holding register: {100+i}")

            # Write multiple holding registers (address 1, values [200, 300])
            write_multiple_reg_result = client.write_registers(address=1, values=[200 + i , 300 + i], slave=test_slave_id)
            if write_multiple_reg_result.isError():
                print(f"Error writing multiple holding registers:", write_multiple_reg_result)
                break
            else:
                print(f"Successfully wrote multiple holding registers: [{200 + i}, {300 + i}]")

            # Read holding registers (address 0, count 3)
            read_holding_result = client.read_holding_registers(address=0, count=3, slave=test_slave_id)
            if not read_holding_result.isError():
                print(f"Holding registers values: {read_holding_result.registers}")
            else:
                print(f"Error reading holding registers:", read_holding_result)
                break

            # Add small delay between iterations for stability on Raspberry Pi
            # time.sleep(0.05)

        except ModbusException as e:
            print(f"Modbus error:", e)

    # Reset coil state before exiting
    write_single_coil_result = client.write_coil(address=9, value=False, slave=test_slave_id)
    if write_single_coil_result.isError():
        print(f"Error write_single coil:", write_single_coil_result)
    else:
        print(f"Successfully reset coil to False")

except KeyboardInterrupt:
    print("\nProgram interrupted by user")

finally:
    client.close()
    print("Connection closed")
    
    total_time = time.perf_counter() - total_start
    print(f"Total execution time: {total_time:.6f}s")
