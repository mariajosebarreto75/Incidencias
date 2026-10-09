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
const _xlFilters = {};      // field -> Set de valores raw seleccionados
let _xlDropdown = null;
let _xlDropdownField = null;

function _xlUniqueVals(field) {
    const seen = new Map(); // raw -> display
    (datosDistribucion || []).forEach(row => {
        const raw = String(row[field] ?? "");
        const disp = field === "fecha" ? fmtFecha(raw) : raw;
        if (raw !== "") seen.set(raw, disp || raw);
    });
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1], "es"));
}

function _xlIsFiltered(field) {
    const sel = _xlFilters[field];
    if (!sel) return false;
    return sel.size < _xlUniqueVals(field).length;
}

function _xlApply() {
    const active = Object.keys(_xlFilters).filter(f => _xlIsFiltered(f));
    if (active.length === 0) { tabla.clearFilter(); return; }
    tabla.setFilter(function(data) {
        return active.every(field => {
            const raw = String(data[field] ?? "");
            return _xlFilters[field].has(raw);
        });
    });
}

function _xlUpdateBtn(field) {
    document.querySelectorAll(`.xl-fb[data-field="${field}"]`).forEach(btn => {
        const f = _xlIsFiltered(field);
        btn.style.color = f ? "#007d8a" : "#94a3b8";
        btn.style.fontWeight = f ? "800" : "400";
        btn.title = f ? "Filtro activo" : "Filtrar";
    });
}

function xlFilterOpen(field, btnEl) {
    if (_xlDropdown) {
        _xlDropdown.remove();
        _xlDropdown = null;
        if (_xlDropdownField === field) { _xlDropdownField = null; return; }
    }
    _xlDropdownField = field;

    const entries = _xlUniqueVals(field);
    if (!_xlFilters[field]) _xlFilters[field] = new Set(entries.map(e => e[0]));
    const selected = _xlFilters[field];

    const rect = btnEl.getBoundingClientRect();
    const div = document.createElement("div");
    div.id = "xlFDD";
    const left = Math.min(rect.left, window.innerWidth - 230);
    div.style.cssText = `
        position:fixed;z-index:10000;
        top:${rect.bottom + 4}px;left:${left}px;
        background:#fff;border:1.5px solid #00b8c9;border-radius:8px;
        padding:10px 8px 8px;box-shadow:0 6px 24px rgba(0,0,0,.18);
        min-width:210px;max-width:290px;
        display:flex;flex-direction:column;
        font-size:.82rem;font-family:inherit;
    `;

    // Botones Todos / Ninguno
    const tb = document.createElement("div");
    tb.style.cssText = "display:flex;gap:6px;margin-bottom:8px;";
    [["Todos", true], ["Ninguno", false]].forEach(([label, all]) => {
        const btn = document.createElement("button");
        btn.textContent = label;
        btn.style.cssText = `flex:1;font-size:.74rem;padding:3px 0;border-radius:4px;cursor:pointer;
            border:1px solid ${all ? "#00b8c9" : "#d1d5db"};
            background:${all ? "#e6fafb" : "#f9fafb"};
            color:${all ? "#007d8a" : "#6b7280"};`;
        btn.onclick = () => {
            all ? entries.forEach(e => selected.add(e[0])) : selected.clear();
            div.querySelectorAll("input[type=checkbox]").forEach(cb => cb.checked = all);
            _xlUpdateBtn(field); _xlApply();
        };
        tb.appendChild(btn);
    });
    div.appendChild(tb);

    const sep = document.createElement("div");
    sep.style.cssText = "border-top:1px solid #e2e8f0;margin-bottom:6px;";
    div.appendChild(sep);

    // Buscador dentro del dropdown
    const search = document.createElement("input");
    search.type = "text";
    search.placeholder = "Buscar…";
    search.style.cssText = `width:100%;margin-bottom:6px;padding:3px 7px;
        border:1px solid #00b8c9;border-radius:4px;font-size:.78rem;background:#f0fdfe;outline:none;`;
    div.appendChild(search);

    const list = document.createElement("div");
    list.style.cssText = "overflow-y:auto;max-height:240px;display:flex;flex-direction:column;gap:1px;";

    function renderList(filter) {
        list.innerHTML = "";
        entries.filter(([, d]) => !filter || d.toLowerCase().includes(filter.toLowerCase())).forEach(([raw, disp]) => {
            const lbl = document.createElement("label");
            lbl.style.cssText = "display:flex;align-items:center;gap:7px;padding:4px 6px;cursor:pointer;border-radius:4px;";
            lbl.onmouseover = () => lbl.style.background = "#f0f9fb";
            lbl.onmouseout = () => lbl.style.background = "";
            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.checked = selected.has(raw);
            cb.style.accentColor = "#00b8c9";
            cb.onchange = () => {
                cb.checked ? selected.add(raw) : selected.delete(raw);
                _xlUpdateBtn(field); _xlApply();
            };
            lbl.appendChild(cb);
            lbl.appendChild(document.createTextNode(disp || "(vacío)"));
            list.appendChild(lbl);
        });
    }

    renderList("");
    search.oninput = () => renderList(search.value);
    div.appendChild(list);
    document.body.appendChild(div);
    _xlDropdown = div;

    setTimeout(() => {
        document.addEventListener("click", function closeDD(e) {
            if (!div.contains(e.target) && !e.target.classList.contains("xl-fb")) {
                div.remove(); _xlDropdown = null; _xlDropdownField = null;
                document.removeEventListener("click", closeDD);
            }
        });
    }, 60);
}

function _xlTitle(cell) {
    const field = cell.getColumn().getField();
    const title = cell.getValue();
    return `<span class="xl-title-wrap">
        <span>${title}</span>
        <button class="xl-fb" data-field="${field}"
            onclick="event.stopPropagation();xlFilterOpen('${field}',this)"
            title="Filtrar">▼</button>
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
            titleFormatter: _xlTitle,
            formatter: function(cell) { return fmtFecha(cell.getValue()); },
        },
        { title: "Contrato",       field: "contrato",           titleFormatter: _xlTitle, minWidth: 220 },
        { title: "Recurso",        field: "recurso",            titleFormatter: _xlTitle, minWidth: 140 },
        { title: "Placa",          field: "placa",              titleFormatter: _xlTitle, width: 100 },
        { title: "Orden Trabajo",  field: "orden_trabajo",      titleFormatter: _xlTitle, minWidth: 130 },
        { title: "Tipo Actividad", field: "tipo_actividad",     titleFormatter: _xlTitle, minWidth: 160 },
        { title: "Tipo Cuadrilla", field: "tipo_cuadrilla",     titleFormatter: _xlTitle, minWidth: 150 },
        { title: "Cédula 1",       field: "cedula_1",           titleFormatter: _xlTitle, width: 110 },
        { title: "Nombre",         field: "nombre_1",           titleFormatter: _xlTitle, minWidth: 180 },
        { title: "Cédula 2",       field: "cedula_2",           titleFormatter: _xlTitle, width: 100 },
        { title: "Cédula 3",       field: "cedula_3",           titleFormatter: _xlTitle, width: 100 },
        { title: "Cédula 4",       field: "cedula_4",           titleFormatter: _xlTitle, width: 100 },
        { title: "Cédula 5",       field: "cedula_5",           titleFormatter: _xlTitle, width: 100 },
        {
            title: "Duración (min)", field: "duracion_actividad",
            titleFormatter: _xlTitle, width: 120, hozAlign: "right",
        },
        {
            title: "Latitud", field: "latitud", titleFormatter: _xlTitle, width: 120,
            formatter: function(cell) {
                const v = cell.getValue();
                return v ? String(v).replace(".", ",") : "";
            },
        },
        {
            title: "Longitud", field: "longitud", titleFormatter: _xlTitle, width: 120,
            formatter: function(cell) {
                const v = cell.getValue();
                return v ? String(v).replace(".", ",") : "";
            },
        },
        { title: "Observación", field: "observacion", titleFormatter: _xlTitle, minWidth: 200 },
        {
            title: "Origen", field: "origen",
            titleFormatter: _xlTitle, formatter: origenBadge, width: 120,
        },
    ],
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
