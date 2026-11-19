from .identity import (
    IdentityAdmissionState, InstitutionApplication, InstitutionClass,
    InstitutionIdentityRecord, InstitutionOnboardingService,
    InMemoryInstitutionIdentityRepository,
)
"""Institution-agnostic integration boundary for RailOne execution providers."""

from .admission import (
    AuthoritativeSnapshotReader, EconomicEffectFenceReader,
    InstitutionalDispatchAdmissionGateway,
)
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
from .wrapper_store import DispatchWrapperStore, InMemoryDispatchWrapperStore
from .wrapper import (
    AuthoritativeDispatchSnapshot, CanonicalDispatchWrapper,
    DispatchWrapperService, SignedDispatchWrapper,
)

__all__ = [
    "IdentityAdmissionState", "InstitutionApplication", "InstitutionClass",
    "InstitutionIdentityRecord", "InstitutionOnboardingService",
    "InMemoryInstitutionIdentityRepository",
    "AuthoritativeSnapshotReader",
    "EconomicEffectFenceReader",
    "InstitutionalDispatchAdmissionGateway",
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
    "AuthoritativeDispatchSnapshot",
    "CanonicalDispatchWrapper",
    "DispatchWrapperService",
    "SignedDispatchWrapper",
    "DispatchWrapperStore",
    "InMemoryDispatchWrapperStore",
]
