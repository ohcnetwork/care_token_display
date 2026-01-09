"""
Custom authentication classes for token display views.

This module provides authentication mechanisms that read tokens from
query parameters instead of HTTP headers, useful for display screens
and embedded content where header management is difficult.
"""

from rest_framework.authentication import TokenAuthentication


class QueryParamTokenAuthentication(TokenAuthentication):
    """
    Token authentication that reads the token from query parameters
    instead of the Authorization header.

    Usage:
        Add to view's authentication_classes:
        authentication_classes = [QueryParamTokenAuthentication]

    Example:
        GET /api/display/?token=abc123def456
    """

    def authenticate(self, request):
        """
        Authenticate the request by reading the token from query parameters.

        Returns:
            tuple: (user, token) if authentication succeeds
            None: if no token is provided (allows anonymous access)

        Raises:
            AuthenticationFailed: if token is invalid
        """
        token = request.query_params.get("token")
        if not token:
            return None  # No authentication attempted

        return self.authenticate_credentials(token)
