#Descarga de textos completos

import re
import time
import gc
import logging
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from sqlalchemy import create_engine, Column, Integer, String, Text, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraping_textos.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
DATABASE_URI       = "postgresql://tomas:2828@localhost:5432/tesis"
PAUSA_ENTRE_NORMAS = 1.5
PAUSA_CADA_N       = 50
PAUSA_LARGA        = 15
TIMEOUT_PAGINA     = 15
REINTENTOS         = 3

RUIDO_INFOLEG = [
    "InfoLEG",
    "Ministerio de Justicia",
    "Secretaría de Justicia",
    "Información Legislativa",
    "ir al texto actualizado",
    "Volver al Índice",
    "BOLETIN OFICIAL",
]

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
    politica_energetica            = Column(Integer, nullable=True)


# ============================================================
# UTILIDADES
# ============================================================

def iniciar_navegador() -> webdriver.Chrome:
    """Instancia Chrome headless con flags anti-detección."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--incognito")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    # webdriver-manager descarga y gestiona ChromeDriver automáticamente
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def limpiar_html(soup: BeautifulSoup) -> BeautifulSoup:
    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    for tag in soup.find_all("a"):
        tag.unwrap()
    for elemento in soup.find_all(["p", "div", "span", "td"]):
        texto = elemento.get_text()
        if any(ruido.lower() in texto.lower() for ruido in RUIDO_INFOLEG):
            if len(texto.strip()) < 200:
                elemento.decompose()
    return soup


def procesar_tablas(soup: BeautifulSoup) -> BeautifulSoup:
    for tabla in soup.find_all("table"):
        filas_texto = []
        for tr in tabla.find_all("tr"):
            celdas = [
                celda.get_text(separator=" ", strip=True)
                for celda in tr.find_all(["td", "th"])
            ]
            if any(celdas):
                filas_texto.append(" | ".join(celdas))
        texto_reemplazo = soup.new_string("\n\n" + "\n".join(filas_texto) + "\n\n")
        tabla.replace_with(texto_reemplazo)
    return soup


def limpiar_markdown(texto: str) -> str:
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    texto = re.sub(r'^\s*[-*=]{3,}\s*$', '', texto, flags=re.MULTILINE)
    texto = "\n".join(linea.rstrip() for linea in texto.splitlines())
    return texto.strip()


def descargar_texto(driver: webdriver.Chrome, url: str, reintentos: int = REINTENTOS) -> str | None:
    for intento in range(1, reintentos + 1):
        try:
            driver.get(url)
            WebDriverWait(driver, TIMEOUT_PAGINA).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(PAUSA_ENTRE_NORMAS)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            soup = limpiar_html(soup)
            soup = procesar_tablas(soup)

            texto_md = md(str(soup.body), heading_style="ATX")
            texto_md = limpiar_markdown(texto_md)

            return texto_md if texto_md else None

        except TimeoutException:
            log.warning(f"  Timeout en intento {intento}/{reintentos}: {url}")
        except WebDriverException as e:
            log.warning(f"  Error de WebDriver en intento {intento}/{reintentos}: {e}")
            if "invalid session id" in str(e).lower():
                raise e
        except Exception as e:
            log.warning(f"  Error inesperado en intento {intento}/{reintentos}: {e}")

        time.sleep(2 ** intento)

    return None


# ============================================================
# CONEXIÓN A BD Y CONSULTA DE PENDIENTES
# ============================================================
engine  = create_engine(DATABASE_URI)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

pendientes = (
    session.query(Normativa)
    .filter(
        Normativa.enlace_texto_completo.isnot(None),
        Normativa.enlace_texto_completo != "",
        Normativa.texto_completo_md.is_(None),
        Normativa.politica_energetica == 1
    )
    .all()
)

total_pendientes   = len(pendientes)
descargas_ok       = 0
descargas_fallidas = 0

log.info(f"Normas pendientes de scraping: {total_pendientes}")

if total_pendientes == 0:
    log.info("No hay normas pendientes. Todos los textos ya fueron descargados.")
    session.close()
    raise SystemExit(0)

# ============================================================
# LOOP PRINCIPAL
# ============================================================
driver = iniciar_navegador()

try:
    for i, norma in enumerate(pendientes, 1):
        log.info(f"[{i}/{total_pendientes}] {norma.tipo_normativa} {norma.numero_norma}")

        if descargas_ok > 0 and descargas_ok % PAUSA_CADA_N == 0:
            log.info(f"  Pausa de cortesía ({PAUSA_LARGA}s) tras {descargas_ok} descargas…")
            time.sleep(PAUSA_LARGA)
            gc.collect()

        try:
            texto_md = descargar_texto(driver, norma.enlace_texto_completo)
        except WebDriverException as e:
            if "invalid session id" in str(e).lower() or "disconnected" in str(e).lower():
                log.warning("Sesión de Chrome muerta. Reiniciando navegador...")
                try: driver.quit()
                except: pass
                driver = iniciar_navegador()
                texto_md = descargar_texto(driver, norma.enlace_texto_completo)
            else:
                texto_md = None

        if texto_md:
            session.execute(
                update(Normativa)
                .where(Normativa.id == norma.id)
                .values(texto_completo_md=texto_md)
            )
            session.commit()
            descargas_ok += 1
            log.info(f"  OK — {len(texto_md)} caracteres guardados en BD.")
        else:
            descargas_fallidas += 1
            log.warning(
                f"  FALLO — No se pudo obtener el texto de "
                f"{norma.tipo_normativa} {norma.numero_norma} "
                f"({norma.enlace_texto_completo})"
            )
            
            # Si falló, reiniciamos el navegador por las dudas para la próxima norma
            try: driver.quit()
            except: pass
            driver = iniciar_navegador()

except Exception as e:
    log.critical(f"Error crítico en el loop principal: {e}")
    session.rollback()
    raise

finally:
    driver.quit()
    session.close()
    gc.collect()
    log.info("Navegador y sesión de BD cerrados.")

log.info(f"\n{'='*55}")
log.info(f"SCRAPING COMPLETO.")
log.info(f"  Descargas exitosas : {descargas_ok}")
log.info(f"  Fallos             : {descargas_fallidas}")
log.info(f"  Total procesados   : {descargas_ok + descargas_fallidas}/{total_pendientes}")
