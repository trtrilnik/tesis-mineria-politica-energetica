import pandas as pd
import numpy as np
import re
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine

# Configuración visual para la tesis
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

DATABASE_URI = "postgresql://tomas:2828@localhost:5432/tesis"
engine = create_engine(DATABASE_URI)

# ==============================================================================
# DICCIONARIOS DE PARADIGMAS (Estatización vs Privatización/Desregulación)
# ==============================================================================
PARADIGMA_ESTATAL = [
    "estatizacion", "nacionalizacion", "expropiacion", "soberania", 
    "intervencion", "control estatal", "empresa del estado", "sociedad del estado",
    "utilidad publica", "sujeto a expropiacion", "recuperacion", "interventor"
]

PARADIGMA_MERCADO = [
    "privatizacion", "desregulacion", "concesion", "libre disponibilidad", 
    "libre mercado", "sector privado", "licitacion publica internacional", 
    "transferencia", "sociedad anonima", "iniciativa privada", "desmonopolizacion"
]

def puntuar_paradigma(texto, keywords):
    if not isinstance(texto, str):
        return 0
    texto = texto.lower()
    score = 0
    for kw in keywords:
        score += len(re.findall(r'\b' + re.escape(kw) + r'\b', texto))
    return score

def main():
    print("Cargando normativas de Alta Jerarquía para análisis de cambios de paradigma...")
    # Solo tomamos Alta Jerarquía porque ahí es donde ocurren los cambios de paradigma político
    query = """
        SELECT ano_sancion, tipo_normativa, taxonomia_irena, resumen, texto_completo_md
        FROM normativas
        WHERE politica_energetica = 1
          AND tipo_normativa IN ('Ley', 'Decreto', 'Decreto/Ley')
          AND ano_sancion ~ '^[0-9]+$'
    """
    df = pd.read_sql(query, engine)
    df['ano_sancion'] = df['ano_sancion'].astype(int)
    
    # Filtrar desde 1940 para tener un gráfico legible
    df = df[df['ano_sancion'] >= 1940]
    
    df['texto_analisis'] = df['resumen'].fillna('') + " " + df['texto_completo_md'].fillna('')
    
    # Calcular scores
    df['score_estatal'] = df['texto_analisis'].apply(lambda x: puntuar_paradigma(x, PARADIGMA_ESTATAL))
    df['score_mercado'] = df['texto_analisis'].apply(lambda x: puntuar_paradigma(x, PARADIGMA_MERCADO))
    
    # Agrupar por año
    df_grouped = df.groupby('ano_sancion')[['score_estatal', 'score_mercado']].sum().reset_index()
    
    # Para suavizar la curva y ver "épocas"
    df_grouped['score_estatal_smooth'] = df_grouped['score_estatal'].rolling(window=3, min_periods=1).mean()
    df_grouped['score_mercado_smooth'] = df_grouped['score_mercado'].rolling(window=3, min_periods=1).mean()
    
    # Encontrar las normas más contradictorias (Top estatizadoras vs Top privatizadoras)
    top_estatal = df.nlargest(5, 'score_estatal')
    top_mercado = df.nlargest(5, 'score_mercado')
    
    print("\n--- TOP NORMAS: PARADIGMA DE ESTATIZACIÓN / INTERVENCIÓN ---")
    for _, row in top_estatal.iterrows():
        print(f"[{row['ano_sancion']}] {row['tipo_normativa']} - {row['taxonomia_irena']} (Score: {row['score_estatal']})")
        print(f"Resumen: {row['resumen'][:150]}...\n")
        
    print("\n--- TOP NORMAS: PARADIGMA DE PRIVATIZACIÓN / DESREGULACIÓN ---")
    for _, row in top_mercado.iterrows():
        print(f"[{row['ano_sancion']}] {row['tipo_normativa']} - {row['taxonomia_irena']} (Score: {row['score_mercado']})")
        print(f"Resumen: {row['resumen'][:150]}...\n")

    # ==========================================================
    # GRAFICAR CAMBIOS DE PARADIGMA
    # ==========================================================
    plt.figure(figsize=(14, 7))
    plt.plot(df_grouped['ano_sancion'], df_grouped['score_estatal_smooth'], color='red', linewidth=2.5, label='Estatización / Intervención Estatal')
    plt.plot(df_grouped['ano_sancion'], df_grouped['score_mercado_smooth'], color='blue', linewidth=2.5, label='Privatización / Desregulación')
    
    plt.fill_between(df_grouped['ano_sancion'], df_grouped['score_estatal_smooth'], color='red', alpha=0.1)
    plt.fill_between(df_grouped['ano_sancion'], df_grouped['score_mercado_smooth'], color='blue', alpha=0.1)
    
    # Hitos Históricos
    plt.axvline(x=1989, color='gray', linestyle='--', alpha=0.7)
    plt.text(1989.5, df_grouped['score_mercado_smooth'].max()*0.8, 'Reforma del Estado (1989)', rotation=90, color='gray', fontsize=10)
    
    plt.axvline(x=2012, color='gray', linestyle='--', alpha=0.7)
    plt.text(2012.5, df_grouped['score_estatal_smooth'].max()*0.8, 'Expropiación YPF (2012)', rotation=90, color='gray', fontsize=10)
    
    plt.title('Cambios de Paradigma en la Política Energética Argentina (1940-2026)', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Año de Sanción', fontsize=13, fontweight='bold')
    plt.ylabel('Frecuencia del discurso normativo (Rolling Mean)', fontsize=13, fontweight='bold')
    plt.legend(loc='upper left', frameon=True, shadow=True, fontsize=11)
    plt.xlim(1940, 2026)
    
    plt.tight_layout()
    plt.savefig('cambios_paradigma_energetico.png', dpi=300, bbox_inches='tight')
    print("\nGráfico de cambios de paradigma guardado como 'cambios_paradigma_energetico.png'")

if __name__ == "__main__":
    main()
