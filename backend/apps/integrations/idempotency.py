import hashlib
import json
from functools import wraps

from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response

from .models import IdempotencyRecord


def _hash_request(method: str, path: str, data) -> str:
    canonical = json.dumps(
        {"method": method, "path": path, "data": data},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def idempotent_endpoint(view_method):
    """Decorator providing Idempotency-Key deduplication for mutating DRF endpoints.

    - If `Idempotency-Key` header is absent, executes normally.
    - If `Idempotency-Key` matches a stored record with identical payload hash, replays the
      stored JSON response with `X-Idempotent-Replayed: true`.
    - If `Idempotency-Key` is reused with a different payload, returns HTTP 409 Conflict.
    """

    @wraps(view_method)
    def wrapper(self, request, *args, **kwargs):
        raw_key = request.headers.get("Idempotency-Key", "").strip()
        if not raw_key:
            return view_method(self, request, *args, **kwargs)

        if len(raw_key) > 128:
            return Response(
                {"detail": "Idempotency-Key header must be 128 characters or fewer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        req_hash = _hash_request(request.method, request.path, request.data)
        existing = IdempotencyRecord.objects.filter(key=raw_key).first()
        if existing:
            if existing.request_hash != req_hash:
                return Response(
                    {"detail": "Idempotency-Key was already used with a different request payload."},
                    status=status.HTTP_409_CONFLICT,
                )
            resp = Response(existing.response_body, status=existing.response_status)
            resp["X-Idempotent-Replayed"] = "true"
            return resp

        response = view_method(self, request, *args, **kwargs)

        # Persist deterministic 2xx/4xx outcomes (never cache 5xx transient server errors)
        if 200 <= response.status_code < 500:
            try:
                serialized = json.loads(json.dumps(response.data, default=str))
                IdempotencyRecord.objects.create(
                    key=raw_key,
                    request_method=request.method,
                    request_path=request.path,
                    request_hash=req_hash,
                    response_status=response.status_code,
                    response_body=serialized,
                )
            except IntegrityError:
                stored = IdempotencyRecord.objects.filter(key=raw_key).first()
                if stored and stored.request_hash == req_hash:
                    replay = Response(stored.response_body, status=stored.response_status)
                    replay["X-Idempotent-Replayed"] = "true"
                    return replay

        response["X-Idempotent-Replayed"] = "false"
        return response

    return wrapper
