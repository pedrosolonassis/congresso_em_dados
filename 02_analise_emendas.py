"""
=============================================================
PROJETO 1: Raio-X das Emendas Pix
Arquivo: analise_emendas.py

Descrição:
  Analisa os dados coletados de Emendas Pix (transferências especiais)
  e gera insights.
=============================================================
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import duckdb
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

INPUT_FILE_CSV = "outputs/emendas_pix_2020_2025.csv"
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

COR_PRIMARIA   = "#1a1a2e"
COR_DESTAQUE   = "#e94560"
COR_SECUNDARIA = "#16213e"

plt.rcParams.update({
    "figure.facecolor": COR_PRIMARIA,
    "axes.facecolor":   COR_SECUNDARIA,
    "axes.edgecolor":   "#ffffff33",
    "axes.labelcolor":  "white",
    "xtick.color":      "white",
    "ytick.color":      "white",
    "text.color":       "white",
    "grid.color":       "#ffffff22",
    "font.family":      "monospace",
})

def carregar_dados() -> pd.DataFrame:
    if not os.path.exists(INPUT_FILE_CSV):
        raise FileNotFoundError(f"Arquivo não encontrado: {INPUT_FILE_CSV}")
    log.info(f"Carregando dados de {INPUT_FILE_CSV}...")
    df = pd.read_csv(INPUT_FILE_CSV)
    
    df['uf_favorecido'] = df['localidadedogasto'].astype(str).str.split(' - ').str[-1]
    
    log.info(f"  {len(df):,} registros carregados | {df.shape[1]} colunas")
    return df

def analise_por_uf(df: pd.DataFrame) -> pd.DataFrame:
    query = """
        SELECT
            uf_favorecido                       AS estado,
            COUNT(*)                            AS qtd_emendas,
            SUM(valorempenhado)                 AS total_empenhado,
            SUM(valorpago)                      AS total_pago
        FROM df
        WHERE uf_favorecido IS NOT NULL
          AND uf_favorecido != 'nan'
          AND LENGTH(uf_favorecido) = 2
        GROUP BY uf_favorecido
        ORDER BY total_pago DESC
    """
    return duckdb.query(query).df()

def analise_por_parlamentar(df: pd.DataFrame) -> pd.DataFrame:
    query = """
        SELECT
            nomeautor                           AS parlamentar,
            COUNT(*)                            AS qtd_emendas,
            SUM(valorpago)                      AS total_pago,
            SUM(valorempenhado)                 AS total_empenhado
        FROM df
        WHERE nomeautor IS NOT NULL
        GROUP BY nomeautor
        ORDER BY total_pago DESC
        LIMIT 20
    """
    return duckdb.query(query).df()

def evolucao_historica(df: pd.DataFrame) -> pd.DataFrame:
    query = """
        SELECT
            ano_coleta                          AS ano,
            COUNT(*)                            AS qtd_emendas,
            SUM(valorempenhado)                 AS total_empenhado,
            SUM(valorpago)                      AS total_pago,
            COUNT(DISTINCT nomeautor)           AS parlamentares_ativos
        FROM df
        GROUP BY ano_coleta
        ORDER BY ano_coleta
    """
    return duckdb.query(query).df()

def grafico_top_estados(df_uf: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(12, 7))
    top = df_uf.head(15).sort_values("total_pago")

    bars = ax.barh(top["estado"], top["total_pago"] / 1e6, color=COR_DESTAQUE, alpha=0.85)
    
    ax.bar_label(bars, fmt="R$ %.0fM", padding=5, color="white", fontsize=9)

    ax.set_title("Top 15 Estados - Emendas Pix Recebidas (2020-2025)", fontsize=14, fontweight="bold", pad=15)
    
    ax.set_xlabel("Valor Pago (em milhões R$)")
    
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"R$ {x:.0f}M"))
    
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "01_top_estados_emendas_pix.png"), dpi=150, facecolor=COR_PRIMARIA)
    plt.close()

def grafico_evolucao_historica(df_hist: pd.DataFrame):
    fig, ax1 = plt.subplots(figsize=(13, 6))

    ax1.fill_between(df_hist["ano"], df_hist["total_pago"] / 1e9, alpha=0.3, color=COR_DESTAQUE)
    ax1.plot(df_hist["ano"], df_hist["total_pago"] / 1e9, color=COR_DESTAQUE, linewidth=2.5, marker="o")

    ax1.set_title("Linha do Tempo das Emendas Pix\nCrescimento do Poder Orçamentário", fontsize=13, fontweight="bold", pad=15)
    ax1.set_xlabel("Ano")
    ax1.set_ylabel("Total Pago (R$ bilhões)", color=COR_DESTAQUE)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"R$ {x:.0f}B"))
    ax1.set_xticks(df_hist["ano"])
    ax1.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "02_evolucao_historica_emendas_pix.png"), dpi=150, facecolor=COR_PRIMARIA)
    plt.close()

def grafico_top_parlamentares(df_parl: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(12, 8))

    df_plot = df_parl.head(15).sort_values("total_pago").copy()

    partidos = {
        "JAYME CAMPOS": "UNIÃO",
        "MARCOS ROGERIO": "PL",
        "DAVI ALCOLUMBRE": "UNIÃO",
        "RANDOLFE RODRIGUES": "PT",
        "CARLOS FAVARO": "PSD",
        "MARCELO CASTRO": "MDB",
        "OTTO ALENCAR": "PSD",
        "LUIS CARLOS HEINZE": "PP",
        "GIORDANO": "MDB",
        "ANGELO CORONEL": "PSD",
        "ROGERIO CARVALHO": "PT",
        "STYVENSON VALENTIM": "PODE",
        "RENAN CALHEIROS": "MDB",
        "ELIZIANE GAMA": "PSD",
        "CHICO RODRIGUES": "PSB"
    }
    
    def formatar_nome(nome):
        partido = partidos.get(nome, "")
        return f"{nome} ({partido})" if partido else nome
        
    df_plot["parlamentar_label"] = df_plot["parlamentar"].apply(formatar_nome)

    bars = ax.barh(df_plot["parlamentar_label"], df_plot["total_pago"] / 1e6, color=COR_DESTAQUE, alpha=0.9)
    ax.bar_label(bars, fmt="R$ %.0fM", padding=5, color="white", fontsize=8)

    ax.set_title("Top 15 Parlamentares - Volume de Emendas Pix (2020-2025)", fontsize=13, fontweight="bold", pad=15)
    ax.set_xlabel("Total Pago (R$ milhões)")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"R$ {x:.0f}M"))
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "03_top_parlamentares_emendas_pix.png"), dpi=150, facecolor=COR_PRIMARIA)
    plt.close()

def main():
    log.info("ANÁLISE: Raio-X das Emendas Pix")
    df = carregar_dados()

    log.info("[1/3] Analisando por estado...")
    df_uf = analise_por_uf(df)
    grafico_top_estados(df_uf)

    log.info("[2/3] Evolução histórica...")
    df_hist = evolucao_historica(df)
    grafico_evolucao_historica(df_hist)

    log.info("[3/3] Ranking de parlamentares...")
    df_parl = analise_por_parlamentar(df)
    grafico_top_parlamentares(df_parl)

    log.info("✅ Análise concluída! Imagens salvas na pasta outputs/")

if __name__ == "__main__":
    main()