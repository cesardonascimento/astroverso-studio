-- 001_init: cortes de vídeo

CREATE TABLE jobs (
    id                bigserial PRIMARY KEY,
    url               text        NOT NULL,
    source_id         text,                              -- id do vídeo no YouTube
    source_title      text,
    source_channel    text,
    source_channel_url text,
    source_duration_s numeric(10,2),
    source_language   text,
    -- de onde veio a autorização para cortar (preenchido por você): programa de cortes, CC BY, próprio...
    rights_note       text,
    state             text        NOT NULL DEFAULT 'QUEUED' CHECK (state IN (
                        'QUEUED','DOWNLOADED','TRANSCRIBED','AWAITING_APPROVAL','APPROVED',
                        'RENDERED','DONE','QC_FAILED','FAILED','CANCELLED')),
    failed_state      text,
    attempts          int         NOT NULL DEFAULT 0,
    max_attempts      int         NOT NULL DEFAULT 3,
    locked_until      timestamptz,
    next_run_at       timestamptz NOT NULL DEFAULT now(),
    last_error        text,
    options           jsonb       NOT NULL DEFAULT '{}',  -- auto_approve, max_duration_s, layout, feedback...
    source_path       text,                               -- relativo a MEDIA_DIR
    transcript_source text,                               -- youtube_manual | youtube_auto | whisper
    transcript        jsonb,                              -- [{"w": "palavra", "s": 1.23, "e": 1.50}, ...]
    plan              jsonb,                              -- roteiro do corte (segmentos, título, legenda...)
    plan_version      int         NOT NULL DEFAULT 0,
    approved_at       timestamptz,
    output_path       text,
    output_duration_s numeric(8,2),
    qc_report         jsonb,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX jobs_work_idx ON jobs (state, next_run_at);
CREATE INDEX jobs_source_idx ON jobs (source_id);

CREATE TABLE job_events (
    id         bigserial PRIMARY KEY,
    job_id     bigint      NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    from_state text,
    to_state   text        NOT NULL,
    note       text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX job_events_job_idx ON job_events (job_id, id);

CREATE TABLE generations (
    id            bigserial PRIMARY KEY,
    job_id        bigint REFERENCES jobs(id) ON DELETE SET NULL,
    step          text        NOT NULL,
    provider      text        NOT NULL,
    model         text,
    input_tokens  int,
    output_tokens int,
    units         numeric(12,3),
    cost_usd      numeric(10,5),
    duration_ms   int,
    ok            boolean     NOT NULL,
    error         text,
    meta          jsonb       NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX generations_job_idx ON generations (job_id);
