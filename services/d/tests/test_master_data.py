"""Real PostgreSQL acceptance tests. TEST_D_DATABASE_URL must target a test DB."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from services.d.main import app
from services.d.master_data import db
from services.d.seed import seed

ADMIN = {"Authorization": "Bearer dev-room-admin"}
CS = {"Authorization": "Bearer dev-student-cs"}
EE = {"Authorization": "Bearer dev-student-ee"}
OPERATOR = {"Authorization": "Bearer dev-operator"}


@unittest.skipUnless(os.getenv("TEST_D_DATABASE_URL"), "Requires isolated PostgreSQL TEST_D_DATABASE_URL; no in-memory replacement")
class MasterDataTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "D_DATABASE_URL": os.environ["TEST_D_DATABASE_URL"], "APP_ENV": "test", "D_USE_DEV_IDENTITY": "1",
            "D_M1_TOKEN": "d02-test-service-credential",  # synthetic test-only value
        })
        self.environment.start()
        self.rooms = []
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        self.service = {"Authorization": "Bearer d02-test-service-credential"}

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        with db.connection() as conn:
            for room_id in self.rooms:
                conn.execute("DELETE FROM seats WHERE room_id=%s", (room_id,))
                conn.execute("DELETE FROM rooms WHERE id=%s", (room_id,))
        self.environment.stop()

    def room(self, **changes):
        data = {"name": "D02 test room", "departmentId": None, "openHour": 8, "closeHour": 22, "weekdays": list(range(7)), **changes}
        response = self.client.post("/api/v1/rooms", headers=ADMIN, json=data)
        self.assertEqual(response.status_code, 201, response.text)
        room = response.json()
        self.rooms.append(room["id"])
        return room

    def seat(self, room, **changes):
        response = self.client.post(f'/api/v1/rooms/{room["id"]}/seats', headers=ADMIN, json={"number": "01", **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_update_stable_ids_and_real_persistence(self):
        room = self.room(departmentId="cs")
        seat = self.seat(room, hasSocket=True)
        result = self.client.patch(f'/api/v1/rooms/{room["id"]}', headers=ADMIN, json={"name": "Renamed", "departmentId": None}).json()
        self.assertEqual(result["id"], room["id"])
        self.assertEqual(result["name"], "Renamed")
        result = self.client.patch(f'/api/v1/seats/{seat["id"]}', headers=ADMIN, json={"number": "02", "hasSocket": False}).json()
        self.assertEqual(result["id"], seat["id"])
        self.assertEqual(result["roomId"], room["id"])
        self.assertFalse(result["hasSocket"])
        # Fresh connection checks committed persistence, independent of API serialization.
        with db.connection() as conn:
            persisted = conn.execute("SELECT * FROM seats WHERE id=%s", (seat["id"],)).fetchone()
            self.assertEqual(persisted["number"], "02")
        internal = self.client.get(f'/internal/v1/rooms/{room["id"]}', headers=self.service).json()
        self.assertEqual(internal["seats"][0]["id"], seat["id"])

    def test_department_filter_and_direct_access_cannot_bypass(self):
        public, cs, ee = self.room(), self.room(departmentId="cs"), self.room(departmentId="ee")
        self.seat(cs)
        visible = {r["id"] for r in self.client.get("/api/v1/rooms", headers=CS).json()["items"]}
        self.assertTrue({public["id"], cs["id"]} <= visible)
        self.assertNotIn(ee["id"], visible)
        for suffix in ("", "/seats"):
            self.assertEqual(self.client.get(f'/api/v1/rooms/{cs["id"]}{suffix}', headers=EE).status_code, 403)
        self.assertEqual(self.client.get(f'/api/v1/rooms/{ee["id"]}', headers=OPERATOR).status_code, 200)

    def test_mutation_permissions_and_unknown_token(self):
        room = self.room()
        seat = self.seat(room)
        requests = [("post", "/api/v1/rooms", {"name": "Forbidden", "openHour": 8, "closeHour": 22, "weekdays": [0]}),
                    ("patch", f'/api/v1/rooms/{room["id"]}', {"name": "Forbidden"}),
                    ("delete", f'/api/v1/rooms/{room["id"]}', None),
                    ("post", f'/api/v1/rooms/{room["id"]}/seats', {"number": "02"}),
                    ("patch", f'/api/v1/seats/{seat["id"]}', {"active": False}),
                    ("delete", f'/api/v1/seats/{seat["id"]}', None)]
        for headers in [CS, OPERATOR]:
            for method, path, body in requests:
                response = self.client.request(method, path, headers=headers, **({"json": body} if body else {}))
                self.assertEqual(response.status_code, 403, (method, path, response.text))
        self.assertEqual(self.client.get("/api/v1/rooms").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/rooms", headers={"Authorization": "Bearer unknown"}).status_code, 401)

    def test_validation_hours_weekdays_unknown_fields_and_partial_patch(self):
        good = {"name": "Invalid fixture", "openHour": 8, "closeHour": 22, "weekdays": [0]}
        for invalid in [{"name": " "}, {"openHour": 24}, {"openHour": True}, {"closeHour": 8},
                        {"weekdays": []}, {"weekdays": [0, 0]}, {"weekdays": [7]}, {"id": "chosen"},
                        {"departmentId": " "}, {"active": "false"}]:
            response = self.client.post("/api/v1/rooms", headers=ADMIN, json={**good, **invalid})
            self.assertEqual(response.status_code, 422, response.text)
        room = self.room(openHour=0, closeHour=24)
        for invalid in [{}, {"retired": True}, {"active": None}, {"name": None}, {"closeHour": 0}]:
            self.assertEqual(self.client.patch(f'/api/v1/rooms/{room["id"]}', headers=ADMIN, json=invalid).status_code, 422)
        self.client.patch(f'/api/v1/rooms/{room["id"]}', headers=ADMIN, json={"openHour": 20})
        response = self.client.patch(f'/api/v1/rooms/{room["id"]}', headers=ADMIN, json={"closeHour": 19})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get(f'/api/v1/rooms/{room["id"]}', headers=ADMIN).json()["closeHour"], 24)

    def test_unique_seat_number_per_room_including_retirement(self):
        first, second = self.room(), self.room()
        seat = self.seat(first)
        self.seat(second)
        response = self.client.post(f'/api/v1/rooms/{first["id"]}/seats', headers=ADMIN, json={"number": "01"})
        self.assertEqual(response.status_code, 409)
        other = self.seat(first, number="02")
        self.assertEqual(self.client.patch(f'/api/v1/seats/{other["id"]}', headers=ADMIN, json={"number": "01"}).status_code, 409)
        self.client.delete(f'/api/v1/seats/{seat["id"]}', headers=ADMIN)
        self.assertEqual(self.client.patch(f'/api/v1/seats/{seat["id"]}', headers=ADMIN, json={"active": True}).status_code, 409)
        self.assertEqual(self.client.post(f'/api/v1/rooms/{first["id"]}/seats', headers=ADMIN, json={"number": "01"}).status_code, 409)
        self.assertNotEqual(seat["id"], other["id"])

    def test_concurrent_duplicate_seat_creates_exactly_one(self):
        room = self.room()
        def create(_):
            return self.client.post(f'/api/v1/rooms/{room["id"]}/seats', headers=ADMIN, json={"number": "concurrent"}).status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(create, range(2))), [201, 409])
        seats = self.client.get(f'/api/v1/rooms/{room["id"]}/seats', headers=ADMIN).json()["items"]
        self.assertEqual(len(seats), 1)

    def test_disable_filters_students_but_internal_sees_every_state(self):
        room = self.room()
        first = self.seat(room)
        self.seat(room, number="02", active=False)
        self.assertEqual(len(self.client.get(f'/api/v1/rooms/{room["id"]}/seats', headers=CS).json()["items"]), 1)
        self.assertEqual(len(self.client.get(f'/internal/v1/rooms/{room["id"]}', headers=self.service).json()["seats"]), 2)
        self.client.patch(f'/api/v1/rooms/{room["id"]}', headers=ADMIN, json={"active": False})
        self.assertEqual(self.client.get(f'/api/v1/rooms/{room["id"]}', headers=CS).status_code, 404)
        internal = self.client.get(f'/internal/v1/rooms/{room["id"]}', headers=self.service).json()
        self.assertFalse(internal["active"])
        self.assertTrue(next(s for s in internal["seats"] if s["id"] == first["id"])["active"])
        self.client.patch(f'/api/v1/rooms/{room["id"]}', headers=ADMIN, json={"active": True})
        self.assertEqual(self.client.get(f'/api/v1/rooms/{room["id"]}', headers=CS).status_code, 200)

    def test_retirement_is_irreversible_idempotent_and_preserves_references(self):
        room = self.room()
        seat = self.seat(room)
        path = f'/api/v1/rooms/{room["id"]}'
        result = self.client.delete(path, headers=ADMIN)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["retired"])
        self.assertEqual(self.client.delete(path, headers=ADMIN).json(), result.json())
        self.assertEqual(self.client.patch(path, headers=ADMIN, json={"active": True}).status_code, 409)
        self.assertEqual(self.client.post(path + "/seats", headers=ADMIN, json={"number": "02"}).status_code, 409)
        self.assertEqual(self.client.patch(f'/api/v1/seats/{seat["id"]}', headers=ADMIN, json={"active": True}).status_code, 409)
        internal = self.client.get(f'/internal/v1/rooms/{room["id"]}', headers=self.service).json()
        self.assertEqual(internal["seats"][0]["id"], seat["id"])
        self.assertTrue(internal["seats"][0]["retired"])
        self.assertFalse(internal["seats"][0]["active"])
        all_internal = self.client.get('/internal/v1/rooms', headers=self.service).json()["items"]
        self.assertIn(room["id"], {r["id"] for r in all_internal})

    def test_internal_service_auth_is_separate(self):
        room = self.room()
        for headers in [ADMIN, CS, {}, {"Authorization": "Bearer wrong"}]:
            self.assertEqual(self.client.get('/internal/v1/rooms', headers=headers).status_code, 401)
        self.assertEqual(self.client.get(f'/internal/v1/rooms/{room["id"]}', headers=self.service).status_code, 200)
        with patch.dict(os.environ, {"D_M1_TOKEN": ""}):
            self.assertEqual(self.client.get('/internal/v1/rooms', headers=self.service).status_code, 503)
        self.assertEqual(self.client.get('/internal/v1/rooms/unknown', headers=self.service).status_code, 404)

    def test_idempotent_migration_and_separate_synthetic_seed(self):
        db.migrate(Path(__file__).parents[1] / "migrations")
        seed()
        seed()
        with db.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM rooms WHERE id LIKE 'demo-room-%'").fetchone()["n"], 3)
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM seats WHERE room_id LIKE 'demo-room-%'").fetchone()["n"], 18)


if __name__ == "__main__":
    unittest.main()
