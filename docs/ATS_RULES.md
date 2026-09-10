# Reglas del validador ATS

> Archivo generado con `uv run cv-ats rules --md` a partir del registro (`validator/rules/*`). No editar a mano.

## Cómo se calcula el puntaje

- Cada regla se ejecuta solo en los destinos con severidad (`–` = no corre en ese destino).
- Una regla con hallazgos descuenta su peso **una sola vez** por reporte: error = peso, warning = peso / 2, info = 0. Puntaje = 100 - descuentos, redondeado hacia abajo, mínimo 0.
- Fase `pre`: corre siempre (datos del CV, perfil, HTML y páginas si se conocen). Fase `post`: solo con el PDF generado (`PdfInfo`).
- Destino `ats`: la exportación se bloquea con al menos un error. `mail` nunca bloquea.

Total: 38 reglas.

## Contacto

| id | Sección | ats | mail | Peso | Fase | Descripción |
|---|---|---|---|---|---|---|
| `contact.email_present` | basics | error | error | 15 | pre | Email obligatorio y válido. |
| `contact.linkedin_present` | links | warning | info | 3 | pre | Perfil de LinkedIn recomendado. |
| `contact.location_present` | basics | warning | info | 3 | pre | Ciudad y país presentes. |
| `contact.phone_present` | basics | error | warning | 10 | pre | Teléfono presente en formato internacional E.164 (+57...). |
| `contact.url_plain` | links | error | – | 5 | pre | Las URLs deben ser texto visible (no solo un hipervínculo «aquí»). Se verifica en el HTML. |

## Estructura

| id | Sección | ats | mail | Peso | Fase | Descripción |
|---|---|---|---|---|---|---|
| `structure.canonical_headings` | profile | error | – | 8 | pre | Los títulos personalizados deben ser nombres canónicos (lista blanca es/en). |
| `structure.no_photo` | profile | error | – | 10 | pre | Sin foto ni imágenes en ATS (`include_photo` debe ser falso). |
| `structure.no_tables` | profile | error | – | 15 | pre | Sin `<table>` en el HTML final. |
| `structure.required_sections` | profile | error | warning | 10 | pre | Experiencia y educación visibles y con al menos un ítem. |
| `structure.section_order` | profile | warning | – | 5 | pre | Orden recomendado: resumen → experiencia → educación → habilidades. |
| `structure.single_column` | profile | error | – | 15 | pre | Una sola columna: el HTML final no usa grid, columnas CSS, float ni posición absoluta. |

## Contenido

| id | Sección | ats | mail | Peso | Fase | Descripción |
|---|---|---|---|---|---|---|
| `content.achievement_length` | achievement | warning | warning | 2 | pre | Logros de 40 a 220 caracteres (1–2 líneas). |
| `content.action_verb` | achievement | warning | warning | 3 | pre | Cada logro empieza con un verbo de acción (`validator/data/verbs_{lang}.txt`). |
| `content.duplicate_skill` | skills | warning | warning | 2 | pre | La misma habilidad en dos categorías. |
| `content.keywords_from_experience` | skills | info | info | 2 | pre | Tecnologías usadas en experiencias que no aparecen en habilidades. |
| `content.max_achievements` | experience | info | info | 1 | pre | Máximo 6 logros por experiencia. |
| `content.metric` | achievement | warning | info | 3 | pre | Al menos 40% de los logros con número, porcentaje, moneda o `metric_value`. |
| `content.min_achievements` | experience | warning | warning | 5 | pre | Al menos 2 logros por experiencia (1 si duró menos de 6 meses). |
| `content.no_pronouns` | achievement | info | – | 1 | pre | Evitar pronombres («yo», «nosotros») en los logros. |
| `content.skills_no_levels_ats` | skills | warning | – | 2 | pre | Sin barras ni porcentajes: los niveles se ocultan en ATS; no los escribas en el nombre. |
| `content.skills_present` | skills | error | warning | 8 | pre | Al menos 5 habilidades visibles. |
| `content.summary_first_person` | summary | warning | info | 2 | pre | Evitar pronombres en primera persona («yo», «mi») en el resumen. |
| `content.summary_length` | summary | warning | warning | 4 | pre | Resumen profesional de 200 a 600 caracteres. |

## Fechas

| id | Sección | ats | mail | Peso | Fase | Descripción |
|---|---|---|---|---|---|---|
| `dates.chronological` | experience | warning | info | 3 | pre | Experiencias en orden cronológico inverso (la más reciente primero). |
| `dates.end_before_start` | all | error | error | 5 | pre | Fecha de fin anterior a la de inicio (incluye vencimiento antes de expedición). |
| `dates.format_consistent` | all | error | warning | 6 | pre | Un solo formato de fecha: el del perfil. Detecta fechas escritas a mano en otro formato. |
| `dates.future` | all | error | error | 5 | pre | Fechas futuras (excepto vencimiento de certificaciones y grado esperado en curso). |
| `dates.gap` | experience | info | – | 1 | pre | Huecos de más de 6 meses entre experiencias (solo informa). |
| `dates.overlap_current` | experience | warning | warning | 2 | pre | Más de una experiencia marcada como actual. |

## Extensión

| id | Sección | ats | mail | Peso | Fase | Descripción |
|---|---|---|---|---|---|---|
| `length.min_content` | doc | warning | warning | 4 | pre | Contenido menor al 60% de una página: hoja de vida muy corta. |
| `length.pages` | doc | error | warning | 10 | pre | Número de páginas ≤ `max_pages` del perfil (tras renderizar). |

## Técnicas (PDF generado)

| id | Sección | ats | mail | Peso | Fase | Descripción |
|---|---|---|---|---|---|---|
| `technical.filename` | export | warning | warning | 1 | post | Nombre de archivo `Nombre_Apellido_CV...` sin espacios ni tildes. |
| `technical.fonts_embedded` | pdf | error | info | 5 | post | Todas las fuentes embebidas en el PDF. |
| `technical.metadata` | pdf | info | info | 1 | post | Título y autor del PDF con el nombre de la persona. |
| `technical.no_special_chars` | pdf | warning | – | 3 | post | Sin caracteres fuera de Latin-1 + símbolos comunes (•, –, —, ·). |
| `technical.text_extractable` | pdf | error | warning | 20 | post | Round-trip: ≥ 95% de los tokens del CV en el texto extraído; email y teléfono presentes. |

## Foto

| id | Sección | ats | mail | Peso | Fase | Descripción |
|---|---|---|---|---|---|---|
| `photo.present_mail` | basics | – | info | 1 | pre | Destino Correo sin foto: sugerir agregarla. |
| `photo.warning_region` | basics | – | warning | 2 | pre | Foto en un país donde no es habitual (fuera de LatAm, ES, DE, FR). |
