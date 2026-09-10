# cv-ats

Editor y validador local de hojas de vida con exportación ATS (plataformas) y diseño (correo).
Especificación completa: [CV_ATS_SPEC.md](CV_ATS_SPEC.md).

```bash
uv sync
uv run alembic upgrade head
uv run cv-ats seed
uv run cv-ats serve --reload   # http://127.0.0.1:8000
```
