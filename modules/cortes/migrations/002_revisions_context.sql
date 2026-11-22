-- 002: instruções do pedido, contexto de origem (Discord), histórico de versões do plano

-- de onde veio o pedido e para onde responder (ex.: {"discord": {"channel_id": "...", "message_id": "..."}})
ALTER TABLE jobs ADD COLUMN context jsonb NOT NULL DEFAULT '{}';
-- prompt adicional enviado junto com o link ("foca na parte X", "corte mais curto"...)
ALTER TABLE jobs ADD COLUMN instructions text;
-- pedido de alteração pendente (aplicado na próxima rodada de plano)
ALTER TABLE jobs ADD COLUMN pending_request jsonb;

ALTER TABLE jobs DROP CONSTRAINT jobs_state_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_state_check CHECK (state IN (
    'QUEUED','DOWNLOADED','TRANSCRIBED','AWAITING_APPROVAL','APPROVED',
    'RENDERED','DONE','QC_FAILED','FAILED','CANCELLED'));

-- cada versão do plano (original, replan, revisão pós-vídeo) fica guardada
CREATE TABLE job_plans (
    id         bigserial PRIMARY KEY,
    job_id     bigint      NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    version    int         NOT NULL,
    kind       text        NOT NULL CHECK (kind IN ('initial','replan','revision')),
    request    text,                                  -- pedido que gerou esta versão
    plan       jsonb       NOT NULL,
    output_path text,                                 -- vídeo renderizado desta versão
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (job_id, version)
);
