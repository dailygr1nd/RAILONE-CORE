from adapters.base.adapter_contract import (
    RailOneAdapter
)


class MpesaAdapter(RailOneAdapter):

    def initiate_execution(self, payload):

        # call daraja api

        pass

    def query_execution_state(self, execution_id):

        pass

    def verify_execution(self, payload):

        pass

    def reconcile_execution(self, execution_id):

        pass

    def recover_execution(self, execution_id):

        pass

    def normalize_webhook(self, payload):

        pass