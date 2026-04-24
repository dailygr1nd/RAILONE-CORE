import redis
import json

r = redis.Redis(host="localhost", port=6379)

QUEUE = "railone:webhooks"


def enqueue_webhook(payload):
    r.lpush(QUEUE, json.dumps(payload))


def dequeue_webhook():
    data = r.rpop(QUEUE)
    return json.loads(data) if data else None