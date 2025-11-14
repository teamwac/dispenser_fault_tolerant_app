from framework.core import Worker
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

class DespenseUnitWorker(Worker):
    def __init__(self, name, client, slave_id=None):
        super().__init__(name)
        self.client = client
        self.slave_id = slave_id
    async def read_regs(self, slave, addr, n=1):
        r = await self.client.read_holding_registers(address=addr, count=n, device_id=slave)
        return r.registers if (r is not None and not r.isError()) else None

    async def write_reg(self, slave, addr, val):
        if not isinstance(val, list):
            val = [val]
        r = await self.client.write_registers(address=addr, values = val, device_id=slave)
        return (r is not None and not r.isError())

    async def read_holding(self, slave, addr, count=1):
        r = await self.client.read_holding_registers(address=addr, count=count, device_id =slave)
        return None if r.isError() else r.registers

    async def read_inputs(self, slave = 4, addr =0, count=1):
        r = await self.client.read_input_registers(address=addr, count=count, device_id =slave)
        return None if r.isError() else r.registers

    async def wait_until(self, slave, addr, val_ok, tmax=90, poll=0.3):
        t0 = time.time()
        while time.time() - t0 < tmax:
            r = await self.read_regs(slave, addr, 1)
            if r is not None and r[0] == val_ok:
                return True
            await asyncio.sleep(poll)
        return False


    async def read_coils(self, default_slave, addr, counts=1):
        r = await self.client.read_coils(address=addr, count=counts, device_id= default_slave)
        return None if r.isError() else r.bits

    async def write_coil(self, default_slave, addr, val):
        r = await self.client.write_coils(address=addr, values = [val], device_id = default_slave)
        result  = await self.client.write_coil(0, True, device_id=4)
        return not r.isError()

    async def despensing_action(self, SLAVE_ID = 4, HR_CMD = 0, IR_WEIGHT = 0, COIL_TARE = 0, TARGET_GRAMS = 30, TIMEOUT_S = 180):
        print(f"⏱️ Requesting TARE (coil[0]=1)...")
        if not await self.write_coil(SLAVE_ID, COIL_TARE, True):
            print(f"❌ Failed to set coil[0]=1 (tare request)")

        # wait until slave clears coil[0] → tare complete
        t0 = time.time()
        while True:
            bits = await self.read_coils(SLAVE_ID, COIL_TARE, 1)
            if bits and not bits[0]:
                print(f"✅ TARE done (coil cleared).")
                break
            if time.time() - t0 > 3.0:
                print(f"⚠️ Timeout waiting for TARE to finish.")
                break
            await asyncio.sleep(0.1)

        # optional: check weight (should be ~0)
        ri = await self.read_regs(slave= SLAVE_ID, addr= IR_WEIGHT, n= 1)
        w0 = ri[0] if ri else None
        print(f"Weight after TARE: {w0} g\n")

        # --- Start dispense ---
        print(f"▶ Starting dispense: target {TARGET_GRAMS} g")
        if not await self.write_reg(slave = SLAVE_ID, addr= HR_CMD, val= [1, TARGET_GRAMS]):
            print(f"❌ Failed to write CMD/TARGET.")

        print(f"✅ CMD=1, TARGET={TARGET_GRAMS} written.\n")

        # --- Monitor loop ---
        t0 = time.time()
        stable_err = 0
        last_w = None

        while True:
            hr = await self.read_holding(slave= SLAVE_ID, addr=HR_CMD, count= 1)
            ir = await self.read_inputs(slave = SLAVE_ID, addr = IR_WEIGHT, count= 1)
            
            cmd = hr[0] if hr else None
            w   = ir[0] if ir else None

            if cmd is None or w is None:
                stable_err += 1
                if stable_err > 5:
                    print(f"⚠️ Communication lost repeatedly – aborting.")
                    break
                await asyncio.sleep(0.3)
                continue
            stable_err = 0

            if w != last_w:
                print(f"   CMD={cmd}, Weight={w} g", end="\r", flush=True)
                last_w = w

            if cmd == 0:
                print(f"\n✅ Dispense complete (CMD=0). Final weight: {w} g.")
                break

            if time.time() - t0 > TIMEOUT_S:
                print(f"\n⏰ Timeout after {TIMEOUT_S}s, forcing CMD=0.")
                await self.write_reg(slave= SLAVE_ID, addr= HR_CMD, val= [0])
                break
            
            await asyncio.sleep(0.3)
        return w



    async def handle(self, msg):
        future = None
        if isinstance(msg, tuple):
            msg, future = msg
            print("Tuple msg received:", msg)
            print("Tuple future received:", future)
           
        required_fields = {"req_id", "id", "weight"}
        if not required_fields.issubset(msg.keys()):
            response = {"action":"dispense", "data": {"status": "error", "message": "Missing required fields."}}
            logger.warning(f"[{self.name}] {response['data']['message']}")
            if future:
                future.set_result(response)
            return response
        
        if msg["req_id"] == "crash":
            #raise RuntimeError(f"[{self.name}] intentional crash triggered!")
            21 / 0 # trigger ZeroDivisionError

        print("Received msg:", msg)
        weight = 0
        weight = await self.despensing_action(SLAVE_ID = self.slave_id , HR_CMD = 0, IR_WEIGHT = 0, COIL_TARE = 0, TARGET_GRAMS = msg["weight"], TIMEOUT_S = 180)
        print(f"Weight after dispense: {weight} g")
        if weight >= msg["weight"]:
            response = {"action":"dispense", "data": {"req_id": msg["req_id"], "status": "success", "weight": weight}}
        else:
            response = {"action":"dispense", "data": {"req_id": msg["req_id"], "status": "error", "weight": weight}}

        logger.warning(f"[{self.name}] {response['data']}")
        if future:
            future.set_result(response)
        return response


class ElevatorWorker(Worker):
    def __init__(self, name, client, slave_id=None):
        super().__init__(name)
        self.client = client
        self.slave_1_id = slave_id
        self.slave_2_id = slave_id + 1
        self.HR = {
                    1: {  # SLAVE 1 → motor vertical
                        "HOMING":       0,
                        "WORK_POS_H":   1,
                        "WORK_POS_L":   2,
                        "MOVE_CMD":     3,
                        "MOVE_TARGET_H":4,
                        "MOVE_TARGET_L":5,
                        "MOVE_STATUS":  6,
                    },
                    2: {  # SLAVE 2 → módulo elevador/telescópio (exemplo)
                        "HOMING": 10,
                        "M2_CMD": 50, "M2_TGT": 51, "M2_STS": 52,
                        "M3_CMD": 53, "M3_TGT": 54, "M3_STS": 55,
                    },
                }

    async def read_regs(self, slave, addr, n=1):
        r = await self.client.read_holding_registers(address=addr, count=n, device_id=slave)
        return r.registers if (r is not None and not r.isError()) else None

    async def write_reg(self, slave, addr, val):
        if not isinstance(val, list):
            val = [val]
        r = await self.client.write_registers(address=addr, values = val, device_id=slave)
        return (r is not None and not r.isError())

    async def read_holding(self, slave, addr, count=1):
        r = await self.client.read_holding_registers(address=addr, count=count, device_id =slave)
        return None if r.isError() else r.registers

    async def read_inputs(self, slave = 4, addr =0, count=1):
        r = await self.client.read_input_registers(address=addr, count=count, device_id =slave)
        return None if r.isError() else r.registers

    async def wait_until(self, slave, addr, val_ok, tmax=90, poll=0.3):
        t0 = time.time()
        while time.time() - t0 < tmax:
            r = await self.read_regs(slave, addr, 1)
            if r is not None and r[0] == val_ok:
                return True
            await asyncio.sleep(poll)
        return False


    async def read_coils(self, default_slave, addr, counts=1):
        r = await self.client.read_coils(address=addr, count=counts, device_id= default_slave)
        return None if r.isError() else r.bits

    async def write_coil(self, default_slave, addr, val):
        r = await self.client.write_coils(address=addr, values = [val], device_id = default_slave)
        result  = await self.client.write_coil(0, True, device_id=4)
        return not r.isError()

    async def do_homing(self, slave):
        print("do_homing called: ", slave)
        addr = self.HR[slave]["HOMING"]
        print(f"\n[SLAVE {slave}] Iniciar homing (HR{addr})")
        await self.write_reg(slave, addr, 1)
        ok = await self.wait_until(slave, addr, 2, tmax=120)
        print("   → concluído" if ok else "   ⚠ timeout")

    async def move_motor1(self, target):
        """
        Movimento do motor vertical em ticks relativos ao home.
        target: signed 32-bit (pode ser negativo, pode ser > 65535).
        """
        orig_target = target
        if target < 0:
            target &= 0xFFFFFFFF  # 2's complement

        high = (target >> 16) & 0xFFFF
        low  = target & 0xFFFF

        print(f"\n[SLAVE 1] M1 -> {orig_target} ticks (high={high}, low={low})")

        # limpar status
        await self.write_reg(1, self.HR[1]["MOVE_STATUS"], 0)

        # escrever alvo 32-bit (2x FC06)
        await self.write_reg(self.slave_1_id, self.HR[1]["MOVE_TARGET_H"], high)
        await self.write_reg(self.slave_1_id, self.HR[1]["MOVE_TARGET_L"], low)

        # debug: ler de volta
        r = await self.read_regs(self.slave_1_id, self.HR[1]["MOVE_TARGET_H"], 2)
        print(f"[DEBUG][M1] HR4-5 lidos: {r}")

        # disparar comando
        await self.write_reg(self.slave_1_id, self.HR[1]["MOVE_CMD"], 1)

        ok = await self.wait_until(self.slave_1_id, self.HR[1]["MOVE_STATUS"], 2, tmax=120)
        print("   → alvo atingido" if ok else "   ⚠ timeout")

    async def move_motor2(self, target):
        """
        Exemplo de comando 16-bit (antigo) para slave 2.
        Aqui ainda tratamos como 16-bit signed em 1 reg.
        """
        print(f"\n[SLAVE 2] M2 -> {target}")
        await self.write_reg(self.slave_2_id, self.HR[2]["M2_STS"], 0)

        # Converter signed para unsigned 16-bit (Modbus)
        modbus_val = target & 0xFFFF

        await self.write_reg(self.slave_2_id, self.HR[2]["M2_TGT"], modbus_val)
        await self.write_reg(self.slave_2_id, self.HR[2]["M2_CMD"], 1)
        ok = await self.wait_until(self.slave_2_id, self.HR[2]["M2_STS"], 2, tmax=120)
        print("   → alvo atingido" if ok else "   ⚠ timeout")

    async def move_motor3(self, target):
        """
        Outro exemplo 16-bit direto para slave 2.
        """
        print(f"\n[SLAVE 2] M3 -> {target}")
        await self.write_reg(self.slave_2_id, self.HR[2]["M3_STS"], 0)
        await self.write_reg(self.slave_2_id, self.HR[2]["M3_TGT"], target & 0xFFFF)
        await self.write_reg(self.slave_2_id, self.HR[2]["M3_CMD"], 1)
        ok = await self.wait_until(self.slave_2_id, self.HR[2]["M3_STS"], 2, tmax=120)
        print("   → alvo atingido" if ok else "   ⚠ timeout")

    async def handle(self, msg):
        future = None
        if isinstance(msg, tuple):
            msg, future = msg
            print("Tuple msg received:", msg)
            print("Tuple future received:", future)
           
        required_fields = {"req_id"}
        if not required_fields.issubset(msg.keys()):
            response = {"action":"dispense", "data": {"status": "error", "message": "Missing required fields."}}
            logger.warning(f"[{self.name}] {response['data']['message']}")
            if future:
                future.set_result(response)
            return response
        
        if msg["req_id"] == "crash":
            #raise RuntimeError(f"[{self.name}] intentional crash triggered!")
            21 / 0 # trigger ZeroDivisionError

        print("Received msg:", msg)
        if msg["task"] == "deliver" and "id" in msg:
            try:
                #await self.do_homing(1)
                if msg["id"] % 2 == 1:
                    telescope_rotation = 19800
                elif msg["id"] % 2 == 0:
                    telescope_rotation = 11500
        
                await self.move_motor1(5000)
                await self.move_motor3(telescope_rotation)
                await self.move_motor2(-15000)
                await self.move_motor1(1500)
                await self.move_motor2(0) 
                await self.move_motor3(0)
                await self.move_motor1(36000)
                await self.move_motor2(29000) # close_grip
                response = {"action":"deliver", "data": {"req_id": msg["req_id"], "status": "success"}}
            except Exception as e:
                response = {"action":"deliver", "data": {"req_id": msg["req_id"], "status": "error", "message": str(e)}}

        elif msg["task"] == "rest":
            try:
                await self.move_motor1(39000)
                await self.move_motor2(0)
                await self.move_motor1(-500)
                await self.do_homing(1)
            #await self.move_motor2(29000) # after gripper grips the object
                response = {"action":"rest", "data": {"req_id": msg["req_id"], "status": "success"}}
            except Exception as e:
                response = {"action":"rest", "data": {"req_id": msg["req_id"], "status": "error", "message": str(e)}}

        elif msg["task"] == "pick":
            try:
                await self.move_motor1(39000)
                await self.move_motor2(29000)
                await self.move_motor1(37000)
                response = {"action":"pick", "data": {"req_id": msg["req_id"], "status": "success"}}
            except Exception as e:
                response = {"action":"pick", "data": {"req_id": msg["req_id"], "status": "error", "message": str(e)}}

        elif msg["task"] == "return" and "id" in msg:

            if msg["id"] % 2 == 1:
                telescope_rotation = 19800
            elif msg["id"] % 2 == 0:
                telescope_rotation = 11500
            try:
                await self.move_motor2(0)
                await self.move_motor1(0)
                await self.do_homing(1)
                await self.move_motor1(1500) 
                await self.move_motor3(int(telescope_rotation))
                await self.move_motor2(-15000)
                await self.move_motor1(5000) 
                await self.move_motor2(0)
                await self.move_motor3(0)
                await self.move_motor1(0)

                response = {"action":"return", "data": {"req_id": msg["req_id"], "status": "success"}}
            except Exception as e:
                response = {"action":"return", "data": {"req_id": msg["req_id"], "status": "error", "message": str(e)}}

        logger.warning(f"[{self.name}] {response['data']}")
        if future:
            future.set_result(response)
        return response

class StatusTask:
    def __init__(self, worker, publish_func=None):
        self.worker = worker
        self.name = f"{worker.name}_status_task"
        self.publish_func = publish_func  
    async def run(self):
        while True:
            # If you want to publish, call self.publish_func here!
            # Or just log:
            #logger.info(f"[{self.worker.name}] Status: {self.worker.lifetime}")
            if self.publish_func:
                logger.info(f"[{self.worker.name}] Status: running")
                await self.publish_func({"status": "ok", "message": "Status updated."})  # <-- publish!
            await asyncio.sleep(20)  # Publish every 1 second