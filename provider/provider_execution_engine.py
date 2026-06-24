# ==========================================
# execution/provider_execution_engine.py
# ==========================================

from provider.provider_registry import (
    ProviderRegistry
)


def execute_provider_route(

    provider_name,
    execution
):

    adapter = (
        ProviderRegistry.get(
            provider_name
        )
    )

    return adapter.execute(
        execution
    )