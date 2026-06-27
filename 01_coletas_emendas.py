"""
=============================================================
PROJETO 1: Raio-X das Emendas Pix
Arquivo: outro_teste.py
=============================================================
"""

import requests
import pandas as pd
import time
import os
import logging
from tqdm import tqdm

# ── Configuração de logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────
BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados/emendas"
API_KEY = "7cf69f873d43cc796c6103719606cbc8"
HEADERS = {"chave-api-dados": API_KEY}

ANOS = list(range(2020, 2026))          
TIPO_EMENDA = "Transferências Especiais" 
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Funções auxiliares ─────────────────────────────────────────────────────────

def buscar_emendas_por_ano(ano: int, pagina: int = 1, por_pagina: int = 200) -> dict:
    params = {
        "ano": ano,
        "tipoEmenda": TIPO_EMENDA,
        "pagina": pagina,
        "quantidade": por_pagina,
    }
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        log.error(f"Erro HTTP ao buscar ano={ano} pag={pagina}: {e}")
        return {}
    except requests.exceptions.ConnectionError:
        log.error("Erro de conexão. Verifique sua internet.")
        return {}

def coletar_ano_completo(ano: int) -> pd.DataFrame:
    todos_registros = []
    pagina = 1

    log.info(f"Coletando emendas Pix — ano {ano}...")

    while True:
        dados = buscar_emendas_por_ano(ano, pagina=pagina)

        if isinstance(dados, list):
            registros = dados
        elif isinstance(dados, dict):
            registros = dados.get("data", dados.get("resultado", []))
        else:
            break

        if not registros:
            break

        todos_registros.extend(registros)
        log.info(f"  Ano {ano} — página {pagina}: {len(registros)} registros")

        if len(registros) < 15:
            break

        pagina += 1
        time.sleep(0.5) 

    if not todos_registros:
        log.warning(f"Nenhum registro encontrado para {ano}.")
        return pd.DataFrame()

    df = pd.DataFrame(todos_registros)
    df["ano_coleta"] = ano
    return df

def converter_moeda_segura(val):
    if pd.isna(val) or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
        
    val_str = str(val).replace("R$", "").strip()
    
    if "," in val_str:
        val_str = val_str.replace(".", "")   
        val_str = val_str.replace(",", ".")  
    else:
        if "." in val_str:
            if val_str.count(".") > 1:
                val_str = val_str.replace(".", "")
            else:
                partes = val_str.split(".")
                if len(partes[-1]) == 3:
                    val_str = val_str.replace(".", "")
                
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def limpar_e_normalizar(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # Padroniza nomes de colunas
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
    )

    # Aplica a função segura linha a linha
    cols_valor = [c for c in df.columns if "valor" in c]
    for col in cols_valor:
        df[col] = df[col].apply(converter_moeda_segura)

    # Limpa espaços em branco nos textos
    cols_str = df.select_dtypes(include="object").columns
    for col in cols_str:
        df[col] = df[col].astype(str).str.strip()

    return df

# ── Execução principal ─────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("INÍCIO: Coleta de Emendas Pix — Portal da Transparência")
    log.info("=" * 60)

    frames = []
    for ano in tqdm(ANOS, desc="Anos processados"):
        df_ano = coletar_ano_completo(ano)
        if not df_ano.empty:
            frames.append(df_ano)
        time.sleep(1)

    if not frames:
        log.error("Nenhum dado coletado. Verifique sua chave de API.")
        return

    df_final = pd.concat(frames, ignore_index=True)
    df_final = limpar_e_normalizar(df_final)

    caminho_csv = os.path.join(OUTPUT_DIR, "emendas_pix_2020_2025.csv")
    df_final.to_csv(caminho_csv, index=False, encoding="utf-8-sig")

    log.info(f"\n✅ Coleta concluída!")
    log.info(f"   Total de registros: {len(df_final):,}")
    log.info(f"   Arquivo salvo em: {caminho_csv}")

if __name__ == "__main__":
    main()