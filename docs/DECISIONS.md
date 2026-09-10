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
