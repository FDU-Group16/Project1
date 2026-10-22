CREATE TABLE rooms (
    id text PRIMARY KEY,
    name text NOT NULL CHECK (char_length(trim(name)) BETWEEN 1 AND 120),
    department_id text CHECK (department_id IS NULL OR char_length(trim(department_id)) BETWEEN 1 AND 80),
    open_hour integer NOT NULL CHECK (open_hour >= 0 AND open_hour < 24),
    close_hour integer NOT NULL CHECK (close_hour > open_hour AND close_hour <= 24),
    weekdays integer[] NOT NULL CHECK (cardinality(weekdays) BETWEEN 1 AND 7 AND weekdays <@ ARRAY[0,1,2,3,4,5,6]),
    active boolean NOT NULL DEFAULT true,
    retired boolean NOT NULL DEFAULT false,
    CHECK (NOT retired OR NOT active)
);

CREATE TABLE seats (
    id text PRIMARY KEY,
    room_id text NOT NULL REFERENCES rooms(id),
    number text NOT NULL CHECK (char_length(trim(number)) BETWEEN 1 AND 40),
    has_socket boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT true,
    retired boolean NOT NULL DEFAULT false,
    UNIQUE (room_id, number),
    CHECK (NOT retired OR NOT active)
);
CREATE INDEX seats_room_id_idx ON seats(room_id);
CREATE INDEX rooms_department_id_idx ON rooms(department_id);
