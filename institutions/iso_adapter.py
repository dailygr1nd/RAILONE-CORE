# ==========================================
# institutions/iso_adapter.py
# RailOne ISO 20022 Continuity Adapter
# ==========================================

from datetime import datetime

from uuid import uuid4

from xml.etree.ElementTree import (
    Element,
    SubElement,
    tostring
)


class ISO20022Adapter:

    # ======================================
    # PACS.008 CREDIT TRANSFER
    # ======================================
    @staticmethod
    def generate_pacs008(

        continuity_uid,

        utt_id,

        rtt_id,

        amount,

        currency,

        sender_institution,

        receiver_institution
    ):

        root = Element(
            "Document"
        )

        tx = SubElement(
            root,
            "FIToFICstmrCdtTrf"
        )

        # ==================================
        # GROUP HEADER
        # ==================================
        grp = SubElement(
            tx,
            "GrpHdr"
        )

        SubElement(
            grp,
            "MsgId"
        ).text = utt_id

        SubElement(
            grp,
            "CreDtTm"
        ).text = (
            datetime.utcnow()
            .isoformat()
        )

        # ==================================
        # CREDIT TRANSFER INFO
        # ==================================
        cdt = SubElement(
            tx,
            "CdtTrfTxInf"
        )

        pmt = SubElement(
            cdt,
            "PmtId"
        )

        SubElement(
            pmt,
            "InstrId"
        ).text = utt_id

        SubElement(
            pmt,
            "EndToEndId"
        ).text = continuity_uid

        # ==================================
        # ROUTE CONTINUITY
        # ==================================
        SubElement(
            cdt,
            "UETR"
        ).text = rtt_id

        # ==================================
        # AMOUNT
        # ==================================
        amt = SubElement(

            cdt,

            "IntrBkSttlmAmt",

            Ccy=currency
        )

        amt.text = str(amount)

        # ==================================
        # PARTICIPANTS
        # ==================================
        dbtr = SubElement(
            cdt,
            "Dbtr"
        )

        SubElement(
            dbtr,
            "Nm"
        ).text = sender_institution

        cdtr = SubElement(
            cdt,
            "Cdtr"
        )

        SubElement(
            cdtr,
            "Nm"
        ).text = receiver_institution

        return tostring(
            root,
            encoding="unicode"
        )

    # ======================================
    # PACS.002 STATUS REPORT
    # ======================================
    @staticmethod
    def generate_pacs002(
        continuity_event
    ):

        root = Element(
            "Document"
        )

        status = SubElement(
            root,
            "FIToFIPmtStsRpt"
        )

        grp = SubElement(
            status,
            "GrpHdr"
        )

        SubElement(
            grp,
            "MsgId"
        ).text = str(uuid4())

        SubElement(
            grp,
            "CreDtTm"
        ).text = (
            datetime.utcnow()
            .isoformat()
        )

        tx = SubElement(
            status,
            "TxInfAndSts"
        )

        SubElement(
            tx,
            "OrgnlInstrId"
        ).text = (
            continuity_event
            .railone_execution_id
        )

        SubElement(
            tx,
            "TxSts"
        ).text = (
            ISO20022Adapter
            .map_canonical_to_iso_status(

                continuity_event
                .canonical_state
            )
        )

        return tostring(
            root,
            encoding="unicode"
        )

    # ======================================
    # CANONICAL → ISO STATUS
    # ======================================
    @staticmethod
    def map_canonical_to_iso_status(
        canonical_state
    ):

        mappings = {

            "execution_settled":
                "ACSC",

            "execution_rejected":
                "RJCT",

            "execution_in_progress":
                "PDNG",

            "execution_timeout":
                "PDNG",

            "execution_reversed":
                "RVRS"
        }

        return mappings.get(
            canonical_state,
            "PDNG"
        )