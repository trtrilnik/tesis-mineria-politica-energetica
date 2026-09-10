# ============================================================
# CELDA 6 — INFERENCIA: CLASIFICACIÓN AUTOMÁTICA DE TODAS
# LAS NORMATIVAS SIN ETIQUETAR
# ============================================================
# Lee desde PostgreSQL todas las normas con politica_energetica IS NULL,
# corre el modelo fine-tuned sobre sus resúmenes, y actualiza el campo
# politica_energetica con la predicción (0 o 1) junto con la
# probabilidad de confianza en un campo separado.
#
# PREREQUISITO: haber corrido la Celda 4 exitosamente.
# El directorio ./modelo_politica_energetica debe existir.
# ============================================================

import logging
import numpy as np
import pandas as pd
import torch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from torch.utils.data import DataLoader, Dataset as TorchDataset

# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("inferencia.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
DATABASE_URI = "postgresql://tomas:2828@localhost:5432/tesis"
MODEL_DIR    = "./modelo_politica_energetica"
MAX_LENGTH   = 512
BATCH_SIZE   = 8     # puede subirse a 16 o 32 en Colab
UMBRAL       = 0.45   # probabilidad mínima para clasificar como 1
               # subir a 0.6 o 0.7 para mayor precisión (menos falsos positivos)
               # bajar a 0.4 para mayor recall (menos falsos negativos)
#Resultados por Umbral:
#Umbral | Precision | Recall | F1-Score
#----------------------------------------
# 0.10  |   0.785   | 0.949  |  0.859
# 0.15  |   0.809   | 0.944  |  0.871
# 0.20  |   0.829   | 0.944  |  0.883
# 0.25  |   0.845   | 0.935  |  0.887
# 0.30  |   0.859   | 0.935  |  0.895
# 0.35  |   0.863   | 0.935  |  0.897
# 0.40  |   0.870   | 0.930  |  0.899
# 0.45  |   0.884   | 0.926  |  0.905
# 0.50  |   0.886   | 0.902  |  0.894
# 0.55  |   0.889   | 0.898  |  0.894
# 0.60  |   0.893   | 0.888  |  0.890
# 0.65  |   0.904   | 0.874  |  0.889
# 0.70  |   0.917   | 0.874  |  0.895
# 0.75  |   0.925   | 0.865  |  0.894
# 0.80  |   0.943   | 0.842  |  0.889
# 0.85  |   0.945   | 0.805  |  0.869
# 0.90  |   0.960   | 0.772  |  0.856
#----------------------------------------
# EL UMBRAL OPTIMO ES: 0.45
# Logra un F1-Score de 0.905 (Precision: 0.884, Recall: 0.926)


# ============================================================
# VERIFICACIÓN DE GPU
# ============================================================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if device.type == "cuda":
    log.info(f"GPU disponible: {torch.cuda.get_device_name(0)}")
else:
    log.warning("Corriendo en CPU. La inferencia será lenta con 25.000+ normas.")

# ============================================================
# CARGA DEL MODELO FINE-TUNED
# ============================================================
import os
if not os.path.exists(MODEL_DIR):
    log.error(f"No se encontró el modelo en '{MODEL_DIR}'. "
              f"Corré la Celda 5 primero.")
    raise SystemExit(1)

log.info(f"Cargando modelo desde: {MODEL_DIR}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model     = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
model.to(device)
model.eval()
log.info("Modelo cargado correctamente.")

# ============================================================
# CARGA DE NORMAS PENDIENTES DESDE POSTGRESQL
# ============================================================
log.info("Cargando normas pendientes de clasificar...")
engine = create_engine(DATABASE_URI)

df = pd.read_sql("""
    SELECT 
        id, 
        TRIM(CONCAT_WS(' - ', NULLIF(tema, ''), NULLIF(titulo, ''), NULLIF(resumen, ''))) AS input_text
    FROM normativas
    WHERE (es_muestra_entrenamiento IS NULL OR es_muestra_entrenamiento = 0)
      AND (resumen IS NOT NULL AND resumen != '')
""", engine)

total = len(df)
log.info(f"Normas pendientes de clasificar: {total}")

if total == 0:
    log.info("No hay normas pendientes. Todas ya tienen clasificación.")
    raise SystemExit(0)

# ============================================================
# DATASET PYTORCH PARA INFERENCIA EN BATCHES
# ============================================================
class NormasDataset(TorchDataset):
    """Dataset minimalista para inferencia por batches."""
    def __init__(self, textos, tokenizer, max_length):
        self.encodings = tokenizer(
            textos,
            padding="max_length",
            truncation=True,
            max_length=max_length,
            return_tensors="pt"
        )

    def __len__(self):
        return self.encodings["input_ids"].shape[0]

    def __getitem__(self, idx):
        return {k: v[idx] for k, v in self.encodings.items()}


log.info("Tokenizando resúmenes para inferencia...")
dataset_inferencia = NormasDataset(
    df["input_text"].tolist(),
    tokenizer,
    MAX_LENGTH
)
dataloader = DataLoader(dataset_inferencia, batch_size=BATCH_SIZE)

# ============================================================
# INFERENCIA
# ============================================================
log.info(f"Iniciando inferencia sobre {total} normas "
         f"(batch size: {BATCH_SIZE}, umbral: {UMBRAL})...")

todas_probs  = []
todos_preds  = []
procesadas   = 0

with torch.no_grad():
    for batch in dataloader:
        batch = {k: v.to(device) for k, v in batch.items()}
        outputs = model(**batch)

        # Convertir logits a probabilidades con softmax
        probs = torch.softmax(outputs.logits, dim=-1)

        # Probabilidad de la clase positiva (índice 1)
        prob_positiva = probs[:, 1].cpu().numpy()

        # Aplicar umbral para obtener predicción binaria
        prediccion = (prob_positiva >= UMBRAL).astype(int)

        todas_probs.extend(prob_positiva.tolist())
        todos_preds.extend(prediccion.tolist())

        procesadas += len(prediccion)
        if procesadas % 500 == 0:
            log.info(f"  Procesadas: {procesadas}/{total}")

df["prediccion"]        = todos_preds
df["prob_positiva"]     = todas_probs

positivas = sum(todos_preds)
log.info(f"\nInferencia completada.")
log.info(f"  Clasificadas como Política Energética (1): {positivas} "
         f"({positivas/total*100:.1f}%)")
log.info(f"  Clasificadas como No Política (0):          {total - positivas} "
         f"({(total-positivas)/total*100:.1f}%)")

# ============================================================
# ESCRITURA EN POSTGRESQL
# ============================================================
# Se agrega la columna confianza_modelo si no existe
# Esta columna guarda la probabilidad para que puedas revisar
# casos borderline (probabilidades cercanas al umbral)
log.info("\nEscribiendo resultados en PostgreSQL...")

with engine.connect() as conn:
    # Agregar columna de confianza si no existe todavía
    conn.execute(text("""
        ALTER TABLE normativas
        ADD COLUMN IF NOT EXISTS confianza_modelo FLOAT
    """))
    conn.commit()

Session = sessionmaker(bind=engine)
session = Session()

try:
    actualizadas = 0
    for _, fila in df.iterrows():
        session.execute(
            text("""
                UPDATE normativas
                SET politica_energetica = :pred,
                    confianza_modelo      = :conf
                WHERE id = :id
            """),
            {
                "pred": int(fila["prediccion"]),
                "conf": float(fila["prob_positiva"]),
                "id":   int(fila["id"])
            }
        )
        actualizadas += 1

        # Commit cada 500 registros para no mantener transacciones largas
        if actualizadas % 500 == 0:
            session.commit()
            log.info(f"  Actualizadas: {actualizadas}/{total}")

    session.commit()
    log.info(f"  Actualizadas: {actualizadas}/{total} — COMPLETO")

except Exception as e:
    log.critical(f"Error escribiendo en BD: {e}")
    session.rollback()
    raise

finally:
    session.close()

# ============================================================
# RESUMEN FINAL Y CASOS BORDERLINE
# ============================================================
log.info(f"\n{'='*55}")
log.info("INFERENCIA COMPLETA")
log.info(f"  Total clasificadas:          {total}")
log.info(f"  Políticas energéticas (1):   {positivas}")
log.info(f"  No políticas (0):            {total - positivas}")

# Identificar casos borderline (confianza entre 0.4 y 0.6)
# Estos son los candidatos más útiles para revisión manual
borderline = df[
    (df["prob_positiva"] >= 0.35) &
    (df["prob_positiva"] <= 0.65)
]
log.info(f"\n  Casos borderline (prob entre 0.35 y 0.65): {len(borderline)}")
log.info("  Estos casos son los más recomendables para revisión manual.")
log.info(f"  Sus IDs están disponibles en el DataFrame `borderline`.")

log.info(f"\nResultados guardados en PostgreSQL.")
log.info(f"Campo `politica_energetica`: predicción binaria (0/1)")
log.info(f"Campo `confianza_modelo`: probabilidad de ser política energética")
log.info(f"\nPara revisar los resultados en pgAdmin:")
log.info(f"  SELECT tipo_normativa, numero_norma, resumen,")
log.info(f"         politica_energetica, confianza_modelo")
log.info(f"  FROM normativas")
log.info(f"  ORDER BY confianza_modelo DESC;")