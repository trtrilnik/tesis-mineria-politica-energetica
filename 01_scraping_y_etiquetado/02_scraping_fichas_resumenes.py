import os
import re
import time
import gc
import logging
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, Column, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("enriquecimiento.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
DATABASE_URI    = "postgresql://tomas:2828@localhost:5432/tesis"
TAMANIO_BATCH   = 50
PAUSA_CADA_N    = 100
PAUSA_SEGUNDOS  = 10
TIMEOUT_REQUEST = 15

HEADERS_HTTP = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
    "Connection": "keep-alive",
}

# ============================================================
# MODELO ORM
# ============================================================
Base = declarative_base()

class Normativa(Base):
    __tablename__ = "normativas"

    id                               = Column(Integer, primary_key=True, autoincrement=True)
    tipo_normativa                   = Column(String(50))
    numero_norma                     = Column(String(50))
    ano_sancion                      = Column(String(4))
    resumen                          = Column(Text)
    enlace_ficha                     = Column(String, unique=True)
    enlace_texto_completo            = Column(String)
    tiene_texto_completo_actualizado = Column(Integer)
    modifica_a                       = Column(JSONB)
    es_modificada_por                = Column(JSONB)
    texto_completo_md                = Column(Text)
    politica_energetica              = Column(Integer, nullable=True)   
    termino_busqueda                 = Column(String(100), nullable=True)
    variante_busqueda                = Column(String(200), nullable=True)
    
    # Nuevas columnas Scraping V2
    tema                             = Column(Text, nullable=True)
    titulo                           = Column(Text, nullable=True)
    dependencia                      = Column(Text, nullable=True)

# ============================================================
# UTILIDADES
# ============================================================

def construir_url_absoluta(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return "https://servicios.infoleg.gob.ar" + href
    return "https://servicios.infoleg.gob.ar/infolegInternet/" + href

def obtener_con_reintentos(url: str, reintentos: int = 5) -> requests.Response | None:
    for intento in range(1, reintentos + 1):
        try:
            respuesta = requests.get(url, headers=HEADERS_HTTP, timeout=TIMEOUT_REQUEST)
            respuesta.raise_for_status()
            return respuesta
        except requests.exceptions.RequestException as e:
            espera = 3 ** intento
            log.warning(f"  Intento {intento}/{reintentos} fallido ({url}): {e}. "
                        f"Reintentando en {espera}s…")
            time.sleep(espera)
    log.error(f"  Se agotaron los reintentos para: {url}")
    return None

def extraer_dependencia(soup: BeautifulSoup) -> str:
    # Buscar el div primero por clase o id
    div = soup.find(id="Textos_Completos")
    if not div:
        div = soup.find("div", class_="Textos_Completos")
        
    if not div:
        return ""
    
    primer_strong = div.find("strong")
    if primer_strong:
        texto = primer_strong.get_text(separator=" ").strip()
        # Regex básico para buscar dependencias comunes (terminando en salto o fin de frase)
        match = re.search(r'(PODER EJECUTIVO NACIONAL|MINISTERIO DE[\w\s,]+|SECRETARIA DE[\w\s,]+|SUBSECRETARIA DE[\w\s,]+|DIRECCION NACIONAL DE[\w\s,]+|ENTE NACIONAL[\w\s,]+|ADMINISTRACION NACIONAL[\w\s,]+)', texto, re.IGNORECASE)
        if match:
            # Limpiamos posibles comas o espacios finales extraídos
            return match.group(1).strip(' ,.\n\r\t')
        else:
            return texto
    return ""

def realizar_migracion(engine):
    """Ejecuta los ALTER TABLE de forma segura y directa para evitar problemas con SQLAlchemy create_all."""
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE normativas ADD COLUMN IF NOT EXISTS tema TEXT;"))
        conn.execute(text("ALTER TABLE normativas ADD COLUMN IF NOT EXISTS titulo TEXT;"))
        conn.execute(text("ALTER TABLE normativas ADD COLUMN IF NOT EXISTS dependencia TEXT;"))
        conn.execute(text("ALTER TABLE normativas ADD COLUMN IF NOT EXISTS filtrado_heuristico INTEGER;"))
        conn.commit()

# ============================================================
# INICIO
# ============================================================
if __name__ == "__main__":
    engine = create_engine(DATABASE_URI)
    log.info("Asegurando que las nuevas columnas existan en la base de datos...")
    realizar_migracion(engine)
    
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    
    session = Session()
    
    try:
        pendientes = session.query(Normativa).filter(Normativa.titulo == None).all()
        total_pendientes = len(pendientes)
        log.info(f"Se encontraron {total_pendientes} registros pendientes de enriquecimiento.")
        
        procesados_lote = 0
        actualizados_total = 0
        
        for i, norma in enumerate(pendientes, 1):
            log.info(f"[{i}/{total_pendientes}] Enriqueciendo ID: {norma.id} - URL: {norma.enlace_ficha}")
            
            if i % PAUSA_CADA_N == 0:
                log.info(f"  Pausa para evitar sobrecarga ({PAUSA_SEGUNDOS}s)…")
                time.sleep(PAUSA_SEGUNDOS)
                gc.collect()
                
            url_limpia = construir_url_absoluta(norma.enlace_ficha)
            respuesta = obtener_con_reintentos(url_limpia)
            
            if respuesta is None:
                continue
                
            try:
                soup = BeautifulSoup(respuesta.content, "html.parser")
                
                # Extraer tema
                span_tema = soup.find("span", class_="destacado")
                if span_tema:
                    norma.tema = span_tema.get_text(separator=" ").strip()
                else:
                    norma.tema = ""
                    
                # Extraer titulo
                h1_titulo = soup.find("h1")
                if h1_titulo:
                    norma.titulo = h1_titulo.get_text(separator=" ").strip()
                else:
                    norma.titulo = ""
                    
                # Extraer dependencia
                norma.dependencia = extraer_dependencia(soup)
                
                procesados_lote += 1
                actualizados_total += 1
                
                if procesados_lote >= TAMANIO_BATCH:
                    session.commit()
                    log.info(f"  [DB] Lote de {procesados_lote} registros actualizado.")
                    procesados_lote = 0
                    
            except Exception as e:
                log.error(f"  Error parseando '{norma.enlace_ficha}': {e}")
                session.rollback()
                continue
                
        if procesados_lote > 0:
            session.commit()
            log.info(f"  [DB] Lote final de {procesados_lote} registros actualizado.")
            
    except Exception as e:
        log.critical(f"Error crítico en el loop principal: {e}")
        session.rollback()
        raise
    finally:
        session.close()
        log.info("Sesión de BD cerrada.")
    
    log.info(f"\n{'='*55}")
    log.info(f"ENRIQUECIMIENTO COMPLETO. Total de registros actualizados: {actualizados_total}")
