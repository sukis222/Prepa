-- Summaries contain selected evidence quotes, never the raw lesson transcript.
create table lesson_summary_sessions (
    teacher_id bigint primary key references teachers(telegram_user_id),
    preparation_id prepa_id not null,
    version integer not null,
    student_id prepa_id not null,
    worksheet jsonb not null,
    updated_at timestamptz not null default now(),
    foreign key (preparation_id, version, teacher_id)
        references preparation_versions(preparation_id, version, teacher_id),
    foreign key (student_id, teacher_id) references students(student_id, teacher_id)
);

create table lesson_summaries (
    summary_id bigint generated always as identity primary key,
    teacher_id bigint not null,
    preparation_id prepa_id not null,
    version integer not null,
    student_id prepa_id not null,
    input_digest char(64) not null check (input_digest ~ '^[0-9a-f]{64}$'),
    summary jsonb not null check (jsonb_typeof(summary) = 'object'),
    status text not null default 'pending' check (status in ('pending', 'confirmed')),
    created_at timestamptz not null default now(),
    confirmed_at timestamptz,
    foreign key (preparation_id, version, teacher_id)
        references preparation_versions(preparation_id, version, teacher_id),
    foreign key (student_id, teacher_id) references students(student_id, teacher_id),
    unique (teacher_id, preparation_id, version, input_digest),
    check ((status = 'confirmed') = (confirmed_at is not null))
);
create index lesson_summaries_student_idx
    on lesson_summaries(teacher_id, student_id, created_at);
insert into schema_migrations(version) values (4);
