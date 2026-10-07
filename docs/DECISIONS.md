# Decisiones fuera de la especificación

Registro de decisiones tomadas por el agente jefe (y aprobadas por él) que no están
cerradas en `CV_ATS_SPEC.md`. Formato: fecha — decisión — motivo.

## 2026-09-10 — Organización del trabajo

- **Raíz del repo = carpeta actual** (`modificar mi cv/`), no una subcarpeta `cv-ats/`.
  Motivo: la spec ya vive aquí; evita anidar un repo dentro de otro.
- **Sin remoto ni PRs por ahora.** La spec pide rama `feat/<id>` + PR por tarea. Al no haber
  remoto, el jefe revisa y hace commit (Conventional Commits) por fase/tarea en `main`.
  Los agentes de trabajo **no** hacen operaciones git. Cuando exista remoto se retoma el flujo de PRs.
- **Equipos con propiedad de carpetas disjunta** para trabajar en paralelo en el mismo árbol:
  - Backend: `pyproject.toml`, `uv.lock`, `alembic/`, `app/`, `models/`, `schemas/`, `services/`,
    `validator/`, `export/`, `importer/`, `match/`, `render/*.py`, `tests/`.
  - Diseño: `render/templates/`, `web/`, `static/`, `docs/design/`.
  - El contrato entre ambos es `docs/RENDER_CONTEXT.md` (solo lo cambia el jefe).

## 2026-09-10 — Stack

- `pydantic[email]` en lugar de `pydantic`: `EmailStr` exige `email-validator`.
- `pytest-cov` agregado al grupo dev: la spec exige cobertura mínima del 85%.
- `[tool.hatch.build.targets.wheel] packages = [...]`: el proyecto tiene varios paquetes
  top-level (`app`, `models`, …); hatchling no los detecta solo.
- El CSS de las plantillas de render se **inyecta inline** en `<style>` (vía `{% include %}` de Jinja),
  así el mismo HTML sirve para la preview en `<iframe>` (`srcdoc`) y para WeasyPrint sin rutas relativas.
- La foto se pasa al template como **data URI** (`basics.photo_src`), mismo motivo.
- Disco del proyecto es NTFS (`ntfs3`): se usa `UV_LINK_MODE=copy` si `uv` avisa de hardlinks entre sistemas de archivos.

## 2026-09-10 — Diseño

- **Sidebar multipágina del `mail`**: la sidebar es un ítem de CSS Grid (WeasyPrint 70 sí
  fragmenta grid entre páginas) y su fondo se pinta en `@page` con un `linear-gradient` de corte
  duro al 32% (márgenes laterales de página = 0). La franja continúa en la página 2+ aunque el
  contenido de la sidebar termine antes; si la sidebar se desborda (muchas skills) sigue en la
  página 2 en su columna. No se usa `position: running()` (en WeasyPrint solo sirve para cajas de
  margen). Consecuencia: no se puede poner fondo en `html`/`body` en impresión (taparía el degradado).
- **`mail` ignora `profile.font_family`**: el valor por defecto del perfil es `Arial` y anularía
  la tipografía de los temas. Las fuentes del `mail` las define el tema (`--font-head`, `--font-body`).
- **Iconos SVG con trazo blanco fijo** sobre círculo pintado por CSS (`--icon-bg`): WeasyPrint 70
  no aplica CSS externo ni `currentColor` a SVG inline.
- **Separadores " · " de metadatos vía CSS** (`.meta > span + span::before`): el PDF los contiene
  como texto real (verificado con pdfplumber) y la plantilla no necesita lógica de separadores.
  La línea de contacto ATS sí lleva ` | ` literal en el HTML.
- **Densidad del `ats` con páginas con nombre** (`body.density-compact { page: compact }` +
  `@page compact { margin: 14mm }`): todo el CSS queda en `ats.css`.
- **Preview**: el `ats` incluye `ats/preview.css` (hoja simulada en pantalla) solo si
  `for_preview`; así el HTML exportado solo contiene `#000`/`#333`. El `mail` usa `@media screen`.
- **Tema desconocido o `None` en `mail`** → `slate` (include con lista de respaldo de Jinja).
- **Educación `in_progress`**: se muestra `t.in_progress` como pieza extra de la línea de metadatos.
- **`mail` sin foto**: no hay hueco ni placeholder; una barra de acento corta alinea la sidebar con
  el nombre. No hay iniciales porque el contrato no trae `initials` (propuesto al jefe).
- **`web/i18n/{es,en}.json`**: `{"sections": {key: {"upper", "title"}}, "t": {...}, "levels":
  {"skill": {basic..expert}, "language": {A1..C2, native}}}`.
- **Vendor**: htmx 2.0.4, Alpine.js 3.14.8, SortableJS 1.15.6 (`static/vendor/VERSIONS.md`).

## 2026-09-10 — Diseño (ronda 2)

- Plantillas migradas a `section.entries` (contrato actualizado por el jefe).
- **Monograma sin foto** (`basics.initials`): sello de 30 mm con las iniciales en `--font-head`,
  centrado donde iría la foto; forma y colores por tema vía `--mono-bg/-text/-ring/-radius/-weight`
  (slate: cuadrado redondeado sólido en acento; ocean: círculo con anillo cian; graphite: círculo
  con anillo e iniciales ámbar). La barra de acento queda solo como respaldo si no hay iniciales.
- `employment_type_label`: solo en `mail`, como última pieza (en cursiva) de la línea
  `Empresa · Ubicación · Tipo`. En `ats` no se muestra para no alterar la línea 2 `Ubicación · fechas`.
- `years_label`: solo en `mail`, junto al nivel (`Experto · 8 años`). En `ats` nada de niveles/años.
- Educación en curso: la plantilla ya no añade `t.in_progress` (viene en `dates`); en `mail`
  `in_progress` solo colorea las fechas con el acento.
- `web/i18n/{es,en}.json` agregan `employment_types` y `years` (`one` / `many` con `{n}`).

## 2026-09-10 — Backend

- **Settings** (`app/config.py`): variables de entorno con prefijo `CV_ATS_` (`CV_ATS_DB_URL`,
  `CV_ATS_DATA_DIR`, `CV_ATS_PDF_ENGINE`, `CV_ATS_LOG_LEVEL`) y `.env`. `DB_URL` por defecto
  `sqlite:///<repo>/data/cv.db`. Motivo: nombres genéricos como `DB_URL` chocan con otras apps.
- **Basics "vacío" al crear un CV**: strings vacíos en las columnas NOT NULL y `country="CO"`.
  `BasicsOut.email` es `str` (no `EmailStr`) para poder devolver ese estado; el validador reporta
  los faltantes. `PUT /api/resumes/{id}/basics` **fusiona** solo los campos enviados
  (`BasicsUpdate`), para no borrar la foto ni otros campos si el formulario envía un subconjunto.
- **Fechas**: toda fecha de entrada (`YYYY-MM` o `YYYY-MM-DD`) se guarda con día 01. `""` → `None`.
- **Teléfono E.164**: el prefijo por defecto sale de `basics.country` (tabla corta de códigos de
  LatAm/ES/US/UE; `CO`=57 si no hay país). Acepta `+`, `00` y números con el código ya incluido.
- **Actualizaciones**: ítems con `PATCH` (parcial). El servicio fusiona el estado actual con el
  cambio y **revalida con el esquema Create**, así las reglas cruzadas (is_current/end_date, fechas,
  ats/mail) valen también al editar. `is_current=true` sin `end_date` en el PATCH limpia `end_date`.
- **Errores**: 422 `{"detail":[{"field","msg"}]}` (mensajes en español; los `model_validator`
  indican el campo con `FieldValueError`), 404 y 409 `{"detail": "mensaje"}`.
- **Cuerpos**: `PUT .../order` recibe un array JSON de ids (`[3,1,2]`) que debe contener exactamente
  los ids actuales; `PUT .../technologies` un array de nombres; `PUT /profiles/{id}/sections` un
  array con las 7 secciones (el orden del array es la posición).
- **Orden**: `UNIQUE(parent, position)` existe en BD en todas las tablas ordenables; el servicio
  reescribe 0..n-1 en dos fases (posiciones negativas y luego finales) porque SQLite no difiere
  UNIQUE. Tras borrar se compacta.
- **Orden cronológico por defecto de experiencias** (spec §8.1): no se guarda un flag de "el
  usuario reordenó". Al crear/editar, si el resto de experiencias ya está en orden cronológico
  inverso se reordena todo por `start_date` desc; si el usuario lo cambió a mano, se agrega al final.
  El render usa siempre `position`.
- **Perfiles por defecto**: `Plataforma` (ats, Arial, `MM/YYYY`) y `Correo` (mail, `slate`,
  `MMM YYYY`). Temas válidos: `slate|ocean|graphite`. Pasar a `ats` fuerza además
  `font_family="Arial"` si la fuente no es ATS; pasar a `mail` sin tema pone `slate`.
  `font_family` es NOT NULL con default `Arial` (la spec solo da DEFAULT).
- **Restricciones solo en servicio**: `contact_link` único por `kind` salvo `other`; nombres de
  categoría/skill/idioma/perfil/CV únicos sin distinguir mayúsculas (409). `education` sin CHECK de
  fechas en BD (sí en el esquema). `education.level` es NULL-able.
- **Tecnologías**: `name` UNIQUE `NOCASE`; el seed incluye alias (`name`≠`canonical`, p. ej.
  `postgres`→`PostgreSQL`). `get_or_create` busca por `canonical` sin mayúsculas, luego por alias;
  si no existe crea `name=canonical=<normalizado>`. En el CV se muestra `canonical`. Una `skill`
  se enlaza sola a la tecnología del catálogo si el nombre coincide (solo búsqueda, no crea).
- **Borrado de CV por ORM**: la relación `Resume.export_jobs` se declara antes que `profiles` para
  que se borren primero los jobs (`export_job.profile_id` es RESTRICT). Borrar un perfil con
  exportaciones → 409.
- `TimestampMixin` también en las tablas M2M; `AUTOINCREMENT` en todas las PK sustitutas.
- `mypy` también cubre `schemas/` y `render/` (además de los paquetes de la spec).
- **Snapshots**: crear/listar/leer implementados; restaurar queda 501 (F2-07).
- **Preview** `GET /api/resumes/{id}/preview?profile_id=&density=` ya implementado (HTML);
  sin `profile_id` usa el primer perfil; `X-Pages` solo cuando exista el conteo (F2-04).
- **Render** (`render/context.py`): lee `web/i18n/{lang}.json` (de Diseño). Solo viven en Python
  lo que no está en el JSON: etiquetas por defecto de enlaces, sufijo de `doc_title`
  ("Hoja de vida"/"Resume") y nombres de país ISO→es/en. Todas las secciones usan el
  `date_format` del perfil; un rango con el mismo texto en ambos extremos se colapsa ("2021").
  `display` de URLs quita también `www.` (como los fixtures de Diseño). Ubicación de experiencia
  remota: "Ciudad · Remoto" (sin país). `initials`: heurística hispana (2–3 palabras → 1ª y 2ª;
  4+ → 1ª y penúltima; se ignoran partículas "de", "la"…).
- **Seed**: `cv-ats seed` aplica `alembic upgrade head` y luego es idempotente: tecnologías por
  `name` y CV de ejemplo por nombre (`Ejemplo — Backend`; se marca default si no hay otro).

## 2026-09-10 — Diseño (ronda 3)

- **Bloque de idiomas indivisible en la sidebar del `mail`**: `.side-block.languages { break-inside: avoid }`
  sobre el contenedor completo (título incluido). Verificado que WeasyPrint 70 lo respeta dentro
  del ítem de grid: en las 18 combinaciones (3 temas × con/sin foto × 3 densidades) no se parte
  ninguna; como control, con `break-inside: auto` se parten 9 de 18. No depende de la altura de
  la foto o del monograma.
- `render_sample.py` falla si algún nombre de idioma no está en la misma página que el título
  IDIOMAS/LANGUAGES. En `mail` la comprobación usa solo la franja de la sidebar (x < 32%), porque
  pdfplumber une en una línea el texto de las dos columnas que está a la misma altura.
- `render_sample.py` escribe cada PDF en un solo `write_bytes` y acepta `--out`: en el disco NTFS
  (ntfs3) una escritura incremental de WeasyPrint quedó bloqueada en estado D.

## 2026-09-10 — Backend (cierre ronda 1)

- **`basics.initials`** (decisión del jefe): las partículas (de, del, la, las, los, y, da, das, do,
  dos, van, von) se unen a la palabra siguiente formando una unidad. 1 unidad → su letra;
  2–3 unidades → unidad 0 + unidad 1; 4+ unidades → unidad 0 + unidad 2. La letra es la primera
  alfabética de la unidad sin contar la partícula, en mayúsculas y conservando tildes
  ("María de los Ángeles Pérez" → "MÁ", "Juan de la Cruz Gómez Ruiz" → "JG").
- El trabajo se movió a la copia en disco interno (`/home/jose/cv-ats-rescate-1551`) por el cuelgue
  del driver `ntfs3` en el disco externo; `tests/test_models.py` se reescribió (quedó truncado).

## 2026-09-10 — Jefe (cierre ronda 1, interfaz validador/export)

- **Formato de fecha único**: el `date_format` del perfil se aplica a TODAS las secciones
  (experiencia, educación, proyectos, certificaciones). Motivo: regla `dates.format_consistent`
  (error en ats). Los fixtures de Diseño con `YYYY` en educación son solo ilustrativos.
- **Textos de render en Python** (etiquetas de enlaces, sufijo de `doc_title`, países ISO→nombre):
  se aceptan en `render/`; no se mueven al i18n por ahora.
- **Verbos de acción**: `validator/data/verbs_es.txt` incluye infinitivo y pretérito en 1ª persona
  ("Lideré", "Reduje", "Diseñé") además de 3ª ("Lideró"). Es la forma habitual en CVs en español y
  no cuenta como pronombre para `content.no_pronouns` / `summary_first_person`.
- **Firma de reglas** (desvío de §9.1): `def regla(ctx: RuleContext) -> list[Hit]` en lugar de
  `(cv, profile)`, porque `structure.*`, `length.*` y `technical.*` necesitan HTML, páginas o
  `PdfInfo`. La severidad por destino la asigna el motor desde el decorador; `"–"` en la tabla de
  §9.2 = la regla no corre para ese destino. Interfaz en `validator/types.py` (del jefe).
- **Puntaje**: cada regla descuenta su peso **una sola vez** por reporte, aunque genere varios
  hallazgos (error = peso, warning = peso/2, info = 0; mínimo 0). Motivo: evitar que un CV con
  muchos logros quede en 0 por una sola regla.
- **Fases**: `engine.run(ctx)` corre las reglas `PRE` siempre y las `POST` solo si `ctx.pdf` no es
  None. Export: corrida pre (sin pdf) → bloqueo si ats con errores → genera PDF → corrida completa
  (con html, pages y pdf) → ese es el reporte que se persiste.
- **Dos agentes de Backend en paralelo** para Fase 2 (resto) y Fase 3: *Backend-Export* y
  *Backend-Validador*, con carpetas disjuntas; archivos compartidos (`app/cli.py`, `app/main.py`,
  `app/routers/pending.py`, `docs/DECISIONS.md`) solo con ediciones puntuales releyendo antes.

## 2026-09-10 — Backend-Export (F2-04…F2-07, §10)

- **PDF** (`export/pdf.py`): WeasyPrint por defecto; metadatos `title`/`authors`/`description`
  (→ /Subject "Hoja de vida")/`generator` (→ /Creator "cv-ats"). `PDF_ENGINE=playwright` importa
  Playwright de forma perezosa y, si falta, lanza `PdfEngineError` con la instrucción de
  instalación; con Chromium no se puede fijar /Author (limitación conocida).
- **Conteo de páginas**: `render(..., with_pages=True)` usa `count_pages(html)`, cacheado por hash
  del HTML (LRU de 64). Por defecto `render()` no maqueta. La preview manda `X-Pages` siempre
  (`?pages=false` lo omite).
- **Round-trip** (`export/verify.py`): tokens = nombre, empresas, cargos, logros y skills (§9.3);
  normalización NFKD sin tildes, minúsculas, sin puntuación y tokens de ≥2 caracteres. `verify()`
  acepta un `profile=` opcional (extensión compatible de la firma) para contar solo lo visible en
  ese destino (show_in + secciones visibles); sin perfil cuenta todo. Fuentes embebidas: todas las
  fuentes no Type3 deben tener `FontFile*` en su descriptor. Símbolos permitidos fuera de
  Latin-1: `• – — ·`.
- **Un `export_job` por petición** (aunque pida varios formatos): `format` = primer formato
  pedido; `output_path` = carpeta `data/exports/{job_id}/`. Descarga con
  `GET /api/exports/{id}/download?format=pdf|docx|json[&variant=sinfoto]`.
- **Flujo** (`ExportService.run`): render HTML → validación pre (con `html`, sin PDF) → si ats con
  errores: `blocked`, sin snapshot ni archivos → snapshot → PDF → `verify` → validación completa
  (html + pages + pdf; es el reporte que se persiste) → ats con error `technical.text_extractable`:
  `failed`; ats con cualquier otro error post-render (p. ej. `length.pages`): `blocked`; si no,
  `done` y se escriben los archivos. Solo los `done` dejan archivos. Error inesperado → `failed`
  con el mensaje. `roundtrip_ok = has_text and coverage ≥ 0.95`.
- **Nombres**: `{Nombre}_{Apellido}_CV_{ats|correo}[_sinfoto].{ext}` con la regla de unidades de
  `initials` (primer nombre + primer apellido), sin tildes ni espacios (`Andres_Rojas_CV_ats.pdf`).
  La variante `_sinfoto` se genera solo en `mail` con `include_photo=true` y solo para PDF.
- **Motor de validación inyectable**: `ExportService(engine=...)`; por defecto `default_engine()`
  importa `validator.engine.run` de forma perezosa (si no existe usa un motor nulo, score 100, y lo
  registra en el log). En la API es la dependencia `get_validation_engine` (sobrescribible).
- **Persistencia del reporte**: `ExportService._persist_report` escribe `validation_report` +
  `validation_finding` directamente (recortando textos a los largos de las columnas) porque
  `services/validation.py` aún no existe; cuando exista, debe reemplazarse por ese servicio.
- **DOCX**: estilos `Title` (nombre), `Heading 1` (secciones), `Heading 2` (ítems),
  `List Bullet` (logros) y `Normal`; Letter; fuente y tamaño/márgenes por densidad como la
  plantilla ats; sin tablas. Mismo contexto de render, así que los textos coinciden con el HTML.
- **Restore de snapshot**: en una transacción; las listas de contenido se recrean (ids nuevos),
  `basics` y los perfiles que coinciden por id se actualizan en su lugar (así los `export_job`
  siguen apuntando a su perfil); los perfiles creados después del snapshot se borran salvo que
  tengan exportaciones (RESTRICT), en cuyo caso se conservan. No cambia `is_default`; el nombre
  del CV se restaura solo si no lo usa otro CV. Round-trip exacto salvo `id`, `created_at` y
  `updated_at`.
- Los tests escriben siempre bajo un `CV_ATS_DATA_DIR` temporal (fixture autouse en `conftest`).

## 2026-09-10 — Backend-Validador

- **Registro**: `@rule(id, section, severity={"ats": ..., "mail": ...}, weight, phase)`; `"-"`/`"–"`/
  clave ausente = no corre en ese destino. La descripción de cada regla es su docstring (fuente de
  `docs/ATS_RULES.md`, generado con `cv-ats rules --md`; un test exige que el archivo esté al día).
  Re-registrar la misma función es un no-op; otra función con el mismo id → `ValueError`.
- **Puntaje**: descuento por regla una sola vez; el total se **redondea hacia abajo**
  (100 − 12,5 = 87). Hallazgos ordenados por severidad y luego por id de regla.
- **HTML**: las reglas de estructura ignoran comentarios CSS/HTML (el `ats.css` menciona
  «position:absolute» en un comentario). `single_column` detecta grid, `grid-template`, columnas
  CSS, `float` y `position: absolute/fixed`; `no_photo` además `<img>`/`<svg>` en el HTML.
- **`canonical_headings`**: lista blanca es/en por sección, comparada sin tildes/mayúsculas y con
  `&` = y/and; un título válido de otra sección no vale (p. ej. «Experiencia» en habilidades).
- **`dates.format_consistent`**: el perfil ya impone un formato; la regla busca fechas escritas a
  mano en otro formato (`MM/YYYY` o `mmm YYYY`) en textos libres y, si no hay, en el HTML. Los años
  sueltos no se revisan (ambiguos). `dates.future` exime vencimiento de certificaciones y la fecha de
  fin de educación `in_progress` (grado esperado).
- **`length.min_content`**: si hay ≥ 2 páginas no reporta; con 1 página o sin conteo estima por
  texto visible: página llena ≈ 2500/2100/1650 caracteres (compacto/normal/amplio, medido con
  WeasyPrint sobre el CV de ejemplo); < 60% → aviso. `length.pages` usa `ctx.pages` o `pdf.pages`.
- **`technical.filename`**: regex `Nombre_Apellido_CV[_...].ext` ASCII sin espacios, y la primera
  pieza debe ser el primer nombre sin tildes. `technical.metadata`: autor = nombre y título contiene
  el nombre. `photo.*` considera foto incluida si `include_photo` y `photo_asset_id`.
- **Persistencia**: `ValidationService(session).run_and_save(resume_id, profile_id=None, *, html,
  pages, pdf, render_html)` hace commit. `services.validation.save_report(session, *, resume_id,
  profile_id, report)` **no hace commit** (lo usa `ExportService._persist_report` dentro de su unidad
  de trabajo). La API y el CLI renderizan el HTML final y cuentan páginas con `export.pdf.count_pages`
  (si falla, `pages=None`).
- **CLI `validate`**: guarda el reporte; `--profile` resuelve por nombre y luego por destino (misma
  función que `export`); sale con 1 si el destino es ats y hay errores, 2 si el CV/perfil no existe.
- Pronombres (resumen/logros) como constantes en `validator/text.py`; verbos en
  `validator/data/verbs_{es,en}.txt` (243 es: infinitivo + pretérito 1ª y 3ª; 235 en: base + pasado).

## 2026-10-06 — Jefe (aprobación del contrato del editor)

- `docs/design/EDITOR_CONTEXT.md` queda **aprobado** como contrato Diseño ⇄ Backend para la Fase 4.
  Backend implementa las rutas `/ui` exactamente como están documentadas allí. Enmiendas del jefe:
  1. **Foto**: la lógica de imagen (Pillow: validar mime/tamaño, recorte cuadrado centrado, `_400.jpg`,
     sha256 para dedupe) vive en `services/asset.py` y la usan **ambas** rutas: `POST /ui/resumes/{id}/photo`
     (contrato) y `POST /api/assets` (spec §6). El servidor revalida y recorta aunque el cliente ya recorte.
  2. El test `test_pending_endpoints_return_501` se queda solo con las rutas que sigan sin implementar.
- Equipos a partir de aquí: **Backend-UI** (`app/routers/ui.py`, `app/web.py`, `services/asset.py`,
  `tests/test_ui.py`), **Backend-Import** (importer/, match/), **Diseño** (web/, static/, docs/design/).

## 2026-10-06 — Backend-Import (F5-01, F5-02, §11 y §12)

- **Líneas con layout**: PDF y DOCX se normalizan a `importer.lines.Line`
  (texto, tamaño, negrita, sangría, página, columna, estilo). En PDF las líneas se arman desde
  `extract_words(extra_attrs=["size","fontname"])`; negrita = ≥60% de los caracteres en una fuente
  "bold".
- **Dos columnas**: si existe una banda vertical vacía de ≥12 pt entre el 15% y el 70% del ancho y
  cada lado tiene ≥12% de las palabras, la página se parte en dos. La columna con más palabras es
  `main` y la otra `side` (sidebar de LinkedIn o de la plantilla de correo). El sectionizer lleva
  **una sección actual por columna**, para que el nombre del cuerpo no caiga en la última sección
  de la barra lateral.
- **Segmentación de ítems en dos modos**: modo A, cuando la sección tiene líneas en negrita que no
  son etiquetas (PDF/DOCX de esta app, LinkedIn), cada negrita abre un ítem; modo B, texto plano,
  las líneas con rango de fechas son anclas y el título son hasta 2 líneas anteriores. Sin fechas,
  cada línea es un ítem (listas de certificaciones). Una línea solo corta la búsqueda del título si
  parece oración (termina en "." y más de 8 palabras), para no partir siglas como "S.A.S.".
- **Fechas**: `MM/YYYY`, `marzo de 2021`, `Mar 2021` y `2021`, con rangos separados por
  `– — - a al hasta to until` y fin abierto (`Actualidad`, `Present`, `En curso`). La confianza
  depende de la precisión: 0,95 numérica, 0,9 con nombre de mes, 0,7 solo año. Se descartan las
  duraciones tipo "(2 años 3 meses)".
- **Separadores de título**: `—` (0,92), `|` (0,85), `–` (0,85), `-` (0,8), `@` (0,8) y por último
  "en"/"at" con `rsplit` (0,7). En certificaciones solo `—` y `|`, porque los nombres suelen
  llevar guiones ("Solutions Architect – Associate"). Si el título llega en MAYÚSCULAS se pasa a
  tipo título y la confianza baja 0,15, así queda marcado para revisión.
- **Nombre partido en dos líneas** (LinkedIn): las líneas siguientes con el mismo tamaño de fuente
  se unen al nombre y no se reusan como headline ni como contacto.
- **El preview no escribe nunca**. `ImportService.apply(mode=...)`: `replace` (por defecto) vacía
  las listas de contenido y luego inserta; `append` agrega después de lo existente, fusiona
  categorías de habilidades por nombre (sin duplicar skills) y omite enlaces por `kind` e idiomas
  repetidos. Los campos de `basics` solo se sobrescriben cuando el preview trae valor.
- **Validación por ítem**: cada elemento pasa por su esquema `*Create`; los inválidos se omiten y
  se reportan en `skipped` con `path` y motivo (p. ej. `experiences.1`), y el resto se escribe en
  una sola transacción. Motivo: un CV importado casi siempre trae algún bloque incompleto y
  abortar todo sería peor para el usuario.
- **§17.4 medido**: reimportar el PDF `Plataforma` del CV de ejemplo recupera **88/89 campos
  (98,9%)** con confianza ≥0,8, y el DOCX lo mismo. El único campo que no vuelve es el país de la
  experiencia remota, porque la plantilla ats imprime "Bogotá · Remoto" sin país. La comparación
  solo cuenta campos que la plantilla ats realmente imprime (no el tipo de contrato ni los niveles
  de habilidad) y normaliza URLs con `url_display`.
- **Match**: TF-IDF (scikit-learn) sobre `[vacante, texto del CV renderizado en ats]` con un
  analizador propio: unigramas y bigramas de tokens adyacentes que no son stopwords (es/en, más
  relleno típico de ofertas). Los tokens conservan `+ # . / -`, así sobreviven `C++`, `CI/CD` y
  `Node.js`. Las tecnologías del catálogo se detectan por frase completa y pesan el doble, así
  quedan arriba del top-40 y se muestran con su nombre canónico. Los nombres cortos o en
  mayúsculas (`Go`, `R`, `REST`) se buscan respetando mayúsculas para no confundirlos con palabras
  comunes.
- **`GET /api/postings/{id}/match` recalcula** `found_in_cv` contra el CV actual y lo persiste, así
  el panel refleja los cambios del editor sin volver a pegar la vacante. `coverage` = presentes /
  total de palabras clave.

## 2026-10-06 — Diseño (Fase 4, editor)

- **Contrato del editor**: `docs/design/EDITOR_CONTEXT.md` (rutas `/ui/...`, contexto por template,
  eventos y endpoints `/api` que usa el JS). Decisiones que lo sostienen:
  - Los templates reciben los `*Out` reales sin transformar; solo 3 filtros (`ym`, `mdate`, `dt`)
    y dos globales (`static_url`, `choices`).
  - `choices` se arma desde `web/i18n/ui_es.json` (labels de UI, propiedad de Diseño) zipeado con
    los enums de Backend, para que las etiquetas no vivan en código Python.
  - Form → esquema: clave ausente = sin cambio, `""` = `None`, clave repetida = gana la última
    (de ahí el `<input type="hidden" value="false">` antes de cada checkbox).
  - Campo `_open` (no es del esquema): el ítem conserva expandido/colapsado al re-renderizarse.
  - 422 = el mismo partial con `errors` y lo enviado (htmx hace swap de 422 y no de otros 4xx);
    el resto de errores van como texto plano y el JS los muestra como toast.
  - `data-entity` del editor = `entity` del validador (`contact_link`, no `link`);
    `profile`/`profile_section` enlazan a la pantalla de perfiles en vez de a un campo.
  - El modal de exportación no ofrece «guardar snapshot»: `ExportService` siempre crea uno;
    solo se informa. `formats` es el único campo repetible del contrato.
- **Reordenar, tecnologías y secciones del perfil** usan las rutas `/api` existentes desde el JS
  (no hay `/ui` para eso); tras cada llamada el JS emite `cv-changed`.
- **Prototipo** `docs/design/editor_preview.py`: arma datos con forma de `ResumeOut` desde
  `sample_context_es.json` y escribe páginas estáticas en `docs/design/out/editor/`. Enlaza
  `static/` con ruta relativa; quita el disparador `load` de la barra porque sin servidor
  `/ui/.../preview` no existe (la preview ya va incrustada).
- **Capturas**: Playwright MCP no sirve aquí (intenta crear `.playwright-mcp` en el cwd de la
  sesión, que es el disco externo muerto, y bloquea `file://`). Se usa **Chrome headless**
  (`google-chrome-stable --headless=new --screenshot`) contra un `python -m http.server` local,
  con `--user-data-dir` en `~/.cache`. Salida en `docs/design/out/editor/shots/`.

## 2026-10-06 — Backend-UI (F4, rutas `/ui`, `docs/design/EDITOR_CONTEXT.md`)

- **Entorno Jinja propio** (`app/web.py`): `Environment(FileSystemLoader("web"), autoescape)` en vez
  de `Jinja2Templates` (§7 del contrato lo menciona, §1 describe el `Environment`). Motivo:
  `Jinja2Templates` exige un `Request` en cada contexto e inyecta `url_for`, que ningún template usa;
  así el contexto es exactamente el del contrato. Las respuestas son `HTMLResponse` normales.
- **Filtros tolerantes a texto**: `ym`/`mdate` aceptan `date`, `None` **y** el string `"2024-03"`,
  porque en un 422 el ítem del contexto es el `*Out` mezclado con los valores crudos del formulario.
- **Booleanos en el 422**: al mezclar (`merged`), si el campo del `*Out` es `bool` y llega
  `"true"`/`"false"` se convierte a bool. Si no, `{% if item.is_current %}` sería verdadero también
  con `"false"` y los checkbox se re-pintarían mal.
- **`max_pages` (`Literal[1,2,3]`)**: Pydantic no convierte `"2"` → `2` para un `Literal` de enteros
  y el `<select>` del perfil manda texto. `app/web.py` castea solo los campos cuyo tipo es un
  `Literal` de enteros (`coerce_for`); el resto lo convierte Pydantic.
- **`employment_type` no tiene enum** en `models/enums.py` (es `VARCHAR(30)` libre). El test de
  `choices` compara ese bloque con las claves de `web/i18n/es.json["employment_types"]`, que es la
  fuente de las etiquetas del render. Los demás bloques se comparan con los enums, `THEMES`,
  `ATS_FONTS` y los `Literal` de `schemas/profile.py`, **por conjunto de claves**: el contrato pide
  conservar el orden del JSON de la UI, que no es el de los enums.
- **Campo obligatorio vacío**: el contrato manda `""` → `None`, y Pydantic reportaba entonces
  «Debe ser texto». `schemas/errors.py` traduce ahora a «Campo obligatorio» cualquier error de tipo
  (`string_type`, `date_type`, `enum`…) cuyo `input` sea `None`. Afecta también a `/api` (mejora).
- **Errores de dominio en `/ui`**: decorador `ui_errors` (no un `exception_handler` global, que
  cambiaría `/api`): `NotFoundError` → 404, `ConflictError` → 409, error de validación sin partial →
  422, todos en **texto plano** español como pide §2.2.
- **Rutas explícitas por colección** en `app/routers/ui_items.py` (una tabla `SPECS` genera las 4
  rutas de cada una de las 9 colecciones) en vez de `/ui/{parent}/{parent_id}/{coll}`. Motivo: evita
  que `/ui/resumes/1/photo` o `/ui/resumes/1/validate` casen con la ruta genérica y deja el OpenAPI
  correcto. Las URLs resultantes son exactamente las del contrato.
- **Padre equivocado → 404** vía `ChildService.require_parent` (comprueba el modelo del padre) y
  `service.get(item_id)` para `PUT`/`DELETE`; el padre de un `PUT` se resuelve desde el ítem.
- **Foto normalizada a JPEG** (`services/asset.py`): se valida que la entrada sea JPEG/PNG/WebP
  (≤5 MB), se recorta cuadrado centrado, se guarda `<uuid>.jpg` (lado ≤800) y `<uuid>_400.jpg`, y
  `asset.mime` queda siempre `image/jpeg`. Motivo: una foto de CV no necesita alfa y así el `sha256`
  (calculado sobre el JPEG normalizado) deduplica dos archivos con los mismos píxeles en distinto
  contenedor. `width`/`height` son los del recorte.
- **`DELETE /ui/resumes/{id}/photo` solo desvincula** (`photo_asset_id=None`) y borra el `asset` +
  sus archivos **solo si ningún `basics` lo referencia** (`AssetService.delete_if_unused`). Motivo:
  `ResumeService.duplicate` comparte el asset con la copia; borrarlo rompería el otro CV. Así se
  cumple §4.5.3 (borrar el archivo del disco) sin dejar huérfanos.
- `POST /api/assets` (spec §6) vive en `app/routers/assets.py` y usa el mismo `AssetService`;
  `app/routers/pending.py` se queda sin rutas (su router vacío sigue montado) y
  `test_pending_endpoints_return_501` se eliminó porque ya no queda ningún 501.
- **Orden del panel de validación**: `SECTION_ORDER` (el de las secciones del editor, con `profile`,
  `doc`, `pdf`, `export`, `all` al final y las desconocidas después) y luego severidad
  (error, warning, info) y `rule_id`; así `loop.changed(f.section)` del template agrupa bien.
- **Último reporte del perfil** para el modal de exportación: consulta directa a
  `validation_report` ordenada por id desc (no hay método de servicio para «el último»).
