# ==========================================
# ledger/locking.py
# RailOne Continuity Locking
# ==========================================

from threading import Lock


class ContinuityLockManager:

    def __init__(self):

        self.execution_locks = {}

    def acquire_lock(
        self,
        continuity_uid
    ):

        if (
            continuity_uid
            not in self.execution_locks
        ):

            self.execution_locks[
                continuity_uid
            ] = Lock()

        self.execution_locks[
            continuity_uid
        ].acquire()

    def release_lock(
        self,
        continuity_uid
    ):

        if (
            continuity_uid
            in self.execution_locks
        ):

            self.execution_locks[
                continuity_uid
            ].release()


continuity_lock_manager = (
    ContinuityLockManager()
)