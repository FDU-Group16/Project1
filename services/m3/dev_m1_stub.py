"""TEMPORARY-DEPENDENCY M3-M1-DEV: standalone HTTP contract receipt fixture.

This stores synthetic source receipts only. It is not an M1 seat-state provider.
It must run as a separate loopback process and is never selected by production.
"""
from copy import deepcopy
import os
from threading import Lock
from fastapi import FastAPI, Header, HTTPException
from .service import iso, utcnow


def create_stub():
    app = FastAPI(title="M3 development M1 HTTP fixture")
    receipts, lock = {}, Lock()

    @app.get("/healthz")
    def health():
        return {"service": "m3-development-m1-fixture", "status": "ok", "simulated": True}

    @app.put("/internal/v1/room-blocks/m3/{source_id}")
    def apply(source_id: str, payload: dict, authorization: str = Header(default="")):
        if authorization != "Bearer m3-development-only":
            raise HTTPException(401)
        if (set(payload) != {"roomId", "revision", "status", "startsAt"} or
            payload.get("status") not in {"ACTIVE", "RELEASED"} or
            type(payload.get("revision")) is not int or payload["revision"] < 1):
            raise HTTPException(422)
        with lock:
            existing = receipts.get(source_id)
            if existing:
                if payload["revision"] < existing["revision"]:
                    raise HTTPException(409)
                if payload["revision"] == existing["revision"]:
                    if any(existing.get(key) != value for key, value in payload.items()):
                        raise HTTPException(409)
                    return deepcopy(existing)
            receipt = {"sourceSystem": "M3", "sourceId": source_id, **payload, "appliedAt": iso(utcnow())}
            receipts[source_id] = receipt
            return deepcopy(receipt)

    return app


app = create_stub()

if __name__ == "__main__":
    if os.getenv("M3_MODE") != "development":
        raise SystemExit("M3_MODE=development is required for the HTTP fixture")
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3113)
