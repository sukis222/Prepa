-- Durable preparation queue and persisted delivery artifacts.
BEGIN;
CREATE TABLE preparation_jobs (
    preparation_id prepa_id NOT NULL,
    version integer NOT NULL,
    teacher_id bigint NOT NULL,
    mode text NOT NULL CHECK (mode IN ('demo', 'real')),
    students jsonb NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','ready','failed')),
    attempts integer NOT NULL DEFAULT 0,
    lease_until timestamptz,
    claim_token uuid,
    result jsonb,
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (preparation_id, version),
    FOREIGN KEY (preparation_id, version, teacher_id)
        REFERENCES preparation_versions(preparation_id, version, teacher_id),
    CHECK ((status = 'ready') = (result IS NOT NULL))
);
CREATE INDEX preparation_jobs_queue_idx ON preparation_jobs(mode, status, lease_until);
INSERT INTO schema_migrations(version) VALUES (3);
COMMIT;
