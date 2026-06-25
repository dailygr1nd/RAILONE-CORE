# ==============================
# execution/execution_result.py
# RailOne Execution Result
# ==============================

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionResult:

    success: bool

    utt_id: str

    rtt_id: str

    attempt_number: int

    status: str

    provider: Optional[str] = None

    provider_reference: Optional[str] = None

    message: Optional[str] = None

    payload: Optional[dict] = None