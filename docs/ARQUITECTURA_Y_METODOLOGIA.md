# Documentación del Pipeline de Datos (Celdas 1 a 7)

Este documento detalla el propósito de cada script ("celda") dentro del pipeline automatizado de la tesis, explicando la arquitectura del sistema y justificando las decisiones técnicas y librerías utilizadas en cada etapa.

---

## Celda 1: Extracción del Índice General de Normas (`celda1.py` / `celda1b.py`)
**Propósito:** Automatizar la búsqueda en la base de datos de InfoLEG para extraer el universo completo de normativas sancionadas históricamente en Argentina. Obtiene el número de norma, año, tipo y el enlace a la ficha.
**Librerías principales:**
- `selenium`: Elegido porque los buscadores gubernamentales suelen depender de peticiones POST, formularios complejos o renderizado de JavaScript. Selenium permite interactuar con la página como un usuario humano.
- `webdriver_manager`: Facilita la instalación y gestión automática del ChromeDriver, evitando problemas de versiones.
- `logging`: Para registrar el progreso, dada la duración extensa de la descarga.

## Celda 2: Scraping de Fichas Técnicas (`celda2.py` / `celda2b.py` / `celda2c.py`)
**Propósito:** Recorrer los enlaces extraídos en la Celda 1 para raspar los metadatos de cada norma (título, resumen, fecha de sanción y el grafo de modificaciones legislativas: qué norma modifica y por cuál es modificada).
**Librerías principales:**
- `requests`: A diferencia de la Celda 1, acá ya tenemos los enlaces directos. `requests` es muchísimo más rápido y ligero que Selenium para descargar el HTML estático de las fichas.
- `bs4 (BeautifulSoup)`: El estándar de la industria para parsear árboles HTML. Permite navegar fácilmente para extraer el resumen y aislar los hipervínculos de modificaciones.
- `sqlalchemy` (con `JSONB`): Elegido por su robustez como ORM. El uso del tipo `JSONB` nativo de PostgreSQL es fundamental acá para guardar de forma flexible el grafo de dependencias normativas (listas de diccionarios `modifica_a`).

## Celda 3: Gestión de Etiquetado Humano (`celda3.py` / `celda3b.py`)
**Propósito:** Facilitar el ciclo iterativo de curación de datos (Active Learning). Exporta muestras aleatorias a Excel, calcula la concordancia inter-anotadores y vuelve a importar las decisiones humanas a la base de datos.
**Librerías principales:**
- `pandas`: Excelente para transformar consultas SQL complejas en tablas (DataFrames) y aplicar estratificaciones aleatorias (`sample`).
- `openpyxl`: Permite exportar los archivos `.xlsx` aplicando formatos visuales (colores, anchos de columna, negritas) para que el etiquetador humano trabaje cómodo.
- `sklearn.metrics (cohen_kappa_score)`: Esencial metodológicamente. Permite calcular el Índice Kappa de Cohen para validar estadísticamente que los criterios de inclusión/exclusión son consistentes (agreement) antes de entrenar la IA.

## Celda 4: Scraping de Textos Completos (`celda4.py`)
**Propósito:** Descargar el cuerpo completo de las 14.491 normas identificadas como "política energética". Limpia la basura de la web y lo convierte a formato limpio para futuro procesamiento de lenguaje natural (NLP).
**Librerías principales:**
- `selenium`: Se vuelve a utilizar porque las páginas de "texto completo" de InfoLEG suelen ser muy inestables, tener redirecciones o cargar lentamente. El `WebDriverWait` maneja estos timeouts de forma robusta.
- `markdownify`: Librería crucial. Transforma el HTML caótico (y tablas mal formateadas) de InfoLEG en texto plano estructurado (Markdown). Esto elimina etiquetas inútiles y ruido, mejorando exponencialmente la calidad de los datos para la IA.

## Celda 5: Entrenamiento del Modelo Fundacional (`celda5.py`)
**Propósito:** Entrenar un modelo de Inteligencia Artificial (basado en Transformers) para que aprenda el criterio humano de qué es y qué no es una "política energética" basándose en el título y el resumen.
**Librerías principales:**
- `transformers` (HuggingFace) y `datasets`: El estándar actual del estado del arte para NLP. Permite importar modelos masivos pre-entrenados (RoBERTa/BERT) y hacerles *fine-tuning* con nuestros datos.
- `torch` (PyTorch): El motor de tensor que corre por debajo de HuggingFace. Permite compilar la red neuronal, calcular gradientes y aprovechar aceleración por hardware.
- `sklearn.metrics`: Se usa para validar el modelo y calcular el Recall, Precision y F1-Score macro, optimizando el umbral de decisión.

## Celda 6: Inferencia a Escala (`celda6.py`)
**Propósito:** Cargar el modelo entrenado en la Celda 5 y procesar masivamente los 100.000+ resúmenes sin etiquetar, decidiendo automáticamente cuáles pertenecen al corpus de política energética (`politica_energetica = 1`).
**Librerías principales:**
- `torch.utils.data (DataLoader)`: Fundamental por razones de memoria (OOM). Permite dividir la base de datos en "batches" (lotes de ej: 32 normas) para que el modelo no colapse la RAM al predecir 100.000 textos.
- `transformers (AutoModelForSequenceClassification)`: Carga los pesos del modelo que guardamos localmente para ejecutarlo en modo evaluación (`model.eval()`).

## Celda 7: Ingeniería de Datos, NLP y Reportes Finales (`celda7.py` y derivados)
**Propósito:** Extraer la base de datos final curada, aplicar filtros temporales/temáticos, correr algoritmos de minería de texto (LDA, TF-IDF) y generar los entregables para la tesis.
**Librerías principales:**
- `pandas`: Como motor analítico principal (`groupby`, `pivot`, `merge`).
- `scikit-learn (CountVectorizer, LatentDirichletAllocation)`: Se incorporaron para realizar el *Topic Modeling* de los textos sin necesidad de frameworks pesados, revelando automáticamente los focos temáticos por década.
- `networkx` y `matplotlib`: Usadas para la generación de gráficos vectoriales (áreas, barras) y redes de co-ocurrencia de conceptos (Network Graphs), empaquetando visualmente los hallazgos sociológicos e históricos.
- `sqlalchemy (text)`: Se requiere el uso del wrapper `text()` para parametrizar consultas SQL seguras a PostgreSQL desde pandas.
