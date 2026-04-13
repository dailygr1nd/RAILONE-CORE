# handshake.py
import os
import hashlib
from datetime import datetime
from audit import append_log  # use your existing audit chain

LOG_FILE = "etk_handshake_logs.txt"  # Optional plain log file for debug

def run_handshake():
    print("\n🔐 Running Dual Handshake...")

    # Generate ETK (sender)
    etk_s = os.urandom(32)

    # Generate ETK (receiver)
    etk_r = hashlib.sha256(etk_s + b"receiver").digest()

    # Round-trip token
    rtt = hashlib.sha256(etk_s + etk_r).digest()

    # --------------------------
    # Log handshake to plain file (optional)
    # --------------------------
    with open(LOG_FILE, "a") as f:
        f.write(hashlib.sha256(rtt + etk_s + etk_r).hexdigest() + "\n")

    # --------------------------
    # Log handshake to audit.json with chained hash
    # --------------------------
    payload = {
        "rtt": rtt.hex(),
        "etk_sender": etk_s.hex(),
        "etk_receiver": etk_r.hex()
    }

    append_log("HANDSHAKE", payload)

    print("✅ Handshake complete")
    print("RTT:", rtt.hex()[:20], "...")

    return rtt