-- Checkpoint the whole dialog, including unfinished lesson/student wizards.
BEGIN;
CREATE TABLE bot_sessions (
    teacher_id bigint PRIMARY KEY REFERENCES teachers(telegram_user_id),
    state jsonb NOT NULL CHECK (jsonb_typeof(state) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO schema_migrations(version) VALUES (2);
COMMIT;
