class InstitutionRouter:
    def __init__(self, registry):
        self.registry = registry

    def call(self, institution_id, method, *args):
        inst = self.registry[institution_id]
        func = getattr(inst, method)
        return func(*args)