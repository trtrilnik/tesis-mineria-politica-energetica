import pandas as pd
import numpy as np
import re
from sqlalchemy import create_engine, text
from sklearn.feature_extraction.text import TfidfVectorizer
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATABASE_URI = "postgresql://tomas:2828@localhost:5432/tesis"
engine = create_engine(DATABASE_URI)

# Stopwords en español (extendidas)
STOP_WORDS = ['de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para', 'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'más', 'pero', 'sus', 'le', 'ya', 'o', 'este', 'sí', 'porque', 'esta', 'entre', 'cuando', 'muy', 'sin', 'sobre', 'también', 'me', 'hasta', 'hay', 'donde', 'quien', 'desde', 'todo', 'nos', 'durante', 'todos', 'uno', 'les', 'ni', 'contra', 'otros', 'ese', 'eso', 'ante', 'ellos', 'e', 'esto', 'mí', 'antes', 'algunos', 'qué', 'unos', 'yo', 'otro', 'otras', 'otra', 'él', 'tanto', 'esa', 'estos', 'mucho', 'quienes', 'nada', 'muchos', 'cual', 'poco', 'ella', 'estar', 'estas', 'algunas', 'algo', 'nosotros', 'mi', 'mis', 'tú', 'te', 'ti', 'tu', 'tus', 'ellas', 'nosotras', 'vosotros', 'vosotras', 'os', 'mío', 'mía', 'míos', 'mías', 'tuyo', 'tuya', 'tuyos', 'tuyas', 'suyo', 'suya', 'suyos', 'suyas', 'nuestro', 'nuestra', 'nuestros', 'nuestras', 'vuestro', 'vuestra', 'vuestros', 'vuestras', 'esos', 'esas', 'estoy', 'estás', 'está', 'estamos', 'estáis', 'están', 'esté', 'estés', 'estemos', 'estéis', 'estén', 'estaré', 'estarás', 'estará', 'estaremos', 'estaréis', 'estarán', 'estaría', 'estarías', 'estaríamos', 'estaríais', 'estarían', 'estaba', 'estabas', 'estábamos', 'estabais', 'estaban', 'estuve', 'estuviste', 'estuvo', 'estuvimos', 'estuvisteis', 'estuvieron', 'estuviera', 'estuvieras', 'estuviéramos', 'estuvierais', 'estuvieran', 'estuviese', 'estuvieses', 'estuviésemos', 'estuvieseis', 'estuviesen', 'estando', 'estado', 'estada', 'estados', 'estadas', 'estad', 'he', 'has', 'ha', 'hemos', 'habéis', 'han', 'haya', 'hayas', 'hayamos', 'hayáis', 'hayan', 'habré', 'habrás', 'habrá', 'habremos', 'habréis', 'habrán', 'habría', 'habrías', 'habríamos', 'habríais', 'habrían', 'había', 'habías', 'habíamos', 'habíais', 'habían', 'hube', 'hubiste', 'hubo', 'hubimos', 'hubisteis', 'hubieron', 'hubiera', 'hubieras', 'hubiéramos', 'hubierais', 'hubieran', 'hubiese', 'hubieses', 'hubiésemos', 'hubieseis', 'hubiesen', 'habiendo', 'habido', 'habida', 'habidos', 'habidas', 'soy', 'eres', 'es', 'somos', 'sois', 'son', 'sea', 'seas', 'seamos', 'seáis', 'sean', 'seré', 'serás', 'será', 'seremos', 'seréis', 'serán', 'sería', 'serías', 'seríamos', 'seríais', 'serían', 'era', 'eras', 'éramos', 'erais', 'eran', 'fui', 'fuiste', 'fue', 'fuimos', 'fuisteis', 'fueron', 'fuera', 'fueras', 'fuéramos', 'fuerais', 'fueran', 'fuese', 'fueses', 'fuésemos', 'fueseis', 'fuesen', 'sintiendo', 'sentido', 'sentida', 'sentidos', 'sentidas', 'siente', 'sentid', 'tengo', 'tienes', 'tiene', 'tenemos', 'tenéis', 'tienen', 'tenga', 'tengas', 'tengamos', 'tengáis', 'tengan', 'tendré', 'tendrás', 'tendrá', 'tendremos', 'tendréis', 'tendrán', 'tendría', 'tendrías', 'tendríamos', 'tendríais', 'tendrían', 'tenía', 'tenías', 'teníamos', 'teníais', 'tenían', 'tuve', 'tuviste', 'tuvo', 'tuvimos', 'tuvisteis', 'tuvieron', 'tuviera', 'tuvieras', 'tuviéramos', 'tuvierais', 'tuvieran', 'tuviese', 'tuvieses', 'tuviésemos', 'tuvieseis', 'tuviesen', 'teniendo', 'tenido', 'tenida', 'tenidos', 'tenidas', 'tened', 'ley', 'decreto', 'resolucion', 'disposicion', 'articulo', 'nacional', 'apruebase', 'energia', 'electrica', 'gas', 'nro', 'modificase', 'ser', 'asi']

def clean_text(txt):
    if not isinstance(txt, str): return ""
    txt = txt.lower()
    txt = re.sub(r'[^a-záéíóúñ]+', ' ', txt)
    return txt

def extraer_verbo_inicial(txt):
    if not isinstance(txt, str): return ""
    palabras = re.findall(r'[A-Za-záéíóúñ]+', txt)
    if len(palabras) > 0:
        verbo = palabras[0].lower()
        if verbo.endswith('se') or verbo.endswith('ar') or verbo.endswith('er') or verbo.endswith('ir'):
            if verbo.startswith('aprueb'): return 'aprobar'
            if verbo.startswith('otorga'): return 'otorgar'
            if verbo.startswith('autoriza'): return 'autorizar'
            if verbo.startswith('sancion'): return 'sancionar'
            if verbo.startswith('desestim'): return 'desestimar'
            if verbo.startswith('modific'): return 'modificar'
            if verbo.startswith('prorrog'): return 'prorrogar'
            if verbo.startswith('creas'): return 'crear'
            if verbo.startswith('das'): return 'dar'
            if verbo.startswith('fijas'): return 'fijar'
            if verbo.startswith('establec'): return 'establecer'
            if verbo.startswith('derogas'): return 'derogar'
            if verbo.startswith('convoca'): return 'convocar'
            if verbo.startswith('rechazas'): return 'rechazar'
            return verbo
    return ""

def asignar_espiritu(row):
    verb = row['verbo_accion']
    keywords = row['top_keywords']
    text_str = str(keywords) + " " + str(verb)
    
    # 1. Sanciones / Multas
    if "sancionar" in verb or any(k in text_str for k in ["multa", "penalidad", "sancion", "apercibimiento"]):
        return "Sanción / Multa"
    
    # 2. Audiencias Públicas
    if "convocar" in verb or "audiencia publica" in text_str or "audiencia" in text_str:
        return "Audiencia Pública"
        
    # 3. Tarifas y Precios
    if "fijar" in verb or any(k in text_str for k in ["tarifa", "cuadro tarifario", "precio", "cargo", "estacional", "aumento", "facturacion"]):
        return "Fijación Tarifaria / Precios"
        
    # 4. Desregulación / Privatización / Liberación
    if "derogar" in verb or any(k in text_str for k in ["desregulacion", "privatizacion", "concesion", "libre", "mercado", "derogacion", "transferencia", "emergencia", "competencia"]):
        return "Desregulación / Concesión"
        
    # 5. Estatización / Intervención
    if "intervenir" in verb or "expropiar" in verb or any(k in text_str for k in ["estatizacion", "nacionalizacion", "expropiacion", "intervencion", "soberania", "sociedad del estado", "yacimientos petroliferos fiscales"]):
        return "Estatización / Intervención"
        
    # 6. Regulación / Creación de Programas (Positivo institucional)
    if "crear" in verb or "establecer" in verb or any(k in text_str for k in ["programa", "plan", "reglamentacion", "registro", "fondo", "promocion"]):
        return "Regulación / Programas"
        
    # 7. Rechazos
    if "desestimar" in verb or "rechazar" in verb or "rechazo" in text_str:
        return "Rechazo de Reclamos"
        
    # Por defecto
    return "Administrativo / Operativo (Genérico)"

def main():
    log.info("Cargando normativas para análisis de Espíritu...")
    query = """
        SELECT id, tipo_normativa, ano_sancion, presidencia, resumen, texto_completo_md
        FROM normativas
        WHERE politica_energetica = 1
    """
    df = pd.read_sql(query, engine)
    
    log.info("Preprocesando textos y calculando verbos...")
    df['texto_limpio'] = (df['resumen'].fillna('') + " " + df['texto_completo_md'].fillna('')).apply(clean_text)
    df['verbo_accion'] = df['resumen'].apply(extraer_verbo_inicial)
    
    log.info("Calculando TF-IDF masivo (max 1000 features)...")
    vectorizer = TfidfVectorizer(stop_words=STOP_WORDS, max_features=1000, ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform(df['texto_limpio'])
    feature_names = vectorizer.get_feature_names_out()
    
    log.info("Extrayendo Top 5 palabras clave por documento...")
    # Para hacerlo rápido en pandas, sacamos el argmax de cada fila
    # Esto es una optimización, no sacamos los 5 exactos si es muy pesado, 
    # pero podemos hacer argsort de la matriz rala
    
    # Extraer índices top de cada fila
    top_n = 5
    keywords_list = []
    
    for row in tfidf_matrix:
        # Indices de los n más altos
        # Para evitar dense matrix, usamos la fila CSR
        indices = row.indices
        data = row.data
        if len(indices) == 0:
            keywords_list.append("")
        else:
            # ordenar por data
            sorted_indices = indices[np.argsort(data)[::-1][:top_n]]
            kws = [feature_names[i] for i in sorted_indices]
            keywords_list.append(" ".join(kws))
            
    df['top_keywords'] = keywords_list
    
    log.info("Clasificando el Espíritu Normativo...")
    df['espiritu_normativo'] = df.apply(asignar_espiritu, axis=1)
    
    log.info("Guardando en la base de datos...")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE normativas ADD COLUMN IF NOT EXISTS espiritu_normativo VARCHAR(100)"))
        
    df_updates = df[['id', 'espiritu_normativo']].copy()
    df_updates.to_sql('temp_espiritu', engine, if_exists='replace', index=False)
    
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE normativas n
            SET espiritu_normativo = t.espiritu_normativo
            FROM temp_espiritu t
            WHERE n.id = t.id
        """))
        conn.execute(text("DROP TABLE temp_espiritu"))
        
    log.info("=========================================================================")
    log.info(" DISTRIBUCIÓN GENERAL DEL ESPÍRITU NORMATIVO (1854 - 2026)")
    log.info("=========================================================================")
    resumen_general = df['espiritu_normativo'].value_counts()
    print(resumen_general.to_string())
    
    log.info("\n=========================================================================")
    log.info(" PERFIL NORMATIVO DE LA PRESIDENCIA DE JAVIER MILEI (2023 - 2027)")
    log.info("=========================================================================")
    df_milei = df[df['presidencia'].str.contains("Milei", na=False, case=False)]
    if len(df_milei) > 0:
        resumen_milei = df_milei['espiritu_normativo'].value_counts()
        porcentajes = (resumen_milei / len(df_milei) * 100).round(1).astype(str) + "%"
        reporte_milei = pd.DataFrame({'Cantidad': resumen_milei, 'Porcentaje': porcentajes})
        print(f"Total normas Milei: {len(df_milei)}")
        print(reporte_milei.to_string())
    else:
        print("No se encontraron normas de Milei.")

if __name__ == "__main__":
    main()
