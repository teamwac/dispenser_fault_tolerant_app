# Fault-Tolerant Async Dispenser System

A robust, fault-tolerant industrial automation system for controlling dispensing units and elevator mechanisms through MQTT and Modbus communication.

## 🌟 Features

- **Fault-Tolerant Architecture**: Automatic service supervision and restart on failures
- **Asynchronous Processing**: High-performance async/await patterns for concurrent operations
- **MQTT Communication**: Distributed messaging for system coordination
- **Modbus RTU Integration**: Direct hardware control via serial communication
- **Modular Worker Design**: Extensible worker system for different device types
- **Real-time Monitoring**: Built-in status reporting and health checks
- **Comprehensive API**: AsyncAPI documentation for standardized interfaces

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Fault-Tolerant Supervisor                 │
│                      (Auto-restart on crash)               │
└─────────────────────────────────────────────────────────────┘
                              │
    ┌─────────────────────────┼─────────────────────────┐
    │                         │                         │
┌───▼───┐            ┌───────▼───────┐         ┌──────▼─────┐
│ MQTT  │            │  Dispenser    │         │  Elevator  │
│Manager│            │    Worker     │         │   Worker   │
└───────┘            └───────────────┘         └────────────┘
                              │                         │
                    ┌─────────▼─────────┐       ┌───────▼─────┐
                    │   Modbus RTU      │       │  Modbus RTU │
                    │ (COM12/USB0)      │       │ (SLAVE 1,2) │
                    │                   │       │             │
                    │ • Read/Write Regs │       │ • Homing    │
                    │ • Coil Operations │       │ • Movement  │
                    │ • Error Recovery  │       │ • Positioning│
                    └───────────────────┘       └─────────────┘
```

### Core Framework

- **AbstractService**: Base class for all supervised services
- **Worker**: Asynchronous worker with queue-based messaging
- **Supervisor**: Automatic restart mechanism for fault tolerance
- **MqttManager**: MQTT broker communication handler

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Modbus RTU compatible devices (dispenser unit, elevator system)
- MQTT broker (default: 192.168.2.197)
- Serial port access (COM12 on Windows, /dev/ttyUSB0 on Linux)

### Installation

```bash
# Clone the repository
git clone https://github.com/teamwac/dispenser_fault_tolerant_app.git
cd dispenser_fault_tolerant_app

# Install dependencies (if using uv)
uv sync

# Or with pip
pip install -r requirements.txt
```

### Configuration

Update the configuration in `main.py`:

```python
# Hardware Configuration
port = "COM12" if platform.system() == "Windows" else "/dev/ttyUSB0"
client = AsyncModbusSerialClient(
    framer=FramerType.RTU, 
    port=port, 
    baudrate=115200, 
    timeout=0.7, 
    retries=10
)

# MQTT Configuration
mqtt_manager = MqttManager("192.168.2.197", workers)
```

### Running the System
```bash
uv run main.py
```
or if you prefer manual setup

```bash
python main.py
```

## 📖 Usage

### MQTT Commands

The system responds to MQTT messages with the following topics and payloads:

#### Dispense Action
```bash
# Topic: storage/dispenser/{id}/action/dispense/in
# Payload:
{
  "req_id": "unique-request-id",
  "id": 1,
  "weight": 30
}

# Response: storage/dispenser/{id}/action/dispense/out
{
  "req_id": "unique-request-id",
  "status": "success",
  "weight": 30
}
```

#### Elevator Operations
```bash
# Deliver operation
# Topic: storage/dispenser/{id}/action/deliver/in
{
  "req_id": "unique-request-id",
  "id": 1
}

#response: storage/dispenser/{id}/action/deliver/out
{
  "req_id": "unique-request-id",
  "status": "success"
}
#-------------------------------

# Pick operation  
# Topic: storage/dispenser/{id}/action/pick/in
{
  "req_id": "unique-request-id"
}
# Response: storage/dispenser/{id}/action/pick/out
{
  "req_id": "unique-request-id",
  "status": "success"
}
#-------------------------------

# Rest operation
# Topic: storage/dispenser/{id}/action/rest/in
{
  "req_id": "unique-request-id"
}
#response: storage/dispenser/{id}/action/rest/out
{
  "req_id": "unique-request-id",
  "status": "success"
}
#-------------------------------

# Return operation
# Topic: storage/dispenser/{id}/action/return/in
{
  "req_id": "unique-request-id",
  "id": 1
}
# Response: storage/dispenser/{id}/action/return/out
{
  "req_id": "unique-request-id",
  "status": "success"
}

```

## 🔧 Development

### Project Structure

```
dispenser_fault_tolerant_app/
├── main.py                    # System entry point and configuration
├── my_workers.py             # Worker implementations (Dispenser, Elevator)
├── framework/
│   ├── core.py               # Base classes and supervisor
│   └── mqtt.py               # MQTT communication handler
├── asyncapi_doc.json         # AsyncAPI specification
├── test_script.py            # Basic testing utilities
└── modbus_useful_reference.py # Modbus communication reference
```

### Adding New Workers

1. **Create Worker Class**:
```python
from framework.core import Worker

class MyNewWorker(Worker):
    def __init__(self, name, client, slave_id=None):
        super().__init__(name)
        self.client = client
        self.slave_id = slave_id

    async def handle(self, msg):
        # Implement your worker logic here
        response = {"status": "success", "data": "processed"}
        return response
```

2. **Register Worker**:
```python
workers = {
    "my_worker": MyNewWorker("my_worker", client, slave_id=5),
}
```

3. **Add to Supervisor**:
```python
services = [
    workers["my_worker"],
    # ... other services
]
await asyncio.gather(*[asyncio.create_task(supervisor(s)) for s in services])
```

### Modbus Communication

The system provides helper methods for Modbus communication:

```python
# Read holding registers
regs = await worker.read_regs(slave=4, addr=0, n=1)

# Write registers
success = await worker.write_reg(slave=4, addr=0, val=100)

# Read input registers
inputs = await worker.read_inputs(slave=4, addr=0, count=1)

# Read/write coils
bits = await worker.read_coils(slave=4, addr=0, counts=1)
await worker.write_coil(slave=4, addr=0, val=True)

# Wait for condition
await worker.wait_until(slave=4, addr=0, val_ok=2, tmax=120)
```

## 🧪 Testing

### Manual Testing

Use the included test script for basic functionality testing:


```bash
python test_script.py
```

### Testing MQTT Commands

You can test the system using any MQTT client:

```bash
# Using mosquitto_pub
mosquitto_pub -h 192.168.2.197 -t storage/dispenser/1/action/dispense/in \
  -m '{"req_id":"test-123","id":1,"weight":25}'

# Subscribe to responses
mosquitto_sub -h 192.168.2.197 -t storage/dispenser/1/action/dispense/out
```

## 🔍 Troubleshooting

### Common Issues

**1. Modbus Connection Failed**
```
Failed to connect Modbus.
```
- Check serial cable connections
- Verify COM port (Windows) or device path (Linux)
- Confirm baud rate (115200) matches device settings

**2. MQTT Connection Issues**
```
MQTT connection failed
```
- Verify broker IP address and port
- Check network connectivity
- Ensure MQTT broker is running

**3. Worker Crashes**
```
[Supervisor] worker_name crashed: error. Restarting...
```
- Check hardware connections
- Review error logs for specific issues
- Verify Modbus device addresses

**4. Homing/Positioning Failures**
- Ensure mechanical limits are not exceeded
- Check for mechanical obstructions
- Verify motor enable signals

### Debug Mode

Enable detailed logging by modifying the logging level:

```python
logging.basicConfig(level=logging.DEBUG)
```

### Hardware Verification

Use the Modbus reference utility to test basic connectivity:

```python
# Check communication with specific slave
python -c "
import asyncio
from modbus_useful_refference import test_connection
asyncio.run(test_connection(slave_id=3))
"
```

## 📄 API Reference

### AsyncAPI Documentation

Full API documentation is available in `asyncapi_doc.json`. You can visualize it using:

- [AsyncAPI Studio](https://studio.asyncapi.com/)
- [ Swagger UI](https://swagger.io/tools/swagger-ui/) with converter
- [Redoc](https://redoc.ly/) with converter

### Worker Interface

All workers implement the following interface:

```python
class Worker(AbstractService):
    async def run(self):           # Main worker loop
    async def handle(self, msg):   # Process incoming messages
    async def send(self, msg):     # Send message to worker
    async def send_and_wait(self, msg):  # Send and wait for response
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow async/await patterns consistently
- Add proper error handling and logging
- Include type hints where possible
- Add comprehensive docstrings
- Test hardware interactions with proper cleanup

## 📊 Performance Considerations

- **Concurrency**: Workers run concurrently via asyncio
- **Fault Tolerance**: Automatic restart on failures with 2-second delay
- **Timeout Handling**: Configurable timeouts for all operations
- **Retry Logic**: Built-in retries for unreliable communications
- **Memory Management**: Queue-based message passing prevents memory leaks

## 🛡️ Safety Notes

- **Hardware Limits**: Always verify mechanical limits before operation
- **Emergency Stop**: Implement hardware emergency stops for production use
- **Monitoring**: Use status monitoring for early failure detection
- **Backup Systems**: Consider redundant systems for critical operations

## 📜 License

Not Avaiable 

## 👥 Authors

- **Tanim - W&C** - *Initial work* - [dispenser_fault_tolerant_app](https://github.com/teamwac/dispenser_fault_tolerant_app)

## 🙏 Acknowledgments

- AsyncAPI community for standardized documentation
- Python asyncio community for robust async patterns
- Modbus community for industrial communication standards

---

**Need Help?** Check out the troubleshooting section or create an issue in the repository.
