# processingdispatcher.py

from smove_wallet import process_transfer as smove_transfer
from bank_ke import process_transfer as bank_ke_transfer
from bank_tz import process_transfer as bank_tz_transfer
from bank_ug import process_transfer as bank_ug_transfer
from psp_ke import process_transfer as psp_ke_transfer
from psp_tz import process_transfer as psp_tz_transfer
from psp_ug import process_transfer as psp_ug_transfer


DISPATCH_MAP = {
    "SMOVE": smove_transfer,
    "BANK_KE": bank_ke_transfer,
    "BANK_TZ": bank_tz_transfer,
    "BANK_UG": bank_ug_transfer,
    "PSP_KE": psp_ke_transfer,
    "PSP_TZ": psp_tz_transfer,
    "PSP_UG": psp_ug_transfer,
}


def dispatch(route, **kwargs):
    """
    Generic dispatcher used by routing / failover layer.
    """

    handler = DISPATCH_MAP.get(route["type"])

    if not handler:
        return {
            "success": False,
            "reason": f"NO_HANDLER_FOR_{route['type']}"
        }

    return handler(**kwargs)