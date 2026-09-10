import json
import time
import gc
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("recoleccion.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ============================================================
# CONFIGURACIÓN DE BÚSQUEDA
# ============================================================
TERMINOS_CON_VARIANTES = [
    {
        "termino": "Energía",
        "variantes": ["Energía", "Energías"]
    },
    {
        "termino": "Hidrocarburos",
        "variantes": ["Hidrocarburo", "Hidrocarburos"]
    },
    {
        "termino": "Combustible",
        "variantes": ["Combustible", "Combustibles"]
    },
    {
        "termino": "Combustible fósil",
        "variantes": ["Combustible fósil", "Combustibles fósiles"]
    },
    {
        "termino": "Combustible líquido",
        "variantes": ["Combustible líquido", "Combustibles líquidos"]
    },
    {
        "termino": "Combustible gaseoso",
        "variantes": ["Combustible gaseoso", "Combustibles gaseosos"]
    },
    {
        "termino": "Energía nuclear",
        "variantes": ["Energía nuclear", "Energías nucleares",
                      "Nuclear", "Nucleares", "Central nuclear",
                      "Centrales nucleares"]
    },
    {
        "termino": "Gas natural",
        "variantes": ["Gas natural", "Gases naturales"]
    },
    {
        "termino": "Gas licuado",
        "variantes": ["Gas licuado", "Gas natural licuado", "GNL"]
    },
    {
        "termino": "Energía renovable",
        "variantes": ["Energía renovable", "Energías renovables"]
    },
    {
        "termino": "Fuente renovable",
        "variantes": ["Fuente renovable", "Fuentes renovables"]
    },
    {
        "termino": "Fuente alternativa",
        "variantes": ["Fuente alternativa", "Fuentes alternativas",
                      "Energía alternativa", "Energías alternativas"]
    },
    {
        "termino": "Energía eléctrica",
        "variantes": ["Energía eléctrica", "Energías eléctricas"]
    },
    {
        "termino": "Mercado eléctrico",
        "variantes": ["Mercado eléctrico", "Mercados eléctricos",
                      "Mercado eléctrico mayorista"]
    },
    {
        "termino": "Energía eólica",
        "variantes": ["Energía eólica", "Energías eólicas",
                      "Eólica", "Eólicas"]
    },
    {
        "termino": "Energía solar",
        "variantes": ["Energía solar", "Energías solares"]
    },
    {
        "termino": "Energía geotérmica",
        "variantes": ["Energía geotérmica", "Energías geotérmicas",
                      "Geotérmica", "Geotérmicas"]
    },
    {
        "termino": "Biomasa",
        "variantes": ["Biomasa", "Biomasas", 
                      "Biocombustible", "Biocombustibles"]
    },
    {
        "termino": "Energía distribuida",
        "variantes": ["Energía distribuida", "Energías distribuidas",
                      "Generación distribuida"]
    },
    {
        "termino": "Distribución eléctrica",
        "variantes": ["Distribución eléctrica"]
    },
    {
        "termino": "Transmisión eléctrica",
        "variantes": ["Transmisión eléctrica"]
    },
    {
        "termino": "Diversificación energética",
        "variantes": ["Diversificación energética",
                      "matriz energética"]
    },
    {
        "termino": "Autoabastecimiento energético",
        "variantes": ["Autoabastecimiento energético",
                      "Autoabastecimiento de energía"]
    },
    {
        "termino": "Aprovechamiento energético",
        "variantes": ["Aprovechamiento energético"]
    }
]

# Lista plana de todas las variantes para el loop de búsqueda
# Se conserva también el término padre para registrarlo en el historial
BUSQUEDAS = [
    {"termino": grupo["termino"], "variante": variante}
    for grupo in TERMINOS_CON_VARIANTES
    for variante in grupo["variantes"]
]

TIPOS_NORMATIVA = [
    "Ley", "Decreto", "Decisión Administrativa", "Resolución", "Disposición",
    "Acordada", "Acta", "Actuacion", "Acuerdo", "Circular", "Comunicación",
    "Comunicado", "Convenio", "Decisión", "Decreto/Ley", "Directiva",
    "Instrucción", "Interpretación", "Laudo", "Memorandum", "Misión",
    "Nota", "Nota Externa", "Ordenanza", "Protocolo", "Providencia",
    "Recomendación"
]

ARCHIVO_ENLACES   = "enlaces.json"
ARCHIVO_PROGRESO  = "progreso.json"
ARCHIVO_HISTORIAL = "historial_ejecuciones.json"
URL_BUSQUEDA      = "https://servicios.infoleg.gob.ar/infolegInternet/mostrarBusquedaNormas.do"
PAUSA_ENTRE_PAGINAS  = 3
PAUSA_ENTRE_TERMINOS = 10
PAUSA_ENTRE_TIPOS    = 20

# ============================================================
# UTILIDADES
# ============================================================

def cargar_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def guardar_json(path: str, data) -> None:
    import os
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp, path)


def iniciar_navegador() -> webdriver.Chrome:
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
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def hay_pagina_siguiente(driver) -> bool:
    try:
        btn = driver.find_element(By.CLASS_NAME, "page-right")
        clases = btn.get_attribute("class") or ""
        deshabilitado = any(c in clases for c in ("disabled", "inactive", "no-active"))
        return not deshabilitado
    except NoSuchElementException:
        return False


def buscar_con_reintentos(driver, tipo: str, variante: str, reintentos: int = 5) -> bool:
    for intento in range(1, reintentos + 1):
        try:
            driver.get(URL_BUSQUEDA)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.NAME, "tipoNorma"))
            )
            Select(driver.find_element(By.NAME, "tipoNorma")).select_by_visible_text(tipo)
            campo = driver.find_element(By.NAME, "texto")
            campo.clear()
            campo.send_keys(variante)
            driver.find_element(By.CSS_SELECTOR, "input[value='Buscar']").click()
            return True
        except Exception as e:
            espera = 5 ** intento
            log.warning(f"  Intento {intento}/{reintentos} fallido para "
                        f"'{tipo}' + '{variante}': {e}. Reintentando en {espera}s…")
            time.sleep(espera)
    log.error(f"  Se agotaron los reintentos para '{tipo}' + '{variante}'. Se omite.")
    return False


# ============================================================
# CARGA DE ESTADO
# ============================================================
# enlaces.json ahora almacena: {url: {"texto": str, "termino": str, "variante": str}}
normas_unicas: dict = cargar_json(ARCHIVO_ENLACES, {})
progreso: dict      = cargar_json(ARCHIVO_PROGRESO,
                                  {"ultimo_tipo": None, "ultimo_termino": None,
                                   "ultima_variante": None})

if progreso["ultima_variante"]:
    variantes_actuales = [b["variante"] for b in BUSQUEDAS]
    if progreso["ultima_variante"] not in variantes_actuales:
        log.warning(
            f"La variante guardada '{progreso['ultima_variante']}' "
            f"ya no existe en el listado actual. Reseteando progreso."
        )
        progreso = {"ultimo_tipo": None, "ultimo_termino": None, "ultima_variante": None}
        guardar_json(ARCHIVO_PROGRESO, progreso)

log.info(f"Enlaces acumulados hasta ahora: {len(normas_unicas)}")

if progreso["ultimo_tipo"]:
    log.info(f"Retomando desde tipo='{progreso['ultimo_tipo']}' / "
             f"termino='{progreso['ultimo_termino']}' / "
             f"variante='{progreso['ultima_variante']}'")
else:
    log.info("Iniciando recorrido completo desde el principio.")

saltando_tipo     = bool(progreso["ultimo_tipo"])
saltando_variante = bool(progreso["ultima_variante"])

registro_ejecucion = {
    "inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "fin": None,
    "enlaces_al_inicio": len(normas_unicas),
    "enlaces_al_fin": None,
    "nuevos_total": None,
    "por_tipo": {}
}

# ============================================================
# FASE 1: RECOLECCIÓN DE LINKS
# ============================================================
for tipo in TIPOS_NORMATIVA:

    if saltando_tipo and tipo != progreso["ultimo_tipo"]:
        log.info(f"Saltando (retoma): {tipo}")
        continue
    if saltando_tipo and tipo == progreso["ultimo_tipo"]:
        saltando_tipo = False

    log.info(f"\n{'='*55}")
    log.info(f"TIPO DE NORMA: {tipo.upper()}")
    log.info(f"{'='*55}")

    normas_del_tipo        = 0
    resultados_por_termino = {}
    driver                 = iniciar_navegador()

    try:
        for busqueda in BUSQUEDAS:
            termino = busqueda["termino"]
            variante = busqueda["variante"]

            if saltando_variante and variante != progreso["ultima_variante"]:
                log.info(f"  Saltando (retoma): '{variante}'")
                continue
            if saltando_variante and variante == progreso["ultima_variante"]:
                saltando_variante = False
                continue

            log.info(f"\n--- Buscando: {tipo} + '{variante}' (término: {termino}) ---")
            normas_del_variante = 0

            if not buscar_con_reintentos(driver, tipo, variante):
                continue

            numero_pagina = 1

            while True:
                try:
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "a[href*='verNorma.do']")
                        )
                    )
                except TimeoutException:
                    if numero_pagina == 1:
                        log.info(f"  Sin resultados para '{variante}'.")
                    break

                time.sleep(PAUSA_ENTRE_PAGINAS)

                links = driver.find_elements(
                    By.CSS_SELECTOR, "a[href*='verNorma.do']"
                )
                nuevos_en_pag = 0

                for link in links:
                    texto = link.text.strip()
                    if "ver norma y textos resaltados" in texto.lower():
                        continue
                    href = link.get_attribute("href")
                    if href and href not in normas_unicas:
                        # Se registra URL, texto, término padre y variante usada
                        normas_unicas[href] = {
                            "texto":    texto,
                            "termino":  termino,
                            "variante": variante
                        }
                        nuevos_en_pag       += 1
                        normas_del_variante += 1
                        normas_del_tipo     += 1

                if nuevos_en_pag > 0:
                    log.info(f"  Página {numero_pagina}: +{nuevos_en_pag} nuevas normas.")

                if hay_pagina_siguiente(driver):
                    btn = driver.find_element(By.CLASS_NAME, "page-right")
                    driver.execute_script("arguments[0].click();", btn)
                    numero_pagina += 1
                    time.sleep(PAUSA_ENTRE_PAGINAS)
                else:
                    break

            log.info(f"  '{variante}': {normas_del_variante} normas nuevas acumuladas.")

            # Acumular por término padre en el historial
            resultados_por_termino[termino] = (
                resultados_por_termino.get(termino, 0) + normas_del_variante
            )

            guardar_json(ARCHIVO_ENLACES, normas_unicas)
            guardar_json(ARCHIVO_PROGRESO, {
                "ultimo_tipo":     tipo,
                "ultimo_termino":  termino,
                "ultima_variante": variante
            })
            log.info("  [+] Progreso guardado en disco.")

            time.sleep(PAUSA_ENTRE_TERMINOS)

    finally:
        registro_ejecucion["por_tipo"][tipo] = {
            "nuevas_normas":    normas_del_tipo,
            "por_termino":      resultados_por_termino
        }
        driver.quit()
        gc.collect()
        log.info(f"\n>>> Tipo '{tipo.upper()}': {normas_del_tipo} normas únicas nuevas. "
                 f"Sesión cerrada. <<<")
        time.sleep(PAUSA_ENTRE_TIPOS)

guardar_json(ARCHIVO_PROGRESO, {
    "ultimo_tipo": None, "ultimo_termino": None, "ultima_variante": None
})

registro_ejecucion["fin"]            = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
registro_ejecucion["enlaces_al_fin"] = len(normas_unicas)
registro_ejecucion["nuevos_total"]   = (
    len(normas_unicas) - registro_ejecucion["enlaces_al_inicio"]
)

historial = cargar_json(ARCHIVO_HISTORIAL, [])
historial.append(registro_ejecucion)
guardar_json(ARCHIVO_HISTORIAL, historial)
log.info(f"[+] Ejecución registrada en {ARCHIVO_HISTORIAL}")

log.info(f"\n{'='*55}")
log.info(f"RECOLECCIÓN COMPLETA. Total de enlaces acumulados: {len(normas_unicas)}")
log.info(f"Nuevos enlaces en esta ejecución: {registro_ejecucion['nuevos_total']}")