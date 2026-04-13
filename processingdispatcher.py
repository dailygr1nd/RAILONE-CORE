# processingdispatcher.py

import bank              # 👈 your original file
import bank_a
import bank_b
import psp


def process_route(route, amount):

    if route["type"] == "BANK_FAIL":
        return bank.process(amount)   # 👈 use your original logic

    elif route["type"] == "BANK_A":
        return bank_a.process(amount)

    elif route["type"] == "BANK_B":
        return bank_b.process(amount)

    elif route["type"] == "PSP":
        return psp.process(amount)