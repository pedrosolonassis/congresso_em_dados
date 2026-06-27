import pandas as pd

# 1. Carrega o seu arquivo de cotas
caminho_arquivo = 'outputs/cotas_parlamentares.csv'
df = pd.read_csv(caminho_arquivo)

# 2. Verifica se a coluna está com o nome original da Câmara ou se já foi renomeada
coluna_alvo = 'tipo_despesa' if 'tipo_despesa' in df.columns else 'txtDescricao'

if coluna_alvo in df.columns:
    # 3. Extrai apenas os valores únicos e remove valores nulos
    categorias = df[coluna_alvo].dropna().unique()
    
    print("=== CATEGORIAS DE DESPESA ENCONTRADAS ===")
    for cat in sorted(categorias):
        print(f"- {cat}")
else:
    print(f"Coluna não encontrada. As colunas disponíveis são:\n{df.columns.tolist()}")