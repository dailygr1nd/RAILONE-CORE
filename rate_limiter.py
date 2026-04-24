import time

REQUEST_LOG = {}

LIMIT = 10  # per minute


def check_rate_limit(client_id):
    now = time.time()

    if client_id not in REQUEST_LOG:
        REQUEST_LOG[client_id] = []

    REQUEST_LOG[client_id] = [
        t for t in REQUEST_LOG[client_id] if now - t < 60
    ]

    if len(REQUEST_LOG[client_id]) >= LIMIT:
        return False

    REQUEST_LOG[client_id].append(now)
    return True