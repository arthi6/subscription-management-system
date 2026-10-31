class DomainError(Exception):
    """A business rule was violated (state machine, billing, discounts, payments).
    Converted to HTTP 422 by the exception handler in app/main.py."""
