class PaymentVerificationError(Exception):
    pass


class PaymentProvider:
    def verify(self, reference, amount, currency):
        raise NotImplementedError


class FreePaymentProvider(PaymentProvider):
    def verify(self, reference, amount, currency):
        return amount == 0


PROVIDERS = {"local": FreePaymentProvider}


def get_provider(name):
    provider_class = PROVIDERS.get(name)
    if provider_class is None:
        raise PaymentVerificationError(
            "Ce fournisseur de paiement n'est pas encore configuré."
        )
    return provider_class()
