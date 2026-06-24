# ==========================================
# provider/provider_registry.py
# ==========================================

class ProviderRegistry:

    _providers = {}

    @classmethod
    def register(

        cls,
        provider_name,
        adapter
    ):

        cls._providers[
            provider_name
        ] = adapter

    @classmethod
    def get(

        cls,
        provider_name
    ):

        provider = cls._providers.get(
            provider_name
        )

        if not provider:

            raise Exception(

                f"Provider not found: "
                f"{provider_name}"
            )

        return provider