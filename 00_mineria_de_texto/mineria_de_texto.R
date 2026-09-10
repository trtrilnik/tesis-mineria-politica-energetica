setwd("D:/Documentos/1FCEYS/tesis/text_mining/R/etapa_1-mineria")

rm(list=ls())

# Instalación de paquetes
{if(!requireNamespace("pdftools", quietly = TRUE)) install.packages("pdftools")
if(!requireNamespace("stringr", quietly = TRUE)) install.packages("stringr")
if(!requireNamespace("stopwords", quietly = TRUE)) install.packages("stopwords")
if(!requireNamespace("readr", quietly = TRUE)) install.packages("readr")
if(!requireNamespace("ggplot2", quietly = TRUE)) install.packages("ggplot2")
if(!requireNamespace("forcats", quietly = TRUE)) install.packages("forcats")
if(!requireNamespace("wordcloud2", quietly = TRUE)) install.packages("wordcloud2")
if(!requireNamespace("igraph", quietly = TRUE)) install.packages("igraph")
if(!requireNamespace("tidyverse", quietly = TRUE)) install.packages("tidyverse")
if(!requireNamespace("ggpubr", quietly = TRUE)) install.packages("ggpubr")
if(!requireNamespace("Matrix", quietly = TRUE)) install.packages("Matrix")
if(!requireNamespace("slam", quietly = TRUE)) install.packages("slam")
if(!requireNamespace("bench", quietly = TRUE)) install.packages("bench")
if(!requireNamespace("tm", quietly = TRUE)) install.packages("tm")
if(!requireNamespace("udpipe", quietly = TRUE)) install.packages("udpipe")
if(!requireNamespace("tidytext", quietly = TRUE)) install.packages("tidytext")
if(!requireNamespace("text2vec", quietly = TRUE)) install.packages("text2vec")
if(!requireNamespace("topicmodels", quietly = TRUE)) install.packages("topicmodels")
if(!requireNamespace("ggrepel", quietly = TRUE)) install.packages("ggrepel")
if(!requireNamespace("dplyr", quietly = TRUE)) install.packages("dplyr")
if(!requireNamespace("word2vec", quietly = TRUE)) install.packages("word2vec")
}

{library(ggrepel)
  library(text2vec)
  library(topicmodels)
  library(udpipe)
  library(tm)
  library(dplyr)
  library(wordcloud2)
  library(ggplot2)
  library(forcats)
  library(pdftools)
  library(stringr)
  library(tidytext)
  library(stopwords)
  library(readr)
  library(tidyverse)
  library(igraph)
  library(ggraph)
  library(SnowballC)
  library(ggpubr)
  library(Matrix)
  library(slam)
  library(bench)
  library(pdftools)
  library(udpipe)
  library(word2vec)
  }



# 1.
# Selección del directorio con la carpeta que están todos los pdfs a analizar

directorio_pdfs <- "textos_input"

# Obtener una lista de los PDFs en el directorio
todoslos_pdf <- list.files(
  path = directorio_pdfs,
  pattern = "\\.pdf$",
  full.names = TRUE,
  ignore.case = TRUE
)
todoslos_pdf # Control 

# 2.
# Función global que permite leer cada uno de los pdfs dispoonibles en la carpeta sin unificarlos

leer_todoslospdf <- function(path_pdf) {
  paste(pdf_text(path_pdf), collapse = " ")
}

rm(limpiar_texto)  #opcional para asegurar que no queda grabado en la memoria ninguna función similar para limpiar textos

# ====================================================
# 3. LIMPIEZA ESTRUCTURAL (preserva texto para udpipe)
# ====================================================

limpiar_estructura <- function(txt) {
  
  # Unión de palabras partidas por guión al final de línea
  txt <- str_replace_all(txt, "[\u00AD\u2010-\u2015]", "-")
  txt <- str_replace_all(txt, "([[:alpha:]])-\\s+([[:alpha:]])", "\\1\\2")
  
  # Saltos de línea → espacio
  txt <- gsub("\n", " ", txt, fixed = TRUE)
  
  # URLs
  txt <- gsub("https?://\\S+|www\\.[^\\s]+", " ", txt)
  
  # Bloques LaTeX/markdown
  txt <- gsub("\\$[^$]+\\$", " ", txt)
  txt <- gsub("\\\\\\(.*?\\\\\\)", " ", txt)
  txt <- gsub("\\\\\\[.*?\\\\\\]", " ", txt)
  
  # Emojis / emoticones
  txt <- gsub("[\\p{So}\\p{Cn}]+", " ", txt, perl = TRUE)
  txt <- gsub("[:;=8][-~]?[\\)D\\]\\[pPoO3]", " ", txt)
  
  # Números aislados y operadores matemáticos
  txt <- gsub("\\b\\d+\\b", " ", txt)
  txt <- gsub("(=|\\+|\\*|/|<|>|%|\\^|\\-)+", " ", txt, perl = TRUE)
  
  # Encabezados y pies de página repetitivos
  # (deben escribirse con tildes y mayúsculas tal como aparecen en los PDFs)
  txt <- gsub("Política energética argentina: un balance del periodo 2003-2015", " ", txt)
  txt <- gsub("Los efectos estructurales de la política energética en la economía argentina", " ", txt)
  txt <- gsub("Abordando la transición energética en Argentina: un análisis de la sostenibilidad ambiental", " ", txt)
  txt <- gsub("Politics in the Age of Transboundary Crises", " ", txt)
  txt <- gsub("Regulación energética y consumo industrial en Argentina", " ", txt)
  txt <- gsub("Jornadas ITE - Facultad de Ingeniería - UNLP", " ", txt, ignore.case = TRUE)
  txt <- gsub("Revista de Economía Institucional.*?semestre.*?pp", " ", txt, ignore.case = TRUE)
  txt <- gsub("FACES.*?ISSN[^\\n]*", " ", txt, ignore.case = TRUE)
  txt <- gsub("Fecha de recepción[^\\n]*", " ", txt, ignore.case = TRUE)
  txt <- gsub("Fecha de aceptación[^\\n]*", " ", txt, ignore.case = TRUE)
  txt <- gsub("Avances en Energías Renovables y Medio Ambiente.*?ASADES", " ", txt, ignore.case = TRUE)
  txt <- gsub("Revista Administración Pública y Sociedad.*?ISSN[^\\n]*", " ", txt, ignore.case = TRUE)
  txt <- gsub("Modelo de publicación sin fines de lucro.*?JATS-R", " ", txt, ignore.case = TRUE)
  
  # Espacios múltiples
  txt <- gsub("\\s+", " ", txt)
  trimws(txt)
}

# ====================================================
# 4. LECTURA Y LIMPIEZA ESTRUCTURAL
# ====================================================

docs_sinunir      <- lapply(todoslos_pdf, leer_todoslospdf)
docs_estructurados <- lapply(docs_sinunir, limpiar_estructura)

# Corpus para udpipe: con tildes y mayúsculas, sin ruido estructural
corpus_para_udpipe <- paste(unlist(docs_estructurados), collapse = " ")
writeLines(corpus_para_udpipe, "corpus_para_udpipe.txt", useBytes = TRUE)

# ====================================================
# 5. STOPWORDS Y NOMBRES PROPIOS
# ====================================================

stop_extra <- c(
  "able", "abstract", "abril", "acoplando", "acto", "acusa", "adelante",
  "agentes", "agosto", "ahi", "aires", "al", "alc", "alcanzar", "algo",
  "algun", "alguna", "algunas", "alguno", "algunos", "alto", "ambiciosos",
  "and", "anexo", "ante", "anterior", "antes", "antioquia", "anual",
  "año", "años", "aquel", "aquellas", "aquellos", "aqui", "archivo",
  "archivese", "ario", "articulo", "asi", "aun", "aunque", "author",
  "autor", "autora", "autores", "avance", "avances",
  "balance", "bariloche", "base", "bdte", "beneficios", "best",
  "bibliografia", "bien", "bienes", "boiteux", "boletin", "bolivia",
  "brasil", "brazil", "buen", "buenos", "buratovich", "busqueda",
  "cacion", "cada", "capitulo", "carga", "caso", "casos", "catalunya",
  "ceb", "cepal", "chile", "cien", "ciente", "cientifica",
  "ciento", "cit", "cita", "citada", "citado", "civil",
  "clase", "clave", "cliente", "cnd", "cobertura", "coe", "cols",
  "como", "comodoro", "committee", "comuniquese", "conclusi",
  "conclusion", "confianza", "conservar", "construido", "construir",
  "content", "contrario", "cooperativas", "corresponde",
  "correspondiente", "corte", "cosa", "cosas", "covid", "cuales",
  "cualquier", "cuando", "cuanto", "cuatro", "cuenta", "cutral", "cts",
  "cuadro", "cuyo",
  "dado", "dar", "dato", "datos", "deber","deda", "definir", "dejar", "demas",
  "der", "derogada", "desde", "despues", "destacar", "developing", "dia",
  "dias", "dicha", "dicho", "diciembre", "diferencia", "diferentes",
  "dificil", "digital", "digithum", "direccion", "directa", "diseño",
  "distintas", "distintos", "diversas",
  "diversos", "docente", "documento", "doi", "dolares", "donde", "dos",
  "durante",
  "e", "ed", "edi", "educacion", "edf", "efm", "efr", "eje", "ejecutivo",
  "ejemplo", "elaboracion", "ello", "embargo", "emissions", "emotions",
  "en", "enero", "enseñanza", "entonces", "entre", "era", "es",
  "escribano", "esfuerzo", "espacio", "especial", "especi", "espera",
  "esta", "estaban", "estan", "estas", "este", "estimacion", "et",
  "etapa", "europa", "evaluacion", "evidentemente", "evitar", "ex",
  "existe", "existencia", "existen",
  "faces", "factible", "falta", "fceys", "fcs", "febrero", "figura",
  "fin", "final", "finales", "fines", "firma", "flexible",
  "fnre", "foreign", "fpv", "from", "fuoc",
  "gcp", "gei", "generation",  "grafico", "gratuito",
  "greenpeace", "grupos", "gura",
  "ha", "haber", "hace", "hacen", "hacer", "han", "hasta", "hay",
  "heat", "hecho", "hogares", "hora", "hoy", "hubo",
  "iapg", "ibidem", "idem", "identi", "iesct", "iifap", "imagen",
  "imaginario", "imaginarios", "impuesto", "impuestos", "incertidumbre",
  "inciso", "incremento", "indice", "items", "izq",
  "jats", "judicial", "julio", "junio",
  "km", "la", "lado", "largo", "las", "le", "lewis", "libre", "litio",
  "llevar", "llo", "lo", "london", "los", "lucro", "luego", "lugar",
  "lund", "lundqvist", "lll",
  "manuela", "maquinaria", "margen", "marginal", "market", "marzo",
  "mas", "materia", "materiales", "maximo", "mayo", "mayoritariamente",
  "mbtu", "mediante", "medios", "mejor", "mejora", "mejorar", "menor",
  "menores", "mes", "meses", "metodologia", "metros", "mil", "miles",
  "milia", "millones", "minem", "misma", "mismas", "mismo", "mismos",
  "mmm", "modo", "momento", "moneda", "movilidad", "muchas", "muchos",
  "municipal", "muy",
  "nacion", "nen", "nes", "nicion", "ningun", "norte", "nota",
  "noviembre", "num", "numero", "nunca",
  "o", "oberta", "observaciones", "obstante", "obtencion", "octubre",
  "oficial", "org",
  "pags", "para", "parecer", "parque", "paso", "patron", "pbi", "pdf",
  "per", "pequeñas", "periodicidad", "pero", "pesar", "pese", "pib",
  "pist", "poca", "poco", "poder","podia", "podria", "podrian", "por",
  "porcentaje", "porque", "posdesarrollo", "post", "power", "practicas",
  "press", "previo", "primer", "primera", "primero",
  "prioridad", "profundacer", "promedio", "promulga", "propia",
  "propicio", "propio", "provenientes", "puesto", "punto",
  "que", "queda", "quien", "quienes", "quieren",
  "racional", "rda", "real", "reciente", "reglamento", "reporte", "republica", "requisitos", "respuesta",
  "rev", "revista", "rivadavia", "rmar", "rubro",
  "sanciona", "scpl", "scienti", "scientific", "se", "seccion",
  "segun", "segunda", "segundo", "seis", "sellos", "sentido",
  "septiembre", "ser","sera", "seria", "serie", "sfv", "si", "sido",
  "siempre", "siendo", "significativo", "siguiente", "siguientes",
  "silva", "simenr", "similares", "sin", "sino", "solo", "son", "spot",
  "spivak", "su", "subsecretaria", "suerte", "suma", "super", "superior",
  "supuesto", "sur", "sus",
  "tabla", "tal", "tambien", "tanto", "tasa", "tco", "tecnocienti", "tener",
  "tes", "textos", "tgs", "the", "thermal", "tierra", "titulo", "toda",
  "todas", "todo", "todos", "toma", "tomar", "toneladas", "too",
  "total", "trade", "traduccion", "transmission", "trave", "traves",
  "tres", "one", "ite", "investigadores", "investigador", "indicador", "usd", "issn",
  "ubicado", "ultimo", "ultimos", "un", "una", "unc", "unidas", "unidos",
  "unidad", "unidades", "universidad", "universitat", "university",
  "unlp", "unmdp", "unq", "unruh", "uno", "unos", "uoc", "urbano",
  "url", "usa", "usgs", "util", "utilizacion",
  "variacion", "varios", "vease", "vecinos", "velocidad", "venta", "ver",
  "vez", "via", "vigencia", "vinculados", "vision", "visto", "vital",
  "vivienda", "vol", "volumen", "vuelto",
  "wind", "wiser", "xml",
  "y", "ya", "zhang", "zona", "zonas","ctyp", "cyt", "eer", "ene", "gdenc", "geis", "genren", "rtm", "vie",
  "wti", "hualong",
  "acer", "ben", "cion", "gentina", "tep",
  "cluster", "compilado", "cuaderno", "jornadas", "jornado", "monitor",
  "pagina", "recuperado", "tempo", "universitaria",
  "celda", "tematico", "verificar",
  "caribe", "china", "colombia", "kioto",
  "brutos", "mencion", "relevo", "abonar"
)

stop_en <- stopwords("en")
stop_es <- unique(c(stopwords("es"), stop_extra, stop_en))
# Las stopwords se normalizan DESPUÉS de la lematización,
# por lo que aquí se mantienen con tildes para mayor cobertura
stop_es_norm <- tolower(chartr("áéíóúÁÉÍÓÚ", "aeiouAEIOU", stop_es))

nombres_propios <- c(
  "a", "aarhus", "abadie", "abascal", "aguado", "aichele", "alexander", "alicia", "amba",
  "ana", "andersen", "arias", "barcena", "barrera", "bianchetti", "blanco", "bora","bouille",
  "bravo", "bruno", "buitrago", "buratovich", "burg","cacioppo", "camarda", "canada", "cantarero",
  "carina", "carlos", "caruana", "castelao", "catelen", "ceppi", "claromeco","clementi","crespi", "cristiano",
  "cristina", "daniel", "darwin", "david", "davidson", "del", "deloitte", "diaz", "dr",
  "duhalde", "ejecutiva", "ekman", "enrique", "esteban", "eugenia", "felbermayr", "feng","fernandez",
  "ferrer", "florencia", "florini", "fodis","fornillo", "freier", "gabriela", "galindo", "gardner",
  "garrido", "goliat", "graaf", "grubler", "gudynas", "guerrero", "guzowski", "hernandez", "hessling","hoste",
  "hubert", "ibarra", "indec", "james", "japon", "jasanoff", "jenkins", "jemse","jimenez", "katz",
  "kazimierski", "kim", "kirchner","kirchnerismo", "kozulj", "lacaze", "lambert", "laura", "leandro",
  "levenson", "lia", "lopez", "luca", "maria", "mariano", "marin", "marina",
  "matthieu", "mauricio","menem", "mercosur", "moralejo", "natalia", "navarro", "nestor", "oatley",
  "pendon", "pereira","pilar", "pistonesi", "porcelli", "recalde", "repsol", "rioja","roberto", "rocha",
  "rosemberg", "rosetti", "rossetti", "samaniego", "sanchez", "santos","santiago", "saul", "secretaria",
  "serrani", "shen", "simensen", "singh", "spivak", "vaca", "valle", "vanegas",
  "verre", "victoria", "vogel", "william", "yesica", "ypfb", "zabaloy", "alberta", "alberto", "adriano", "ada", "emilce", "ethel", "franco",
  "graciel", "herrera", "nogar", "ottavianelli", "casola", "furlan",
  "sabbatella"
)
nombres_propios_norm <- tolower(chartr("áéíóú", "aeiou", nombres_propios))

# ====================================================
# 6. TOKENIZACIÓN Y LEMATIZACIÓN (por documento)
# ====================================================

model_file  <- udpipe_download_model(language = "spanish")
ud_model_es <- udpipe_load_model(model_file$file_model)

# Anotar cada documento por separado, conservando el nombre del PDF
x_df_lista <- mapply(
  function(texto, nombre) {
    anotado <- udpipe_annotate(ud_model_es, x = texto, doc_id = nombre)
    as.data.frame(anotado)
  },
  texto  = docs_estructurados,
  nombre = basename(todoslos_pdf),
  SIMPLIFY = FALSE
)

# Identificar documentos vacíos
doc_nrows <- sapply(x_df_lista, nrow)
names(doc_nrows) <- basename(todoslos_pdf)
doc_nrows[doc_nrows == 0]

x_df <- do.call(rbind, x_df_lista)

write.csv(x_df, "x_df_anotado.csv", row.names = FALSE)
cat("x_df guardado.\n")
# ====================================================
# 7. LIMPIEZA POST-LEMATIZACIÓN
# ====================================================

# x_df tiene una columna doc_id con el nombre del PDF
x_df$lemma_limpio <- tolower(x_df$lemma)
x_df$lemma_limpio <- chartr("áéíóú", "aeiou", x_df$lemma_limpio)

x_df_filtrado <- x_df %>%
  filter(!is.na(lemma_limpio)) %>%
  filter(grepl("^[a-zñ]+$", lemma_limpio)) %>%
  filter(nchar(lemma_limpio) > 2) %>%
  filter(!(lemma_limpio %in% stop_es_norm)) %>%
  filter(!(lemma_limpio %in% nombres_propios_norm))

# ====================================================
# 8. GUARDADO
# ====================================================

# Corpus global (para embeddings)
tokens2      <- x_df_filtrado$lemma_limpio
corpus_final <- paste(tokens2, collapse = " ")
writeLines(corpus_final, "corpus_final_sin_stopwords.txt", useBytes = TRUE)

freq3pdf  <- sort(table(tokens2), decreasing = TRUE)
freq_3pdf <- data.frame(palabra = names(freq3pdf), n = as.integer(freq3pdf), row.names = NULL)
write.csv(freq_3pdf, "frecuencias_tokens_3pdf.csv", row.names = FALSE)
freq_3pdf
# Corpus por documento (para poder realizar TF-IDF)
# x_df_filtrado conserva doc_id y se usa directamente en el bloque TF-IDF

# ====================================================
# 9. Nube de palabras para frecuencias absolutas
# ====================================================

{# Formato correcto: columna 'word' y 'freq' y por tokens

wc_data <- freq_3pdf
colnames(wc_data) <- c("word", "freq")
wc_data <- wc_data[wc_data$freq > 50, ] # Solo muestra palabras que se repitan 50 veces o más


# Grafico de nube de palabras

set.seed(5424)
wordcloud2(
  data = wc_data,
  size = 1.2,                # tamaño global
  color = "random-dark",     # colores aleatorios oscuros
  backgroundColor = "white", # fondo blanco
  shape = "circle"           # otras formas: "star", "diamond", "pentagon", "cardioid"
)
}

# ====================================================
# 10. Cálculo y gráfico de TF–IDF
# ====================================================

# x_df_filtrado ya tiene doc_id y lemma_limpio: no se re-tokeniza
frecuencias_TF <- x_df_filtrado %>%
  count(doc_id, lemma_limpio, sort = TRUE) %>%
  rename(documento = doc_id, palabra = lemma_limpio)

tfidf_TF <- frecuencias_TF %>%
  bind_tf_idf(term = palabra, document = documento, n = n) %>%
  arrange(desc(tf_idf))

write.csv(tfidf_TF, "TFIDF_tokens_por_documento.csv", row.names = FALSE)

# ====================================================
# 11. Gráfico de palabras más distintivas por documento (TF–IDF)
# ====================================================

{top_tfidf <- tfidf_TF %>%
  group_by(documento) %>%
  slice_max(tf_idf, n = 10) %>%
  ungroup() %>%
  mutate(palabra = reorder_within(palabra, tf_idf, documento))

ggplot(top_tfidf, aes(x = palabra, y = tf_idf, fill = documento)) +
  geom_col(show.legend = FALSE) +
  facet_wrap(~ documento, scales = "free_y") +
  coord_flip() +
  scale_x_reordered() +
  labs(
    title = "Palabras más distintivas por documento (TF–IDF)",
    subtitle = "TF–IDF identifica los términos relevantes y específicos en cada PDF",
    x = "Término",
    y = "Peso TF–IDF"
  ) +
  theme_minimal(base_size = 13)
}

# ====================================================
# 12. BOW Y BIGRAMAS
# ====================================================

# 12.1. Frecuencias desde x_df_filtrado (ya lematizado y limpio)
# No se re-tokeniza: se usa directamente la columna lemma_limpio

bow_frecuencias <- x_df_filtrado %>%
  count(lemma_limpio, sort = TRUE) %>%
  rename(palabra = lemma_limpio)

write_csv(bow_frecuencias, "bow_frecuencias.csv")
print(head(bow_frecuencias, 20))

# 12.2. Bigramas desde tokens ANTES de filtrar stopwords
# Se usa x_df con todos los tokens para preservar consecutividad real

bigramas_df <- x_df %>%
  mutate(
    lemma_limpio = tolower(lemma),
    lemma_limpio = chartr("áéíóú", "aeiou", lemma_limpio),
    token_id_int = suppressWarnings(as.integer(token_id)),
    sentence_id  = as.integer(sentence_id)
  ) %>%
  filter(!is.na(token_id_int)) %>%       # excluir tokens multipalabra
  filter(!is.na(lemma_limpio)) %>%
  filter(grepl("^[a-zñ]+$", lemma_limpio)) %>%
  arrange(doc_id, sentence_id, token_id_int) %>%
  mutate(
    palabra_siguiente = lead(lemma_limpio),
    doc_siguiente     = lead(doc_id),
    sent_siguiente    = lead(sentence_id),
    token_siguiente   = lead(token_id_int)
  ) %>%
  filter(!is.na(palabra_siguiente)) %>%
  filter(doc_id       == doc_siguiente) %>%
  filter(sentence_id  == sent_siguiente) %>%
  filter(token_id_int + 1 == token_siguiente) %>%
  filter(!(lemma_limpio      %in% stop_es_norm)) %>%
  filter(!(palabra_siguiente %in% stop_es_norm)) %>%
  filter(!(lemma_limpio      %in% nombres_propios_norm)) %>%
  filter(!(palabra_siguiente %in% nombres_propios_norm)) %>%
  filter(nchar(lemma_limpio) > 2) %>%
  filter(nchar(palabra_siguiente) > 2) %>%
  transmute(bigrama = paste(lemma_limpio, palabra_siguiente, sep = " "))

bigramas_frecuencias <- bigramas_df %>%
  count(bigrama, sort = TRUE)

write_csv(bigramas_frecuencias, "bigramas_frecuencias.csv")

head(bigramas_frecuencias, 20)

# 12.3. Gráficos
top_bow     <- bow_frecuencias    %>% slice_max(n, n = 15)
top_bigrams <- bigramas_frecuencias %>% slice_max(n, n = 15)

ggplot(top_bow, aes(x = fct_reorder(palabra, n), y = n)) +
  geom_col(fill = "#1f78b4") +
  coord_flip() +
  labs(title    = "Palabras más frecuentes en 'Política energética'",
       subtitle = "Bolsa de Palabras (Bag of Words)",
       x = "Palabra", y = "Frecuencia") +
  theme_minimal(base_size = 14)

ggplot(top_bigrams, aes(x = fct_reorder(bigrama, n), y = n)) +
  geom_col(fill = "#ff7f00") +
  coord_flip() +
  labs(title    = "Bigramas más frecuentes en 'Política energética'",
       subtitle = "Secuencias de dos palabras consecutivas",
       x = "Bigrama", y = "Frecuencia") +
  theme_minimal(base_size = 14)

# 12.4. Nubes de palabras
wc_palabras <- bow_frecuencias %>%
  arrange(desc(n)) %>%
  slice_head(n = 100) %>%
  select(word = palabra, freq = n)

wordcloud2(data = wc_palabras, size = 1.2,
           color = "random-light", backgroundColor = "black", shape = "star")

wc_bigramas <- bigramas_frecuencias %>%
  arrange(desc(n)) %>%
  slice_head(n = 100) %>%
  select(word = bigrama, freq = n)

wordcloud2(data = wc_bigramas, size = 1.2,
           color = "random-light", backgroundColor = "black", shape = "star")

# ====================================================
# 13. WORD EMBEDDINGS — Word2Vec
# ====================================================

set.seed(123)
modelo_w2v <- word2vec(
  x         = "corpus_final_sin_stopwords.txt",
  type      = "skip-gram",
  dim       = 50,
  window    = 5L,
  iter      = 100L,
  min_count = 3L,
  threads   = 1L
)

write.word2vec(modelo_w2v, "modelo_word2vec.bin")
cat("Modelo Word2Vec guardado.\n")

word_vectors_w2v <- as.matrix(modelo_w2v)

# Filtrar al vocabulario de alta frecuencia (min=15), independiente de GloVe
vocab_frecuente  <- freq_3pdf$palabra[freq_3pdf$n >= 15]
palabras_validas <- intersect(rownames(word_vectors_w2v), vocab_frecuente)
word_vectors_w2v_f <- word_vectors_w2v[palabras_validas, ]

cat("Vocabulario Word2Vec original:", nrow(word_vectors_w2v), "términos\n")
cat("Vocabulario Word2Vec filtrado:", nrow(word_vectors_w2v_f), "términos\n")

# Similitudes semánticas sobre vocabulario filtrado
sim_w2v_energia <- predict(modelo_w2v, newdata = "energia",
                           type = "nearest", top_n = 15)
sim_w2v_energia$energia <- sim_w2v_energia$energia[
  sim_w2v_energia$energia$term2 %in% palabras_validas, ]
print(sim_w2v_energia)

sim_w2v_politica <- predict(modelo_w2v, newdata = "politica",
                            type = "nearest", top_n = 15)
sim_w2v_politica$politica <- sim_w2v_politica$politica[
  sim_w2v_politica$politica$term2 %in% palabras_validas, ]
print(sim_w2v_politica)

# K-means sobre vocabulario filtrado
set.seed(123)
cl <- kmeans(word_vectors_w2v_f, centers = 5, iter.max = 100)
table(cl$cluster)

dist_to_center <- function(cluster_id) {
  mat       <- word_vectors_w2v_f[cl$cluster == cluster_id, ]
  centroide <- colMeans(mat)
  distancias <- sim2(
    x      = mat,
    y      = matrix(centroide, ncol = ncol(mat)),
    method = "cosine",
    norm   = "l2"
  )
  orden <- sort(distancias[, 1], decreasing = TRUE)
  return(names(orden)[1:10])
}

for (i in 1:5) {
  cat("\n Cluster", i, "→ palabras más representativas:\n")
  print(dist_to_center(i))
}

# PCA y visualización Word2Vec
pca_w2v    <- prcomp(word_vectors_w2v_f)
df_pca_w2v <- as.data.frame(pca_w2v$x[, 1:2])
df_pca_w2v$cluster <- factor(cl$cluster)
df_pca_w2v$word    <- rownames(word_vectors_w2v_f)

set.seed(123)
df_pca_sample <- df_pca_w2v %>%
  group_by(cluster) %>%
  sample_n(15, replace = FALSE)

ggplot(df_pca_w2v, aes(PC1, PC2, color = cluster)) +
  geom_point(alpha = 0.4) +
  geom_text_repel(data = df_pca_sample, aes(label = word),
                  size = 3, max.overlaps = Inf) +
  labs(title    = "Mapa de Word2Vec genuino (skip-gram)",
       subtitle = "Vocabulario equivalente a GloVe (mín. 15 ocurrencias)") +
  theme_minimal()

# ====================================================
# WORD EMBEDDINGS — GloVe
# ====================================================

tokensG    <- word_tokenizer(corpus_final)
itG        <- itoken(tokensG, progressbar = FALSE)
vocabG     <- create_vocabulary(itG)
vocabG     <- prune_vocabulary(vocabG, term_count_min = 15)
vectorizerG <- vocab_vectorizer(vocabG)
tcmG       <- create_tcm(itG, vectorizerG, skip_grams_window = 5L)

glove_model       <- GlobalVectors$new(rank = 50, x_max = 10)
word_vectors_main <- glove_model$fit_transform(tcmG, n_iter = 20)
word_vectors_context <- glove_model$components
word_vectors      <- word_vectors_main + t(word_vectors_context)

saveRDS(word_vectors, "embeddings_glove_esp.rds")
cat("Embeddings GloVe guardados.\n")
cat("Vocabulario GloVe:", nrow(word_vectors), "términos\n")

# Verificar que ambos vocabularios coinciden
cat("Vocabularios coinciden:",
    identical(sort(palabras_validas), sort(rownames(word_vectors))), "\n")

# Similitudes GloVe
sim_glove_energia <- sim2(x = word_vectors,
                          y = word_vectors["energia", , drop = FALSE],
                          method = "cosine", norm = "l2")
cat("\nGloVe — similitudes a 'energia':\n")
print(head(sort(sim_glove_energia[, 1], decreasing = TRUE), 10))

sim_glove_politica <- sim2(x = word_vectors,
                           y = word_vectors["politica", , drop = FALSE],
                           method = "cosine", norm = "l2")
cat("\nGloVe — similitudes a 'politica':\n")
print(head(sort(sim_glove_politica[, 1], decreasing = TRUE), 10))

# K-means GloVe
set.seed(123)
clG <- kmeans(word_vectors, centers = 5)
table(clG$cluster)

for (i in 1:5) {
  cat("\n Cluster", i, "→ palabras más representativas:\n")
  print(head(rownames(word_vectors[clG$cluster == i, ]), 10))
}

# PCA y visualización GloVe
pcaG        <- prcomp(word_vectors)
df_pcaG     <- as.data.frame(pcaG$x[, 1:2])
df_pcaG$word    <- rownames(word_vectors)
df_pcaG$cluster <- factor(clG$cluster)

set.seed(123)
df_sample <- df_pcaG %>%
  group_by(cluster) %>%
  sample_n(size = min(15, n()), replace = FALSE)

ggplot(df_pcaG, aes(PC1, PC2, color = cluster)) +
  geom_point(alpha = 0.4, size = 1.8) +
  geom_text_repel(data = df_sample, aes(label = word),
                  size = 3, max.overlaps = Inf) +
  labs(title    = "Mapa semántico (Word Embeddings con GloVe)",
       subtitle = "Corpus en español: agrupación semántica por proximidad",
       x = "Componente principal 1",
       y = "Componente principal 2") +
  theme_minimal() +
  theme(legend.position = "bottom")

saveRDS(word_vectors, "embeddings_glove_esp.rds")
write.csv(df_pcaG, "pca_glove_embeddings.csv", row.names = FALSE)

# ====================================================
# COMPARACIÓN SEMÁNTICA: Word2Vec vs GloVe
# Ambos modelos sobre el mismo vocabulario (palabras_validas)
# ====================================================

df_w2v          <- as.data.frame(pca_w2v$x[, 1:2])
df_w2v$word     <- rownames(word_vectors_w2v_f)
df_w2v$model    <- "Word2Vec"

pca_glove       <- prcomp(word_vectors[palabras_validas, ])
df_glove        <- as.data.frame(pca_glove$x[, 1:2])
df_glove$word   <- rownames(word_vectors[palabras_validas, ])
df_glove$model  <- "GloVe"

df_comparativo  <- rbind(df_w2v, df_glove)

set.seed(123)
palabras_muestra <- sample(palabras_validas, min(50, length(palabras_validas)))
df_sample        <- df_comparativo[df_comparativo$word %in% palabras_muestra, ]

# Gráfico lado a lado
ggplot(df_sample, aes(PC1, PC2, color = model)) +
  geom_point(size = 2, alpha = 0.6) +
  geom_text_repel(aes(label = word), size = 3, max.overlaps = Inf) +
  facet_wrap(~model) +
  labs(title    = "Comparación de espacios semánticos: Word2Vec vs GloVe",
       subtitle = "Cada punto representa una palabra en el espacio vectorial (reducido con PCA)",
       x = "Componente principal 1",
       y = "Componente principal 2",
       color = "Modelo") +
  theme_minimal(base_size = 13) +
  theme(legend.position = "bottom")

# Gráfico superpuesto
set.seed(123)
palabras_muestra2 <- sample(palabras_validas, min(40, length(palabras_validas)))
df_sample2        <- df_comparativo[df_comparativo$word %in% palabras_muestra2, ]

ggplot(df_sample2, aes(PC1, PC2, color = model)) +
  geom_point(alpha = 0.7, size = 2.2) +
  geom_text_repel(aes(label = word), size = 3, alpha = 0.8, max.overlaps = Inf) +
  labs(title    = "Comparación superpuesta: Word2Vec y GloVe",
       subtitle = "Ambos modelos en el mismo plano PCA — Corpus en español",
       x = "Componente principal 1",
       y = "Componente principal 2",
       color = "Modelo") +
  theme_minimal(base_size = 13) +
  theme(legend.position = "bottom")

write.csv(df_comparativo, "comparacion_word2vec_glove.csv", row.names = FALSE)


# Correr esto y compartir el output completo
# Word2Vec
cat("Vocabulario Word2Vec original:", nrow(word_vectors_w2v), "\n")
cat("Vocabulario Word2Vec filtrado:", nrow(word_vectors_w2v_f), "\n")
cat("Vocabulario GloVe:", nrow(word_vectors), "\n")

print(sim_w2v_energia)
print(sim_w2v_politica)

for (i in 1:5) {
  cat("\n Cluster W2V", i, ":\n")
  print(dist_to_center(i))
}

# GloVe
print(head(sort(sim_glove_energia[,1], decreasing = TRUE), 10))
print(head(sort(sim_glove_politica[,1], decreasing = TRUE), 10))

for (i in 1:5) {
  cat("\n Cluster GloVe", i, ":\n")
  print(head(rownames(word_vectors[clG$cluster == i,]), 10))
}

# ====================================================
#Validación términos de búsqueda para embeddings
# ====================================================

# Términos de búsqueda en formato normalizado (sin tildes, minúsculas)
# para que coincidan con el vocabulario de los embeddings
terminos_busqueda <- c(
  "energia", "hidrocarburo", "combustible", 
  "nuclear", "gas", "natural",
  "renovable", "electrico", "electrica",
  "eolico", "distribuido", "distribucion",
  "diversificacion"
)

cat("=== VALIDACIÓN Y EXPANSIÓN DE TÉRMINOS DE BÚSQUEDA ===\n")
cat("Modelo: GloVe —", nrow(word_vectors), "términos\n\n")

for (termino in terminos_busqueda) {
  if (termino %in% rownames(word_vectors)) {
    sim <- sim2(
      x      = word_vectors,
      y      = word_vectors[termino, , drop = FALSE],
      method = "cosine",
      norm   = "l2"
    )
    vecinos <- head(sort(sim[, 1], decreasing = TRUE), 15)
    # Excluir el propio término
    vecinos <- vecinos[names(vecinos) != termino]
    cat("Vecinos de '", termino, "':\n")
    print(round(vecinos, 3))
    cat("\n")
  } else {
    cat("'", termino, "' no está en el vocabulario GloVe\n\n")
  }
}

# También verificar con Word2Vec para comparación
cat("\n=== CONFIRMACIÓN Word2Vec ===\n\n")

for (termino in terminos_busqueda) {
  if (termino %in% rownames(word_vectors_w2v_f)) {
    sim_w2v <- predict(modelo_w2v,
                       newdata = termino,
                       type    = "nearest",
                       top_n   = 15)
    resultado <- sim_w2v[[termino]]
    resultado <- resultado[resultado$term2 %in% palabras_validas, ]
    cat("W2V — Vecinos de '", termino, "':\n")
    print(resultado[, c("term2", "similarity")])
    cat("\n")
  } else {
    cat("'", termino, "' no está en vocabulario W2V filtrado\n\n")
  }
}


# ====================================================
#Guardado para próximas sesiones
# ====================================================
save(
  word_vectors,
  word_vectors_w2v,
  word_vectors_w2v_f,
  modelo_w2v,
  palabras_validas,
  freq_3pdf,
  corpus_final,
  tfidf_TF,
  bigramas_frecuencias,
  bow_frecuencias,
  stop_es_norm,
  nombres_propios_norm,
  x_df_filtrado,
  file = "sesion_mineria_texto.RData"
)
cat("Sesión completa guardada.\n")

# ====================================================
#Carga para nueva sesión
# ====================================================

load("sesion_mineria_texto.RData")
modelo_w2v <- read.word2vec("modelo_word2vec.bin")
word_vectors <- readRDS("embeddings_glove_esp.rds")