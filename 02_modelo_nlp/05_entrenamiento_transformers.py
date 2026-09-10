# ============================================================
# CELDA 5 — FINE-TUNING DE RoBERTalex PARA CLASIFICACIÓN
# DE POLÍTICAS ENERGÉTICAS (VERSIÓN LOCAL + DICE LOSS)
# ============================================================
# Modelo: PlanTL-GOB-ES/RoBERTalex
# Input:  campo `resumen` de la tabla `normativas`
# Output: modelo fine-tuned guardado en ./modelo_politica_energetica
# ============================================================

import logging
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback
)
import torch
import torch.nn as nn
import torch.nn.functional as F

# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("entrenamiento.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ============================================================
# CONFIGURACIÓN GENERAL (ENTORNO LOCAL)
# ============================================================
DATABASE_URI   = "postgresql://tomas:2828@localhost:5432/tesis"
MODEL_NAME     = "PlanTL-GOB-ES/RoBERTalex"
OUTPUT_DIR     = "./modelo_politica_energetica"
MAX_LENGTH     = 512       
TEST_SIZE      = 0.2       
RANDOM_SEED    = 42        

# --- Hiperparámetros (Ajustados para tu GTX 1060 local) ---
BATCH_SIZE                  = 4
GRADIENT_ACCUMULATION_STEPS = 8    # batch efectivo = 4 x 8 = 32
LEARNING_RATE               = 2e-5
NUM_EPOCHS                  = 4
WARMUP_RATIO                = 0.1  

# ============================================================
# VERIFICACIÓN DE GPU
# ============================================================
if torch.cuda.is_available():
    device_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    log.info(f"GPU disponible: {device_name} ({vram_gb:.1f} GB VRAM)")
else:
    log.warning("GPU no detectada. El entrenamiento correrá en CPU y será muy lento.")

# ============================================================
# CARGA DE DATOS ETIQUETADOS DESDE POSTGRESQL LOCAL
# ============================================================
log.info("Cargando datos etiquetados desde PostgreSQL...")

engine = create_engine(DATABASE_URI)

df = pd.read_sql("""
    SELECT 
        TRIM(CONCAT_WS(' - ', NULLIF(tema, ''), NULLIF(titulo, ''), NULLIF(resumen, ''))) AS input_text, 
        politica_energetica AS label
    FROM normativas
    WHERE es_muestra_entrenamiento = 1
      AND (resumen IS NOT NULL AND resumen != '')
""", engine)

log.info(f"Total de ejemplos etiquetados: {len(df)}")
log.info(f"Distribución de clases:\n{df['label'].value_counts().to_string()}")

if df['label'].value_counts().min() < 50:
    log.warning("Hay muy pocos ejemplos de alguna clase.")

# ============================================================
# DIVISIÓN TRAIN / VALIDACIÓN
# ============================================================
df_train, df_val = train_test_split(
    df,
    test_size=TEST_SIZE,
    random_state=RANDOM_SEED,
    stratify=df['label']
)

log.info(f"Set de entrenamiento: {len(df_train)} ejemplos")
log.info(f"Set de validación:    {len(df_val)} ejemplos")

# ============================================================
# TOKENIZACIÓN
# ============================================================
log.info(f"Cargando tokenizador: {MODEL_NAME}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

def tokenizar(batch):
    return tokenizer(
        batch["input_text"],
        padding="max_length",
        truncation=True,
        max_length=MAX_LENGTH
    )

dataset_train = Dataset.from_pandas(df_train.reset_index(drop=True))
dataset_val   = Dataset.from_pandas(df_val.reset_index(drop=True))

log.info("Tokenizando datasets...")
dataset_train = dataset_train.map(tokenizar, batched=True)
dataset_val   = dataset_val.map(tokenizar, batched=True)

dataset_train = dataset_train.rename_column("label", "labels")
dataset_val   = dataset_val.rename_column("label", "labels")

dataset_train.set_format("torch", columns=["input_ids", "attention_mask", "labels"])
dataset_val.set_format("torch",   columns=["input_ids", "attention_mask", "labels"])

# ============================================================
# CARGA DEL MODELO
# ============================================================
log.info(f"Cargando modelo: {MODEL_NAME}")
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME,
    num_labels=2,
    id2label={0: "NO_POLITICA_ENERGETICA", 1: "POLITICA_ENERGETICA"},
    label2id={"NO_POLITICA_ENERGETICA": 0, "POLITICA_ENERGETICA": 1}
)

# ============================================================
# MÉTRICAS DE EVALUACIÓN
# ============================================================
def calcular_metricas(eval_pred):
    logits, labels = eval_pred
    predicciones   = np.argmax(logits, axis=-1)

    from sklearn.metrics import precision_recall_fscore_support, accuracy_score
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predicciones, average="binary", zero_division=0
    )
    accuracy = accuracy_score(labels, predicciones)

    log.info(f"  Precisión: {precision:.4f} | Recall: {recall:.4f} | F1: {f1:.4f}")
    return {"precision": precision, "recall": recall, "f1": f1, "accuracy": accuracy}

# ============================================================
# ARGUMENTOS DE ENTRENAMIENTO
# ============================================================
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
    learning_rate=LEARNING_RATE,
    warmup_ratio=WARMUP_RATIO,
    weight_decay=0.01,
    fp16=torch.cuda.is_available(),
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    greater_is_better=True,
    logging_dir="./logs_entrenamiento",
    logging_steps=50,
    report_to="none",
    seed=RANDOM_SEED,
)

# ============================================================
# TRAINER (CROSS ENTROPY LOSS)
# ============================================================
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset_train,
    eval_dataset=dataset_val,
    processing_class=tokenizer,
    compute_metrics=calcular_metricas,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
)

# ============================================================
# ENTRENAMIENTO
# ============================================================
log.info("="*55)
log.info("INICIANDO ENTRENAMIENTO (CROSS ENTROPY LOSS)")
log.info(f"  Modelo:            {MODEL_NAME}")
log.info(f"  Batch efectivo:    {BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS}")
log.info("="*55)

train_result = trainer.train()

log.info("Entrenamiento finalizado.")
log.info(f"  Loss final train:  {train_result.training_loss:.4f}")

# ============================================================
# EVALUACIÓN FINAL Y REPORTE COMPLETO
# ============================================================
log.info("\nEvaluación final sobre el set de validación:")
eval_result = trainer.evaluate()

predicciones_raw = trainer.predict(dataset_val)
preds = np.argmax(predicciones_raw.predictions, axis=-1)
labels_val = df_val["label"].values

reporte = classification_report(
    labels_val, preds,
    target_names=["No Política Energética", "Política Energética"]
)
log.info(f"\nReporte de clasificación detallado:\n{reporte}")

# ============================================================
# GUARDADO DEL MODELO
# ============================================================
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

log.info(f"\nModelo guardado exitosamente en: {OUTPUT_DIR}")
