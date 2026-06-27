-- =============================================================
-- PROJETO 2: Eficiência Partidária na Cota Parlamentar
-- Arquivo: cotas_sql_queries.sql
--
-- Análises comparativas de gasto da CEAP por partido,
-- espectro ideológico e categorias de despesa.
-- Tabela: cotas_parlamentares
-- =============================================================


-- ── 1. RANKING GERAL DE GASTOS ────────────────────────────────
SELECT
    parlamentar,
    partido,
    espectro,
    uf,
    SUM(valor_liquido)              AS total_gasto,
    COUNT(*)                        AS qtd_notas_fiscais,
    AVG(valor_liquido)              AS ticket_medio,
    MAX(valor_liquido)              AS maior_nota
FROM cotas_parlamentares
WHERE valor_liquido > 0
GROUP BY parlamentar, partido, espectro, uf
ORDER BY total_gasto DESC
LIMIT 30;


-- ── 2. GASTOS POR ESPECTRO IDEOLÓGICO ────────────────────────
SELECT
    espectro,
    COUNT(DISTINCT parlamentar)             AS n_parlamentares,
    SUM(valor_liquido)                      AS total_gasto,
    SUM(valor_liquido)
        / COUNT(DISTINCT parlamentar)       AS media_por_parlamentar,
    AVG(valor_liquido)                      AS ticket_medio_transacao
FROM cotas_parlamentares
WHERE espectro NOT IN ('Não classificado')
  AND valor_liquido > 0
GROUP BY espectro
ORDER BY media_por_parlamentar DESC;


-- ── 3. TOP CATEGORIAS DE DESPESA POR ESPECTRO ────────────────
-- (responde: esquerda gasta mais em viagens? direita em divulgação?)
WITH totais_espectro AS (
    SELECT espectro, SUM(valor_liquido) AS total_espectro
    FROM cotas_parlamentares
    WHERE valor_liquido > 0
    GROUP BY espectro
)
SELECT
    c.espectro,
    c.tipo_despesa,
    SUM(c.valor_liquido)                    AS total_categoria,
    te.total_espectro,
    ROUND(SUM(c.valor_liquido) * 100.0
          / te.total_espectro, 2)           AS perc_do_espectro
FROM cotas_parlamentares c
JOIN totais_espectro te ON c.espectro = te.espectro
WHERE c.valor_liquido > 0
  AND c.espectro NOT IN ('Não classificado')
GROUP BY c.espectro, c.tipo_despesa, te.total_espectro
ORDER BY c.espectro, total_categoria DESC;


-- ── 4. VARIAÇÃO MENSAL (SAZONALIDADE DOS GASTOS) ─────────────
SELECT
    mes,
    espectro,
    AVG(valor_liquido)                      AS media_mensal,
    SUM(valor_liquido)                      AS total_mensal
FROM cotas_parlamentares
WHERE valor_liquido > 0
  AND mes BETWEEN 1 AND 12
GROUP BY mes, espectro
ORDER BY mes, espectro;


-- ── 5. ALERTAS: NOTAS FISCAIS SUSPEITAS ─────────────────────
-- Transações com valor acima de 3 desvios padrão da média
WITH stats AS (
    SELECT
        tipo_despesa,
        AVG(valor_liquido)      AS media,
        STDDEV(valor_liquido)   AS desvio
    FROM cotas_parlamentares
    WHERE valor_liquido > 0
    GROUP BY tipo_despesa
)
SELECT
    c.parlamentar,
    c.partido,
    c.tipo_despesa,
    c.fornecedor,
    c.valor_liquido,
    c.data_emissao,
    ROUND((c.valor_liquido - s.media) / NULLIF(s.desvio, 0), 2) AS z_score
FROM cotas_parlamentares c
JOIN stats s ON c.tipo_despesa = s.tipo_despesa
WHERE c.valor_liquido > 0
  AND (c.valor_liquido - s.media) / NULLIF(s.desvio, 0) > 3
ORDER BY z_score DESC
LIMIT 50;


-- ── 6. DIVERSIFICAÇÃO DE GASTOS ──────────────────────────────
-- Parlamentares que usam mais categorias (vs. concentrados em poucas)
SELECT
    parlamentar,
    partido,
    espectro,
    COUNT(DISTINCT tipo_despesa)            AS categorias_distintas,
    SUM(valor_liquido)                      AS total_gasto,
    -- Índice de concentração (1 = gasta tudo em 1 categoria)
    MAX(SUM(valor_liquido))
        OVER (PARTITION BY parlamentar)
        / NULLIF(SUM(SUM(valor_liquido))
        OVER (PARTITION BY parlamentar), 0) AS indice_concentracao
FROM cotas_parlamentares
WHERE valor_liquido > 0
GROUP BY parlamentar, partido, espectro
ORDER BY categorias_distintas DESC
LIMIT 30;