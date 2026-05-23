# ==============================
# iso_adapter.py
# ==============================

from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring


def _iso_ts():
    return datetime.utcnow().isoformat()


# --------------------------------
# pacs.008 (Credit Transfer)
# --------------------------------
def build_pacs008(tx: dict) -> str:
    """
    Minimal ISO 20022 pacs.008 generator
    """

    doc = Element("Document")
    cdt = SubElement(doc, "FIToFICstmrCdtTrf")

    # Group Header
    grp = SubElement(cdt, "GrpHdr")
    SubElement(grp, "MsgId").text = tx["utt_id"]
    SubElement(grp, "CreDtTm").text = _iso_ts()
    SubElement(grp, "NbOfTxs").text = "1"

    # Transaction Info
    txinf = SubElement(cdt, "CdtTrfTxInf")

    # Payment Identification
    pmtid = SubElement(txinf, "PmtId")
    SubElement(pmtid, "EndToEndId").text = tx["utt_id"]

    # Amount
    amt = SubElement(txinf, "IntrBkSttlmAmt", Ccy=tx["currency_to"])
    amt.text = str(tx["net_amount"])

    SubElement(txinf, "IntrBkSttlmDt").text = datetime.utcnow().date().isoformat()

    # Debtor (Sender)
    dbtr = SubElement(txinf, "Dbtr")
    SubElement(dbtr, "Nm").text = tx["sender_account"]

    # Creditor (Receiver)
    cdtr = SubElement(txinf, "Cdtr")
    SubElement(cdtr, "Nm").text = tx["receiver_account"]

    return tostring(doc, encoding="unicode")


# --------------------------------
# pacs.002 (Status Report)
# --------------------------------
def build_pacs002(tx: dict) -> str:
    """
    Status mapping:
    PENDING → PDNG
    SETTLED → ACCC
    FAILED  → RJCT
    """

    status_map = {
        "PENDING": "PDNG",
        "SETTLED": "ACCC",
        "FAILED": "RJCT"
    }

    doc = Element("Document")
    rpt = SubElement(doc, "FIToFIPmtStsRpt")

    grp = SubElement(rpt, "GrpHdr")
    SubElement(grp, "MsgId").text = f"STS-{tx['utt_id']}"
    SubElement(grp, "CreDtTm").text = _iso_ts()

    txinf = SubElement(rpt, "TxInfAndSts")
    SubElement(txinf, "OrgnlEndToEndId").text = tx["utt_id"]

    SubElement(txinf, "TxSts").text = status_map.get(tx["status"], "PDNG")

    return tostring(doc, encoding="unicode")