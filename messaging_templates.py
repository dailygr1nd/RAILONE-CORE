from datetime import datetime


def sender_success_message(amount, currency, recipient_name, masked_account, bank_name, ref_id, new_balance):
    return (
        f"Confirmed: Your transfer of {currency} {amount:,.2f} "
        f"to {recipient_name} ({masked_account}) at {bank_name} "
        f"via RailOne is successful. Ref: {ref_id}. "
        f"Your new balance is {currency} {new_balance:,.2f}. "
        f"Thank you for using RailOne"
    )


def receiver_success_bank_message(amount, currency, sender_name, ref_id):
    return (
        f"ALERT: You have received a transfer of "
        f"{currency} {amount:,.2f} from {sender_name}. "
        f"Ref: {ref_id}. The funds have been credited "
        f"to your account. RailOne."
    )


def receiver_success_wallet_message(amount, recipient_name, balance, ref_id):
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"Transaction Successful: {amount:,.2f} received "
        f"from RailOne for {recipient_name} on {today}. "
        f"Your mobile wallet balance is {balance:,.2f}. "
        f"Ref: {ref_id}."
    )


def rollback_sms_template(amount, currency, ref_id, new_balance):
    return (
        f"RailOne Update: Your transfer reversal of {currency} {amount:,.2f} "
        f"has been completed successfully. "
        f"The funds have been returned to your account. "
        f"Ref: {ref_id}. "
        f"New balance: {currency} {new_balance:,.2f}"
    )
