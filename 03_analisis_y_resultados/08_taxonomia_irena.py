import pandas as pd
import numpy as np
import re
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATABASE_URI = "postgresql://tomas:2828@localhost:5432/tesis"
engine = create_engine(DATABASE_URI)

# ==============================================================================
# DICCIONARIO DE TAXONOMÍA IRENA 2024 (Adaptado a terminología legal argentina)
# ==============================================================================
TAXONOMY_KEYWORDS = {
    "110000 - Combustibles Fósiles (Fossil Fuels)": [
        "hidrocarburo", "petroleo", "gas natural", "carbon", "combustible", 
        "nafta", "gasoil", "gnc", "glp", "ypf", "refinacion", "pozo", 
        "exploracion", "cuenca", "yacimiento", "gasoducto", "oleoducto"
    ],
    "120000 - Energía Nuclear (Nuclear Energy)": [
        "nuclear", "atomica", "uranio", "cnea", "nucleoelectrica", 
        "reactor", "radioactivo", "atucha", "embalse"
    ],
    "210000 - Hidroenergía (Hydropower)": [
        "hidroelectrica", "represa", "salto grande", "yacyreta", "chocon", 
        "apipé", "hidraulica", "aprovechamiento hidroelectrico"
    ],
    "230000 - Energía Eólica (Wind Energy)": [
        "eolica", "viento", "aerogenerador", "parque eolico"
    ],
    "240000 - Energía Solar (Solar Energy)": [
        "solar", "fotovoltaica", "panel", "parque solar"
    ],
    "260000 - Bioenergía (Bioenergy)": [
        "biocombustible", "biomasa", "biodiesel", "bioetanol", "biodigestor", "etanol"
    ],
    "300000 - Almacenamiento (Energy Storage)": [
        "bateria", "almacenamiento de energia", "acumulador"
    ],
    "Portador: Energía Eléctrica (Electricity Carrier)": [
        "electricidad", "electrico", "edenor", "edesur", "cammesa", 
        "enre", "transmision", "alta tension", "distribuidora electrica", "sistema argentino de interconexion", "sadi"
    ]
}

def clasificar_irena(texto):
    if not isinstance(texto, str):
        return "No clasificable"
    texto = texto.lower()
    
    # Contar ocurrencias de cada categoría
    scores = {cat: 0 for cat in TAXONOMY_KEYWORDS.keys()}
    for cat, keywords in TAXONOMY_KEYWORDS.items():
        for kw in keywords:
            # Usar regex para coincidencia exacta de palabra/frase
            matches = len(re.findall(r'\b' + re.escape(kw) + r'\b', texto))
            scores[cat] += matches
            
    # Obtener la categoría con mayor puntaje
    max_score = max(scores.values())
    if max_score == 0:
        return "No clasificable (Otra / Genérica)"
    
    # En caso de empate, priorizar energías primarias sobre "Energía Eléctrica"
    categorias_top = [c for c, v in scores.items() if v == max_score]
    if len(categorias_top) > 1 and "Portador: Energía Eléctrica (Electricity Carrier)" in categorias_top:
        categorias_top.remove("Portador: Energía Eléctrica (Electricity Carrier)")
        
    return categorias_top[0]

def main():
    log.info("Cargando normativas de política energética...")
    query = """
        SELECT id, tipo_normativa, ano_sancion, tema, resumen, texto_completo_md
        FROM normativas
        WHERE politica_energetica = 1
    """
    df = pd.read_sql(query, engine)
    log.info(f"Se cargaron {len(df)} normativas.")

    log.info("Aplicando Taxonomía IRENA...")
    # Combinar título/resumen/texto para tener más contexto
    df['texto_analisis'] = df['tema'].fillna('') + " " + df['resumen'].fillna('') + " " + df['texto_completo_md'].fillna('')
    df['taxonomia_irena'] = df['texto_analisis'].apply(clasificar_irena)

    log.info("Distribución de Taxonomía IRENA:")
    print(df['taxonomia_irena'].value_counts())

    log.info("Actualizando base de datos...")
    # Guardar los resultados en la BD. Creamos columna si no existe.
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE normativas ADD COLUMN IF NOT EXISTS taxonomia_irena VARCHAR(255)"))
    except Exception as e:
        log.warning(f"Error alterando tabla: {e}")

    # Update masivo iterativo para no colapsar la memoria (idealmente usar to_sql a tabla temporal)
    # Como son 14k, podemos iterar o usar tabla temporal
    df_updates = df[['id', 'taxonomia_irena']].copy()
    df_updates.to_sql('temp_irena', engine, if_exists='replace', index=False)
    
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE normativas n
            SET taxonomia_irena = t.taxonomia_irena
            FROM temp_irena t
            WHERE n.id = t.id
        """))
        conn.execute(text("DROP TABLE temp_irena"))
        
    log.info("¡Taxonomía IRENA aplicada exitosamente!")

if __name__ == "__main__":
    main()
