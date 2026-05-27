from dataclasses import dataclass


@dataclass
class ExecutionReceipt:

    railone_execution_id: str

    provider_reference: str

    canonical_state: str

    replay_protected: bool

    continuity_verified: bool

    execution_hash: str