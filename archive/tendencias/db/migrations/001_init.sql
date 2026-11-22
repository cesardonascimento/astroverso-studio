-- 001_init: schema base da máquina de conteúdo
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------
-- Tendências
-- ---------------------------------------------------------------
CREATE TABLE trend_snapshots (
    id          bigserial PRIMARY KEY,
    source      text        NOT NULL,              -- apify:data_xplorer~tiktok-trends, manual...
    country     text        NOT NULL,
    period_days int,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    raw         jsonb       NOT NULL
);

CREATE TABLE trends (
    id          bigserial PRIMARY KEY,
    snapshot_id bigint      NOT NULL REFERENCES trend_snapshots(id) ON DELETE CASCADE,
    kind        text        NOT NULL CHECK (kind IN ('hashtag','video','sound','topic')),
    name        text        NOT NULL,
    rank        int,
    posts       bigint,
    views       bigint,
    direction   text,                               -- up / down / stable
    industries  text[]      NOT NULL DEFAULT '{}',
    country     text,
    data        jsonb       NOT NULL DEFAULT '{}',
    UNIQUE (snapshot_id, kind, name)
);
CREATE INDEX trends_name_idx ON trends (name);

-- temas que o LLM extrai de um snapshot (o que de fato vira ideia)
CREATE TABLE trend_themes (
    id               bigserial PRIMARY KEY,
    snapshot_id      bigint      NOT NULL REFERENCES trend_snapshots(id) ON DELETE CASCADE,
    theme            text        NOT NULL,
    description      text        NOT NULL,
    related_hashtags text[]      NOT NULL DEFAULT '{}',
    momentum         text,                           -- rising / peaking / stable
    content_angles   jsonb       NOT NULL DEFAULT '[]',
    fit_score        int,                            -- 0-10: quão bem cabe em vídeo faceless com IA
    risk_notes       text,
    model            text,
    prompt_version   text,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------
-- Ideias
-- ---------------------------------------------------------------
CREATE TABLE ideas (
    id                bigserial PRIMARY KEY,
    theme_id          bigint REFERENCES trend_themes(id) ON DELETE SET NULL,
    title             text        NOT NULL,
    hook              text        NOT NULL,
    angle             text        NOT NULL,
    format            text        NOT NULL,
    why_now           text,
    related_hashtags  text[]      NOT NULL DEFAULT '{}',
    language          text        NOT NULL DEFAULT 'pt-BR',
    target_duration_s int,
    scores            jsonb       NOT NULL,          -- notas por critério (0-10) dadas pelo LLM
    similarity_max    numeric(4,3),                  -- maior similaridade com ideias anteriores
    final_score       numeric(6,2) NOT NULL,         -- calculado no código (scoring.py)
    score_breakdown   jsonb       NOT NULL DEFAULT '{}',
    status            text        NOT NULL DEFAULT 'proposed'
                      CHECK (status IN ('proposed','selected','rejected','auto_rejected','produced')),
    model             text,
    prompt_version    text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    decided_at        timestamptz
);
CREATE INDEX ideas_status_score_idx ON ideas (status, final_score DESC);
CREATE INDEX ideas_title_trgm_idx   ON ideas USING gin (title gin_trgm_ops);
CREATE INDEX ideas_hook_trgm_idx    ON ideas USING gin (hook gin_trgm_ops);

-- ---------------------------------------------------------------
-- Roteiros
-- ---------------------------------------------------------------
CREATE TABLE scripts (
    id             bigserial PRIMARY KEY,
    idea_id        bigint      NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    version        int         NOT NULL DEFAULT 1,
    content        jsonb       NOT NULL,             -- roteiro completo (cenas, narração, prompts...)
    caption        text,
    hashtags       text[]      NOT NULL DEFAULT '{}',
    review         jsonb,                            -- revisão automática (fatos, segurança)
    model          text,
    prompt_version text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (idea_id, version)
);

-- ---------------------------------------------------------------
-- Vídeos + máquina de estados
-- ---------------------------------------------------------------
CREATE TABLE videos (
    id            bigserial PRIMARY KEY,
    idea_id       bigint      NOT NULL REFERENCES ideas(id),
    script_id     bigint REFERENCES scripts(id),
    state         text        NOT NULL DEFAULT 'QUEUED' CHECK (state IN (
                    'QUEUED','SCRIPTED','VOICED','VISUALS_READY','RENDERED',
                    'READY_FOR_REVIEW','QC_FAILED','APPROVED','REJECTED',
                    'PUBLISHING','PUBLISHED','FAILED','CANCELLED')),
    failed_state  text,                               -- estado em que falhou (para retomar)
    attempts      int         NOT NULL DEFAULT 0,
    max_attempts  int         NOT NULL DEFAULT 3,
    locked_until  timestamptz,                        -- lease do worker (evita processamento duplo)
    next_run_at   timestamptz NOT NULL DEFAULT now(), -- backoff entre tentativas
    last_error    text,
    settings      jsonb       NOT NULL DEFAULT '{}',  -- variáveis do experimento: voz, ritmo, estilo...
    output_path   text,
    duration_s    numeric(6,2),
    qc_report     jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX videos_work_idx ON videos (state, next_run_at);
-- um vídeo "vivo" por ideia por vez (evita jobs duplicados)
CREATE UNIQUE INDEX videos_one_active_per_idea ON videos (idea_id)
    WHERE state NOT IN ('FAILED','CANCELLED','REJECTED');

CREATE TABLE video_events (
    id         bigserial PRIMARY KEY,
    video_id   bigint      NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    from_state text,
    to_state   text        NOT NULL,
    note       text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX video_events_video_idx ON video_events (video_id, created_at);

CREATE TABLE video_assets (
    id          bigserial PRIMARY KEY,
    video_id    bigint      NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    kind        text        NOT NULL CHECK (kind IN ('voice','image','clip','music','subtitle','render')),
    scene_index int         NOT NULL DEFAULT -1,      -- -1 = asset do vídeo inteiro
    path        text        NOT NULL,                 -- relativo a MEDIA_DIR
    provider    text,
    meta        jsonb       NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (video_id, kind, scene_index)
);

-- ---------------------------------------------------------------
-- Chamadas a providers (custo, tempo, falhas)
-- ---------------------------------------------------------------
CREATE TABLE generations (
    id            bigserial PRIMARY KEY,
    video_id      bigint REFERENCES videos(id) ON DELETE SET NULL,
    idea_id       bigint REFERENCES ideas(id)  ON DELETE SET NULL,
    snapshot_id   bigint REFERENCES trend_snapshots(id) ON DELETE SET NULL,
    step          text        NOT NULL,               -- trend_analysis, ideas, script, review, tts, image...
    provider      text        NOT NULL,
    model         text,
    input_tokens  int,
    output_tokens int,
    units         numeric(12,3),                      -- caracteres, imagens, segundos...
    cost_usd      numeric(10,5),
    duration_ms   int,
    ok            boolean     NOT NULL,
    error         text,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX generations_video_idx ON generations (video_id);
CREATE INDEX generations_created_idx ON generations (created_at);

-- ---------------------------------------------------------------
-- Publicação e métricas (usadas a partir da etapa TikTok)
-- ---------------------------------------------------------------
CREATE TABLE publications (
    id               bigserial PRIMARY KEY,
    video_id         bigint      NOT NULL REFERENCES videos(id),
    platform         text        NOT NULL DEFAULT 'tiktok',
    mode             text        NOT NULL CHECK (mode IN ('inbox','direct')),
    idempotency_key  text        NOT NULL UNIQUE,     -- ex: tiktok:video:42:v1 — impede publicar 2x
    publish_id       text UNIQUE,                      -- devolvido pelo TikTok no init
    status           text        NOT NULL DEFAULT 'pending',
    platform_post_id text,
    raw              jsonb       NOT NULL DEFAULT '{}',
    requested_at     timestamptz NOT NULL DEFAULT now(),
    published_at     timestamptz
);

CREATE TABLE metrics (
    id              bigserial PRIMARY KEY,
    publication_id  bigint      NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
    captured_at     timestamptz NOT NULL DEFAULT now(),
    hours_since_pub numeric(8,2),
    views           bigint,
    likes           bigint,
    comments        bigint,
    shares          bigint,
    saves           bigint,
    avg_watch_s     numeric(8,2),
    completion_rate numeric(5,4),
    raw             jsonb       NOT NULL DEFAULT '{}'
);
CREATE INDEX metrics_pub_idx ON metrics (publication_id, captured_at);

-- ---------------------------------------------------------------
-- Aprendizado: insights que voltam para os prompts
-- ---------------------------------------------------------------
CREATE TABLE insights (
    id         bigserial PRIMARY KEY,
    content    text        NOT NULL,                  -- "hooks com pergunta direta retêm mais..."
    evidence   jsonb       NOT NULL DEFAULT '{}',
    active     boolean     NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
