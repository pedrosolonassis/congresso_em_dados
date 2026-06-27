"""
=============================================================
PROJETO 3: A Bancada dos Gastos
Arquivo: analise_custo_mandato.py

Descrição:
  Correlaciona o custo total do mandato (cotas + emendas) com
  a produção legislativa (projetos de lei apresentados).
  Identifica os 10 parlamentares mais caros e compara com
  sua produtividade legislativa usando faixas estatísticas.

Fontes:
  - Cotas: outputs/cotas_parlamentares.parquet
  - Emendas: outputs/emendas_pix_2014_2025.parquet
  - Proposições: API Câmara (dadosabertos.camara.leg.br)
=============================================================
"""

import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import duckdb
import numpy as np
import time
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUTPUT_DIR = "outputs"
API_PROPOSICOES = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"


# ── Coleta de proposições via API da Câmara ───────────────────────────────────

def buscar_proposicoes_deputado(id_dep: int, ano: int) -> int:
    """
    Retorna o número de proposições apresentadas por um deputado num ano.
    """
    params = {
        "idDeputadoAutor": id_dep,
        "ano": ano,
        "itens": 1,          
        "pagina": 1,
    }
    try:
        resp = requests.get(API_PROPOSICOES, params=params, timeout=20)
        if resp.status_code == 200:
            total = int(resp.headers.get("X-Total-Count", 0))
            return total
    except Exception as e:
        log.warning(f"Falha na API para ID {id_dep} no ano {ano}: {e}")
    return 0


def coletar_producao_legislativa(df_deps: pd.DataFrame, anos: list) -> pd.DataFrame:
    log.info("A INICIAR EXTRAÇÃO EM MASSA (FULL LOAD)... Isto pode demorar vários minutos.")
    resultados = []
    
    total_deputados = len(df_deps)
    contador = 1

    for _, dep in df_deps.iterrows():
        total_props = 0
        for ano in anos:
            n = buscar_proposicoes_deputado(int(dep["id"]), ano)
            total_props += n
            time.sleep(0.5) 

        resultados.append({
            "id_parlamentar": dep["id"],
            "parlamentar": dep["nome"],
            "partido": dep.get("siglaPartido", ""), # Pegamos o partido aqui
            "uf": dep.get("siglaUf", ""),           # Pegamos a UF aqui
            "total_proposicoes": total_props,
        })
        log.info(f"  [{contador}/{total_deputados}] {dep['nome']}: {total_props} proposições")
        contador += 1

    return pd.DataFrame(resultados)


# ── Análise de custo vs. produção ─────────────────────────────────────────────

def calcular_custo_mandato(df_cotas: pd.DataFrame) -> pd.DataFrame:
    # Removemos partido do GROUP BY do custo para evitar duplicados caso o parlamentar mude de partido.
    # O partido oficial será o que vier da API (df_prod)
    query = """
        SELECT
            parlamentar,
            SUM(valor_liquido)              AS custo_cota,
            COUNT(*)                        AS qtd_notas
        FROM df_cotas
        WHERE valor_liquido > 0
        GROUP BY parlamentar
    """
    return duckdb.query(query).df()


def correlacionar_custo_producao(df_custo: pd.DataFrame,
                                  df_prod: pd.DataFrame) -> pd.DataFrame:
    """Junta custo do mandato com produção legislativa e aplica faixas de análise."""
    
    # Merge usando a coluna 'parlamentar'
    # Agora df_prod traz partido e UF
    df_merged = df_custo.merge(
        df_prod[["parlamentar", "partido", "uf", "total_proposicoes"]], 
        on="parlamentar",
        how="inner"
    )

    # CORREÇÃO 1: Força o arredondamento de 2 casas decimais (centavos) para o Power BI não bugar
    df_merged["custo_cota"] = df_merged["custo_cota"].round(2)

    # Calcula custo por proposição apenas como métrica secundária
    df_merged["custo_por_proposicao"] = (
        df_merged["custo_cota"] /
        df_merged["total_proposicoes"].replace(0, np.nan)
    ).round(2)

    # CORREÇÃO 2: Novas Categorias (Regras de Negócio Ajustadas para 9 faixas)
    def categorizar(row):
        custo = row["custo_cota"]
        prod = row["total_proposicoes"]
        
        # Faixas de Custo
        if custo <= 1_300_000:
            cat_custo = "Baixo Custo"
        elif custo <= 2_500_000:
            cat_custo = "Médio Custo"
        else:
            cat_custo = "Alto Custo"
            
        # Faixas de Volume de Produção (Qtd Documentos)
        if prod < 300:
            cat_prod = "Baixo Volume"
        elif prod <= 800:
            cat_prod = "Médio Volume"
        else:
            cat_prod = "Alto Volume"
            
        # Alertas Visuais para Extremos
        if cat_custo == "Alto Custo" and cat_prod == "Baixo Volume":
            return "Alto Custo / Baixo Volume 🔴"
        elif cat_custo == "Baixo Custo" and cat_prod == "Alto Volume":
            return "Baixo Custo / Alto Volume 🟢"
        elif cat_custo == "Alto Custo" and cat_prod == "Médio Volume":
            return "Alto Custo / Médio Volume 🟡"
            
        return f"{cat_custo} / {cat_prod}"

    # Note que aqui estou usando 'atividade_volume' conforme estava no seu último print
    df_merged["atividade_volume"] = df_merged.apply(categorizar, axis=1)
    
    # Preenchemos partidos ou UFs vazios com "N/I" (Não Informado) para evitar erros no Power BI
    df_merged['partido'] = df_merged['partido'].fillna("N/I")
    df_merged['uf'] = df_merged['uf'].fillna("N/I")
    
    return df_merged.sort_values("custo_cota", ascending=False)


# ── Visualizações ──────────────────────────────────────────────────────────────

def grafico_scatter_custo_producao(df: pd.DataFrame):
    """Scatter plot: custo do mandato × volume de projetos."""
    
    CORES_CAT = {
        "Alto Custo / Baixo Volume 🔴": "#e63946",  # Vermelho Alerta
        "Alto Custo / Médio Volume 🟡": "#ffb703",
        "Alto Custo / Alto Volume":     "#e9c46a",  # Amarelo
        
        "Médio Custo / Baixo Volume":   "#9c89b8",  # Roxo
        "Médio Custo / Médio Volume":   "#6c757d",  # Cinza Neutro
        "Médio Custo / Alto Volume":    "#2a9d8f",  # Verde Água
        
        "Baixo Custo / Baixo Volume":   "#457b9d",  # Azul
        "Baixo Custo / Médio Volume":   "#81b29a",  # Verde Claro
        "Baixo Custo / Alto Volume 🟢": "#2b9348",  # Verde Forte
    }

    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")

    for cat, cor in CORES_CAT.items():
        sub = df[df["atividade_volume"] == cat]
        if not sub.empty:
            ax.scatter(
                sub["total_proposicoes"], sub["custo_cota"] / 1e6,
                c=cor, alpha=0.75, s=60, label=cat, edgecolors="none"
            )

    ax.set_xlabel("Volume Total de Proposições (Qtd. Documentos)", color="#c9d1d9")
    ax.set_ylabel("Custo da Cota Parlamentar (R$ Milhões)", color="#c9d1d9")
    ax.set_title(
        "🎯 Gasto vs Volume de Atividade no Mandato\nCada ponto = 1 parlamentar",
        fontsize=14, fontweight="bold", color="white", pad=15
    )
    
    # Ajusta a legenda para caber as 9 categorias
    ax.legend(facecolor="#21262d", edgecolor="#30363d", labelcolor="white", 
              fontsize=8, loc='upper right', bbox_to_anchor=(1.25, 1))
    
    ax.grid(alpha=0.15)
    ax.tick_params(colors="#c9d1d9")

    plt.tight_layout()
    caminho = os.path.join(OUTPUT_DIR, "07_scatter_custo_producao.png")
    plt.savefig(caminho, dpi=150, bbox_inches="tight", facecolor="#0d1117")
    plt.close()
    log.info(f"  Scatter salvo: {caminho}")


def grafico_bancada_dos_gastos(df: pd.DataFrame):
    """Perfil dos 10 parlamentares mais caros."""
    top10 = df.nlargest(10, "custo_cota").reset_index(drop=True)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.patch.set_facecolor("#0d1117")
    fig.suptitle(
        "A Bancada dos Gastos - Top 10 Parlamentares mais caros (2019-2025)",
        fontsize=14, fontweight="bold", color="white", y=1.02
    )

    # Gráfico 1: Custo da cota
    ax = axes[0]
    ax.set_facecolor("#161b22")
    nomes = top10["parlamentar"].apply(lambda x: x[:20])
    bars = ax.barh(nomes[::-1], top10["custo_cota"][::-1] / 1e6, 
                   color="#e63946", alpha=0.85)
    ax.bar_label(bars, fmt="R$ %.1fM", padding=5, color="white", fontsize=8)
    ax.set_xlabel("Custo da Cota (R$ Milhões)", color="#c9d1d9")
    ax.set_title("Custo Total do Mandato", color="white")
    ax.tick_params(colors="#c9d1d9")
    ax.grid(axis="x", alpha=0.2)

    # Gráfico 2: Proposições apresentadas
    ax2 = axes[1]
    ax2.set_facecolor("#161b22")
    bars2 = ax2.barh(nomes[::-1], top10["total_proposicoes"][::-1],
                     color="#2b9348", alpha=0.85)
    ax2.bar_label(bars2, fmt="%.0f docs", padding=5, color="white", fontsize=8)
    ax2.set_xlabel("Volume de Proposições", color="#c9d1d9")
    ax2.set_title("Volume de Atividade", color="white")
    ax2.tick_params(colors="#c9d1d9")
    ax2.grid(axis="x", alpha=0.2)

    plt.tight_layout()
    caminho = os.path.join(OUTPUT_DIR, "08_bancada_dos_gastos.png")
    plt.savefig(caminho, dpi=150, bbox_inches="tight", facecolor="#0d1117")
    plt.close()
    log.info(f"  Bancada dos gastos salvo: {caminho}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("ANÁLISE: A Bancada dos Gastos (CARGA TOTAL)")
    log.info("=" * 60)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Carrega cotas
    if not os.path.exists("outputs/cotas_parlamentares.parquet"):
        raise FileNotFoundError("Execute coleta_cotas.py primeiro.")

    df_cotas = pd.read_parquet("outputs/cotas_parlamentares.parquet")
    df_custo = calcular_custo_mandato(df_cotas)

    # Verifica o cache
    prod_path = "outputs/producao_legislativa.csv"
    recoletar = False
    
    if os.path.exists(prod_path):
        log.info("Carregando produção legislativa do cache...")
        df_prod = pd.read_csv(prod_path)
        
        # PROTEÇÃO: Verifica se o cache é antigo e não tem as colunas partido/uf
        if "partido" not in df_prod.columns or "uf" not in df_prod.columns:
            log.warning("⚠️ O seu cache antigo não possui as colunas 'partido' e 'uf'.")
            log.warning("⚠️ Forçando nova extração para atualizar a estrutura de dados...")
            recoletar = True
    else:
        recoletar = True

    if recoletar:
        deps_path = "outputs/deputados.csv"
        if not os.path.exists(deps_path):
            raise FileNotFoundError("Execute coleta_cotas.py para obter a lista de deputados.")

        df_deps = pd.read_csv(deps_path)
        
        # O SEGREDO DO FULL LOAD: Pega todos os deputados que tiveram algum gasto
        nomes_com_gastos = df_custo["parlamentar"].unique().tolist()
        df_deps_filtrado = df_deps[df_deps["nome"].isin(nomes_com_gastos)]

        # Passa a lista completa de anos
        df_prod = coletar_producao_legislativa(df_deps_filtrado, anos=list(range(2019, 2026)))
        
        try:
            df_prod.to_csv(prod_path, index=False, encoding="utf-8-sig")
        except PermissionError:
            log.error(f"\n❌ ERRO DE PERMISSÃO: O ficheiro '{prod_path}' está aberto em outro programa!")
            log.error("   FECHE O POWER BI ou EXCEL e rode o script novamente.\n")
            return

    # Correlaciona e visualiza
    df_final = correlacionar_custo_producao(df_custo, df_prod)
    
    # Exporta a versão final completa (Protegido contra conflitos com o Power BI)
    final_path = os.path.join(OUTPUT_DIR, "custo_vs_producao.csv")
    try:
        # AQUI ESTÁ A MAGIA: sep=';' e decimal=',' forçam o padrão nativo PT-BR
        df_final.to_csv(final_path, index=False, sep=';', decimal=',', encoding="utf-8-sig")
        log.info("\n✅ Análise da Bancada dos Gastos concluída!")
        log.info(f"   Parlamentares analisados no total: {len(df_final)}")
        log.info(f"   Colunas exportadas: {', '.join(df_final.columns)}")
    except PermissionError:
        log.error(f"\n❌ ERRO DE ACESSO: O ficheiro '{final_path}' está ABERTO no Power BI ou Excel!")
        log.error("   O Windows não permite que o Python substitua o ficheiro enquanto ele estiver a ser lido.")
        log.error("   ➡️ SOLUÇÃO: Feche o Power BI, Excel ou qualquer visualizador e rode o script novamente.\n")

if __name__ == "__main__":
    main()