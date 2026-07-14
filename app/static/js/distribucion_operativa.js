// Distribución Operativa — solo lectura, datos desde GPS Monitor
// ====================================================

function fmtFecha(val) {
    if (!val) return "";
    const p = String(val).split("-");
    return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : val;
}

function origenBadge(cell) {
    const v = (cell.getValue() || "").toLowerCase();
    if (v === "gps_monitor") {
        return `<span class="badge" style="background:#0ea5e9;font-size:11px;">GPS Monitor</span>`;
    }
    return `<span class="badge bg-secondary" style="font-size:11px;">Manual</span>`;
}

let tabla = new Tabulator("#tablaDistribucion", {
    data: datosDistribucion,
    layout: "fitDataStretch",
    height: "72vh",
    pagination: true,
    paginationSize: 50,
    resizableColumns: true,
    movableColumns: true,
    clipboard: true,
    clipboardCopyStyled: false,
    clipboardCopyConfig: { rowHeaders: false, columnHeaders: true },
    columns: [
        {
            title: "Fecha",
            field: "fecha",
            frozen: true,
            formatter: function(cell) { return fmtFecha(cell.getValue()); },
            headerFilter: true,
            headerFilterPlaceholder: "DD/MM/AAAA",
            headerFilterFunc: function(hv, rv) {
                if (!hv) return true;
                const raw = String(rv || "");
                if (raw.includes(hv)) return true;
                const p = raw.split("-");
                return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}`.includes(hv) : false;
            },
            width: 110,
        },
        {
            title: "Contrato",
            field: "contrato",
            headerFilter: true,
            minWidth: 220,
        },
        {
            title: "Recurso",
            field: "recurso",
            headerFilter: true,
            minWidth: 140,
        },
        {
            title: "Placa",
            field: "placa",
            headerFilter: true,
            width: 100,
        },
        {
            title: "Orden Trabajo",
            field: "orden_trabajo",
            headerFilter: true,
            minWidth: 130,
        },
        {
            title: "Tipo Actividad",
            field: "tipo_actividad",
            headerFilter: true,
            minWidth: 160,
        },
        {
            title: "Tipo Cuadrilla",
            field: "tipo_cuadrilla",
            headerFilter: true,
            minWidth: 150,
        },
        {
            title: "Cédula 1",
            field: "cedula_1",
            headerFilter: true,
            width: 110,
        },
        {
            title: "Nombre",
            field: "nombre_1",
            headerFilter: true,
            minWidth: 180,
        },
        {
            title: "Cédula 2",
            field: "cedula_2",
            headerFilter: true,
            width: 100,
        },
        {
            title: "Cédula 3",
            field: "cedula_3",
            headerFilter: true,
            width: 100,
        },
        {
            title: "Cédula 4",
            field: "cedula_4",
            headerFilter: true,
            width: 100,
        },
        {
            title: "Cédula 5",
            field: "cedula_5",
            headerFilter: true,
            width: 100,
        },
        {
            title: "Meta",
            field: "meta",
            headerFilter: false,
            width: 120,
            hozAlign: "right",
            formatter: function(cell) {
                const v = cell.getValue();
                if (v === null || v === undefined || v === "") return "—";
                return "$ " + Number(v).toLocaleString("es-CO", {
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 0
                });
            },
        },
        {
            title: "Duración (min)",
            field: "duracion_actividad",
            headerFilter: true,
            width: 120,
            hozAlign: "right",
        },
        {
            title: "Latitud",
            field: "latitud",
            headerFilter: true,
            width: 120,
            formatter: function(cell) {
                const v = cell.getValue();
                return v ? String(v).replace(".", ",") : "";
            },
        },
        {
            title: "Longitud",
            field: "longitud",
            headerFilter: true,
            width: 120,
            formatter: function(cell) {
                const v = cell.getValue();
                return v ? String(v).replace(".", ",") : "";
            },
        },
        {
            title: "Observación",
            field: "observacion",
            headerFilter: true,
            minWidth: 200,
        },
        {
            title: "Origen",
            field: "origen",
            formatter: origenBadge,
            headerFilter: true,
            width: 120,
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

// Actualizar contador al filtrar
tabla.on("dataFiltered", function(filters, rows) {
    const el = document.getElementById("totalRegistros");
    if (el) el.textContent = rows.length;
});

// El filtro de contrato se maneja desde el template (acceso a variable tabla via window)
