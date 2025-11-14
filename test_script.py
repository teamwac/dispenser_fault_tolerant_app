import asyncio
import uuid
import json
from gmqtt import Client as MQTTClient

# Fill in with your MQTT broker host (and credentials if needed)
HOST = '192.168.2.197'

# Topics and base payloads (use placeholders for req_id)
TOPICS = [
   # "storage/dispenser/1/action/dispense/in",
    "storage/dispenser/1/action/deliver/in",
    "storage/dispenser/1/action/rest/in",
    "storage/dispenser/1/action/pick/in",
    "storage/dispenser/1/action/return/in"
]

PAYLOADS = [
    #{"id": 2, "weight": 20},
    {"id": 2},
    {},
    {},
    {"id": 2}
]

# Track of sent req_ids
sent_req_ids = {}

# Out topics to subscribe
OUT_TOPICS = [topic.replace('/in', '/out') for topic in TOPICS]

def on_connect(client, flags, rc, properties):
    print("Connected!")

    for topic in OUT_TOPICS:
        print(f"Subscribing to {topic}")
        client.subscribe(topic)

async def main():
    client = MQTTClient("abba_tanim_test_client")
    client.on_connect = on_connect

    # Track responses
    def on_message(client, topic, payload, qos, properties):
        data = json.loads(payload)
        req_id = data.get('req_id')
        if req_id in sent_req_ids:
            print(f"Response for req_id={req_id} on {topic}:", data)
        else:
            print(f"Ignored message on {topic} (unknown req_id):", data)
    client.on_message = on_message

    await client.connect(HOST)

    # Publish all messages
    for topic, extra_payload in zip(TOPICS, PAYLOADS):
        req_id = str(uuid.uuid4())
        pl = {"req_id": req_id, **extra_payload}
        sent_req_ids[req_id] = topic
        print(f"Publishing to {topic}:", pl)
        client.publish(topic, json.dumps(pl), qos=1)

    # Wait to receive responses (adjust sleep as per expected return timing)
    while True:
        await asyncio.sleep(20)
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())