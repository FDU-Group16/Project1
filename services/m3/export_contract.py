"""Export the reviewable M3 contract; --check prevents schema drift in CI."""
import json
from pathlib import Path
import sys
from .main import CreateBody, ACTION_MODELS


def contract():
    def ref(name):
        return {"$ref": f"#/components/schemas/{name}"}

    def obj(properties, required=None):
        return {"type": "object", "additionalProperties": False,
                "properties": properties, "required": list(properties) if required is None else required}

    def array(item):
        return {"type": "array", "items": item}

    def nullable(item):
        return {"anyOf": [item, {"type": "null"}]}

    string = {"type": "string"}
    timestamp = {"type": "string", "format": "date-time", "pattern": "Z$"}
    state = {"type": "string", "enum": ["SUBMITTED", "ASSIGNED", "BLOCK_PENDING", "IN_PROGRESS", "PENDING_ACCEPTANCE", "RELEASE_PENDING", "CLOSED", "CANCELLED"]}
    role = {"type": "string", "enum": ["reporter", "admin", "technician"]}
    schemas = {
        "CreateOrder": CreateBody.model_json_schema(),
        "Identity": obj({"id": string, "name": string, "role": role}),
        "Room": obj({"id": string, "name": string}),
        "Problem": obj({"error": obj({"code": string, "message": string})}),
        "Rating": obj({"score": {"type": "integer", "minimum": 1, "maximum": 5}, "comment": string, "createdAt": timestamp}),
        "HistoryEntry": obj({"id": string, "action": string, "actorId": string, "actorName": string, "note": string, "createdAt": timestamp}),
        "Sync": obj({"status": {"type": "string", "enum": ["pending", "processing", "succeeded", "failed"]},
                     "attempts": {"type": "integer", "minimum": 0, "maximum": 5}, "error": nullable(string), "retryable": {"type": "boolean"}}),
    }
    schemas["Context"] = obj({
        "mode": {"type": "string", "enum": ["production", "development", "test"]},
        "directoryMode": string, "m1Mode": string, "businessReady": {"type": "boolean"},
        "demoIdentities": array(obj({"id": string, "name": string, "role": role, "token": string})),
    })
    schemas["WorkOrder"] = obj({
        "id": string, "roomId": string, "roomName": string,
        "category": {"type": "string", "enum": ["facilities", "electrical", "environment", "other"]},
        "title": string, "description": string, "reporterId": string, "reporterName": string,
        "assigneeId": nullable(string), "assigneeName": nullable(string), "status": state,
        "version": {"type": "integer", "minimum": 1}, "createdAt": timestamp, "updatedAt": timestamp,
        "dueAt": nullable(timestamp), "escalated": {"type": "boolean"}, "rating": nullable(ref("Rating")),
        "sync": nullable(ref("Sync")), "history": array(ref("HistoryEntry")),
        "allowedActions": array({"type": "string", "enum": list(ACTION_MODELS)}),
    })
    for action, model in ACTION_MODELS.items():
        schemas[f"Action_{action}"] = model.model_json_schema()
    paths = {}
    base = "/api/m3/v1"

    def response(schema, description="Success"):
        return {"description": description, "content": {"application/json": {"schema": schema}}}

    def operation(method, path, operation_id, output, body=None, parameters=None, public=False):
        result = {"operationId": operation_id, "tags": ["M3 work orders"],
                  "responses": {"200": response(output)}, "security": [] if public else [{"userBearer": []}]}
        if not public:
            for status in [401, 403, 404, 409, 422, 503]:
                result["responses"][str(status)] = response(ref("Problem"), {
                    401: "Missing/invalid identity", 403: "Forbidden action", 404: "Missing or inaccessible object",
                    409: "Version/state/idempotency conflict", 422: "Invalid input", 503: "Dependency/storage unavailable",
                }[status])
        if body:
            result["requestBody"] = {"required": True, "content": {"application/json": {"schema": body}}}
        if parameters:
            result["parameters"] = parameters
        paths.setdefault(base + path, {})[method] = result
        return result

    operation("get", "/context", "m3Context", ref("Context"), public=True)
    operation("get", "/me", "m3CurrentIdentity", ref("Identity"))
    operation("get", "/rooms", "m3VisibleRooms", obj({"items": array(ref("Room"))}))
    operation("get", "/technicians", "m3Technicians", obj({"items": array(ref("Identity"))}))
    operation("get", "/work-orders", "m3ListOrders", obj({"items": array(ref("WorkOrder"))}), parameters=[
        {"name": name, "in": "query", "schema": schema}
        for name, schema in [("status", state), ("roomId", {"type": "string", "maxLength": 128}),
                             ("view", {"type": "string", "enum": ["all", "mine", "assigned", "acceptance", "overdue"], "default": "all"}),
                             ("q", {"type": "string", "maxLength": 200})]
    ])
    created = operation("post", "/work-orders", "m3CreateOrder", ref("WorkOrder"), ref("CreateOrder"), parameters=[
        {"name": "Idempotency-Key", "in": "header", "required": True,
         "description": "去除首尾空白后须为非空可打印 ASCII；同一用户同一键仅允许相同内容。",
         "schema": {"type": "string", "minLength": 1, "maxLength": 128}}
    ])
    created["responses"]["201"] = response(ref("WorkOrder"), "Created")
    created["responses"]["200"]["description"] = "Idempotent replay"
    identifier = {"name": "id", "in": "path", "required": True, "schema": string}
    operation("get", "/work-orders/{id}", "m3GetOrder", ref("WorkOrder"), parameters=[identifier])
    for action in ACTION_MODELS:
        operation("post", f"/work-orders/{{id}}/{action}", f"m3_{action.replace('-', '_')}",
                  ref("WorkOrder"), ref(f"Action_{action}"), parameters=[identifier])
    return {"openapi": "3.1.0", "info": {"title": "M3 物业报修工单", "version": "1.0.0-proposed",
            "description": "本任务实现基线；团队评审、真实 M1/D 集成和部署状态独立记录。见 m3-work-orders.md。"},
            "paths": paths, "components": {"schemas": schemas, "securitySchemes": {
                "userBearer": {"type": "http", "scheme": "bearer", "description": "用户身份由 D 适配器校验；开发令牌只在显式开发模式可用。"}}}}


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[2] / "contracts" / "m3-work-orders.openapi.json"
    content = json.dumps(contract(), ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        if not target.exists() or target.read_text() != content:
            raise SystemExit("M3 contract drift: run python -m services.m3.export_contract")
        print("M3 contract matches request models and documented response schemas")
    else:
        target.write_text(content)
