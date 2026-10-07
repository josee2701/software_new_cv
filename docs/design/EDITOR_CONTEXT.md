# Contrato del editor (Diseño ⇄ Backend) — BORRADOR para aprobación del jefe

Rutas del editor (páginas y fragmentos HTMX `/ui/...`), el contexto Jinja de cada template en `web/`,
los eventos y los endpoints `/api` que llama `static/js/editor.js`. Backend implementa las rutas
`/ui` **exactamente** así; Diseño mantiene los templates contra este documento.

Principios:
1. Los templates reciben los **esquemas `*Out` reales** (`schemas/`) sin transformar, más unos
   pocos extras que se listan aquí. Nada de formateo en Backend para la UI salvo 3 filtros.
2. Las rutas `/ui` **reutilizan los servicios** (`services/`) y los esquemas `*Create`/`*Update`;
   no duplican validación.
3. Donde ya existe una ruta `/api` JSON adecuada (orden, tecnologías, secciones del perfil), el JS
   la llama directamente y **no hay ruta `/ui`**.

---

## 1. Entorno Jinja de `web/`

```python
env = Environment(loader=FileSystemLoader("web"), autoescape=True)   # propio, no el de render/
env.filters["ym"] = ...     # date | None → "2024-03" | ""          (value de <input type="month">)
env.filters["mdate"] = ...  # date | None → "mar 2024" | ""         (resumen de la cabecera de un ítem)
env.filters["dt"] = ...     # datetime   → "10 sep 2026, 15:04"     (lista de CVs; hora local)
env.globals["static_url"] = "/static"
env.globals["choices"] = {...}   # ver abajo
```

`choices: dict[str, list[{"value": str, "label": str}]]` se arma **una vez** desde
`web/i18n/ui_es.json["choices"]`, conservando el orden del JSON:
`{name: [{"value": k, "label": v} for k, v in labels.items()]}`. Claves: `show_in`, `link_kind`,
`degree_level`, `skill_level`, `language_level`, `employment_type`, `destination`, `density`,
`theme`, `ats_font`, `date_format`, `max_pages`, `section_key`, `export_format`. Backend añade un
test que verifique que las claves de cada bloque coinciden con los valores de `models/enums.py`
(y `THEMES`, `ATS_FONTS`, `DateFormat` de `schemas/profile.py`).

Los textos de UI están en español literal en los templates (spec §16); no hay bloque `t`.

## 2. Convenciones comunes

### 2.1 Peticiones
- Todas las rutas `/ui` responden **HTML** (fragmento o página). HTMX añade `HX-Request: true`.
- Los formularios llegan como `application/x-www-form-urlencoded` (la foto, `multipart/form-data`).
- **Form → esquema** (un helper común, p. ej. `form_to_model(form, Schema)`):
  - Clave ausente → no se envía al esquema (en `*Update` = sin cambio).
  - Valor `""` → `None`.
  - Clave repetida → **gana la última** (los checkbox van precedidos de
    `<input type="hidden" name="x" value="false">`: marcado envía `false,true`; desmarcado `false`).
    Excepción: `formats` en exportación es una lista (todas las ocurrencias).
  - `"true"`/`"false"` → bool (Pydantic lo convierte solo).
  - El campo **`_open`** (`"1"`/`"0"`) no es del esquema: se quita antes de validar y se pasa al
    template como `open = (form.get("_open") == "1")`.
- Sin CSRF (app local).

### 2.2 Respuestas
| Caso | Status | Cuerpo | Headers |
|---|---|---|---|
| Escritura correcta que devuelve un partial | 200 | el partial | `HX-Trigger: cv-changed` |
| Borrado de ítem | 200 | vacío | `HX-Trigger: cv-changed` |
| Error de validación en un formulario con partial (ítems, basics, ajustes de perfil) | **422** | **el mismo partial**, con `errors` y los valores enviados | — |
| Otros errores (404, 409, 400, 422 sin partial) | 4xx | texto plano con el mensaje en español | — |
| Redirección | 200 | vacío | `HX-Redirect: <url>` |

- `errors: dict[str, str]` = campo → mensaje, de `schemas.errors.to_field_errors` (usar el último
  segmento de `field`). Los `FieldValueError` de los validadores ya traen el campo correcto.
- En 422 el ítem del contexto es el `*Out` actual (o el borrador) **mezclado con lo enviado**
  (`{**item.model_dump(), **valores_enviados}` como dict), para no perder lo escrito, y `open=True`.
- `layout.html` configura htmx para hacer swap de 422 y no de 4xx/5xx; los 4xx/5xx se muestran
  como aviso (toast) con el texto de la respuesta (o `detail` si es JSON).

### 2.3 Contexto por defecto de todo partial de ítem
| Variable | Tipo | Nota |
|---|---|---|
| `item` | el `*Out` o un borrador (dict con `id=None`) | ver §4.3 |
| `errors` | `dict[str, str]` | `{}` si no hay |
| `open` | `bool` | `False` al pintar la página; en PUT/POST según §2.1 |
| id del padre | `resume_id` / `experience_id` / `category_id` | según la colección (§4.3) |

Los templates toleran que `errors` y `open` no estén definidos.

## 3. Páginas (HTML completo)

| Ruta | Template | Contexto |
|---|---|---|
| `GET /` | `index.html` | `resumes: list[ResumeSummaryOut]` (`ResumeService.list()`) |
| `GET /resumes/{resume_id}/edit` query `profile_id: int?`, `density: Density?` | `editor/index.html` | `resume: ResumeOut`; `profiles: list[ExportProfileOut]` (= `resume.profiles`); `active_profile: ExportProfileOut` (el de `profile_id` o `profiles[0]`); `density: str` (el de la query o `active_profile.density`); `photo_url: str \| None` (§4.2) |
| `GET /resumes/{resume_id}/profiles` query `profile_id: int?` | `editor/profiles.html` | `resume: ResumeOut`; `profiles`; `active_profile` |

`editor/index.html` incluye todos los `editor/section_*.html` con el mismo contexto. La preview se
carga sola al abrir la página (§4.4), no hace falta pasar `preview_html`.

## 4. Fragmentos `/ui`

### 4.1 Lista de CVs — `partials/resume_list.html` (contexto: `resumes`)
| Método y ruta | Form | Respuesta |
|---|---|---|
| `POST /ui/resumes` | `name`, `language` (`ResumeCreate`) | `HX-Redirect: /resumes/{nuevo_id}/edit`. Nombre repetido → 409 texto |
| `POST /ui/resumes/{resume_id}/duplicate` | — (nombre automático del servicio) | `partials/resume_list.html` |
| `POST /ui/resumes/{resume_id}/default` | — (`ResumeUpdate(is_default=True)`) | `partials/resume_list.html` |
| `DELETE /ui/resumes/{resume_id}` | — | `partials/resume_list.html` |

### 4.2 Datos personales y foto — `editor/section_basics.html` (contexto: `resume`, `photo_url`, `errors?`)
| Método y ruta | Entrada | Respuesta |
|---|---|---|
| `PUT /ui/resumes/{resume_id}/basics` | form `full_name`, `headline`, `email`, `phone`, `city`, `region`, `country`, `summary`, `_open` (`BasicsUpdate`) | 200 `section_basics.html` + `cv-changed` · 422 igual con `errors` (y `resume.basics` mezclado con lo enviado) |
| `POST /ui/resumes/{resume_id}/photo` | multipart `file` (JPEG 800×800 ya recortado en el cliente) | 200 `section_basics.html` + `cv-changed`. Mime/tamaño inválido → 400 texto |
| `DELETE /ui/resumes/{resume_id}/photo` | — (`photo_asset_id=None`) | 200 `section_basics.html` + `cv-changed` |
| `GET /ui/assets/{asset_id}` | — | `FileResponse` de la versión `_400.jpg` |

`photo_url = f"/ui/assets/{b.photo.id}?v={b.photo.sha256[:8]}"` si `resume.basics.photo`, si no `None`.
La foto sigue spec §4.4 (`asset`): Pillow valida, recorta cuadrado centrado y guarda `_400.jpg`.

### 4.3 Secciones e ítems
| Método y ruta | Qué hace | Respuesta |
|---|---|---|
| `GET /ui/resumes/{resume_id}/sections/{key}` | Re-pinta una sección. `key` ∈ `basics`, `links`, `experience`, `education`, `skills`, `projects`, `certifications`, `languages` | `editor/section_{key}.html` con `resume` (y `photo_url` para `basics`) |
| `GET /ui/{parent}/{parent_id}/{coll}/new` | Borrador **sin persistir** | partial del ítem con `item` = borrador (tabla abajo) |
| `POST /ui/{parent}/{parent_id}/{coll}` | Crea con `*Create` | 200 partial del ítem creado (`open=True`) + `cv-changed` · 422 partial del borrador + `errors` |
| `PUT /ui/{coll}/{item_id}` | Actualiza con `*Update` (parcial) | 200 partial del ítem (`open` según `_open`) + `cv-changed` · 422 partial + `errors` (`open=True`) |
| `DELETE /ui/{coll}/{item_id}` | Borra | 200 vacío + `cv-changed` |

| `{coll}` | `{parent}` | Create / Update | Template de ítem | id del padre en el contexto | `data-entity` |
|---|---|---|---|---|---|
| `links` | `resumes` | `ContactLinkCreate` / `ContactLinkUpdate` | `editor/item_link.html` | `resume_id` | `contact_link` |
| `experiences` | `resumes` | `ExperienceCreate` / `ExperienceUpdate` | `editor/item_experience.html` | `resume_id` | `experience` |
| `achievements` | `experiences` | `AchievementCreate` / `AchievementUpdate` | `editor/item_achievement.html` | `experience_id` | `achievement` |
| `education` | `resumes` | `EducationCreate` / `EducationUpdate` | `editor/item_education.html` | `resume_id` | `education` |
| `skill-categories` | `resumes` | `SkillCategoryCreate` / `SkillCategoryUpdate` | `editor/item_skill_category.html` | `resume_id` | `skill_category` |
| `skills` | `skill-categories` | `SkillCreate` / `SkillUpdate` | `editor/item_skill.html` | `category_id` | `skill` |
| `projects` | `resumes` | `ProjectCreate` / `ProjectUpdate` | `editor/item_project.html` | `resume_id` | `project` |
| `certifications` | `resumes` | `CertificationCreate` / `CertificationUpdate` | `editor/item_certification.html` | `resume_id` | `certification` |
| `languages` | `resumes` | `LanguageCreate` / `LanguageUpdate` | `editor/item_language.html` | `resume_id` | `language` |

Los `item_id`/`parent_id` de otra jerarquía → 404 (usar los servicios con `parent_id`, como los
routers `/api`). Para `PUT/DELETE /ui/{coll}/{item_id}` el padre se resuelve desde el ítem.

**Borrador** (`GET .../new`): dict con **todas** las claves del `*Out` correspondiente, `id=None`,
strings/fechas/opcionales `None`, booleanos `False`, `show_in="both"`, listas vacías, `position=0`;
`languages` con `level="B2"`; `links` con `kind="linkedin"`. El template lo detecta por `id=None`
(usa `hx-post` y botón «Crear»).

**Campos del formulario por colección** (nombres = campos del esquema):
- links: `kind`, `url`, `label`
- experiences: `role`, `company`, `employment_type`, `city`, `country`, `remote`, `start_date`,
  `end_date`, `is_current`, `description` (fechas `YYYY-MM`; con `is_current` marcado el input de
  fin va `disabled` y no se envía → `end_date` ausente; el servicio debe aceptar pasar a actual
  poniendo `end_date=None`)
- achievements: `text`, `metric_value`
- education: `degree`, `institution`, `level`, `field`, `city`, `start_date`, `end_date`,
  `in_progress`, `gpa`, `description`
- skill-categories: `name`
- skills: `name`, `level`, `years`
- projects: `name`, `role`, `url`, `start_date`, `end_date`, `description`
- certifications: `name`, `issuer`, `issue_date`, `expiry_date`, `credential_id`, `url`
- languages: `name`, `level`

**`show_in`**: cada ítem con `show_in` (todas salvo links, skill-categories y languages) tiene un
control propio que hace `PUT /ui/{coll}/{item_id}` con **solo** `show_in` y `_open`.

**Filas en línea** (`item_skill`, `item_language`) llevan `data-autosave`: el JS envía el form al
cambiar un campo. Los demás ítems se guardan con su botón o con `Ctrl+S`.

### 4.4 Preview — `partials/preview_frame.html`
`GET /ui/resumes/{resume_id}/preview` query `profile_id: int?`, `density: Density?` (los manda el
formulario de la barra superior).

Implementación = la de `GET /api/resumes/{id}/preview` (`render(cv, profile, for_preview=True,
with_pages=True)` con `density` aplicado al perfil), pero devolviendo el fragmento con contexto:

| Variable | Valor |
|---|---|
| `preview_html` | `result.html` (va en `<iframe srcdoc>`; el autoescape lo escapa bien) |
| `pages` | `result.pages` (`int \| None`) — el mismo número que el header `X-Pages` de `/api` |
| `max_pages` | `profile.max_pages` |

El fragmento actualiza el indicador de páginas de la barra con `hx-swap-oob` (id `pages-badge`).

### 4.5 Validación — `partials/validation_panel.html`
`POST /ui/resumes/{resume_id}/validate` form `profile_id`, `density` (se ignora `density`).
Llama a `ValidationService(session).run_and_save(resume_id, profile_id, render_html=True)` (lo mismo
que `POST /api/resumes/{id}/validate?profile_id=`).

| Variable | Tipo |
|---|---|
| `report` | `ValidationReportOut` (`score`, `errors`, `warnings`, `findings: list[FindingOut]`) |
| `profile` | `ExportProfileOut` usado |
| `blocked` | `bool` = `profile.destination == "ats" and report.errors > 0` |

Los hallazgos llegan en el orden del motor; el panel agrupa por `section` consecutiva, así que
**Backend los ordena por sección y luego por severidad** (error, warning, info). Cada hallazgo con
`entity`/`entity_id` enlaza al `data-entity`/`data-entity-id` del editor (tabla §4.3; `basics` →
datos personales); `entity` = `profile`/`profile_section` enlaza a la pantalla de perfiles.

### 4.6 Exportación — `partials/export_modal.html` y `partials/export_result.html`
| Método y ruta | Entrada | Respuesta |
|---|---|---|
| `GET /ui/resumes/{resume_id}/export` | query `profile_id`, `density` | `partials/export_modal.html`: `resume: ResumeOut`, `profiles`, `active_profile`, `report: ValidationReportOut \| None` (el último del perfil activo, si existe) |
| `POST /ui/resumes/{resume_id}/export` | form `profile_id`, `formats` (repetido: `pdf`/`docx`/`json`), `with_photo_variant` | 200 `partials/export_result.html` con `result: ExportResultOut` (mismo builder `_result` de `app/routers/exports.py`) |

El resultado se pinta dentro del cuerpo del modal (`#export-body`). `result.downloads[i]` es la ruta
`/api/exports/{job_id}/download?format=…[&variant=sinfoto]` del archivo `result.files[i]`.
El snapshot lo crea siempre `ExportService`; el modal solo lo informa (no hay campo `snapshot`).

### 4.7 Perfiles — `editor/profiles.html` y `partials/profile_settings.html`
| Método y ruta | Entrada | Respuesta |
|---|---|---|
| `POST /ui/resumes/{resume_id}/profiles` | form `name`, `destination` (`ExportProfileCreate`; si `mail`, `theme="slate"`) | `HX-Redirect: /resumes/{resume_id}/profiles?profile_id={nuevo_id}`. Error → 409/422 **texto** (no hay partial) |
| `PUT /ui/profiles/{profile_id}` | form `name`, `density`, `date_format`, `max_pages` y, según destino, `font_family` (ats) o `theme`, `accent_color`, `include_photo` (mail) (`ExportProfileUpdate`; `accent_color=""` → `None` = acento del tema) | 200 `partials/profile_settings.html` con `profile` + `cv-changed` · 422 igual con `errors` |
| `DELETE /ui/profiles/{profile_id}` | — | `HX-Redirect: /resumes/{resume_id}/profiles`. Último perfil → 409 texto |

Orden, visibilidad y títulos de las secciones del perfil → `PUT /api/profiles/{pid}/sections` desde el JS (§5).

## 5. Endpoints `/api` que llama el JS (ya existen)

| Uso | Método y ruta | Cuerpo | Respuesta usada |
|---|---|---|---|
| Reordenar (arrastre y Alt+↑/↓) | `PUT` a la `data-order-url` de cada lista: `/api/resumes/{id}/links/order`, `…/experiences/order`, `…/education/order`, `…/skill-categories/order`, `…/projects/order`, `…/certifications/order`, `…/languages/order`, `/api/experiences/{id}/achievements/order`, `/api/skill-categories/{id}/skills/order` | JSON `[id, …]` | status |
| Autocompletar tecnologías | `GET /api/technologies?q=…&limit=8` | — | `list[TechnologyOut]` (usa `canonical`) |
| Guardar tecnologías | `PUT /api/experiences/{id}/technologies` · `PUT /api/projects/{id}/technologies` | JSON `["Python", …]` | `list[str]` canónicos (se re-pintan los chips) |
| Secciones del perfil | `PUT /api/profiles/{pid}/sections` | JSON `[{section, visible, title_override}, …]` (orden = posición) | status |

Tras cada llamada correcta el JS emite `cv-changed` en `body`. Errores: toast con `detail`.

## 6. Eventos y comportamiento del cliente

- **`cv-changed`** (en `body`): lo produce el header `HX-Trigger` de cualquier escritura `/ui` o el
  JS tras una llamada `/api`. El formulario `#toolbar` (perfil + densidad) tiene
  `hx-get="/ui/resumes/{id}/preview" hx-trigger="load, change, cv-changed from:body delay:500ms"`
  → recarga la preview con debounce de 500 ms (spec §7). El JS conserva el scroll del iframe.
- **Validar**: `hx-post="/ui/resumes/{id}/validate" hx-include="#toolbar" hx-target="#vpanel-slot"`.
- **Exportar**: `hx-get="/ui/resumes/{id}/export" hx-include="#toolbar" hx-target="#modal-slot"`;
  el `<dialog data-autoshow>` se abre solo y se elimina al cerrarse.
- **Ir al campo**: abre la sección (`<details>`) y el ítem, hace scroll, resalta y enfoca el primer
  campo; también resalta el mismo `data-entity` en la preview.
- **Sin guardar**: escribir en un formulario lo marca; `Ctrl+S` envía todos los marcados;
  aviso al salir de la página si queda alguno.
- **Solo este destino**: 100% cliente; oculta en el formulario los ítems cuyo `data-show-in` no
  corresponde al destino del perfil elegido en la barra.

## 7. Qué implementa Backend (resumen)

1. `app/routers/ui.py` con las 3 páginas (§3) y todos los fragmentos (§4), montado **sin** prefijo
   `/api`; entorno Jinja de §1 (`Jinja2Templates` sobre `web/` con los filtros y globales).
2. Helper form → esquema y respuesta 422 con partial (§2).
3. Foto: subida (`POST /ui/resumes/{id}/photo`), borrado y `GET /ui/assets/{asset_id}` (§4.2).
4. Orden de hallazgos por sección y severidad en el panel (§4.5).
5. Tests: cada ruta `/ui` responde 200 con el template correcto y `HX-Trigger: cv-changed` en
   escrituras; un 422 re-pinta el partial con el mensaje; las claves de `choices` coinciden con los enums.
