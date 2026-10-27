from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Actor:
    id: str
    name: str
    role: str
    # A legacy injected test actor may omit permissions. HTTP identities always
    # carry an explicit set, including the empty set; never infer their grants.
    permissions: frozenset[str] | None = None
    department_id: str | None = None
    bearer: str = field(default="", repr=False, compare=False)

    def can(self, capability):
        if self.permissions is None:
            return (capability == "report" and self.role in {"reporter", "admin", "technician"}
                    or capability == "dispatch" and self.role == "admin"
                    or capability == "work" and self.role == "technician")
        return (f"repair:{capability}" in self.permissions
                or capability == "report" and "seat:reserve" in self.permissions)

    def public(self):
        return {"id": self.id, "name": self.name, "role": self.role}


class Directory(Protocol):
    def authenticate(self, token: str) -> Actor | None: ...
    def rooms(self, actor: Actor) -> list[dict]: ...
    def technicians(self, actor: Actor) -> list[Actor]: ...


class UnavailableDirectory:
    """No HTTP directory has been configured; business calls fail closed."""
    def authenticate(self, token):
        return None

    def rooms(self, actor):
        return []

    def technicians(self, actor):
        return []
