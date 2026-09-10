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
