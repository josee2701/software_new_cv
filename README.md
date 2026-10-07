# cv-ats

Editor y validador local de hojas de vida con exportación ATS (plataformas) y diseño (correo).
Especificación completa: [CV_ATS_SPEC.md](CV_ATS_SPEC.md). Decisiones: [docs/DECISIONS.md](docs/DECISIONS.md).
Reglas del validador: [docs/ATS_RULES.md](docs/ATS_RULES.md).

## Arrancar

Requisitos: [`uv`](https://docs.astral.sh/uv/), Python 3.12 (uv lo instala) y Pango (WeasyPrint).

```bash
uv sync                        # crea .venv e instala todo desde uv.lock
uv run alembic upgrade head    # crea data/cv.db
uv run cv-ats seed             # tecnologías + CV de ejemplo (idempotente)
uv run cv-ats serve --reload   # http://127.0.0.1:8000
```

- Editor: <http://127.0.0.1:8000/>
- API (OpenAPI interactivo): <http://127.0.0.1:8000/docs>

## CLI

| Acción | Comando |
|---|---|
| Validar | `uv run cv-ats validate --resume 1 --profile ats [--json]` |
| Exportar | `uv run cv-ats export --resume 1 --profile Plataforma --format pdf,docx,json --out out/` |
| Importar | `uv run cv-ats import mi_cv.pdf --resume 1 [--apply] [--append]` |
| Guardar versión | `uv run cv-ats snapshot --resume 1 --label "antes de cambios"` |
| Restaurar versión | `uv run cv-ats restore --snapshot ID` |
| Reglas ATS en Markdown | `uv run cv-ats rules --md` |

## Desarrollo

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q
```

Variables de entorno (prefijo `CV_ATS_`): `CV_ATS_DB_URL`, `CV_ATS_DATA_DIR`, `CV_ATS_PDF_ENGINE`,
`CV_ATS_LOG_LEVEL`.
