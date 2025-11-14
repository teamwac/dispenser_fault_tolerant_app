import asyncio
import logging
from framework.core import supervisor
from framework.mqtt import MqttManager
from my_workers import StatusTask, DespenseUnitWorker, ElevatorWorker

logging.basicConfig(level=logging.INFO)
master_id = 1
async def main():
    from pymodbus.client import AsyncModbusSerialClient
    from pymodbus import FramerType
    import platform

    # --- Modbus Client Setup ---
    port = "COM12" if platform.system() == "Windows" else "/dev/ttyUSB0"
    client = AsyncModbusSerialClient(
        framer=FramerType.RTU, port=port, baudrate=115200, timeout=0.7, retries=10
    )

    if not await client.connect():
        print("Failed to connect Modbus.")
        return
    
    logging.info("Modbus connected.")
    # Initialize workers
    workers = {
        "dispense_1": DespenseUnitWorker("dispense_1", client, slave_id=3),
        "dispense_2": DespenseUnitWorker("dispense_2", client, slave_id=4),
        "elevator": ElevatorWorker("elevator", client, slave_id=1),
    }
    await workers["elevator"].do_homing(1)
    #await workers["elevator"].move_motor1(36000)
    await workers["elevator"].do_homing(2)
    #await workers["elevator"].move_motor1(0)
    #await workers["elevator"].do_homing(1)

    mqtt_manager = MqttManager("192.168.2.197", workers)


    # Define publish function for status task
    async def publish_func(lifetime):
        import json
        topic = f'dispenser/{workers["dispense_1"].name}/status'
        mqtt_manager.client.publish(topic, json.dumps(lifetime), qos=1)
    
    # additional Status Task for ViscousWorker
    status_task = StatusTask(workers["dispense_1"], publish_func=publish_func)


    services = [
        workers["dispense_1"],
        workers["dispense_2"],
        workers["elevator"],
        status_task,
        mqtt_manager
    ]

    # Supervise all
    await asyncio.gather(*[asyncio.create_task(supervisor(s)) for s in services])

if __name__ == "__main__":
    asyncio.run(main())