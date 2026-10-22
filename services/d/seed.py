"""Idempotent synthetic D-02 seed; run `python -m services.d.seed`."""

from pathlib import Path
from services.platform import Database


def seed():
    db = Database("d")
    db.migrate(Path(__file__).parent / "migrations")
    with db.connection() as conn:
        for room_id, name, department in [("demo-room-public", "公共自习室（合成演示）", None),
                                           ("demo-room-cs", "计算机院系自习室（合成演示）", "cs"),
                                           ("demo-room-ee", "电子院系自习室（合成演示）", "ee")]:
            conn.execute("""INSERT INTO rooms(id,name,department_id,open_hour,close_hour,weekdays)
                VALUES (%s,%s,%s,8,22,ARRAY[0,1,2,3,4,5,6]) ON CONFLICT (id) DO NOTHING""",
                (room_id, name, department))
            for number in range(1, 7):
                # Never restore a retired room or seat during repeated seed runs.
                conn.execute("""INSERT INTO seats(id,room_id,number,has_socket)
                    SELECT %s,%s,%s,%s WHERE EXISTS (SELECT 1 FROM rooms WHERE id=%s AND NOT retired)
                    ON CONFLICT DO NOTHING""", (f"{room_id}-seat-{number:02d}", room_id, f"{number:02d}", number % 2 == 0, room_id))
    print("D-02 synthetic seed complete (stable demo-* IDs; existing/retired records preserved)")


if __name__ == "__main__":
    seed()
