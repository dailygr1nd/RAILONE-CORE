# ==========================================
# provider/provider_interface.py
# ==========================================

from abc import (
    ABC,
    abstractmethod
)


class ProviderInterface(ABC):

    @abstractmethod
    def execute(self, execution):
        pass

    @abstractmethod
    def query_status(
        self,
        provider_reference
    ):
        pass

    @abstractmethod
    def reverse(
        self,
        provider_reference
    ):
        pass