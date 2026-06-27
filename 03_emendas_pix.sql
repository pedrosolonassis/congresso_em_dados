-- =============================================================
-- PROJETO 1: Raio-X das Emendas Pix
-- Arquivo: emendas_pix.sql
--
-- Queries de análise prontas para uso no DuckDB, SQLite ou
-- qualquer banco que suporte SQL padrão.
-- Tabela esperada: emendas_pix (gerada pelo coleta_emendas.py)
-- =============================================================


-- ── 1. VISÃO GERAL ────────────────────────────────────────────
-- Resumo total da base
SELECT
    COUNT(*)                                AS total_registros,
    COUNT(DISTINCT nome_parlamentar)        AS parlamentares_unicos,
    COUNT(DISTINCT uf_favorecido)           AS estados_beneficiados,
    MIN(ano_coleta)                         AS ano_inicio,
    MAX(ano_coleta)                         AS ano_fim,
    SUM(valor_empenhado)                    AS total_empenhado,
    SUM(valor_pago)                         AS total_pago,
    SUM(valor_empenhado) - SUM(valor_pago)  AS diferenca_empenho_pagamento
FROM emendas_pix;


-- ── 2. RANKING DE ESTADOS ─────────────────────────────────────
-- Top 10 estados que mais receberam emendas Pix (2020-2025)
SELECT
    uf_favorecido                           AS estado,
    COUNT(*)                                AS qtd_emendas,
    SUM(valor_pago)                         AS total_pago,
    ROUND(SUM(valor_pago) * 100.0 / SUM(SUM(valor_pago)) OVER (), 2) AS perc_total
FROM emendas_pix
WHERE ano_coleta >= 2020
GROUP BY uf_favorecido
ORDER BY total_pago DESC
LIMIT 10;


-- ── 3. CONCENTRAÇÃO PARLAMENTAR ───────────────────────────────
-- Qual percentual do total é dominado pelos top 10% de parlamentares?
-- (Indicador de concentração / Curva de Lorenz simplificada)
WITH ranking AS (
    SELECT
        nome_parlamentar,
        SUM(valor_pago)                     AS total_parlamentar,
        NTILE(10) OVER (ORDER BY SUM(valor_pago)) AS decil
    FROM emendas_pix
    GROUP BY nome_parlamentar
)
SELECT
    decil,
    COUNT(*)                                AS qtd_parlamentares,
    SUM(total_parlamentar)                  AS soma_decil,
    ROUND(SUM(total_parlamentar) * 100.0 /
          SUM(SUM(total_parlamentar)) OVER (), 2) AS perc_total
FROM ranking
GROUP BY decil
ORDER BY decil DESC;


-- ── 4. CRESCIMENTO ANUAL ──────────────────────────────────────
-- Variação ano a ano do volume de emendas Pix
SELECT
    ano_coleta                              AS ano,
    SUM(valor_pago)                         AS total_pago,
    LAG(SUM(valor_pago)) OVER (ORDER BY ano_coleta)
                                            AS total_pago_ano_anterior,
    ROUND(
        (SUM(valor_pago) - LAG(SUM(valor_pago)) OVER (ORDER BY ano_coleta))
        * 100.0
        / NULLIF(LAG(SUM(valor_pago)) OVER (ORDER BY ano_coleta), 0),
        2
    )                                       AS variacao_percentual
FROM emendas_pix
GROUP BY ano_coleta
ORDER BY ano_coleta;


-- ── 5. PERFIL DOS TOP 20 PARLAMENTARES ───────────────────────
-- Parlamentares com maior volume de emendas Pix destinadas
SELECT
    nome_parlamentar                        AS parlamentar,
    partido_politico                        AS partido,
    uf_parlamentar                          AS uf,
    COUNT(*)                                AS qtd_emendas,
    SUM(valor_pago)                         AS total_pago,
    AVG(valor_pago)                         AS ticket_medio,
    COUNT(DISTINCT uf_favorecido)           AS estados_beneficiados
FROM emendas_pix
GROUP BY nome_parlamentar, partido_politico, uf_parlamentar
ORDER BY total_pago DESC
LIMIT 20;


-- ── 6. ANÁLISE DE TRANSPARÊNCIA ───────────────────────────────
-- Emendas com baixa execução (empenhado mas não pago > 50%)
SELECT
    nome_parlamentar                        AS parlamentar,
    partido_politico                        AS partido,
    COUNT(*)                                AS qtd_emendas_pendentes,
    SUM(valor_empenhado)                    AS total_empenhado,
    SUM(valor_pago)                         AS total_pago,
    SUM(valor_empenhado - valor_pago)       AS valor_nao_executado,
    ROUND(
        SUM(valor_empenhado - valor_pago) * 100.0
        / NULLIF(SUM(valor_empenhado), 0), 2
    )                                       AS perc_nao_executado
FROM emendas_pix
WHERE valor_empenhado > 0
  AND (valor_empenhado - valor_pago) / valor_empenhado > 0.5
GROUP BY nome_parlamentar, partido_politico
HAVING qtd_emendas_pendentes >= 5
ORDER BY valor_nao_executado DESC
LIMIT 20;


-- ── 7. DESTINOS INTRAESTADO ───────────────────────────────────
-- Parlamentar que mais destina recursos FORA do seu estado de origem
SELECT
    nome_parlamentar                        AS parlamentar,
    uf_parlamentar                          AS uf_origem,
    COUNT(DISTINCT uf_favorecido)           AS estados_destino,
    SUM(CASE WHEN uf_favorecido != uf_parlamentar
             THEN valor_pago ELSE 0 END)    AS valor_fora_estado,
    SUM(valor_pago)                         AS total_pago,
    ROUND(
        SUM(CASE WHEN uf_favorecido != uf_parlamentar
                 THEN valor_pago ELSE 0 END) * 100.0
        / NULLIF(SUM(valor_pago), 0), 2
    )                                       AS perc_fora_estado
FROM emendas_pix
GROUP BY nome_parlamentar, uf_parlamentar
ORDER BY perc_fora_estado DESC
LIMIT 20;