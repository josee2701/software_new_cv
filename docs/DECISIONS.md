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
