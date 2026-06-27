"""
=============================================================
PROJETO 2: Eficiência Partidária na Cota Parlamentar
Arquivo: analise_cotas.py

Descrição:
  Compara padrões de gastos da cota parlamentar entre espectros
  ideológicos. Responde perguntas como:
    - Partidos de esquerda gastam diferente dos de direita?
    - Quais categorias (viagens, marketing, etc.) são prioritárias
      para cada espectro político?
    - Quem são os deputados mais e menos eficientes?

Pré-requisito: executar coleta_cotas.py primeiro.
=============================================================
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import duckdb
import numpy as np
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

INPUT_FILE = "outputs/cotas_parlamentares.parquet"
OUTPUT_DIR = "outputs"

# Paleta ideológica
CORES_ESPECTRO = {
    "Esquerda":        "#e63946",
    "Centro-Esquerda": "#f4a261",
    "Centro":          "#a8dadc",
    "Centro-Direita":  "#457b9d",
    "Direita":         "#1d3557",
    "Não classificado":"#6c757d",
}

ESPECTRO_IDEOLOGICO = {
    # Esquerda
    "PSOL": "Esquerda", "PT": "Esquerda", "PCDOB": "Esquerda", "PPL": "Esquerda",
    
    # Centro-Esquerda
    "PDT": "Centro-Esquerda", "PSB": "Centro-Esquerda", "REDE": "Centro-Esquerda", "PV": "Centro-Esquerda",
    
    # Centro
    "MDB": "Centro", "PSD": "Centro", "PODEMOS": "Centro", "PROS": "Centro", "AVANTE": "Centro",
    
    # Centro-Direita
    "PSDB": "Centro-Direita", "CIDADANIA": "Centro-Direita", "PPS": "Centro-Direita", 
    "PHS": "Centro-Direita", "AGIR": "Centro-Direita",
    
    # Direita
    "PP": "Direita", "PL": "Direita", "PR": "Direita", "REPUBLICANOS": "Direita", "PRB": "Direita",
    "UNIÃO": "Direita", "PSL": "Direita", "DEM": "Direita", "NOVO": "Direita", 
    "SOLIDARIEDADE": "Direita", "PRD": "Direita", "PATRIOTA": "Direita", 
    "PATRI": "Direita", "PTB": "Direita", "PSC": "Direita", "MISSÃO": "Direita"
}

plt.rcParams.update({
    "figure.facecolor": "#0d1117",
    "axes.facecolor":   "#161b22",
    "axes.edgecolor":   "#30363d",
    "axes.labelcolor":  "#c9d1d9",
    "xtick.color":      "#c9d1d9",
    "ytick.color":      "#c9d1d9",
    "text.color":       "#c9d1d9",
    "grid.color":       "#21262d",
    "font.family":      "monospace",
})

def limpar_categoria(descricao):
    texto = str(descricao).upper()

    # ── BIG 6 ──────────────────────────────────────────────────────────
    if 'DIVULGA' in texto:                                   return 'Publicidade e Marketing'
    if 'AUTOMOTOR' in texto:                                 return 'Locação de Veículos'
    if 'ESCRIT' in texto or 'MANUTEN' in texto:              return 'Escritório de Apoio'
    if 'COMBUST' in texto:                                   return 'Combustíveis e Lubrificantes'
    if 'CONSULTORIA' in texto or 'PESQUISA' in texto:        return 'Consultorias e Pesquisas'

    # ── PASSAGENS (blindado contra encoding corrompido) ─────────────────
    if 'TERRESTRE' in texto or 'FLUVIAIS' in texto or 'MARITIMA' in texto or 'MARÍTIMA' in texto:
                                                             return 'Passagens Terrestres e Fluviais'
    if 'PASSAGEM' in texto or 'PASSAGEN' in texto or 'AÉRE' in texto or 'AÃRE' in texto:
                                                             return 'Passagens Aéreas'

    # ── DEMAIS ──────────────────────────────────────────────────────────
    if 'ALIMENTA' in texto:                                  return 'Alimentação'
    if 'HOSPEDAGEM' in texto:                                return 'Hospedagem'
    if 'AERONAVE' in texto:                                  return 'Locação de Aeronaves'
    if 'EMBARCA' in texto:                                   return 'Locação de Embarcações'
    if 'CURSO' in texto or 'PALESTRA' in texto:              return 'Cursos e Palestras'
    if 'SEGURAN' in texto or 'SEGURA' in texto:              return 'Segurança Privada'
    if 'TOKEN' in texto or 'CERTIFICADO' in texto:           return 'Certificados Digitais'
    if 'ESTACIONAMENTO' in texto or 'PEDÁGIO' in texto or 'PEDAGIO' in texto \
       or 'PEDÃGIO' in texto or 'TÁXI' in texto or 'TAXI' in texto or 'TÃXI' in texto:
                                                             return 'Táxi, Pedágio e Estacionamento'
    if 'POSTAIS' in texto or 'POSTAL' in texto:              return 'Serviços Postais'
    if 'TELEFONIA' in texto:                                 return 'Telefonia'
    if 'ASSINATURA' in texto or 'PUBLICA' in texto:          return 'Assinaturas de Publicações'

    return 'Outros'

def carregar_dados():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"Execute coleta_cotas.py primeiro. Arquivo não encontrado: {INPUT_FILE}")
    
    df = pd.read_parquet(INPUT_FILE)
    
    # 1. Blindagem: Remove lixo invisível (BOM) e força colunas para minúsculo
    df.columns = [str(c).replace('ï»¿', '').replace('"', '').strip().lower() for c in df.columns]
    
    # 2. Dicionário de Dados Mestre: Renomeia as colunas cruas para o padrão BI
    df = df.rename(columns={
        'txnomeparlamentar': 'parlamentar',
        'txtdescricao': 'tipo_despesa',
        'sgpartido': 'partido',
        'vlrliquido': 'valor_liquido',
        'sguf': 'uf',
        'idecadastro': 'id_deputado',
        'txtdescricaoespecificacao': 'subcategoria_despesa',
        'fornecedor': 'nome_fornecedor',
        'cnpj_cpf': 'cnpj_cpf_fornecedor',
        'numero_doc': 'numero_fatura',
        'valor_documento': 'valor_bruto',
        'valor_glosa': 'valor_recusado',  
        'txtpassageiro': 'nome_passageiro',
        'txttrecho': 'trecho_viagem',
        'vlrrestituicao': 'valor_devolvido',
        'urldocumento': 'url_fatura_pdf'
    })

    if 'parlamentar' in df.columns:
        df['parlamentar'] = df['parlamentar'].str.title()
        
        preposicoes = [' Da ', ' De ', ' Di ', ' Do ', ' Das ', ' Dos ']
        for prep in preposicoes:
            df['parlamentar'] = df['parlamentar'].str.replace(prep, prep.lower(), regex=False)

    # 3. A Peça Faltante: Padronização histórica e criação do espectro
    if 'partido' in df.columns:
        # Coloca tudo em maiúsculo para garantir o padrão
        df['partido'] = df['partido'].str.upper()
        
        # Unifica partidos que mudaram de nome ou se fundiram
        padrao_historico = {
            "PATRI": "PATRIOTA",
            "PRB": "REPUBLICANOS",
            "PR": "PL",
            "PPS": "CIDADANIA",
            "PODE": "PODEMOS",
            "PTN": "PODEMOS",
            "PMDB": "MDB",
            "PTDOB": "AVANTE",
            "PSDC": "DC",
            "PEN": "PATRIOTA"
        }
        df['partido'] = df['partido'].replace(padrao_historico)
        
        # Mapeia o espectro
        df['espectro'] = df['partido'].map(ESPECTRO_IDEOLOGICO).fillna('Não classificado')
    else:
        df['espectro'] = 'Não classificado'

    # 4. Aplica a limpeza nas categorias (As "Big 6")
    if 'tipo_despesa' in df.columns:
        df['tipo_despesa'] = df['tipo_despesa'].apply(limpar_categoria)

    # 5. Salva a versão limpa e definitiva no disco para o Power BI
    df.to_parquet(INPUT_FILE, index=False)
        
    log.info(f"Dados carregados e limpos: {len(df):,} registros")
    return df

# ── Análise 1: Distribuição por espectro ideológico ───────────────────────────

def gasto_por_espectro(df: pd.DataFrame) -> pd.DataFrame:
    query = """
        SELECT
            espectro,
            COUNT(DISTINCT parlamentar)             AS n_parlamentares,
            SUM(valor_liquido)                      AS total_gasto,
            AVG(valor_liquido)                      AS media_por_transacao,
            SUM(valor_liquido) / COUNT(DISTINCT parlamentar) AS gasto_medio_por_parlamentar
        FROM df
        WHERE espectro != 'Não classificado'
          AND valor_liquido > 0
        GROUP BY espectro
        ORDER BY total_gasto DESC
    """
    return duckdb.query(query).df()


# ── Análise 2: Categorias de gasto por espectro ───────────────────────────────

def categorias_por_espectro(df: pd.DataFrame) -> pd.DataFrame:
    query = """
        SELECT
            espectro,
            tipo_despesa,
            SUM(valor_liquido)                      AS total,
            COUNT(*)                                AS qtd_transacoes
        FROM df
        WHERE espectro != 'Não classificado'
          AND valor_liquido > 0
          AND tipo_despesa IS NOT NULL
          AND tipo_despesa != 'nan'
        GROUP BY espectro, tipo_despesa
    """
    df_raw = duckdb.query(query).df()

    # Normaliza por espectro (% do total de cada espectro)
    df_raw["perc"] = df_raw.groupby("espectro")["total"].transform(
        lambda x: x / x.sum() * 100
    )
    return df_raw


# ── Análise 3: Top/Bottom parlamentares por eficiência ────────────────────────

def ranking_gastos(df: pd.DataFrame) -> pd.DataFrame:
    query = """
        SELECT
            parlamentar,
            partido,
            espectro,
            uf,
            SUM(valor_liquido)          AS total_gasto,
            COUNT(*)                    AS qtd_notas,
            COUNT(DISTINCT tipo_despesa) AS categorias_usadas
        FROM df
        WHERE valor_liquido > 0
        GROUP BY parlamentar, partido, espectro, uf
        ORDER BY total_gasto DESC
    """
    return duckdb.query(query).df()


# ── Visualização 1: Heatmap de categorias por espectro ────────────────────────

def grafico_heatmap_categorias(df_cat: pd.DataFrame):
    # Pivota: linhas = categorias, colunas = espectro
    pivot = df_cat.pivot_table(
        index="tipo_despesa", columns="espectro", values="perc", aggfunc="sum", fill_value=0
    )

    # Filtra as 12 maiores categorias por total
    top_cats = (
        df_cat.groupby("tipo_despesa")["total"].sum()
        .nlargest(12).index.tolist()
    )
    pivot = pivot.loc[pivot.index.isin(top_cats)]

    # Ordena colunas da esquerda para direita
    ordem_espectro = ["Esquerda", "Centro-Esquerda", "Centro", "Centro-Direita", "Direita"]
    pivot = pivot[[c for c in ordem_espectro if c in pivot.columns]]

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.heatmap(
        pivot, ax=ax, cmap="RdYlBu_r", annot=True, fmt=".1f",
        linewidths=0.5, linecolor="#0d1117",
        cbar_kws={"label": "% do gasto do espectro"},
    )
    ax.set_title(
        "🔥 Prioridades de Gasto por Espectro Ideológico\n(% do total gasto por cada espectro político)",
        fontsize=13, fontweight="bold", pad=15
    )
    ax.set_xlabel("Espectro Político")
    ax.set_ylabel("Categoria de Despesa")
    plt.xticks(rotation=15)
    plt.yticks(rotation=0)
    plt.tight_layout()

    caminho = os.path.join(OUTPUT_DIR, "05_heatmap_categorias_espectro.png")
    plt.savefig(caminho, dpi=150, bbox_inches="tight", facecolor="#0d1117")
    plt.close()
    log.info(f"  Heatmap salvo: {caminho}")


# ── Visualização 2: Boxplot de gasto por parlamentar, por espectro ────────────

def grafico_boxplot_espectro(df_rank: pd.DataFrame):
    ordem = ["Esquerda", "Centro-Esquerda", "Centro", "Centro-Direita", "Direita"]
    df_plot = df_rank[df_rank["espectro"].isin(ordem)].copy()

    fig, ax = plt.subplots(figsize=(12, 7))
    palette = {e: CORES_ESPECTRO[e] for e in ordem if e in CORES_ESPECTRO}

    sns.boxplot(
        data=df_plot, x="espectro", y="total_gasto",
        order=ordem, palette=palette, ax=ax,
        flierprops=dict(marker="o", markersize=3, alpha=0.3),
        width=0.5,
    )

    ax.set_title(
        "📦 Distribuição de Gastos da Cota por Parlamentar\nAgrupado por Espectro Ideológico",
        fontsize=13, fontweight="bold", pad=15
    )
    ax.set_xlabel("Espectro Político")
    ax.set_ylabel("Total Gasto (R$)")
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"R$ {x/1e3:.0f}k")
    )
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    caminho = os.path.join(OUTPUT_DIR, "06_boxplot_gasto_espectro.png")
    plt.savefig(caminho, dpi=150, bbox_inches="tight", facecolor="#0d1117")
    plt.close()
    log.info(f"  Boxplot salvo: {caminho}")


def main():
    log.info("=" * 60)
    log.info("ANÁLISE: Eficiência Partidária na Cota Parlamentar")
    log.info("=" * 60)

    df = carregar_dados()

    log.info("\n[1/3] Gasto por espectro ideológico...")
    df_espectro = gasto_por_espectro(df)
    print("\n--- Gasto médio por parlamentar, por espectro ---")
    print(df_espectro[["espectro", "n_parlamentares", "gasto_medio_por_parlamentar"]]
          .to_string(index=False))

    log.info("\n[2/3] Categorias por espectro...")
    df_cat = categorias_por_espectro(df)
    grafico_heatmap_categorias(df_cat)

    log.info("\n[3/3] Ranking de gastos...")
    df_rank = ranking_gastos(df)
    grafico_boxplot_espectro(df_rank)

    # Exporta
    df_rank.to_csv(os.path.join(OUTPUT_DIR, "ranking_gastos_parlamentares.csv"),
                   index=False, encoding="utf-8-sig")
    log.info("\n✅ Análise de cotas concluída!")


if __name__ == "__main__":
    main()