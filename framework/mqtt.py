import asyncio
import json
import logging
from gmqtt import Client as MQTTClient

logger = logging.getLogger(__name__)

class MqttManager:
    def __init__(self, broker_host, workers, master_id=1, client_id="dispenser-client", subscribe_qos=1, subscribe_retain=False):
        self.name = "MqttManager"
        self.client = MQTTClient(client_id)
        self.master_id = master_id
        self.broker_host = broker_host
        self.workers = workers
        self.subscribe_qos = subscribe_qos
        self.subscribe_retain = subscribe_retain
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
        self._stop_event = asyncio.Event()

    def on_connect(self, client, flags, rc, properties):
        logger.info("[MQTT] Connected to broker.")
        for worker_name in self.workers.keys():
            topic = f"storage/dispenser/{self.master_id}/action/+/in"  # topic format storage/dispenser/{self.master_id}/action/dispense/in
            logger.info(f"[MQTT] Subscribing to {topic}")
            self.client.subscribe(topic, qos=self.subscribe_qos, retain=self.subscribe_retain)

    def on_disconnect(self, client, packet, exc=None):
        logger.info("[MQTT] Disconnected from broker.")

    def on_subscribe(self, client, mid, qos, properties):
        logger.info(f"[MQTT] Subscribed with MID {mid} and QoS {qos}")

    async def on_message(self, client, topic, payload, qos, properties):
        logger.info(f"[MQTT] Received message on {topic}: {payload.decode()}")
        try:
            msg = json.loads(payload)
            worker_name = topic.split('/')[4] # storage/dispenser/1/action/dispense/in
            task = worker_name
            if "id" in msg and "weight" in msg and "req_id" in msg:
                worker_name = f"dispense_{msg['id']}"
                print("Key exists! worker_name:", worker_name, "id:", msg["id"], "worker name :", worker_name)
            
            elif "req_id" in msg and (worker_name == "deliver" or worker_name == "rest" or worker_name == "pick" or worker_name == "return"):
                worker_name = "elevator"
                msg["task"] = task
                
            if worker_name in self.workers:
                worker = self.workers[worker_name]
                response = await worker.send_and_wait(msg)
                print("[before processing] Response from worker:", response)
                response_topic = f"storage/dispenser/{self.master_id}/action/{response['action']}/out" # storage/dispenser/1/action/dispense/out
                logger.info(f"[MQTT] Publishing response to {response_topic}: {response}")
                self.client.publish(response_topic, json.dumps(response["data"]), qos=1)
            else:
                logger.warning(f"[MQTT] No worker found for topic: {topic}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"[MQTT] Error processing message: {e}")
        return 0

    async def run(self):
        logger.info(f"[MQTT] Connecting to broker at {self.broker_host}...")
        try:
            await self.client.connect(self.broker_host)
            await self._stop_event.wait()
        except Exception as e:
            logger.error(f"[{self.name}] Connection or runtime error: {e}")
            raise
        finally:
            logger.info(f"[{self.name}] Disconnecting from broker.")
            await self.client.disconnect()

    def stop(self):
        self._stop_event.set()