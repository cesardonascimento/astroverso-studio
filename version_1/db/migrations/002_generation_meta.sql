-- 002: metadados livres por chamada (ex.: custo equivalente em API quando roda pela assinatura)
ALTER TABLE generations ADD COLUMN meta jsonb NOT NULL DEFAULT '{}';
