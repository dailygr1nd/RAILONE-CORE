# ==============================
# provider/provider_result.py
# RailOne Provider Result
# ==============================

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderResult:

    success: bool

    provider: str

    provider_reference: Optional[str]

    latency_ms: int

    status: str

    message: Optional[str] = None

    payload: Optional[dict] = None