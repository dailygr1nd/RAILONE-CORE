from abc import ABC, abstractmethod


class RailOneAdapter(ABC):

    @abstractmethod
    def initiate_execution(self, payload):
        pass

    @abstractmethod
    def query_execution_state(self, execution_id):
        pass

    @abstractmethod
    def verify_execution(self, payload):
        pass

    @abstractmethod
    def reconcile_execution(self, execution_id):
        pass

    @abstractmethod
    def recover_execution(self, execution_id):
        pass

    @abstractmethod
    def normalize_webhook(self, payload):
        pass