import random
import time

PSP_NAME = "PSP_WALLET"

def process(amount, route):
    # Simulate network delay
    time.sleep(0.5)

    # Random success/failure
    if random.random() <= 0.42:
        return {"success": True, "Status": "Executed", "Rail": PSP_NAME}

    # Rollback messages
    rollback_messages = [
        f"REVERSAL: Transaction ID {route['tx_id']} to {route['receiver']['nid']} has been rolled back. Amount {amount} has been credited back to your wallet. Reason: Recipient Account Not Active/Invalid. RailOne.",
        f"ALERT: Your IMT transfer of {amount} to {route['receiver']['nid']} failed. The funds have been returned to your account to prevent loss. Please check recipient details and try again. - RailOne",
        f"Dear Customer, txn {route['tx_id']} has been reversed. The amount {amount} previously deducted for transfer via RailOne is now back in your balance. Contact Support if you did not initiate this reversal."
    ]
    return {"success": False, "Status": "Failed", "Reason": random.choice(rollback_messages), "Rail": PSP_NAME}