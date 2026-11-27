"""Errors that map to an HTTP response without a stack trace, and reading Worker settings."""


class ClientError(Exception):
    """The request itself is invalid. `status` is the HTTP status to return."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def env_text(env, name):
    """A text setting from the Worker env, or None when unset, empty, or "none".

    The Deploy to Cloudflare form asks for every secret, so users type "none"
    for the ones they do not need.
    """
    value = getattr(env, name, None) if env is not None else None
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.lower() == "none":
        return None
    return value
