# ============================================================
# ETIQUETADO MANUAL DE MUESTRA
# ============================================================
# Cuatro modos de uso, seleccionables cambiando MODO:
#
# "muestra_piloto" → Exporta 500 normas aleatorias para la
#                    prueba de doble ciego con el director
#
# "calcular_kappa" → Calcula el Kappa de Cohen comparando
#                    tus etiquetas con las del director
#
# "exportar"       → Exporta la muestra completa (2500 normas)
#                    para el etiquetado definitivo
#
# "importar"       → Lee el Excel etiquetado y carga las
#                    etiquetas en PostgreSQL
# ============================================================

import os
import logging
import pandas as pd
from sqlalchemy import create_engine, text

# ============================================================
# CONFIGURACIÓN — SOLO MODIFICAR ESTA SECCIÓN
# ============================================================
MODO             = "importar"  # cambiar según la etapa

DATABASE_URI     = "postgresql://tomas:2828@localhost:5432/tesis"
RANDOM_SEED      = 42               # mantener siempre el mismo para reproducibilidad

# Archivos
ARCHIVO_PILOTO   = "muestra_piloto_kappa (2).xlsx"
ARCHIVO_MUESTRA  = "muestra_etiquetado.xlsx"

# Tamaños
TAMANIO_PILOTO   = 500               # normas para la prueba de doble ciego
TAMANIO_MUESTRA  = 2500             # normas para el etiquetado definitivo

# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("etiquetado.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ============================================================
# CONEXIÓN A BD
# ============================================================
engine = create_engine(DATABASE_URI)

# ============================================================
# UTILIDADES COMPARTIDAS
# ============================================================

def aplicar_formato_excel(ws, col_resumen="E"):
    """Aplica formato visual uniforme a cualquier hoja de etiquetado."""
    from openpyxl.styles import Alignment, PatternFill, Font
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
    col_idx = ord(col_resumen) - ord("A") + 1
    for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True)


def cargar_normas_desde_bd() -> pd.DataFrame:
    """Carga todas las normas con resumen disponible desde PostgreSQL."""
    return pd.read_sql("""
        SELECT
            id,
            CASE
                WHEN tipo_normativa IS NOT NULL AND tipo_normativa != ''
                THEN tipo_normativa
                ELSE 'Sin clasificar'
            END AS tipo_normativa,
            numero_norma,
            ano_sancion,
            resumen
        FROM normativas
        WHERE resumen IS NOT NULL
          AND resumen != ''
          AND (filtrado_heuristico IS NULL OR filtrado_heuristico = 0)
    """, engine)


def muestra_estratificada(df_total: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """
    Extrae una muestra aleatoria estratificada proporcional al
    peso de cada tipo_normativa en el dataset total.
    """
    fragmentos = []
    conteos = df_total["tipo_normativa"].value_counts()

    for tipo, cantidad_total in conteos.items():
        n_tipo = max(1, round(n * cantidad_total / len(df_total)))
        n_tipo = min(n_tipo, cantidad_total)
        fragmento = df_total[df_total["tipo_normativa"] == tipo].sample(
            n=n_tipo, random_state=seed
        )
        fragmentos.append(fragmento)

    muestra = pd.concat(fragmentos, ignore_index=True)

    if len(muestra) > n:
        muestra = muestra.sample(n=n, random_state=seed).reset_index(drop=True)
    elif len(muestra) < n:
        faltantes = n - len(muestra)
        ids_muestra = muestra["id"].tolist()
        resto = df_total[~df_total["id"].isin(ids_muestra)]
        if len(resto) >= faltantes:
            muestra = pd.concat([
                muestra,
                resto.sample(n=faltantes, random_state=seed)
            ]).reset_index(drop=True)

    return muestra


# ============================================================
# MODO 1: MUESTRA PILOTO PARA DOBLE CIEGO
# ============================================================
if MODO == "muestra_piloto":
    log.info(f"Generando muestra piloto de {TAMANIO_PILOTO} normas para prueba de doble ciego...")

    df_total = cargar_normas_desde_bd()
    log.info(f"Normas disponibles en BD: {len(df_total)}")

    piloto = df_total.sample(n=TAMANIO_PILOTO, random_state=RANDOM_SEED).reset_index(drop=True)

    # Tres columnas de etiquetado: una para vos, una para el director, una de acuerdo
    piloto["tu_etiqueta"]       = ""
    piloto["etiqueta_director"] = ""

    piloto = piloto[[
        "id", "tipo_normativa", "numero_norma", "ano_sancion",
        "resumen", "tu_etiqueta", "etiqueta_director"
    ]]

    with pd.ExcelWriter(ARCHIVO_PILOTO, engine="openpyxl") as writer:
        piloto.to_excel(writer, index=False, sheet_name="Piloto")
        ws = writer.sheets["Piloto"]
        ws.column_dimensions["A"].width = 8
        ws.column_dimensions["B"].width = 25
        ws.column_dimensions["C"].width = 15
        ws.column_dimensions["D"].width = 8
        ws.column_dimensions["E"].width = 80
        ws.column_dimensions["F"].width = 18
        ws.column_dimensions["G"].width = 22
        aplicar_formato_excel(ws, col_resumen="E")

    log.info(f"Muestra piloto exportada: {TAMANIO_PILOTO} normas → {ARCHIVO_PILOTO}")
    log.info("\nPASOS SIGUIENTES:")
    log.info("  1. Completá la columna 'tu_etiqueta' con 1 o 0")
    log.info("  2. Ocultá esa columna en Excel (click derecho → Ocultar)")
    log.info("     antes de enviárselo al director")
    log.info("  3. El director completa 'etiqueta_director' con 1 o 0")
    log.info("  4. Recibís el archivo, mostrás la columna ocultada")
    log.info("  5. Cambiá MODO = 'calcular_kappa' y volvé a correr")

# ============================================================
# MODO 2: CALCULAR KAPPA DE COHEN
# ============================================================
elif MODO == "calcular_kappa":
    from sklearn.metrics import cohen_kappa_score

    if not os.path.exists(ARCHIVO_PILOTO):
        log.error(f"No se encontró '{ARCHIVO_PILOTO}'.")
        raise SystemExit(1)

    log.info(f"Leyendo etiquetas desde {ARCHIVO_PILOTO}...")
    df_piloto = pd.read_excel(ARCHIVO_PILOTO, sheet_name="Piloto")

    # Filtrar filas con ambas etiquetas completas
    df_piloto = df_piloto.dropna(subset=["tu_etiqueta", "etiqueta_director"])
    df_piloto = df_piloto[
        df_piloto["tu_etiqueta"].isin([0, 1, 0.0, 1.0]) &
        df_piloto["etiqueta_director"].isin([0, 1, 0.0, 1.0])
    ]
    df_piloto["tu_etiqueta"]       = df_piloto["tu_etiqueta"].astype(int)
    df_piloto["etiqueta_director"] = df_piloto["etiqueta_director"].astype(int)

    total     = len(df_piloto)
    acuerdos  = (df_piloto["tu_etiqueta"] == df_piloto["etiqueta_director"]).sum()
    kappa     = cohen_kappa_score(df_piloto["tu_etiqueta"], df_piloto["etiqueta_director"])

    log.info(f"\n{'='*55}")
    log.info(f"RESULTADO — KAPPA DE COHEN")
    log.info(f"{'='*55}")
    log.info(f"  Normas evaluadas:  {total}")
    log.info(f"  Acuerdos:          {acuerdos}/{total} ({acuerdos/total*100:.1f}%)")
    log.info(f"  Kappa de Cohen:    {kappa:.4f}")
    log.info("")

    if kappa >= 0.8:
        log.info("  Interpretación: Acuerdo casi perfecto.")
        log.info("  El criterio está bien definido. Podés escalar el etiquetado.")
    elif kappa >= 0.6:
        log.info("  Interpretación: Acuerdo sustancial.")
        log.info("  El criterio es aceptable. Revisá los casos de desacuerdo")
        log.info("  con el director antes de escalar.")
    elif kappa >= 0.4:
        log.info("  Interpretación: Acuerdo moderado.")
        log.info("  Revisá los casos de desacuerdo y refiná el criterio")
        log.info("  antes de etiquetar la muestra completa.")
    else:
        log.info("  Interpretación: Acuerdo débil.")
        log.info("  El criterio necesita redefinirse antes de continuar.")

    # Detalle de casos de desacuerdo
    desacuerdos = df_piloto[df_piloto["tu_etiqueta"] != df_piloto["etiqueta_director"]]

    if len(desacuerdos) == 0:
        log.info("\n  No hubo casos de desacuerdo.")
    else:
        log.info(f"\n  Casos de desacuerdo ({len(desacuerdos)}):")
        log.info("  (Estos son los casos a discutir con el director)")
        for _, row in desacuerdos.iterrows():
            log.info(f"\n  ID {int(row['id'])} | {row['tipo_normativa']} {row['numero_norma']}")
            log.info(f"  Tu etiqueta: {int(row['tu_etiqueta'])} | "
                     f"Director: {int(row['etiqueta_director'])}")
            log.info(f"  Resumen: {str(row['resumen'])[:200]}...")

# ============================================================
# MODO 3: EXPORTAR MUESTRA COMPLETA PARA ETIQUETADO DEFINITIVO
# ============================================================
elif MODO == "exportar":
    log.info(f"Generando muestra estratificada de {TAMANIO_MUESTRA} normas...")

    df_total = cargar_normas_desde_bd()
    log.info(f"Normas disponibles en BD: {len(df_total)}")
    log.info(f"Distribución por tipo:\n{df_total['tipo_normativa'].value_counts().to_string()}")

    muestra = muestra_estratificada(df_total, TAMANIO_MUESTRA, RANDOM_SEED)

    muestra["politica_energetica"] = ""
    muestra["notas"]               = ""

    muestra = muestra[[
        "id", "tipo_normativa", "numero_norma", "ano_sancion",
        "resumen", "politica_energetica", "notas"
    ]]

    with pd.ExcelWriter(ARCHIVO_MUESTRA, engine="openpyxl") as writer:
        muestra.to_excel(writer, index=False, sheet_name="Etiquetado")

        ws = writer.sheets["Etiquetado"]
        ws.column_dimensions["A"].width = 8
        ws.column_dimensions["B"].width = 25
        ws.column_dimensions["C"].width = 15
        ws.column_dimensions["D"].width = 8
        ws.column_dimensions["E"].width = 80
        ws.column_dimensions["F"].width = 20
        ws.column_dimensions["G"].width = 30
        aplicar_formato_excel(ws, col_resumen="E")

        # Segunda hoja: distribución por tipo
        from openpyxl.styles import PatternFill, Font
        dist_muestra = muestra["tipo_normativa"].value_counts().reset_index()
        dist_muestra.columns = ["tipo_normativa", "en_muestra"]
        dist_total = df_total["tipo_normativa"].value_counts().reset_index()
        dist_total.columns = ["tipo_normativa", "en_dataset_total"]
        dist = dist_muestra.merge(dist_total, on="tipo_normativa")
        dist["pct_muestra"]  = (dist["en_muestra"] / dist["en_muestra"].sum() * 100).round(1)
        dist["pct_dataset"]  = (dist["en_dataset_total"] / dist["en_dataset_total"].sum() * 100).round(1)
        dist = dist.sort_values("en_dataset_total", ascending=False)
        dist.to_excel(writer, index=False, sheet_name="Distribucion por tipo")

        ws2 = writer.sheets["Distribucion por tipo"]
        ws2.column_dimensions["A"].width = 28
        ws2.column_dimensions["B"].width = 14
        ws2.column_dimensions["C"].width = 18
        ws2.column_dimensions["D"].width = 14
        ws2.column_dimensions["E"].width = 14
        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        for cell in ws2[1]:
            cell.fill = header_fill
            cell.font = header_font

    log.info(f"Muestra exportada: {len(muestra)} normas → {ARCHIVO_MUESTRA}")
    log.info(f"Distribución en la muestra:\n"
             f"{muestra['tipo_normativa'].value_counts().to_string()}")
    log.info("\nPASOS SIGUIENTES:")
    log.info(f"  1. Abrí {ARCHIVO_MUESTRA} en Excel")
    log.info("  2. Completá la columna 'politica_energetica' con 1 o 0")
    log.info("  3. Guardá el archivo")
    log.info("  4. Cambiá MODO = 'importar' y volvé a correr")

# ============================================================
# MODO 4: IMPORTAR ETIQUETAS A POSTGRESQL
# ============================================================
elif MODO == "importar":
    if not os.path.exists(ARCHIVO_MUESTRA):
        log.error(f"No se encontró '{ARCHIVO_MUESTRA}'.")
        raise SystemExit(1)

    log.info(f"Leyendo etiquetas desde {ARCHIVO_MUESTRA}...")
    df_etiquetado = pd.read_excel(ARCHIVO_MUESTRA, sheet_name="Etiquetado")

    if "politica_energetica" not in df_etiquetado.columns:
        log.error("El archivo no tiene la columna 'politica_energetica'.")
        raise SystemExit(1)

    df_etiquetado = df_etiquetado.dropna(subset=["politica_energetica"])
    df_etiquetado = df_etiquetado[
        df_etiquetado["politica_energetica"].isin([0, 1, 0.0, 1.0])
    ]
    df_etiquetado["politica_energetica"] = df_etiquetado["politica_energetica"].astype(int)

    total     = len(df_etiquetado)
    positivas = df_etiquetado["politica_energetica"].sum()

    log.info(f"Etiquetas válidas encontradas: {total}")
    log.info(f"  Políticas energéticas (1): {positivas} ({positivas/total*100:.1f}%)")
    log.info(f"  No políticas (0):          {total - positivas} "
             f"({(total-positivas)/total*100:.1f}%)")

    if total < 500:
        log.warning(f"Solo hay {total} etiquetas. "
                    f"Se recomiendan al menos 500 para un entrenamiento robusto.")
    if positivas < 50:
        log.warning("Hay muy pocos positivos. Revisá el criterio de etiquetado.")

    log.info("Cargando etiquetas en PostgreSQL...")
    with engine.connect() as conn:
        actualizadas = 0
        for _, fila in df_etiquetado.iterrows():
            conn.execute(
                text("""
                    UPDATE normativas
                    SET politica_energetica = :etiqueta,
                        es_muestra_entrenamiento = 1
                    WHERE id = :id
                """),
                {"etiqueta": int(fila["politica_energetica"]), "id": int(fila["id"])}
            )
            actualizadas += 1
        conn.commit()

    log.info(f"Etiquetas cargadas: {actualizadas} registros actualizados en PostgreSQL.")
    log.info("\nPASOS SIGUIENTES:")
    log.info("  Ya podés correr la Celda 4 para entrenar el modelo.")

else:
    log.error(f"MODO '{MODO}' no reconocido.")
    log.error("Opciones válidas: 'muestra_piloto', 'calcular_kappa', 'exportar', 'importar'")