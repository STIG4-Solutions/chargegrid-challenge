"""Exceções de domínio traduzidas para HTTP no main.py."""


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class Conflict(DomainError):
    status_code = 409
    code = "conflict"


class InvalidTransition(Conflict):
    code = "invalid_transition"


class InsufficientPower(DomainError):
    status_code = 422
    code = "insufficient_power"


class HardwareError(DomainError):
    status_code = 502
    code = "hardware_error"


class PaymentError(DomainError):
    status_code = 402
    code = "payment_error"
