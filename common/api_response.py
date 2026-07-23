"""
common/api_response.py
-----------------------
Standardised DRF Response helpers so every API endpoint returns a
consistent JSON envelope:

Success:
    {"status": "success", "data": {...}, "message": ""}

Error:
    {"status": "error", "data": null, "message": "Something went wrong", "errors": {...}}

Usage:
    from common.api_response import success_response, error_response

    return success_response(data=serializer.data, message="Booking created")
    return error_response(message="Validation failed", errors=serializer.errors, status_code=400)
"""

from rest_framework import status
from rest_framework.response import Response


def success_response(data=None, message: str = "", status_code: int = status.HTTP_200_OK) -> Response:
    """Return a standardised success envelope."""
    return Response(
        {
            "status": "success",
            "message": message,
            "data": data,
        },
        status=status_code,
    )


def error_response(
    message: str = "An error occurred",
    errors=None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> Response:
    """Return a standardised error envelope."""
    return Response(
        {
            "status": "error",
            "message": message,
            "data": None,
            "errors": errors,
        },
        status=status_code,
    )
