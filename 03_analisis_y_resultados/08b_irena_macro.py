import pandas as pd
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATABASE_URI = "postgresql://tomas:2828@localhost:5432/tesis"
engine = create_engine(DATABASE_URI)

def main():
    log.info("Creando la columna irena_tipo_energia en la base de datos...")
    
    with engine.begin() as conn:
        # Añadir la columna si no existe
        conn.execute(text("ALTER TABLE normativas ADD COLUMN IF NOT EXISTS irena_tipo_energia VARCHAR(50)"))
        
        # Mapear las categorías según IRENA
        update_query = text("""
            UPDATE normativas
            SET irena_tipo_energia = CASE
                WHEN taxonomia_irena IN (
                    '110000 - Combustibles Fósiles (Fossil Fuels)', 
                    '120000 - Energía Nuclear (Nuclear Energy)'
                ) THEN 'No Renovable'
                
                WHEN taxonomia_irena IN (
                    '210000 - Hidroenergía (Hydropower)', 
                    '230000 - Energía Eólica (Wind Energy)', 
                    '240000 - Energía Solar (Solar Energy)', 
                    '260000 - Bioenergía (Bioenergy)'
                ) THEN 'Renovable'
                
                WHEN taxonomia_irena = '300000 - Almacenamiento (Energy Storage)' THEN 'Almacenamiento'
                
                ELSE 'Portador / Genérica'
            END
            WHERE politica_energetica = 1
        """)
        
        conn.execute(update_query)
        
    log.info("Columna actualizada exitosamente. Consultando distribución...")
    
    # Mostrar el conteo para el usuario
    df = pd.read_sql("SELECT irena_tipo_energia, count(*) as cantidad FROM normativas WHERE politica_energetica = 1 GROUP BY irena_tipo_energia ORDER BY cantidad DESC", engine)
    print("\nResumen Macro-Categorías IRENA:")
    print(df.to_string(index=False))

if __name__ == "__main__":
    main()
