"""
=============================================================
PROJETO 2: Eficiência Partidária na Cota Parlamentar
Arquivo: coleta_cotas.py

Descrição:
  Coleta dados da Cota para Exercício da Atividade Parlamentar (CEAP)
  diretamente do portal de Dados Abertos da Câmara dos Deputados.
  Também coleta a lista de deputados com informações partidárias.

Fontes:
  - Cotas: http://www.camara.leg.br/cotas/Ano-{ano}.csv.zip
  - Deputados: https://dadosabertos.camara.leg.br/api/v2/deputados
=============================================================
"""

import requests
import pandas as pd
import io
import zipfile
import time
import os
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

ANOS_COTAS    = list(range(2019, 2026))
BASE_COTAS    = "http://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"
API_DEPUTADOS = "https://dadosabertos.camara.leg.br/api/v2/deputados"

# Mapeamento ideológico simplificado (baseado em literatura acadêmica)
# Fonte de referência: POWER & ZUCCO (2012) - Estimating Ideology of Brazilian Legislative Parties
ESPECTRO_IDEOLOGICO = {
    "PSOL": "Esquerda", "PT": "Esquerda", "PCdoB": "Esquerda",
    "PDT": "Centro-Esquerda", "PSB": "Centro-Esquerda", "REDE": "Centro-Esquerda",
    "MDB": "Centro", "PSD": "Centro", "PODE": "Centro",
    "PSDB": "Centro-Direita", "CIDADANIA": "Centro-Direita",
    "PP": "Direita", "PL": "Direita", "REPUBLICANOS": "Direita",
    "UNIÃO": "Direita", "NOVO": "Direita",
    "SOLIDARIEDADE": "Direita", "AVANTE": "Centro", 
    "PRD": "Direita", "AGIR": "Centro-Direita",
}


def baixar_cotas_ano(ano: int) -> pd.DataFrame:
    """Baixa e descomprime o CSV de cotas de um determinado ano."""
    url = BASE_COTAS.format(ano=ano)
    log.info(f"  Baixando cotas {ano}...")

    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            nome_csv = z.namelist()[0]
            with z.open(nome_csv) as f:
                try:
                    # 1. Tenta ler com UTF-8 (padrão mais limpo, comum em arquivos recentes do governo)
                    df = pd.read_csv(f, sep=";", encoding="utf-8-sig", low_memory=False)
                except UnicodeDecodeError:
                    # 2. Se falhar, volta o cursor do arquivo para o início (byte 0)
                    f.seek(0)
                    # 3. Lê em latin-1 (padrão antigo do Windows/Governo)
                    df = pd.read_csv(f, sep=";", encoding="latin-1", low_memory=False)
                    # 4. Força a decodificação correta em todas as células de texto do DataFrame
                    # Nota: O uso do errors='ignore' evita que o código quebre caso encontre um número ou dado vazio
                    df = df.applymap(lambda x: x.encode('latin1').decode('utf-8', errors='ignore') if isinstance(x, str) else x)

        df["ano_referencia"] = ano
        log.info(f"    {len(df):,} registros — {df.shape[1]} colunas")
        return df

    except Exception as e:
        log.error(f"    Erro ao baixar {ano}: {e}")
        return pd.DataFrame()


def buscar_deputados_api() -> pd.DataFrame:
    """Busca lista completa de deputados da legislatura atual via API."""
    log.info("Buscando lista de deputados via API...")
    todos = []
    pagina = 1

    while True:
        params = {"pagina": pagina, "itens": 200, "ordem": "ASC", "ordenarPor": "nome"}
        resp = requests.get(API_DEPUTADOS, params=params, timeout=30)

        if resp.status_code != 200:
            break

        dados = resp.json().get("dados", [])
        if not dados:
            break

        todos.extend(dados)
        pagina += 1
        time.sleep(0.3)

    df = pd.DataFrame(todos)
    log.info(f"  {len(df)} deputados encontrados")
    return df


def padronizar_cotas(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza nomes de colunas e tipos de dados das cotas."""
    renomear = {
        "txNomeParlamentar":   "parlamentar",
        "idecadastro":         "id_parlamentar",
        "nuCarteiraParlamentar": "carteira",
        "nuLegislatura":       "legislatura",
        "sgUF":                "uf",
        "sgPartido":           "partido",
        "cdTiposDespesa":      "cod_tipo_despesa",
        "txtDescricao":        "tipo_despesa",
        "txtCNPJCPF":          "cnpj_cpf",
        "txtFornecedor":       "fornecedor",
        "txtNumero":           "numero_doc",
        "indTipoDocumento":    "tipo_doc",
        "datEmissao":          "data_emissao",
        "vlrDocumento":        "valor_documento",
        "vlrGlosa":            "valor_glosa",
        "vlrLiquido":          "valor_liquido",
        "numMes":              "mes",
        "numAno":              "ano",
    }
    df = df.rename(columns={k: v for k, v in renomear.items() if k in df.columns})

    # Converte valores
    for col in ["valor_documento", "valor_glosa", "valor_liquido"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(",", ".", regex=False)
                .str.replace("[^0-9.]", "", regex=True)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Adiciona espectro ideológico
    if "partido" in df.columns:
        df["espectro"] = df["partido"].map(ESPECTRO_IDEOLOGICO).fillna("Não classificado")

    return df


def main():
    log.info("=" * 60)
    log.info("INÍCIO: Coleta de Cotas Parlamentares")
    log.info("=" * 60)

    # 1. Cotas por ano
    frames = []
    for ano in tqdm(ANOS_COTAS, desc="Baixando cotas"):
        df_ano = baixar_cotas_ano(ano)
        if not df_ano.empty:
            frames.append(df_ano)
        time.sleep(1)

    if not frames:
        log.error("Nenhum dado de cotas coletado.")
        return

    df_cotas = pd.concat(frames, ignore_index=True)
    df_cotas = padronizar_cotas(df_cotas)

    # 2. Lista de deputados
    df_deps = buscar_deputados_api()

    # Salva
    df_cotas.to_parquet(os.path.join(OUTPUT_DIR, "cotas_parlamentares.parquet"), index=False)
    df_cotas.to_csv(os.path.join(OUTPUT_DIR, "cotas_parlamentares.csv"),
                    index=False, encoding="utf-8-sig")

    if not df_deps.empty:
        df_deps.to_csv(os.path.join(OUTPUT_DIR, "deputados.csv"),
                       index=False, encoding="utf-8-sig")

    log.info(f"\n✅ Coleta concluída!")
    log.info(f"   Cotas: {len(df_cotas):,} registros")
    log.info(f"   Deputados: {len(df_deps)} registros")


if __name__ == "__main__":
    main()