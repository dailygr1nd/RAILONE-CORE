from xml.etree.ElementTree import Element, SubElement, tostring

def generate_iso(utt_id, amount, currency, rtt):
    root = Element("Document")
    tx = SubElement(root, "FIToFICstmrCdtTrf")

    grp = SubElement(tx, "GrpHdr")
    SubElement(grp, "MsgId").text = utt_id

    cdt = SubElement(tx, "CdtTrfTxInf")
    pmt = SubElement(cdt, "PmtId")
    SubElement(pmt, "EndToEndId").text = utt_id

    amt = SubElement(cdt, "IntrBkSttlmAmt", Ccy=currency)
    amt.text = str(amount)

    SubElement(cdt, "UETR").text = rtt.hex()

    return tostring(root).decode()