from rest_framework.pagination import PageNumberPagination


class OptionalPageNumberPagination(PageNumberPagination):
    """Backward-compatible DRF pagination activated when ?page= or ?page_size= is passed.

    - Clients omitting both query params receive the full list response (preserving
      existing Vue 3 SPA and E2E API contracts).
    - Clients supplying ?page=1&page_size=20 receive DRF's standard envelope:
      {"count": ..., "next": ..., "previous": ..., "results": [...]}.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        if (
            self.page_query_param not in request.query_params
            and self.page_size_query_param not in request.query_params
        ):
            return None
        return super().paginate_queryset(queryset, request, view=view)
