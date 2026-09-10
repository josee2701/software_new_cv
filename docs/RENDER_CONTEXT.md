# Contrato de render (Backend ⇄ Diseño)

Este documento es **el contrato** entre `render/context.py` (Backend, lo construye desde `ResumeOut`
+ `ExportProfileOut`) y `render/templates/**` (Diseño, lo consume). Solo el agente jefe lo modifica.
Cualquier campo que un equipo necesite y no esté aquí → pedirlo al jefe.

Todos los textos ya llegan **formateados** (fechas, ubicación, niveles). Las plantillas no formatean
nada: solo bucles y condicionales (spec §16).

## Entrada de las plantillas

`render/renderer.py` hace `env.get_template(f"{destination}/base.html").render(**ctx)`
con el entorno Jinja apuntando a `render/templates/` (autoescape activado).

```python
ctx = {
  "lang": "es",                       # "es" | "en"  → <html lang="...">
  "destination": "ats",               # "ats" | "mail"
  "for_preview": False,               # True en la preview del editor (puede mostrar sombra de página, etc.)
  "doc_title": "Juan Pérez — Hoja de vida",

  "profile": {
    "name": "Plataforma",
    "theme": None,                    # "slate" | "ocean" | "graphite" | None (ats)
    "accent_color": None,             # "#1F6FEB" | None → si viene, sobrescribe --accent
    "density": "normal",              # "compact" | "normal" | "wide"
    "font_family": "Arial",           # ats: Arial | Calibri | Helvetica | Georgia
    "include_photo": False,
    "max_pages": 2,
  },

  "t": {                              # textos de UI del documento, ya en el idioma del CV
    "present": "Actual",              # "Present"
    "remote": "Remoto",               # "Remote"
    "contact": "Contacto",            # "Contact"   (título sidebar mail)
    "technologies": "Tecnologías",    # "Technologies"
    "credential": "Credencial",       # "Credential"
    "expires": "Vence",               # "Expires"
    "gpa": "Promedio",                # "GPA"
    "in_progress": "En curso",        # "In progress"
  },

  "basics": {
    "full_name": "Juan Pérez",
    "headline": "Ingeniero de Sistemas · Backend Python",
    "email": "juan@correo.com",
    "phone": "+573001234567",           # E.164 (texto literal, para ATS)
    "phone_display": "+57 300 123 4567",
    "location": "Bogotá, Colombia",     # ciudad[, región], país (nombre) — "" si no hay
    "summary": "Texto…",                # "" si vacío
    "photo_src": None,                  # data URI "data:image/jpeg;base64,..." o None
    "initials": "JP",                   # 1ª letra del primer nombre + 1ª del primer apellido
  },

  "links": [                            # ya ordenados
    {"kind": "linkedin", "label": "LinkedIn", "url": "https://linkedin.com/in/juan",
     "display": "linkedin.com/in/juan"},   # display = URL sin esquema ni "/" final
  ],

  "sections": [                         # SOLO visibles, en el orden del perfil, con ≥1 ítem
    {"key": "summary",   "title": "RESUMEN PROFESIONAL", "entries": []},  # usar basics.summary
    {"key": "experience","title": "EXPERIENCIA PROFESIONAL", "entries": [Experience, ...]},
    ...
  ],
  "sections_by_key": {"experience": <misma sección>, ...},  # acceso directo (útil en mail)
}
```

`title` ya viene resuelto: `title_override` del perfil o el canónico del idioma. En `ats` viene en
MAYÚSCULAS; en `mail` viene en tipo título ("Experiencia profesional") y el CSS decide.
La sección `summary` solo aparece si `basics.summary` no está vacío.

## Ítems por sección

La lista va en la clave `entries` (no `items`: en Jinja `section.items` resolvería al método
`dict.items`). Todos los ítems ya están filtrados por `show_in` y ordenados. Campos opcionales llegan como `""`
o lista vacía (nunca `None`), salvo donde se indica.

### experience
```python
{"id": 3, "role": "Desarrollador Backend", "company": "Banco X",
 "employment_type": "full-time",         # "" si no (valor crudo)
 "employment_type_label": "Tiempo completo",  # localizado; "" si no hay
 "location": "Bogotá, Colombia",         # "" si no; si remote: "Remoto" o "Bogotá · Remoto"
 "dates": "03/2021 – Actual",            # ya formateado con date_format + idioma, guion "–"
 "description": "",
 "achievements": ["Reduje la latencia…", ...],   # strings, ya limpios
 "technologies": ["Python", "PostgreSQL"]}
```

### education
```python
{"id": 1, "degree": "Ingeniería de Sistemas", "institution": "Universidad Nacional",
 "field": "", "location": "Bogotá", "dates": "2014 – 2019",   # "" si sin fechas
 # si in_progress: dates ya trae el fin localizado, p.ej. "2023 – En curso" / "2023 – In progress".
 # La plantilla NO añade t.in_progress; el booleano queda solo para estilo.
 "in_progress": False, "gpa": "", "description": ""}
```

### skills
```python
{"id": 2, "category": "Lenguajes",
 "skills": [{"name": "Python", "level": "expert", "level_label": "Experto", "years": 6,
             "years_label": "6 años"}],   # "1 año" / "6 years"
 # level / level_label / years / years_label pueden ser None
 "names": "Python, Go, SQL"}              # join listo para ats ("Categoría: names")
```
En `ats` la plantilla **no** muestra niveles (regla `content.skills_no_levels_ats`).

### projects
```python
{"id": 1, "name": "cv-ats", "role": "", "description": "…", "url": "https://…",
 "url_display": "github.com/juan/cv-ats", "dates": "2024 – 2025", "technologies": ["FastAPI"]}
```

### certifications
```python
{"id": 1, "name": "AWS Solutions Architect", "issuer": "Amazon", "date": "05/2023",
 "expiry": "05/2026", "credential_id": "", "url": "", "url_display": ""}
```

### languages
```python
{"id": 1, "name": "Inglés", "level": "B2", "level_label": "B2 — Intermedio alto"}
```

## Atributos de enlace para la UI de validación

Cada ítem renderizado lleva `data-entity="<entity>" data-entity-id="{{ item.id }}"` en su
contenedor (entity = `experience`, `education`, `skill_category`, `project`, `certification`,
`language`), y el bloque de datos personales `data-entity="basics"`. El panel de validación del
editor los usa para hacer scroll.

## Reglas duras de la plantilla `ats` (spec §8.2, no negociables)

Sin `<table>`, sin `<img>`, sin iconos, sin columnas CSS, sin `position:absolute`, sin
contenido en márgenes de página (`@top-*`/`@bottom-*`), colores solo `#000`/`#333`, bullets con
`<ul><li>`, `page-break-inside: avoid` por experiencia. Densidad: fuente 9.5/10.5/11.5 pt y márgenes
14/18/22 mm. `@page { size: Letter }`.

## Plantilla `mail`

Grid 32% / 68%. Temas en `render/templates/mail/themes/{slate,ocean,graphite}.css` definen
`--accent`, `--sidebar-bg`, `--text`, `--muted`, `--font-head`, `--font-body`. Si
`profile.accent_color` no es None, base.html emite `:root{--accent: {{ profile.accent_color }}}`
después del tema. Texto real, nunca rasterizado. Iconos SVG inline permitidos.

## Notas transversales (jefe, 2026-09-10)

- `profile.font_family` llega siempre (default `Arial`), pero la plantilla `mail` lo **ignora**:
  las fuentes del correo las define el tema.
- Teléfono: las plantillas muestran `phone_display`. `export/verify.py` y la regla
  `contact.phone_present` deben comparar el teléfono **normalizando a solo dígitos** (y `+`), no
  el literal E.164.
