-- Initial schema proposal, applied automatically ONLY to an empty Docker volume.
-- JSON contracts are validated in Python with prepa.schemas before every write/read.
BEGIN;

CREATE DOMAIN prepa_id AS varchar(100)
    CHECK (VALUE ~ '^[a-zA-Z0-9_-]{1,100}$');

CREATE TABLE teachers (
    telegram_user_id bigint PRIMARY KEY CHECK (telegram_user_id > 0),
    display_name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE students (
    student_id prepa_id PRIMARY KEY,
    teacher_id bigint NOT NULL REFERENCES teachers(telegram_user_id),
    display_name text NOT NULL,
    goal text,
    profile jsonb NOT NULL CHECK (jsonb_typeof(profile) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (student_id, teacher_id),
    CHECK (profile ? 'student_id' AND profile->>'student_id' = student_id)
);
CREATE INDEX students_teacher_idx ON students(teacher_id);

CREATE TABLE preparations (
    preparation_id prepa_id PRIMARY KEY,
    teacher_id bigint NOT NULL REFERENCES teachers(telegram_user_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (preparation_id, teacher_id)
);
CREATE INDEX preparations_teacher_created_idx ON preparations(teacher_id, created_at DESC);

-- Membership is fixed for a preparation; changing students creates a new preparation.
CREATE TABLE preparation_students (
    preparation_id prepa_id NOT NULL,
    student_id prepa_id NOT NULL,
    teacher_id bigint NOT NULL,
    PRIMARY KEY (preparation_id, student_id),
    UNIQUE (preparation_id, student_id, teacher_id),
    FOREIGN KEY (preparation_id, teacher_id)
        REFERENCES preparations(preparation_id, teacher_id),
    FOREIGN KEY (student_id, teacher_id) REFERENCES students(student_id, teacher_id)
);
CREATE INDEX preparation_students_student_idx ON preparation_students(student_id, teacher_id);

CREATE TABLE preparation_versions (
    preparation_id prepa_id NOT NULL,
    version integer NOT NULL CHECK (version >= 1),
    teacher_id bigint NOT NULL,
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'confirmed', 'generating', 'reviewed', 'failed')),
    brief jsonb NOT NULL CHECK (jsonb_typeof(brief) = 'object'),
    -- Complete GenerationContext snapshot; profiles are not re-read into old versions.
    context jsonb CHECK (jsonb_typeof(context) = 'object'),
    confirmed_at timestamptz,
    failure_code text, -- Stable safe code, never provider error text/prompts.
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (preparation_id, version),
    UNIQUE (preparation_id, version, teacher_id),
    FOREIGN KEY (preparation_id, teacher_id)
        REFERENCES preparations(preparation_id, teacher_id),
    CHECK (brief ? 'preparation_id' AND brief->>'preparation_id' = preparation_id),
    CHECK (brief ? 'version' AND brief->'version' = to_jsonb(version)),
    CHECK (brief ? 'confirmed' AND brief->'confirmed' = to_jsonb(confirmed_at IS NOT NULL)),
    CHECK ((status = 'draft') = (confirmed_at IS NULL)),
    CHECK (context IS NULL OR (context ? 'brief' AND context->'brief' = brief))
);
CREATE INDEX preparation_versions_status_idx ON preparation_versions(status)
    WHERE status IN ('confirmed', 'generating');

-- Store only fully validated LessonPackage objects, including content-bound review digests.
CREATE TABLE lesson_packages (
    preparation_id prepa_id NOT NULL,
    version integer NOT NULL,
    teacher_id bigint NOT NULL,
    package jsonb NOT NULL CHECK (jsonb_typeof(package) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (preparation_id, version),
    UNIQUE (preparation_id, version, teacher_id),
    FOREIGN KEY (preparation_id, version, teacher_id)
        REFERENCES preparation_versions(preparation_id, version, teacher_id)
);

CREATE TABLE documents (
    document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id prepa_id NOT NULL,
    version integer NOT NULL,
    teacher_id bigint NOT NULL,
    audience text NOT NULL CHECK (audience IN ('teacher', 'student')),
    student_id prepa_id,
    storage_key text NOT NULL, -- Object storage key; no PDF bytes in this table.
    telegram_file_id text,
    sha256 char(64) NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (preparation_id, version, teacher_id)
        REFERENCES lesson_packages(preparation_id, version, teacher_id),
    FOREIGN KEY (preparation_id, student_id, teacher_id)
        REFERENCES preparation_students(preparation_id, student_id, teacher_id),
    CHECK ((audience = 'student') = (student_id IS NOT NULL)),
    UNIQUE NULLS NOT DISTINCT (preparation_id, version, audience, student_id)
);

CREATE TABLE homeworks (
    preparation_id prepa_id NOT NULL,
    version integer NOT NULL,
    student_id prepa_id NOT NULL,
    teacher_id bigint NOT NULL,
    homework jsonb NOT NULL CHECK (jsonb_typeof(homework) = 'object'),
    issued_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (preparation_id, version, student_id),
    UNIQUE (preparation_id, version, student_id, teacher_id),
    FOREIGN KEY (preparation_id, version, teacher_id)
        REFERENCES lesson_packages(preparation_id, version, teacher_id),
    FOREIGN KEY (preparation_id, student_id, teacher_id)
        REFERENCES preparation_students(preparation_id, student_id, teacher_id),
    CHECK (homework ? 'student_id' AND homework->>'student_id' = student_id)
);
CREATE INDEX homeworks_student_idx ON homeworks(student_id, teacher_id, issued_at DESC);

-- Future HomeworkSubmission / HomeworkCheckResult contracts have not been agreed yet.
CREATE TABLE homework_submissions (
    submission_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id prepa_id NOT NULL,
    version integer NOT NULL,
    student_id prepa_id NOT NULL,
    teacher_id bigint NOT NULL,
    telegram_chat_id bigint NOT NULL,
    telegram_message_id bigint NOT NULL,
    answer_text text,
    telegram_file_id text,
    status text NOT NULL DEFAULT 'received'
        CHECK (status IN ('received', 'checking', 'checked', 'failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (submission_id, teacher_id, student_id),
    UNIQUE (telegram_chat_id, telegram_message_id),
    FOREIGN KEY (preparation_id, version, student_id, teacher_id)
        REFERENCES homeworks(preparation_id, version, student_id, teacher_id),
    CHECK (nullif(btrim(answer_text), '') IS NOT NULL OR telegram_file_id IS NOT NULL)
);
CREATE INDEX submissions_homework_idx
    ON homework_submissions(preparation_id, version, student_id, teacher_id);

CREATE TABLE homework_reviews (
    submission_id uuid PRIMARY KEY,
    teacher_id bigint NOT NULL,
    student_id prepa_id NOT NULL,
    result jsonb NOT NULL CHECK (jsonb_typeof(result) = 'object'),
    teacher_confirmed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (submission_id, teacher_id, student_id),
    FOREIGN KEY (submission_id, teacher_id, student_id)
        REFERENCES homework_submissions(submission_id, teacher_id, student_id)
);

-- Append confirmed changes only, in the same transaction as the student profile update.
CREATE TABLE student_progress_events (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id bigint NOT NULL,
    student_id prepa_id NOT NULL,
    submission_id uuid,
    note text NOT NULL,
    profile_before jsonb NOT NULL CHECK (jsonb_typeof(profile_before) = 'object'),
    profile_after jsonb NOT NULL CHECK (jsonb_typeof(profile_after) = 'object'),
    confirmed_at timestamptz NOT NULL,
    FOREIGN KEY (student_id, teacher_id) REFERENCES students(student_id, teacher_id),
    FOREIGN KEY (submission_id, teacher_id, student_id)
        REFERENCES homework_reviews(submission_id, teacher_id, student_id),
    UNIQUE (submission_id)
);
CREATE INDEX student_progress_history_idx
    ON student_progress_events(student_id, teacher_id, confirmed_at DESC);

CREATE TABLE schema_migrations (
    version integer PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO schema_migrations(version) VALUES (1);
COMMIT;
