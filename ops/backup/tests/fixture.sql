-- Small stand-in for the Science Bank schema, enough for the backup and restore-drill tests.
CREATE TABLE alembic_version (version_num varchar(64) PRIMARY KEY);
INSERT INTO alembic_version VALUES ('0005_results_and_variants');

CREATE TABLE users (id serial PRIMARY KEY, username text UNIQUE NOT NULL, role text NOT NULL, password_hash text NOT NULL);
CREATE TABLE questions (id serial PRIMARY KEY, owner_id int REFERENCES users(id), status text NOT NULL, stem text NOT NULL, meta jsonb NOT NULL DEFAULT '{}');
CREATE TABLE assessments (id serial PRIMARY KEY, owner_id int REFERENCES users(id), title text NOT NULL);
CREATE TABLE administrations (id serial PRIMARY KEY, assessment_id int REFERENCES assessments(id), label text NOT NULL);
CREATE TABLE item_results (id serial PRIMARY KEY, administration_id int REFERENCES administrations(id), correct int NOT NULL, attempted int NOT NULL);
CREATE TABLE audit_events (id serial PRIMARY KEY, at timestamptz NOT NULL DEFAULT now(), detail jsonb NOT NULL DEFAULT '{}');

INSERT INTO users (username, role, password_hash) VALUES
  ('nina', 'power', 'hash-1'), ('brandon', 'admin', 'hash-2'), ('teacher', 'regular', 'hash-3');
INSERT INTO questions (owner_id, status, stem, meta)
  SELECT 1 + (g % 3), (ARRAY['generated','reviewed','approved'])[1 + g % 3],
         'Which statement best describes the relationship shown by the data? (' || g || ') — Mg²⁺ / H₂O',
         jsonb_build_object('seed', 'seed-' || g, 'choices', jsonb_build_array('A', 'B', 'C', 'D'))
  FROM generate_series(1, 40) AS g;
INSERT INTO assessments (owner_id, title) VALUES (1, 'Unit test'), (3, 'Quiz');
INSERT INTO administrations (assessment_id, label) VALUES (1, 'Period 2'), (1, 'Period 4'), (2, 'Period 2');
INSERT INTO item_results (administration_id, correct, attempted)
  SELECT 1 + (g % 3), g % 20, 20 FROM generate_series(1, 25) AS g;
INSERT INTO audit_events (detail) SELECT jsonb_build_object('n', g) FROM generate_series(1, 60) AS g;
