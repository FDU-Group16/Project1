"""Pure retry identity helpers; no authentication, storage or replay service."""

from dataclasses import dataclass
from hashlib import sha256
import json

from services.m2.contracts import ApplicationCreate


@dataclass(frozen=True, slots=True)
class IdempotencyScope:
    """Structured unique-key values, supplied after fresh authorization.

    Preserve opaque values exactly. A database must eventually enforce a
    composite unique constraint on all four fields, in the business transaction.
    """

    user_id: str
    action: str
    target: str
    key: str

    def __post_init__(self) -> None:
        for name in ("user_id", "action", "target", "key"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")

    @property
    def storage_key(self) -> tuple[str, str, str, str]:
        return self.user_id, self.action, self.target, self.key


def application_input_digest(request: ApplicationCreate) -> str:
    """Versioned fingerprint of validated input, not of identity or access.

    Keep the version with persisted records; changing this encoding requires
    an explicit compatibility plan for existing retries. Do not log the input
    or treat its unkeyed digest as anonymization of user data.
    """
    if not isinstance(request, ApplicationCreate):
        raise TypeError("request must be an ApplicationCreate")
    # Revalidate the serialized values: model_construct/model_copy can bypass
    # Pydantic validation even when a model is frozen.
    validated = ApplicationCreate.model_validate_json(request.model_dump_json())
    canonical = json.dumps(
        validated.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    digest = sha256(b"m2.application-create.v1\x00" + canonical).hexdigest()
    return f"m2.application-create.v1:sha256:{digest}"
