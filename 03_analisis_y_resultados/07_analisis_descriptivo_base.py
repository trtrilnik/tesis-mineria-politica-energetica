# ============================================================
# CELDA 7 — VALIDACIÓN
# ============================================================
# Valida la calidad de la clasificación automática realizada
# por el modelo en la Celda 5, mediante revisión manual de
# una muestra aleatoria de los resultados.
#
# Cuatro modos seleccionables cambiando MODO:
#
# "exportar_validacion" → Exporta muestra estratificada para
#                         revisión manual de las predicciones
#
# "calcular_metricas"   → Compara etiquetas manuales de
#                         validación contra predicciones del
#                         modelo y calcula métricas reales
#
# "exportar_borderline" → Exporta los casos con confianza
#                         cercana al umbral para revisión
#                         focalizada
#
# "refinar"             → Carga las correcciones manuales
#                         de vuelta a PostgreSQL para un
#                         eventual re-entrenamiento
# ============================================================

import os
import logging
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

# ============================================================
# CONFIGURACIÓN — SOLO MODIFICAR ESTA SECCIÓN
# ============================================================
MODO = "exportar_validacion"   # cambiar según la etapa

DATABASE_URI           = "postgresql://tomas:2828@localhost:5432/tesis"
RANDOM_SEED            = 42

# Archivos
ARCHIVO_VALIDACION     = "validacion_modelo.xlsx"
ARCHIVO_BORDERLINE     = "validacion_borderline.xlsx"

# Tamaños de muestra
TAMANIO_VALIDACION     = 200    # normas para validación general
TAMANIO_BORDERLINE     = 100    # normas borderline para revisión focalizada

# Rango de confianza considerado "borderline"
UMBRAL_BORDERLINE_MIN  = 0.35
UMBRAL_BORDERLINE_MAX  = 0.65

# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("validacion.log", encoding="utf-8"),
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
    """Aplica formato visual uniforme a la hoja."""
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


def colorear_predicciones(ws, col_pred, col_conf):
    """
    Colorea la columna de predicción: verde para 1, rojo para 0.
    Colorea la confianza: naranja si es borderline.
    """
    from openpyxl.styles import PatternFill
    verde    = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    rojo     = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    naranja  = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")

    col_p = ord(col_pred) - ord("A") + 1
    col_c = ord(col_conf) - ord("A") + 1

    for row in ws.iter_rows(min_row=2):
        cell_pred = row[col_p - 1]
        cell_conf = row[col_c - 1]
        try:
            pred = int(cell_pred.value)
            conf = float(cell_conf.value)
            cell_pred.fill = verde if pred == 1 else rojo
            if UMBRAL_BORDERLINE_MIN <= conf <= UMBRAL_BORDERLINE_MAX:
                cell_conf.fill = naranja
        except (TypeError, ValueError):
            pass


# ============================================================
# MODO 1: EXPORTAR MUESTRA DE VALIDACIÓN GENERAL
# ============================================================
if MODO == "exportar_validacion":
    log.info("Cargando resultados de la inferencia desde PostgreSQL...")

    df_clasificadas = pd.read_sql("""
        SELECT
            id,
            tipo_normativa,
            numero_norma,
            ano_sancion,
            tema,
            titulo,
            resumen,
            politica_energetica   AS prediccion_modelo,
            confianza_modelo
        FROM normativas
        WHERE politica_energetica IS NOT NULL
          AND confianza_modelo IS NOT NULL
          AND resumen IS NOT NULL
          AND resumen != ''
    """, engine)

    total = len(df_clasificadas)
    positivas = df_clasificadas["prediccion_modelo"].sum()
    log.info(f"Normas clasificadas por el modelo: {total}")
    log.info(f"  Predichas como política (1): {positivas} ({positivas/total*100:.1f}%)")
    log.info(f"  Predichas como no política (0): {total-positivas} "
             f"({(total-positivas)/total*100:.1f}%)")

    # Muestra estratificada por predicción del modelo:
    # mitad de positivos y mitad de negativos para evaluar ambas clases
    n_por_clase = TAMANIO_VALIDACION // 2
    df_pos = df_clasificadas[df_clasificadas["prediccion_modelo"] == 1]
    df_neg = df_clasificadas[df_clasificadas["prediccion_modelo"] == 0]

    muestra_pos = df_pos.sample(
        n=min(n_por_clase, len(df_pos)), random_state=RANDOM_SEED
    )
    muestra_neg = df_neg.sample(
        n=min(n_por_clase, len(df_neg)), random_state=RANDOM_SEED
    )
    muestra = pd.concat([muestra_pos, muestra_neg]).sample(
        frac=1, random_state=RANDOM_SEED
    ).reset_index(drop=True)

    # Columna para la revisión manual
    muestra["etiqueta_manual"] = ""   # revisor completa con 1 o 0
    muestra["notas"]           = ""

    muestra = muestra[[
        "id", "tipo_normativa", "numero_norma", "ano_sancion",
        "tema", "titulo", "resumen", "prediccion_modelo", "confianza_modelo",
        "etiqueta_manual", "notas"
    ]]

    with pd.ExcelWriter(ARCHIVO_VALIDACION, engine="openpyxl") as writer:
        muestra.to_excel(writer, index=False, sheet_name="Validacion")

        ws = writer.sheets["Validacion"]
        ws.column_dimensions["A"].width = 8
        ws.column_dimensions["B"].width = 25
        ws.column_dimensions["C"].width = 15
        ws.column_dimensions["D"].width = 8
        ws.column_dimensions["E"].width = 80
        ws.column_dimensions["F"].width = 20
        ws.column_dimensions["G"].width = 18
        ws.column_dimensions["H"].width = 18
        ws.column_dimensions["I"].width = 30
        aplicar_formato_excel(ws, col_resumen="E")
        colorear_predicciones(ws, col_pred="F", col_conf="G")

    log.info(f"\nMuestra de validación exportada: {len(muestra)} normas → {ARCHIVO_VALIDACION}")
    log.info(f"  Predichas positivas en muestra: {muestra['prediccion_modelo'].sum()}")
    log.info(f"  Predichas negativas en muestra: {(muestra['prediccion_modelo']==0).sum()}")
    log.info("\nPASOS SIGUIENTES:")
    log.info("  1. Abrí el Excel y revisá cada fila")
    log.info("  2. Completá 'etiqueta_manual' con 1 o 0 según tu criterio")
    log.info("     (ignorando la predicción del modelo para no sesgarte)")
    log.info("  3. Guardá el archivo")
    log.info("  4. Cambiá MODO = 'calcular_metricas' y volvé a correr")

# ============================================================
# MODO 2: CALCULAR MÉTRICAS DE VALIDACIÓN
# ============================================================
elif MODO == "calcular_metricas":
    from sklearn.metrics import (
        classification_report, cohen_kappa_score,
        confusion_matrix, precision_recall_fscore_support
    )

    if not os.path.exists(ARCHIVO_VALIDACION):
        log.error(f"No se encontró '{ARCHIVO_VALIDACION}'.")
        raise SystemExit(1)

    log.info(f"Leyendo validación desde {ARCHIVO_VALIDACION}...")
    df_val = pd.read_excel(ARCHIVO_VALIDACION, sheet_name="Validacion")

    # Filtrar filas con etiqueta manual completa
    df_val = df_val.dropna(subset=["etiqueta_manual"])
    df_val = df_val[df_val["etiqueta_manual"].isin([0, 1, 0.0, 1.0])]
    df_val["etiqueta_manual"]   = df_val["etiqueta_manual"].astype(int)
    df_val["prediccion_modelo"] = df_val["prediccion_modelo"].astype(int)

    y_true = df_val["etiqueta_manual"].values
    y_pred = df_val["prediccion_modelo"].values
    total  = len(df_val)

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    kappa    = cohen_kappa_score(y_true, y_pred)
    cm       = confusion_matrix(y_true, y_pred)

    log.info(f"\n{'='*55}")
    log.info("MÉTRICAS DE VALIDACIÓN DEL MODELO")
    log.info(f"{'='*55}")
    log.info(f"  Normas revisadas:  {total}")
    log.info(f"  Precisión:         {precision:.4f}")
    log.info(f"  Recall:            {recall:.4f}")
    log.info(f"  F1:                {f1:.4f}")
    log.info(f"  Kappa de Cohen:    {kappa:.4f}")
    log.info(f"\n  Matriz de confusión:")
    log.info(f"                   Pred 0    Pred 1")
    log.info(f"  Real 0 (no pol): {cm[0][0]:>6}    {cm[0][1]:>6}")
    log.info(f"  Real 1 (sí pol): {cm[1][0]:>6}    {cm[1][1]:>6}")
    log.info(f"\n  Reporte completo:")
    log.info(f"\n{classification_report(y_true, y_pred, target_names=['No política', 'Política'])}")

    # Interpretación automática
    log.info(f"{'='*55}")
    log.info("INTERPRETACIÓN Y RECOMENDACIÓN")
    log.info(f"{'='*55}")

    if f1 >= 0.85:
        log.info("  F1 >= 0.85: El modelo clasifica con alta calidad.")
        log.info("  No es necesario refinar el entrenamiento.")
    elif f1 >= 0.70:
        log.info("  F1 entre 0.70 y 0.85: Calidad aceptable.")
        log.info("  Evaluá si los errores son sistemáticos revisando")
        log.info("  los falsos positivos y falsos negativos.")
        log.info("  Considerá correr MODO='exportar_borderline' para")
        log.info("  identificar casos problemáticos.")
    else:
        log.info("  F1 < 0.70: El modelo necesita mejoras.")
        log.info("  Opciones:")
        log.info("  a) Ampliar o revisar la muestra de entrenamiento")
        log.info("  b) Ajustar el umbral de clasificación en la Celda 5")
        log.info("  c) Correr MODO='refinar' para incorporar las")
        log.info("     correcciones manuales y re-entrenar")

    # Análisis de errores por tipo de normativa
    errores = df_val[df_val["etiqueta_manual"] != df_val["prediccion_modelo"]]
    if len(errores) > 0:
        log.info(f"\n  Errores por tipo de normativa ({len(errores)} total):")
        for tipo, count in errores["tipo_normativa"].value_counts().items():
            log.info(f"    {tipo}: {count} errores")

# ============================================================
# MODO 3: EXPORTAR CASOS BORDERLINE
# ============================================================
elif MODO == "exportar_borderline":
    log.info(f"Extrayendo casos borderline "
             f"(confianza entre {UMBRAL_BORDERLINE_MIN} y {UMBRAL_BORDERLINE_MAX})...")

    df_borderline = pd.read_sql(text("""
        SELECT
            id,
            tipo_normativa,
            numero_norma,
            ano_sancion,
            tema,
            titulo,
            resumen,
            politica_energetica  AS prediccion_modelo,
            confianza_modelo
        FROM normativas
        WHERE confianza_modelo BETWEEN :min AND :max
          AND resumen IS NOT NULL
          AND resumen != ''
        ORDER BY confianza_modelo DESC
    """), engine, params={
        "min": UMBRAL_BORDERLINE_MIN,
        "max": UMBRAL_BORDERLINE_MAX
    })

    total_borderline = len(df_borderline)
    log.info(f"Casos borderline encontrados: {total_borderline}")

    if total_borderline == 0:
        log.info("No hay casos borderline en ese rango de confianza.")
        raise SystemExit(0)

    # Si hay más de TAMANIO_BORDERLINE, tomar muestra aleatoria
    if total_borderline > TAMANIO_BORDERLINE:
        df_borderline = df_borderline.sample(
            n=TAMANIO_BORDERLINE, random_state=RANDOM_SEED
        ).reset_index(drop=True)
        log.info(f"Se exporta una muestra aleatoria de {TAMANIO_BORDERLINE} casos.")

    df_borderline["etiqueta_manual"] = ""
    df_borderline["notas"]           = ""

    df_borderline = df_borderline[[
        "id", "tipo_normativa", "numero_norma", "ano_sancion",
        "tema", "titulo", "resumen", "prediccion_modelo", "confianza_modelo",
        "etiqueta_manual", "notas"
    ]]

    with pd.ExcelWriter(ARCHIVO_BORDERLINE, engine="openpyxl") as writer:
        df_borderline.to_excel(writer, index=False, sheet_name="Borderline")

        ws = writer.sheets["Borderline"]
        ws.column_dimensions["A"].width = 8
        ws.column_dimensions["B"].width = 25
        ws.column_dimensions["C"].width = 15
        ws.column_dimensions["D"].width = 8
        ws.column_dimensions["E"].width = 80
        ws.column_dimensions["F"].width = 20
        ws.column_dimensions["G"].width = 18
        ws.column_dimensions["H"].width = 18
        ws.column_dimensions["I"].width = 30
        aplicar_formato_excel(ws, col_resumen="E")
        colorear_predicciones(ws, col_pred="F", col_conf="G")

    log.info(f"Casos borderline exportados → {ARCHIVO_BORDERLINE}")
    log.info("\nPASOS SIGUIENTES:")
    log.info("  1. Revisá cada caso y completá 'etiqueta_manual' con 1 o 0")
    log.info("  2. Guardá el archivo")
    log.info("  3. Cambiá MODO = 'refinar' y volvé a correr para")
    log.info("     incorporar las correcciones a PostgreSQL")

# ============================================================
# MODO 4: REFINAR — CARGAR CORRECCIONES A POSTGRESQL
# ============================================================
elif MODO == "refinar":
    # Acepta correcciones tanto del archivo de validación general
    # como del archivo de casos borderline
    archivos_a_procesar = []
    if os.path.exists(ARCHIVO_VALIDACION):
        archivos_a_procesar.append((ARCHIVO_VALIDACION, "Validacion"))
    if os.path.exists(ARCHIVO_BORDERLINE):
        archivos_a_procesar.append((ARCHIVO_BORDERLINE, "Borderline"))

    if not archivos_a_procesar:
        log.error("No se encontró ningún archivo de validación para procesar.")
        raise SystemExit(1)

    total_corregidas = 0

    for archivo, hoja in archivos_a_procesar:
        log.info(f"Procesando correcciones desde {archivo} (hoja: {hoja})...")
        df = pd.read_excel(archivo, sheet_name=hoja)

        # Solo procesar filas donde la etiqueta manual difiere de la predicción
        df = df.dropna(subset=["etiqueta_manual"])
        df = df[df["etiqueta_manual"].isin([0, 1, 0.0, 1.0])]
        df["etiqueta_manual"]   = df["etiqueta_manual"].astype(int)
        df["prediccion_modelo"] = df["prediccion_modelo"].astype(int)

        correcciones = df[df["etiqueta_manual"] != df["prediccion_modelo"]]
        coincidencias = df[df["etiqueta_manual"] == df["prediccion_modelo"]]

        log.info(f"  Total revisados:   {len(df)}")
        log.info(f"  Coinciden con modelo: {len(coincidencias)}")
        log.info(f"  Correcciones:      {len(correcciones)}")

        if len(correcciones) == 0:
            log.info("  No hay correcciones que aplicar en este archivo.")
            continue

        with engine.connect() as conn:
            for _, fila in correcciones.iterrows():
                conn.execute(
                    text("""
                        UPDATE normativas
                        SET politica_energetica = :etiqueta,
                            es_muestra_entrenamiento = 1
                        WHERE id = :id
                    """),
                    {"etiqueta": int(fila["etiqueta_manual"]), "id": int(fila["id"])}
                )
                total_corregidas += 1
            conn.commit()

        log.info(f"  Correcciones aplicadas: {len(correcciones)}")

    log.info(f"\nTotal de registros corregidos en PostgreSQL: {total_corregidas}")
    log.info("\nPASOS SIGUIENTES:")
    log.info("  Con las correcciones incorporadas, podés:")
    log.info("  a) Re-entrenar el modelo (Celda 5) con el dataset ampliado")
    log.info("     y volver a correr la Celda 5 para reclasificar")
    log.info("  b) Aceptar los resultados actuales si las métricas")
    log.info("     de validación son satisfactorias")

else:
    log.error(f"MODO '{MODO}' no reconocido.")
    log.error("Opciones válidas: 'exportar_validacion', 'calcular_metricas', "
              "'exportar_borderline', 'refinar'")