"""
common/pagination.py
---------------------
Project-wide DRF pagination class.  Import and use in any ViewSet that
needs paged responses.

Usage:
    from common.pagination import StandardPageNumberPagination

    class MyViewSet(viewsets.ModelViewSet):
        pagination_class = StandardPageNumberPagination
"""

from rest_framework.pagination import PageNumberPagination


class StandardPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
