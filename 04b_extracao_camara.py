import requests
import pandas as pd
import time
import logging
import argparse

# Logging estruturado — substitui os print()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

def extrair_despesas_deputado(id_deputado: int, ano: int) -> list:
    """
    Consome a API da Câmara com paginação completa.
    Garante que TODOS os registros do ano sejam coletados.
    """
    url = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{id_deputado}/despesas"
    todas = []
    pagina = 1

    while True:
        params = {
            'ano': ano,
            'ordem': 'ASC',
            'ordenarPor': 'ano',
            'itens': 100,
            'pagina': pagina
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()          # Lança exceção em qualquer erro HTTP
            dados = resp.json().get('dados', [])

            if not dados:
                break                        # Última página — para o loop

            todas.extend(dados)
            pagina += 1
            time.sleep(0.3)                  # Respeita o rate limit da API

        except requests.exceptions.HTTPError as e:
            log.error(f"Deputado {id_deputado} | HTTP {e.response.status_code} na página {pagina}")
            break
        except requests.exceptions.ConnectionError:
            log.error(f"Deputado {id_deputado} | Erro de conexão na página {pagina}")
            break

    return todas

def main(ano: int, ids: list):
    log.info(f"Iniciando extração — {len(ids)} deputados | Ano {ano}")

    todas_despesas = []

    for id_dep in ids:
        log.info(f"Coletando ID {id_dep}...")
        despesas = extrair_despesas_deputado(id_dep, ano)
        log.info(f"  → {len(despesas)} registros coletados")

        for d in despesas:
            todas_despesas.append({
                'ID_Deputado':  id_dep,
                'Ano':          d.get('ano'),
                'Mes':          d.get('mes'),
                'Tipo_Despesa': d.get('tipoDespesa'),
                'Valor_Liquido':d.get('valorLiquido'),
                'Fornecedor':   d.get('nomeFornecedor')
            })

        time.sleep(0.5)   # Pausa extra entre deputados

    if not todas_despesas:
        log.warning("Nenhuma despesa coletada. Verifique os IDs e o ano.")
        return

    df = pd.DataFrame(todas_despesas)
    df['Valor_Liquido'] = pd.to_numeric(df['Valor_Liquido'], errors='coerce').fillna(0.0)
    df['Tipo_Despesa']  = df['Tipo_Despesa'].str.upper().str.strip()

    nome_arquivo = f"dados_cota_parlamentar_{ano}.csv"
    df.to_csv(nome_arquivo, index=False, sep=';', decimal=',', encoding='utf-8-sig')

    log.info(f"Concluído! {len(df):,} registros → {nome_arquivo}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta despesas da cota parlamentar")
    parser.add_argument('--ano',  type=int, default=2024, help='Ano de referência')
    parser.add_argument('--ids',  type=int, nargs='+',
                        default=[204536, 220593, 204521],
                        help='IDs dos deputados')
    args = parser.parse_args()
    main(args.ano, args.ids)