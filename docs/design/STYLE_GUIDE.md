# Guía de estilo del editor (cv-ats)

Dirección visual del **editor** (`web/**`, `static/css/editor.css`). Las plantillas de render
(`render/templates/**`) tienen sus propias reglas: ver spec §8 y `docs/RENDER_CONTEXT.md`.

## Principio

El editor es una **mesa de trabajo**, no una landing: el protagonista es el documento de la
derecha. La interfaz es neutra, densa pero con aire, y usa el color solo para **estado**
(foco, validación, destino). Nada de degradados ni sombras decorativas; bordes finos y superficies
planas. Todo lo interactivo se ve interactivo y tiene foco visible.

## Tokens

Todos viven como variables CSS en `:root` de `editor.css`. No usar valores sueltos en componentes.

### Color

| Token | Valor | Uso |
|---|---|---|
| `--c-bg` | `#f6f6f4` | Fondo de la app (gris cálido, descansa la vista frente al blanco del CV) |
| `--c-surface` | `#ffffff` | Tarjetas, paneles, inputs |
| `--c-surface-2` | `#efefec` | Cabeceras de acordeón, zonas secundarias |
| `--c-border` | `#dcdcd6` | Bordes por defecto |
| `--c-border-strong` | `#b9b9b1` | Bordes de inputs, hover |
| `--c-text` | `#1d1d1b` | Texto principal |
| `--c-text-2` | `#5c5c56` | Ayudas, metadatos |
| `--c-primary` | `#2b54c8` | Acción principal, enlaces, selección (azul tinta) |
| `--c-primary-ink` | `#1d3d99` | Hover/pressed del primario |
| `--c-primary-soft` | `#e8eefc` | Fondo de selección, chips activos |
| `--c-error` / `--c-error-soft` | `#b3261e` / `#fdecea` | Severidad error |
| `--c-warning` / `--c-warning-soft` | `#9a5b00` / `#fff4e0` | Severidad advertencia |
| `--c-info` / `--c-info-soft` | `#1f6690` / `#e6f2f9` | Severidad info |
| `--c-success` / `--c-success-soft` | `#2e6b34` / `#e8f4e9` | Guardado, match presente |
| `--c-dest-ats` | `#3d3d3a` | Marca del destino Plataforma (sobrio, como la plantilla) |
| `--c-dest-mail` | `#7a3fb0` | Marca del destino Correo |
| `--c-focus` | `#2b54c8` | Anillo de foco |

Contraste: todos los pares texto/fondo cumplen WCAG AA (≥ 4.5:1). Las severidades nunca se
comunican solo con color: siempre llevan icono + palabra ("Error", "Advertencia", "Info").

### Tipografía

- UI: `system-ui, "Adwaita Sans", "Segoe UI", "Source Sans 3", Roboto, sans-serif`.
- Monoespaciada (ids de regla, métricas, URLs): `ui-monospace, "DejaVu Sans Mono", Menlo, monospace`.
- Escala (px): 12 (`--fs-xs`, metadatos) · 13 (`--fs-sm`, ayudas, chips) · 14 (`--fs-md`, base) ·
  16 (`--fs-lg`, títulos de sección) · 20 (`--fs-xl`, título de página).
- Pesos: 400 texto, 600 etiquetas y títulos. Sin cursivas salvo placeholders.
- Interlineado base 1.45.

### Espaciado, radios, sombras

- Escala de 4 px: `--sp-1` 4 · `--sp-2` 8 · `--sp-3` 12 · `--sp-4` 16 · `--sp-5` 24 · `--sp-6` 32.
- Radios: `--r-sm` 4 px (inputs, chips), `--r-md` 8 px (tarjetas), `--r-lg` 12 px (modal).
- Sombras: solo `--shadow-pop` para capas flotantes (modal, menú, autocompletado).
- Altura de controles: 32 px (`--ctl-h`); controles compactos 26 px.

## Layout

```
┌──────────────────────── topbar (56px) ────────────────────────┐
│ CV ▾ │ Perfil ▾ │ Densidad ▾ │ ☐ Solo este destino │ ~2 págs │ Validar │ Exportar │
├──────────── formulario (minmax 420px, 40%) ────┬──── preview (iframe) ────┤
│ acordeón de secciones                          │  hoja con sombra, zoom   │
│                                                │  ajustado al ancho       │
└────────────────────────────────────────────────┴──────────────────────────┘
                     panel de validación: drawer derecho 380px sobre la preview
```

`.app` usa grid: `grid-template-rows: auto 1fr; grid-template-columns: minmax(420px, 40%) 1fr`.
Cada columna tiene su propio scroll. Bajo 960 px la preview pasa a una pestaña.

## Componentes

### Acordeón de secciones (`.section-acc`)
`<details>` nativo (accesible por teclado sin JS). `summary` con: asa de arrastre (si la sección
es reordenable en el perfil), título, contador de ítems (`.count`) y punto de estado de validación
(`.dot--error|warning`). Abierto: borde izquierdo primario de 3 px. Solo una abierta a la vez es
opcional (Alpine), no obligatorio.

### Ítem editable (`.item`)
Tarjeta con cabecera compacta: asa `⋮⋮` (`.handle`, único punto de agarre de SortableJS),
resumen del ítem en una línea (cargo — empresa · fechas), selector `show_in`, menú de acciones
(duplicar, eliminar). El cuerpo (formulario) se expande al hacer clic. Estados:
- `.is-dirty`: borde izquierdo ámbar + texto "Sin guardar" (se guarda con `Ctrl+S` o al salir del campo).
- `.is-saving`: opacidad del indicador; `.is-error`: borde error + mensaje bajo el campo.
- `.is-hidden-for-dest`: ítem que no aparece en el destino actual → fondo rayado sutil y opacidad 0.7.
- `.sortable-ghost` / `.sortable-chosen`: placeholder punteado primario / sombra pop.

Logro (`.achievement`): textarea de 2 líneas + input `metric_value` estrecho (monoespaciado) +
ayuda "Empieza con verbo de acción" + contador de caracteres (`.counter`, se pone ámbar fuera
de 40–220).

### Campos (`.field`)
Label siempre visible arriba (nunca solo placeholder), input de 32 px, ayuda debajo en `--fs-sm`.
Error: borde + mensaje con icono y `aria-describedby`. Requeridos con "*" y texto oculto "obligatorio".

### Chips de tecnologías (`.chips`, `.chip`)
Input con autocompletado (`.combo` + `.combo-list` como `role="listbox"`). Chip = texto + botón
`×` (`aria-label="Quitar Python"`). Reordenables por arrastre. `Backspace` en input vacío borra el
último chip. Variante `.chip--present` / `.chip--missing` para el match con vacante.

### Selector `show_in` (`.showin`)
Control segmentado de 3 opciones con icono + texto corto, implementado con radios
(`role="radiogroup"`): **Ambos** (icono dos hojas), **ATS** (icono documento de líneas),
**Correo** (icono sobre). En la cabecera colapsada del ítem se muestra solo el icono activo con
`title` y texto oculto. Colores: ATS `--c-dest-ats`, Correo `--c-dest-mail`, Ambos neutro.

### Panel de validación (`.vpanel`)
Drawer derecho. Cabecera: puntaje grande (0–100) con anillo de color por rango (≥90 éxito,
70–89 advertencia, <70 error), conteo de errores/advertencias/info como filtros (toggle).
Lista agrupada por sección; cada hallazgo (`.finding--error|warning|info`): icono de severidad,
mensaje, sugerencia en `--c-text-2`, `rule_id` en monoespaciada pequeña, y botón "Ir al campo"
que hace scroll al elemento con `data-entity`/`data-entity-id` y lo resalta 1.5 s (`.flash`).
Si el perfil es ATS y hay errores: banner fijo "La exportación está bloqueada: N errores".

### Modal de exportación (`.modal`)
`<dialog>` nativo (foco atrapado y `Esc` gratis). Contenido: perfil (select), formatos (checkbox
PDF/DOCX/JSON en tarjetas), "también versión sin foto" (solo Correo), "guardar snapshot" (on por
defecto), resumen de validación en una línea. Pie: Cancelar (secundario) / Exportar (primario).
Resultado: lista de archivos con botón de descarga y páginas/round-trip.

### Botones (`.btn`)
`.btn` (secundario: superficie + borde), `.btn--primary`, `.btn--ghost` (solo texto), `.btn--danger`,
`.btn--icon` (cuadrado 32 px, siempre con `aria-label`). Deshabilitado: opacidad .5 y cursor
`not-allowed`, nunca oculto.

### Indicadores de la topbar
`.pages-badge` ("≈ 2 págs"; ámbar si supera `max_pages`), `.dest-badge--ats|mail`, `.save-state`
("Guardado" / "Guardando…" / "Sin guardar").

## Accesibilidad

- Foco visible en todo: `:focus-visible { outline: 2px solid var(--c-focus); outline-offset: 2px }`.
  Nunca `outline: none` sin reemplazo.
- Objetivos táctiles ≥ 32 px; el asa de arrastre también responde a teclado (flechas + `Alt`).
- Todo icono solo-visual lleva `aria-hidden="true"`; todo botón solo-icono lleva `aria-label`.
- Respeta `prefers-reduced-motion` (sin transiciones).
- Mensajes de guardado/validación en región `aria-live="polite"`.

## Movimiento

Transiciones de 120 ms `ease-out` solo en color, borde y opacidad. Nada que desplace el layout.
