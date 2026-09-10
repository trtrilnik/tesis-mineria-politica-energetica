import pandas as pd
import re
from sqlalchemy import create_engine, text
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATABASE_URI = "postgresql://tomas:2828@localhost:5432/tesis"
engine = create_engine(DATABASE_URI)

def parse_periodos_gobierno(filepath):
    year_to_presidents = defaultdict(list)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # Regex to match: "1989 – 1995 Carlos Saúl Menem"
    # Handling different dash characters and spaces
    pattern = re.compile(r'^(\d{4})\s*[-–]\s*(\d{4})\s+(.+)$')
    
    for line in lines:
        line = line.strip()
        match = pattern.match(line)
        if match:
            start_year = int(match.group(1))
            end_year = int(match.group(2))
            # Clean up the president name (remove references like [3], (*), etc)
            president = match.group(3)
            president = re.sub(r'\[\d+\]', '', president)
            president = re.sub(r'\(\*\)', '', president)
            president = re.sub(r'\(.*?\)', '', president) # remove (por renuncia...)
            president = president.strip()
            
            for year in range(start_year, end_year + 1):
                if president not in year_to_presidents[year]:
                    year_to_presidents[year].append(president)
                    
    # For years with multiple presidents, join them with " / "
    year_mapping = {}
    for year, presidents in year_to_presidents.items():
        year_mapping[year] = " / ".join(presidents)
        
    return year_mapping

def main():
    log.info("Procesando periodos_de_gobierno.md...")
    year_mapping = parse_periodos_gobierno('periodos_de_gobierno.md')
    
    log.info("Creando columna 'presidencia' en la base de datos...")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE normativas ADD COLUMN IF NOT EXISTS presidencia VARCHAR(255)"))
    
    log.info("Cargando años de las normativas...")
    df = pd.read_sql("SELECT id, ano_sancion FROM normativas WHERE ano_sancion ~ '^[0-9]+$'", engine)
    df['ano_sancion_int'] = df['ano_sancion'].astype(int)
    
    # Asignar presidencia
    df['presidencia'] = df['ano_sancion_int'].map(year_mapping)
    df['presidencia'] = df['presidencia'].fillna("Sin Asignar / Desconocido")
    
    log.info("Actualizando base de datos...")
    df_updates = df[['id', 'presidencia']].copy()
    df_updates.to_sql('temp_presidencias', engine, if_exists='replace', index=False)
    
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE normativas n
            SET presidencia = t.presidencia
            FROM temp_presidencias t
            WHERE n.id = t.id
        """))
        conn.execute(text("DROP TABLE temp_presidencias"))
        
    log.info("¡Presidencias asignadas exitosamente!")
    
    # Mostrar un pequeño reporte de la política energética por presidencia
    df_report = pd.read_sql("""
        SELECT presidencia, count(*) as cantidad_normas 
        FROM normativas 
        WHERE politica_energetica = 1 
        GROUP BY presidencia 
        ORDER BY cantidad_normas DESC 
        LIMIT 15
    """, engine)
    
    print("\n========================================================")
    print(" TOP 15 PRESIDENCIAS CON MÁS NORMAS ENERGÉTICAS (Alta y Baja jerarquía)")
    print("========================================================")
    print(df_report.to_string(index=False))

if __name__ == "__main__":
    main()
