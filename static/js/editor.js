/* cv-ats — comportamiento del editor (sin build). Contrato: docs/design/EDITOR_CONTEXT.md.
 * - Formularios HTMX con marca de "sin guardar" y Ctrl+S.
 * - Reordenar con SortableJS (y Alt+↑/↓) → PUT /api/.../order.
 * - Chips de tecnologías con autocompletado → GET /api/technologies, PUT .../technologies.
 * - Panel de validación: "Ir al campo" (editor + preview).
 * - Recorte cuadrado de la foto, modal de exportación, secciones del perfil.
 */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------------------- utilidades */

  function toast(message, kind = "error") {
    const box = $("#toasts");
    if (!box) return;
    const el = document.createElement("div");
    el.className = `toast toast--${kind}`;
    el.textContent = message;
    box.appendChild(el);
    setTimeout(() => el.classList.add("is-leaving"), 4200);
    setTimeout(() => el.remove(), 4600);
  }

  function errorText(detail, fallback) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(" · ") || fallback;
    return fallback;
  }

  async function api(method, url, body) {
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!res.ok) {
      let msg = `Error ${res.status}`;
      try {
        msg = errorText((await res.json()).detail, msg);
      } catch (_) {
        /* respuesta sin JSON */
      }
      throw new Error(msg);
    }
    return res.status === 204 ? null : res.json();
  }

  function cvChanged() {
    document.body.dispatchEvent(new CustomEvent("cv-changed", { bubbles: true }));
  }

  function eachIn(root, sel, fn) {
    if (root.matches && root.matches(sel)) fn(root);
    $$(sel, root).forEach(fn);
  }

  /* ---------------------------------------------------------------- estado de guardado */

  let inFlight = 0;

  function updateSaveState() {
    const el = $("#save-state");
    if (!el) return;
    const dirty = $$("form.is-dirty").length;
    el.classList.toggle("is-dirty", dirty > 0);
    el.classList.toggle("is-saving", inFlight > 0);
    if (inFlight > 0) el.textContent = "Guardando…";
    else if (dirty === 1) el.textContent = "1 cambio sin guardar";
    else if (dirty > 1) el.textContent = `${dirty} cambios sin guardar`;
    else el.textContent = "Guardado";
  }

  function markDirty(form, dirty = true) {
    form.classList.toggle("is-dirty", dirty);
    const holder = form.closest(".item, .section-acc, .card");
    if (holder) holder.classList.toggle("is-dirty", dirty);
    updateSaveState();
  }

  document.addEventListener("input", (e) => {
    const target = e.target;
    if (target.matches("[data-uppercase]")) target.value = target.value.toUpperCase();
    const form = target.closest("form[data-dirty-track]");
    if (form) markDirty(form);
    if (target.matches("textarea, input")) updateCounter(target);
  });

  document.addEventListener("change", (e) => {
    const form = e.target.closest("form[data-autosave]");
    if (form && form.checkValidity()) form.requestSubmit();
  });

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      const pending = $$("form.is-dirty");
      if (!pending.length) {
        toast("No hay cambios pendientes.", "info");
        return;
      }
      pending.forEach((form) => form.requestSubmit());
    }
  });

  window.addEventListener("beforeunload", (e) => {
    if ($$("form.is-dirty").length) e.preventDefault();
  });

  document.addEventListener("click", (e) => {
    const cancel = e.target.closest("[data-cancel-draft]");
    if (cancel) cancel.closest(".item")?.remove();
  });

  /* ---------------------------------------------------------------- contadores */

  function updateCounter(field) {
    const counter = $(`[data-counter-for="${field.id}"]`);
    if (!counter) return;
    const len = field.value.trim().length;
    const min = Number(counter.dataset.min || 0);
    const max = Number(counter.dataset.max || 0);
    counter.textContent = max ? `${len} · ideal ${min}–${max}` : `${len}`;
    counter.classList.toggle("is-out", len > 0 && (len < min || len > max));
  }

  /* ---------------------------------------------------------------- htmx */

  document.addEventListener("htmx:beforeRequest", (e) => {
    if (e.detail.requestConfig && e.detail.requestConfig.verb !== "get") {
      inFlight += 1;
      updateSaveState();
    }
  });
  document.addEventListener("htmx:afterRequest", (e) => {
    if (e.detail.requestConfig && e.detail.requestConfig.verb !== "get") {
      inFlight = Math.max(0, inFlight - 1);
    }
    updateSaveState();
  });
  document.addEventListener("htmx:responseError", (e) => {
    const xhr = e.detail.xhr;
    let msg = `Error ${xhr.status}`;
    try {
      msg = errorText(JSON.parse(xhr.responseText).detail, msg);
    } catch (_) {
      if (xhr.responseText && xhr.responseText.length < 300) msg = xhr.responseText;
    }
    toast(msg);
  });
  document.addEventListener("htmx:sendError", () => toast("No hay conexión con el servidor."));

  // Conserva el scroll de la preview entre recargas.
  let previewScroll = 0;
  document.addEventListener("htmx:beforeSwap", (e) => {
    if (e.detail.target && e.detail.target.id === "preview") {
      const frame = $("[data-preview-frame]");
      try {
        previewScroll = frame ? frame.contentWindow.scrollY : 0;
      } catch (_) {
        previewScroll = 0;
      }
    }
  });

  /* ---------------------------------------------------------------- reordenar */

  function directChildren(list) {
    return Array.from(list.children).filter((c) => c.matches("[data-id], [data-section]"));
  }

  function saveOrder(list, previous) {
    if (list._save) return list._save(previous);
    const ids = directChildren(list)
      .map((c) => Number(c.dataset.id))
      .filter(Boolean);
    return api("PUT", list.dataset.orderUrl, ids)
      .then(() => {
        cvChanged();
        toast("Orden guardado.", "success");
      })
      .catch((err) => {
        toast(`No se pudo guardar el orden: ${err.message}`);
        if (previous) previous.forEach((node) => list.appendChild(node));
      });
  }

  function initSortable(list) {
    if (list._sortable || typeof Sortable === "undefined") return;
    let previous = null;
    list._sortable = Sortable.create(list, {
      handle: "[data-handle]",
      draggable: ".item, .sec-row",
      animation: reducedMotion() ? 0 : 150,
      ghostClass: "sortable-ghost",
      chosenClass: "sortable-chosen",
      // Un asa dentro de una lista anidada pertenece a esa lista, no a esta.
      filter: (evt) => evt.target.closest("[data-sortable], [data-sections-editor]") !== list,
      preventOnFilter: false,
      onStart: () => {
        previous = directChildren(list);
      },
      onEnd: (evt) => {
        if (evt.oldIndex !== evt.newIndex) saveOrder(list, previous);
      },
    });
  }

  // Alt + ↑/↓ sobre el asa: alternativa de teclado al arrastre.
  document.addEventListener("keydown", (e) => {
    const handle = e.target.closest("[data-handle]");
    if (!handle || !e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    const list = handle.closest("[data-sortable], [data-sections-editor]");
    if (!list) return;
    const row = directChildren(list).find((c) => c.contains(handle));
    if (!row) return;
    e.preventDefault();
    const previous = directChildren(list);
    if (e.key === "ArrowUp" && row.previousElementSibling) {
      list.insertBefore(row, row.previousElementSibling);
    } else if (e.key === "ArrowDown" && row.nextElementSibling) {
      list.insertBefore(row.nextElementSibling, row);
    } else {
      return;
    }
    handle.focus();
    saveOrder(list, previous);
  });

  /* ---------------------------------------------------------------- chips de tecnologías */

  function chipEl(name) {
    const li = document.createElement("li");
    li.className = "chip";
    li.dataset.value = name;
    const span = document.createElement("span");
    span.textContent = name;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("aria-label", `Quitar ${name}`);
    btn.textContent = "×";
    li.append(span, btn);
    return li;
  }

  function initChips(box) {
    if (box._chips) return;
    box._chips = true;
    const list = $("[data-chip-list]", box);
    const input = $("input[role=combobox]", box);
    const listbox = $(".combo-list", box);
    let options = [];
    let active = -1;
    let timer = null;

    const values = () => $$(".chip", list).map((c) => c.dataset.value);
    const render = (names) => {
      $$(".chip", list).forEach((c) => c.remove());
      const anchor = input.closest(".chip-input");
      names.forEach((n) => list.insertBefore(chipEl(n), anchor));
    };

    async function save(next, previous) {
      try {
        render(await api("PUT", box.dataset.saveUrl, next));
        cvChanged();
      } catch (err) {
        render(previous);
        toast(`No se pudieron guardar las tecnologías: ${err.message}`);
      }
    }

    function close() {
      listbox.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      active = -1;
    }

    function highlight(index) {
      const items = $$("[role=option]", listbox);
      items.forEach((o, i) => o.setAttribute("aria-selected", i === index ? "true" : "false"));
      active = index;
      if (items[index]) {
        input.setAttribute("aria-activedescendant", items[index].id);
        items[index].scrollIntoView({ block: "nearest" });
      }
    }

    function show(names) {
      options = names;
      listbox.innerHTML = "";
      if (!names.length) return close();
      names.forEach((name, i) => {
        const li = document.createElement("li");
        li.id = `${input.id}-opt-${i}`;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        li.textContent = name;
        listbox.appendChild(li);
      });
      listbox.hidden = false;
      input.setAttribute("aria-expanded", "true");
      highlight(-1);
    }

    function add(raw) {
      const name = raw.replace(/,/g, "").trim();
      input.value = "";
      close();
      if (!name) return;
      const previous = values();
      if (previous.some((v) => v.toLowerCase() === name.toLowerCase())) return;
      const next = [...previous, name];
      render(next);
      save(next, previous);
    }

    function removeChip(chip) {
      const previous = values();
      chip.remove();
      save(values(), previous);
    }

    function search(q) {
      clearTimeout(timer);
      if (!q.trim()) return close();
      timer = setTimeout(async () => {
        try {
          const url = `${box.dataset.searchUrl}?q=${encodeURIComponent(q.trim())}&limit=8`;
          const res = await api("GET", url);
          const have = new Set(values().map((v) => v.toLowerCase()));
          const seen = new Set();
          const names = [];
          res.forEach((t) => {
            const n = t.canonical || t.name;
            const key = n.toLowerCase();
            if (!have.has(key) && !seen.has(key) && key.includes(q.trim().toLowerCase())) {
              seen.add(key);
              names.push(n);
            }
          });
          show(names);
        } catch (_) {
          close();
        }
      }, 150);
    }

    input.addEventListener("input", () => {
      if (input.value.includes(",")) add(input.value);
      else search(input.value);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" && options.length) {
        e.preventDefault();
        highlight(Math.min(active + 1, options.length - 1));
      } else if (e.key === "ArrowUp" && options.length) {
        e.preventDefault();
        highlight(Math.max(active - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        add(active >= 0 ? options[active] : input.value);
      } else if (e.key === "Escape") {
        close();
      } else if (e.key === "Backspace" && !input.value) {
        const last = $$(".chip", list).pop();
        if (last) removeChip(last);
      }
    });
    input.addEventListener("blur", () => setTimeout(close, 120));
    listbox.addEventListener("mousedown", (e) => {
      const opt = e.target.closest("[role=option]");
      if (!opt) return;
      e.preventDefault();
      add(opt.textContent);
    });
    list.addEventListener("click", (e) => {
      const btn = e.target.closest(".chip button");
      if (btn) removeChip(btn.closest(".chip"));
      else if (e.target === list) input.focus();
    });
  }

  /* ---------------------------------------------------------------- ir al campo */

  function flash(el) {
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
  }

  function gotoEntity(entity, id) {
    const sel = id ? `[data-entity="${entity}"][data-entity-id="${id}"]` : `[data-entity="${entity}"]`;
    const pane = $(".pane-form");
    let el = pane ? $(sel, pane) : null;
    if (!el && pane && entity === "basics") el = $("#sec-basics", pane);
    if (!el) {
      toast("No se encontró ese elemento en el editor.", "info");
      return;
    }
    $("#app")?.dispatchEvent(new CustomEvent("show-form"));
    for (let d = el.closest("details"); d; d = d.parentElement?.closest("details")) d.open = true;
    for (let it = el.closest(".item"); it; it = it.parentElement?.closest(".item")) {
      it.dispatchEvent(new CustomEvent("open-item"));
    }
    setTimeout(() => {
      el.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "center" });
      flash(el);
      const field = $("input:not([type=hidden]), textarea, select", el);
      if (field) field.focus({ preventScroll: true });
    }, 60);

    const frame = $("[data-preview-frame]");
    try {
      const target = frame && frame.contentDocument ? $(sel, frame.contentDocument) : null;
      if (target) {
        target.scrollIntoView({ block: "center" });
        target.style.outline = "3px solid #d97706";
        target.style.outlineOffset = "3px";
        setTimeout(() => {
          target.style.outline = "";
          target.style.outlineOffset = "";
        }, 1800);
      }
    } catch (_) {
      /* iframe no accesible */
    }
  }

  document.addEventListener("click", (e) => {
    const go = e.target.closest("[data-goto-entity]");
    if (go) gotoEntity(go.dataset.gotoEntity, go.dataset.gotoId);
    const closePanel = e.target.closest("[data-close-panel]");
    if (closePanel) closePanel.closest(".vpanel")?.remove();
    const closeDialog = e.target.closest("[data-close-dialog]");
    if (closeDialog) closeDialog.closest("dialog")?.close();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      const panel = $(".vpanel");
      if (panel && panel.contains(document.activeElement)) panel.remove();
    }
  });

  /* ---------------------------------------------------------------- foto: recorte cuadrado */

  function swapOuter(target, html) {
    if (window.htmx && typeof htmx.swap === "function") {
      htmx.swap(target, html, { swapStyle: "outerHTML" });
      return;
    }
    const tpl = document.createElement("template");
    tpl.innerHTML = html.trim();
    const node = tpl.content.firstElementChild;
    target.replaceWith(node);
    if (window.htmx) htmx.process(node);
  }

  function initPhoto(box) {
    if (box._photo) return;
    box._photo = true;
    const input = $("[data-photo-input]", box);
    const cropper = $("[data-cropper]", box);
    const stage = $("[data-crop-stage]", box);
    const img = $("[data-crop-img]", box);
    const zoom = $("[data-crop-zoom]", box);
    const st = { x: 0, y: 0, scale: 1, base: 1, w: 0, h: 0 };
    let drag = null;

    const size = () => stage.clientWidth;
    function apply() {
      const s = size();
      const k = st.base * st.scale;
      st.x = Math.min(0, Math.max(s - st.w * k, st.x));
      st.y = Math.min(0, Math.max(s - st.h * k, st.y));
      img.style.width = `${st.w * k}px`;
      img.style.height = `${st.h * k}px`;
      img.style.transform = `translate(${st.x}px, ${st.y}px)`;
    }
    function setScale(value) {
      const s = size() / 2;
      const k0 = st.base * st.scale;
      const px = (s - st.x) / k0;
      const py = (s - st.y) / k0;
      st.scale = Math.min(3, Math.max(1, value));
      zoom.value = String(st.scale);
      const k1 = st.base * st.scale;
      st.x = s - px * k1;
      st.y = s - py * k1;
      apply();
    }

    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (!file) return;
      if (file.size > 5000000) {
        toast("La imagen supera 5 MB.");
        input.value = "";
        return;
      }
      img.onload = () => {
        cropper.hidden = false;
        const s = size();
        st.w = img.naturalWidth;
        st.h = img.naturalHeight;
        st.base = Math.max(s / st.w, s / st.h);
        st.scale = 1;
        zoom.value = "1";
        st.x = (s - st.w * st.base) / 2;
        st.y = (s - st.h * st.base) / 2;
        apply();
        stage.focus();
      };
      img.src = URL.createObjectURL(file);
    });
    zoom.addEventListener("input", () => setScale(Number(zoom.value)));
    stage.addEventListener("pointerdown", (e) => {
      drag = { x: e.clientX, y: e.clientY };
      stage.setPointerCapture(e.pointerId);
    });
    stage.addEventListener("pointermove", (e) => {
      if (!drag) return;
      st.x += e.clientX - drag.x;
      st.y += e.clientY - drag.y;
      drag = { x: e.clientX, y: e.clientY };
      apply();
    });
    stage.addEventListener("pointerup", () => {
      drag = null;
    });
    stage.addEventListener("keydown", (e) => {
      const step = 10;
      const moves = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
      if (moves[e.key]) {
        e.preventDefault();
        st.x += moves[e.key][0];
        st.y += moves[e.key][1];
        apply();
      } else if (e.key === "+" || e.key === "=") {
        setScale(st.scale + 0.1);
      } else if (e.key === "-") {
        setScale(st.scale - 0.1);
      }
    });
    $("[data-crop-cancel]", box).addEventListener("click", () => {
      cropper.hidden = true;
      input.value = "";
    });
    $("[data-crop-apply]", box).addEventListener("click", () => {
      const k = st.base * st.scale;
      const canvas = document.createElement("canvas");
      canvas.width = 800;
      canvas.height = 800;
      canvas
        .getContext("2d")
        .drawImage(img, -st.x / k, -st.y / k, size() / k, size() / k, 0, 0, 800, 800);
      canvas.toBlob(
        async (blob) => {
          const data = new FormData();
          data.append("file", blob, "foto.jpg");
          try {
            const res = await fetch(box.dataset.uploadUrl, {
              method: "POST",
              body: data,
              headers: { "HX-Request": "true" },
            });
            if (!res.ok) throw new Error((await res.text()).slice(0, 200) || `Error ${res.status}`);
            swapOuter(box.closest(".section-acc"), await res.text());
            cvChanged();
            toast("Foto actualizada.", "success");
          } catch (err) {
            toast(`No se pudo subir la foto: ${err.message}`);
          }
        },
        "image/jpeg",
        0.9,
      );
    });
  }

  /* ---------------------------------------------------------------- secciones del perfil */

  function initSectionsEditor(list) {
    if (list._save) return;
    const state = $("[data-sections-state]");
    list._save = async () => {
      const payload = directChildren(list).map((row) => ({
        section: row.dataset.section,
        visible: $("[data-sec-visible]", row).checked,
        title_override: $("[data-sec-title]", row).value.trim() || null,
      }));
      if (state) state.textContent = "Guardando…";
      try {
        await api("PUT", list.dataset.saveUrl, payload);
        if (state) state.textContent = "Guardado";
        cvChanged();
      } catch (err) {
        if (state) state.textContent = "";
        toast(`No se pudieron guardar las secciones: ${err.message}`);
      }
    };
    list.addEventListener("change", (e) => {
      const row = e.target.closest(".sec-row");
      if (row && e.target.matches("[data-sec-visible]")) {
        row.classList.toggle("is-hidden", !e.target.checked);
        const label = $(".switch-label", row);
        if (label) label.textContent = e.target.checked ? "Visible" : "Oculta";
      }
      list._save();
    });
    initSortable(list);
  }

  /* ---------------------------------------------------------------- inicialización */

  function init(root) {
    eachIn(root, "[data-sortable]", initSortable);
    eachIn(root, "[data-sections-editor]", initSectionsEditor);
    eachIn(root, "[data-chips]", initChips);
    eachIn(root, "[data-photo]", initPhoto);
    eachIn(root, "[data-counter-for]", (c) => {
      const field = document.getElementById(c.dataset.counterFor);
      if (field) updateCounter(field);
    });
    eachIn(root, "dialog[data-autoshow]", (dialog) => {
      if (!dialog.open) dialog.showModal();
      dialog.addEventListener("close", () => dialog.remove(), { once: true });
    });
    eachIn(root, "[data-autofocus]", (el) => el.focus());
    eachIn(root, "[data-preview-frame]", (frame) => {
      frame.addEventListener("load", () => {
        try {
          frame.contentWindow.scrollTo(0, previewScroll);
        } catch (_) {
          /* sin acceso */
        }
      });
    });
    const invalid = root.querySelector && root.querySelector("[aria-invalid=true]");
    if (invalid && root !== document.body) invalid.focus();
    updateSaveState();
  }

  if (window.htmx) {
    htmx.onLoad(init);
  } else {
    document.addEventListener("DOMContentLoaded", () => init(document.body));
  }
  window.cvats = { toast, gotoEntity, cvChanged };
})();
