# Minería de Datos y NLP aplicado a la Política Energética en Argentina (1854-2026)

Este repositorio contiene el código fuente completo, los pipelines de extracción de datos (web scraping) y los modelos de Procesamiento de Lenguaje Natural (NLP) utilizados para la tesis de grado/posgrado sobre la evolución histórica de la política energética argentina.

## 🛠️ Arquitectura del Proyecto

El proyecto está estructurado en tres grandes etapas cronológicas y metodológicas:

### 1. Scraping y Curación de Datos (`/01_scraping_y_etiquetado`)
Contiene los scripts de extracción automatizada desde la base de datos gubernamental InfoLEG.
* Extracción del índice general histórico.
* Scraping de fichas técnicas, metadatos y resúmenes normativos.
* Extracción y limpieza (a formato Markdown) de textos completos de leyes, decretos y resoluciones.
* Herramientas para *Active Learning*, muestreo aleatorio y cálculo del Índice Kappa de Cohen para concordancia de etiquetadores humanos.

### 2. Modelado NLP y Machine Learning (`/02_modelo_nlp`)
Contiene la configuración de los modelos fundacionales (Transformers/BERT) utilizados para la clasificación masiva.
* *Fine-tuning* de un modelo pre-entrenado de HuggingFace utilizando PyTorch.
* Scripts de inferencia a escala para clasificar automáticamente más de 100.000 normativas no etiquetadas, separando las que corresponden a "Política Energética".

### 3. Análisis Sociológico y Resultados (`/03_analisis_y_resultados`)
Contiene la explotación de los datos (Minería de Texto, TF-IDF, Topic Modeling).
* Aplicación automatizada de la taxonomía internacional de energías renovables y fósiles (IRENA 2024).
* Detección de cambios de paradigma histórico (Estatización vs Privatización).
* Identificación automatizada del "Espíritu Normativo" (Multas, Desregulación, Fijación Tarifaria) cruzado por períodos presidenciales.

## 📄 Documentación Extendida

Para una explicación detallada de las decisiones metodológicas, justificación de librerías (Selenium, BeautifulSoup, Scikit-Learn, PyTorch) y el flujo de la base de datos PostgreSQL, referirse a `docs/ARQUITECTURA_Y_METODOLOGIA.md`.

## ⚙️ Requisitos y Tecnologías
* Python 3.10+
* Base de Datos: PostgreSQL
* Librerías Core: `pandas`, `sqlalchemy`, `selenium`, `beautifulsoup4`, `transformers`, `torch`, `scikit-learn`.

---
*Repositorio generado para la reproducibilidad metodológica de la investigación académica.*
