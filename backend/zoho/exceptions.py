"""
zoho/exceptions.py
Custom exceptions for the Zoho integration layer.
"""


class ZohoAuthError(Exception):
    """
    Raised when the authentication module is misconfigured —
    e.g. missing credentials or an unexpected response shape.
    """
    pass


class ZohoTokenRefreshError(Exception):
    """
    Raised when the access-token refresh call to Zoho fails —
    e.g. network error, 4xx/5xx from Zoho, or missing access_token in response.
    """

    def __init__(self, message: str, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body

    def __str__(self):
        base = super().__str__()
        if self.status_code:
            return f"{base} [HTTP {self.status_code}] {self.body}"
        return base
