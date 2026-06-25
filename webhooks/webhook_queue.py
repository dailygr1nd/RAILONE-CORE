# ==============================
# webhook_queue.py (TRACKED)
# ==============================

import redis
import json
import time

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

QUEUE = "railone:webhooks"
DEAD_LETTER = "railone:webhooks:dead"


def enqueue_webhook(job):
    job["attempts"] = 0
    job["created_at"] = int(time.time())
    r.lpush(QUEUE, json.dumps(job))


def dequeue_webhook():
    data = r.rpop(QUEUE)
    return json.loads(data) if data else None


def requeue_webhook(job):
    job["attempts"] += 1
    job["last_attempt"] = int(time.time())
    r.lpush(QUEUE, json.dumps(job))


def send_to_dead_letter(job):
    job["failed_at"] = int(time.time())
    r.lpush(DEAD_LETTER, json.dumps(job))