from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib
import json

app = FastAPI()

SECRET = "webhook_secret_dev"


def verify(signature, timestamp, payload):

    msg = f"{timestamp}.{json.dumps(payload, sort_keys=True)}".encode()
    expected = hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()

    return hmac.compare_digest(signature, expected)


@app.post("/webhook")
async def receive_webhook(request: Request):

    payload = await request.json()

    signature = request.headers.get("X-RailOne-Signature")
    timestamp = request.headers.get("X-RailOne-Timestamp")

    if not verify(signature, timestamp, payload):
        raise HTTPException(401, "INVALID_SIGNATURE")

    print("\n📩 VERIFIED WEBHOOK:")
    print(payload)

    return {"status": "ok"}