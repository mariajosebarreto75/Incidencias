// Distribución Operativa — filtros estilo Excel

function fmtFecha(val) {
    if (!val) return "";
    const p = String(val).split("-");
    return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : val;
}

function origenBadge(cell) {
    const v = (cell.getValue() || "").toLowerCase();
    if (v === "gps_monitor")
        return `<span class="badge" style="background:#0ea5e9;font-size:11px;">GPS Monitor</span>`;
    return `<span class="badge bg-secondary" style="font-size:11px;">Manual</span>`;
}

// ===== Motor de filtros Excel =====
const _xlPending = {};   // field -> Set temporal mientras el dropdown está abierto
const _xlApplied = {};   // field -> Set aplicado
let _xlDropdown = null;
let _xlOpenField = null;

function _xlUniqueVals(field) {
    const seen = new Map();
    (datosDistribucion || []).forEach(row => {
        const raw = String(row[field] ?? "");
        const disp = field === "fecha" ? fmtFecha(raw) : (raw || "");
        if (raw !== "") seen.set(raw, disp);
    });
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1], "es"));
}

function _xlIsFiltered(field) {
    const sel = _xlApplied[field];
    if (!sel) return false;
    const all = _xlUniqueVals(field);
    return sel.size < all.length;
}

function _xlApplyAll() {
    const active = Object.keys(_xlApplied).filter(f => _xlIsFiltered(f));
    if (active.length === 0) { tabla.clearFilter(); return; }
    tabla.setFilter(function(data) {
        return active.every(field => {
            const raw = String(data[field] ?? "");
            return _xlApplied[field].has(raw);
        });
    });
}

function _xlUpdateBtnState(field) {
    document.querySelectorAll(`.xl-fb[data-field="${field}"]`).forEach(btn => {
        const filtered = _xlIsFiltered(field);
        btn.style.color = filtered ? "#007d8a" : "#94a3b8";
        btn.style.fontWeight = filtered ? "800" : "400";
        btn.setAttribute("title", filtered ? "Filtro activo" : "Filtrar");
    });
}

function _xlCloseDropdown() {
    if (_xlDropdown) { _xlDropdown.remove(); _xlDropdown = null; }
    _xlOpenField = null;
}

function _xlOpenDropdown(field, btnEl) {
    _xlCloseDropdown();
    _xlOpenField = field;

    const entries = _xlUniqueVals(field); // [[raw, display], ...]
    const allRaws = entries.map(e => e[0]);

    // inicializar pending desde el applied actual (o todos seleccionados)
    const base = _xlApplied[field] ?? new Set(allRaws);
    _xlPending[field] = new Set(base);

    const rect = btnEl.getBoundingClientRect();
    const div = document.createElement("div");
    div.className = "xl-dropdown";
    const left = Math.min(rect.left, window.innerWidth - 250);
    const top = rect.bottom + 4;
    div.style.cssText = `position:fixed;z-index:10000;top:${top}px;left:${left}px;
        width:240px;background:#fff;border:1px solid #d1d5db;border-radius:6px;
        box-shadow:0 6px 20px rgba(0,0,0,.18);font-size:.82rem;font-family:inherit;overflow:hidden;`;

    // — Ordenar
    const sortRow = document.createElement("div");
    sortRow.style.cssText = "display:flex;gap:1px;padding:6px 6px 4px;border-bottom:1px solid #e5e7eb;";
    [["▲ Menor a mayor","asc"],["▼ Mayor a menor","desc"]].forEach(([label, dir]) => {
        const btn = document.createElement("button");
        btn.textContent = label;
        btn.style.cssText = `flex:1;font-size:.73rem;padding:4px 2px;border:1px solid #d1d5db;
            border-radius:4px;cursor:pointer;background:#f9fafb;color:#374151;`;
        btn.onmouseover = () => btn.style.background = "#f0f9fb";
        btn.onmouseout  = () => btn.style.background = "#f9fafb";
        btn.onclick = () => { tabla.setSort(field, dir); _xlCloseDropdown(); };
        sortRow.appendChild(btn);
    });
    div.appendChild(sortRow);

    // — Buscador
    const search = document.createElement("input");
    search.type = "text";
    search.placeholder = "Buscar...";
    search.style.cssText = `width:calc(100% - 16px);margin:6px 8px 4px;padding:4px 8px;
        border:1px solid #d1d5db;border-radius:4px;font-size:.8rem;outline:none;
        background:#f9fafb;box-sizing:border-box;`;
    search.onfocus = () => search.style.borderColor = "#00b8c9";
    search.onblur  = () => search.style.borderColor = "#d1d5db";
    div.appendChild(search);

    // — Lista de checkboxes
    const list = document.createElement("div");
    list.style.cssText = "max-height:220px;overflow-y:auto;padding:2px 0;border-top:1px solid #e5e7eb;";

    function renderList(q) {
        list.innerHTML = "";
        const filtered = q ? entries.filter(([,d]) => d.toLowerCase().includes(q.toLowerCase())) : entries;

        // "Seleccionar todo"
        const allLbl = document.createElement("label");
        allLbl.style.cssText = "display:flex;align-items:center;gap:8px;padding:4px 10px;cursor:pointer;font-weight:600;";
        allLbl.onmouseover = () => allLbl.style.background = "#f0f9fb";
        allLbl.onmouseout  = () => allLbl.style.background = "";
        const allCb = document.createElement("input");
        allCb.type = "checkbox";
        allCb.style.accentColor = "#00b8c9";
        const visRaws = filtered.map(e => e[0]);
        allCb.checked = visRaws.every(r => _xlPending[field].has(r));
        allCb.indeterminate = !allCb.checked && visRaws.some(r => _xlPending[field].has(r));
        allCb.onchange = () => {
            visRaws.forEach(r => allCb.checked ? _xlPending[field].add(r) : _xlPending[field].delete(r));
            renderList(q);
        };
        allLbl.appendChild(allCb);
        allLbl.appendChild(document.createTextNode("(Seleccionar todo)"));
        list.appendChild(allLbl);

        // Separador
        const sep = document.createElement("div");
        sep.style.cssText = "border-top:1px solid #e5e7eb;margin:2px 0;";
        list.appendChild(sep);

        filtered.forEach(([raw, disp]) => {
            const lbl = document.createElement("label");
            lbl.style.cssText = "display:flex;align-items:center;gap:8px;padding:3px 10px;cursor:pointer;";
            lbl.onmouseover = () => lbl.style.background = "#f0f9fb";
            lbl.onmouseout  = () => lbl.style.background = "";
            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.style.accentColor = "#00b8c9";
            cb.checked = _xlPending[field].has(raw);
            cb.onchange = () => {
                cb.checked ? _xlPending[field].add(raw) : _xlPending[field].delete(raw);
                // actualizar el "seleccionar todo"
                allCb.checked = visRaws.every(r => _xlPending[field].has(r));
                allCb.indeterminate = !allCb.checked && visRaws.some(r => _xlPending[field].has(r));
            };
            lbl.appendChild(cb);
            lbl.appendChild(document.createTextNode(disp || "(vacío)"));
            list.appendChild(lbl);
        });
    }

    renderList("");
    search.oninput = () => renderList(search.value);
    div.appendChild(list);

    // — Botones Limpiar / Aplicar
    const footer = document.createElement("div");
    footer.style.cssText = "display:flex;gap:6px;padding:8px;border-top:1px solid #e5e7eb;";
    const btnLimpiar = document.createElement("button");
    btnLimpiar.textContent = "Limpiar";
    btnLimpiar.style.cssText = `flex:1;padding:5px 0;border:1px solid #d1d5db;border-radius:4px;
        background:#f9fafb;color:#6b7280;cursor:pointer;font-size:.8rem;`;
    btnLimpiar.onclick = () => {
        _xlPending[field] = new Set(allRaws);
        delete _xlApplied[field];
        _xlUpdateBtnState(field);
        _xlApplyAll();
        _xlCloseDropdown();
    };
    const btnAplicar = document.createElement("button");
    btnAplicar.textContent = "Aplicar";
    btnAplicar.style.cssText = `flex:1;padding:5px 0;border:none;border-radius:4px;
        background:#00b8c9;color:#fff;cursor:pointer;font-size:.8rem;font-weight:600;`;
    btnAplicar.onmouseover = () => btnAplicar.style.background = "#007d8a";
    btnAplicar.onmouseout  = () => btnAplicar.style.background = "#00b8c9";
    btnAplicar.onclick = () => {
        _xlApplied[field] = new Set(_xlPending[field]);
        _xlUpdateBtnState(field);
        _xlApplyAll();
        _xlCloseDropdown();
    };
    footer.appendChild(btnLimpiar);
    footer.appendChild(btnAplicar);
    div.appendChild(footer);

    document.body.appendChild(div);
    _xlDropdown = div;

    setTimeout(() => {
        document.addEventListener("click", function closeDD(e) {
            if (!div.contains(e.target) && !e.target.classList.contains("xl-fb")) {
                _xlCloseDropdown();
                document.removeEventListener("click", closeDD);
            }
        });
    }, 80);
}

function _xlTitleFormatter(cell) {
    const field = cell.getColumn().getField();
    const title = cell.getValue();
    return `<span class="xl-title-wrap" data-field="${field}">
        <span>${title}</span>
        <button class="xl-fb" data-field="${field}" title="Filtrar" type="button">▼</button>
    </span>`;
}

// ===== Tabla Tabulator =====
let tabla = new Tabulator("#tablaDistribucion", {
    data: datosDistribucion,
    layout: "fitDataStretch",
    height: false,
    maxHeight: "80vh",
    pagination: false,
    resizableColumns: true,
    movableColumns: true,
    clipboard: true,
    clipboardCopyStyled: false,
    clipboardCopyConfig: { rowHeaders: false, columnHeaders: true },
    columns: [
        {
            title: "Fecha", field: "fecha", frozen: true, width: 110,
            titleFormatter: _xlTitleFormatter,
            formatter: function(cell) { return fmtFecha(cell.getValue()); },
        },
        { title: "Contrato",        field: "contrato",           titleFormatter: _xlTitleFormatter, minWidth: 220 },
        { title: "Recurso",         field: "recurso",            titleFormatter: _xlTitleFormatter, minWidth: 140 },
        { title: "Placa",           field: "placa",              titleFormatter: _xlTitleFormatter, width: 100 },
        { title: "OT",              field: "orden_trabajo",      titleFormatter: _xlTitleFormatter, minWidth: 130 },
        { title: "Tipo Actividad",  field: "tipo_actividad",     titleFormatter: _xlTitleFormatter, minWidth: 160 },
        { title: "Tipo Cuadrilla",  field: "tipo_cuadrilla",     titleFormatter: _xlTitleFormatter, minWidth: 150 },
        { title: "Cédula 1",        field: "cedula_1",           titleFormatter: _xlTitleFormatter, width: 110 },
        { title: "Nombre",          field: "nombre_1",           titleFormatter: _xlTitleFormatter, minWidth: 180 },
        { title: "Cédula 2",        field: "cedula_2",           titleFormatter: _xlTitleFormatter, width: 100 },
        { title: "Cédula 3",        field: "cedula_3",           titleFormatter: _xlTitleFormatter, width: 100 },
        { title: "Cédula 4",        field: "cedula_4",           titleFormatter: _xlTitleFormatter, width: 100 },
        { title: "Cédula 5",        field: "cedula_5",           titleFormatter: _xlTitleFormatter, width: 100 },
        {
            title: "Duración (min)", field: "duracion_actividad",
            titleFormatter: _xlTitleFormatter, width: 120, hozAlign: "right",
        },
        {
            title: "Latitud", field: "latitud", titleFormatter: _xlTitleFormatter, width: 120,
            formatter: function(cell) {
                const v = cell.getValue();
                return v ? String(v).replace(".", ",") : "";
            },
        },
        {
            title: "Longitud", field: "longitud", titleFormatter: _xlTitleFormatter, width: 120,
            formatter: function(cell) {
                const v = cell.getValue();
                return v ? String(v).replace(".", ",") : "";
            },
        },
        { title: "Observación", field: "observacion", titleFormatter: _xlTitleFormatter, minWidth: 200 },
        {
            title: "Origen", field: "origen",
            titleFormatter: _xlTitleFormatter, formatter: origenBadge, width: 120,
        },
    ],
});

// Adjuntar listeners a los botones ▼ DESPUÉS de que la tabla renderice
tabla.on("tableBuilt", function() {
    document.querySelectorAll(".xl-fb").forEach(btn => {
        btn.addEventListener("click", function(e) {
            e.stopPropagation();
            const field = this.getAttribute("data-field");
            if (_xlOpenField === field) { _xlCloseDropdown(); return; }
            _xlOpenDropdown(field, this);
        });
    });
});

// Exportar Excel
const btnExportar = document.getElementById("btnExportar");
if (btnExportar) {
    btnExportar.addEventListener("click", function() {
        tabla.download("xlsx", "distribucion_operativa.xlsx", { sheetName: "Distribución" });
    });
}

// Contador al filtrar
tabla.on("dataFiltered", function(filters, rows) {
    const el = document.getElementById("totalRegistros");
    if (el) el.textContent = rows.length;
});
