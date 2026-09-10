# Librerías vendorizadas

Descargadas de cdn.jsdelivr.net el 2026-09-10. Versiones fijadas: para actualizar, cambiar la
versión en la URL, volver a descargar y actualizar el hash.

| Archivo | Paquete | Versión | Origen | sha256 |
|---|---|---|---|---|
| `htmx.min.js` | htmx.org | 2.0.4 | https://cdn.jsdelivr.net/npm/htmx.org@2.0.4/dist/htmx.min.js | `e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447` |
| `alpine.min.js` | alpinejs | 3.14.8 | https://cdn.jsdelivr.net/npm/alpinejs@3.14.8/dist/cdn.min.js | `b600e363d99d95444db54acbfb2deffec9ae792aa99a09229bcda078e5b55643` |
| `Sortable.min.js` | sortablejs | 1.15.6 | https://cdn.jsdelivr.net/npm/sortablejs@1.15.6/Sortable.min.js | `6d0a831fc19b4bae851797ad3393157e861afb7862459c11226359b27e2c4337` |

Licencias: htmx (0BSD), Alpine.js (MIT), SortableJS (MIT).

Carga en `web/layout.html`: `Sortable.min.js` y `htmx.min.js` normales; `alpine.min.js` con `defer`
(debe ir después de cualquier script que registre componentes Alpine).
