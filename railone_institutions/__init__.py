"""Institution-agnostic integration boundary for RailOne execution providers."""

from .manifest import CapabilityManifestSigner
from .models import (
    AdapterCertificationStatus,
    AdapterDescriptor,
    AdapterEnvironment,
    FinalityLevel,
    InstitutionAuthProfile,
    InstitutionCapabilityManifest,
    InstitutionExecutionInstruction,
    InstitutionOperation,
    InstitutionOutcome,
    InstitutionSubmissionResult,
    MessageStandard,
    SignedCapabilityManifest,
    TransportKind,
)
from .registry import AdapterEligibilityQuery, InstitutionAdapterRegistry
from .spi import InstitutionAdapter, InstitutionAdapterBridge

__all__ = [
    "AdapterCertificationStatus",
    "AdapterDescriptor",
    "AdapterEligibilityQuery",
    "AdapterEnvironment",
    "CapabilityManifestSigner",
    "FinalityLevel",
    "InstitutionAdapter",
    "InstitutionAdapterBridge",
    "InstitutionAdapterRegistry",
    "InstitutionAuthProfile",
    "InstitutionCapabilityManifest",
    "InstitutionExecutionInstruction",
    "InstitutionOperation",
    "InstitutionOutcome",
    "InstitutionSubmissionResult",
    "MessageStandard",
    "SignedCapabilityManifest",
    "TransportKind",
]
