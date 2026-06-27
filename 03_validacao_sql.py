import duckdb

print("Iniciando motor analítico do DuckDB...\n")

# Conecta ao DuckDB em memória
con = duckdb.connect(database=':memory:')

# 1. Criamos uma "View" (Tabela Virtual) lendo o seu CSV e ajustando os nomes
# Usamos a função RIGHT() do SQL para pegar a sigla do estado, igual fizemos no DAX!
con.execute("""
    CREATE VIEW emendas_pix AS 
    SELECT 
        ano_coleta,
        nomeautor AS nome_parlamentar,
        valorpago AS valor_pago,
        valorempenhado AS valor_empenhado,
        CASE 
            WHEN localidadedogasto LIKE '% - %' THEN RIGHT(localidadedogasto, 2)
            ELSE 'Nacional/Múltiplo' 
        END AS uf_favorecido
    FROM read_csv_auto('outputs/emendas_pix_2014_2025.csv')
""")

# 2. Rodamos a Query Avançada de Crescimento Anual (Copiada do seu arquivo .sql)
query_crescimento = """
    SELECT
        ano_coleta AS ano,
        SUM(valor_pago) AS total_pago,
        LAG(SUM(valor_pago)) OVER (ORDER BY ano_coleta) AS total_pago_ano_anterior,
        ROUND(
            (SUM(valor_pago) - LAG(SUM(valor_pago)) OVER (ORDER BY ano_coleta))
            * 100.0
            / NULLIF(LAG(SUM(valor_pago)) OVER (ORDER BY ano_coleta), 0),
            2
        ) AS variacao_percentual
    FROM emendas_pix
    GROUP BY ano_coleta
    ORDER BY ano_coleta;
"""

print("📊 RESULTADO DA QUERY DE CRESCIMENTO ANUAL (WINDOW FUNCTION):")
resultado = con.execute(query_crescimento).df()

# Formatando os valores para ficar bonito no terminal (em Milhões/Bilhões)
resultado['total_pago'] = resultado['total_pago'].apply(lambda x: f"R$ {x/1e9:.2f} Bi" if x > 1e9 else f"R$ {x/1e6:.2f} Mi")
print(resultado.to_string(index=False))