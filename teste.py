import pandas as pd

# Lendo o arquivo parquet
df = pd.read_parquet('outputs/cotas_parlamentares.parquet')

# Mostrando as colunas exatas e uma amostra da primeira linha
print("AS COLUNAS REAIS SÃO:\n", df.columns.tolist())
print("\nAMOSTRA DA PRIMEIRA LINHA:\n", df.head(1).to_dict('records'))