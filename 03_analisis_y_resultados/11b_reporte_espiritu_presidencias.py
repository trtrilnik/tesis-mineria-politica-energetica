import pandas as pd
from sqlalchemy import create_engine

DATABASE_URI = "postgresql://tomas:2828@localhost:5432/tesis"
engine = create_engine(DATABASE_URI)

def main():
    # Consultar los datos
    query = """
        SELECT presidencia, espiritu_normativo, COUNT(*) as cantidad
        FROM normativas
        WHERE politica_energetica = 1
        GROUP BY presidencia, espiritu_normativo
    """
    df = pd.read_sql(query, engine)
    
    # Calcular el total de normas por presidencia para sacar el porcentaje
    totales_por_presidencia = df.groupby('presidencia')['cantidad'].sum().reset_index()
    totales_por_presidencia.rename(columns={'cantidad': 'total_normas'}, inplace=True)
    
    # Unir para tener el total al lado de cada cantidad
    df = pd.merge(df, totales_por_presidencia, on='presidencia')
    
    # Calcular porcentaje
    df['porcentaje'] = (df['cantidad'] / df['total_normas']) * 100
    df['porcentaje_str'] = df['porcentaje'].round(1).astype(str) + "%"
    
    # Ordenar por presidencia y luego por cantidad descendente
    df = df.sort_values(by=['total_normas', 'presidencia', 'cantidad'], ascending=[False, True, False])
    
    # 1. Exportar a Excel
    excel_path = "Reporte_Espiritu_Normativo_Por_Presidencia.xlsx"
    # Formatear un poco para el excel final
    df_excel = df[['presidencia', 'espiritu_normativo', 'cantidad', 'porcentaje']]
    df_excel.to_excel(excel_path, index=False)
    
    # 2. Generar Markdown para las presidencias con más de 100 normas
    md_lines = []
    presidencias_importantes = totales_por_presidencia[totales_por_presidencia['total_normas'] >= 100].sort_values(by='total_normas', ascending=False)
    
    for _, row in presidencias_importantes.iterrows():
        pres = row['presidencia']
        total = row['total_normas']
        
        md_lines.append(f"### {pres} (Total: {total} normas)\n")
        md_lines.append("| Espíritu de Norma | Cantidad | Porcentaje |")
        md_lines.append("| :--- | :---: | :---: |")
        
        df_pres = df[df['presidencia'] == pres]
        for _, r_pres in df_pres.iterrows():
            esp = r_pres['espiritu_normativo']
            cant = r_pres['cantidad']
            pct = r_pres['porcentaje_str']
            md_lines.append(f"| {esp} | {cant} | {pct} |")
        
        md_lines.append("\n")
        
    with open("reporte_presidencias.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

if __name__ == "__main__":
    main()
