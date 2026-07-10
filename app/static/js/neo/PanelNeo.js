// =====================================
// UTILIDADES
// =====================================

function setField(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value;
}

function limpiarCamposAuto() {
    const selOrden = document.getElementById("orden_trabajo");
    if (selOrden) selOrden.innerHTML = '<option value="">— Seleccione recurso primero —</option>';
    setField("tipo_actividad", "");
    setField("placa",          "");
    setField("tipo_cuadrilla", "");
    setField("meta",           "");
}

function limpiarRecurso() {
    document.getElementById("recurso").innerHTML =
        '<option value="">— Seleccione un recurso —</option>';
    limpiarCamposAuto();
}

function mostrarAlerta(mensaje, tipo) {
    const el = document.getElementById("rptAlerta");
    if (!el) return;
    el.innerHTML =
        `<div class="alert alert-${tipo} alert-dismissible fade show" role="alert">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>${mensaje}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
         </div>`;
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function limpiarAlerta() {
    const el = document.getElementById("rptAlerta");
    if (el) el.innerHTML = "";
}

// =====================================
// CARGAR RECURSOS (fecha + contrato)
// =====================================

async function cargarRecursos() {

    const fecha    = document.getElementById("fecha_reporte").value;
    const contrato = document.getElementById("contrato").value;

    limpiarRecurso();

    if (!fecha || !contrato) return;

    try {

        const params    = new URLSearchParams({ fecha, contrato });
        const respuesta = await fetch("/neo/recursos?" + params);
        const lista     = await respuesta.json();

        const sel = document.getElementById("recurso");

        if (lista.length === 0) {
            sel.innerHTML =
                '<option value="">— Sin recursos para esa fecha y contrato —</option>';
            mostrarAlerta(
                "No se encontraron recursos en la distribución operativa " +
                "para la fecha y contrato seleccionados.",
                "warning"
            );
            return;
        }

        limpiarAlerta();

        lista.forEach(function (r) {
            const opt = document.createElement("option");
            opt.value       = r;
            opt.textContent = r;
            sel.appendChild(opt);
        });

    } catch (err) {
        console.error(err);
    }

}

// =====================================
// CARGAR DATOS OPERATIVOS (+ recurso)
// =====================================

async function cargarDatosOperativos() {

    const fecha    = document.getElementById("fecha_reporte").value;
    const contrato = document.getElementById("contrato").value;
    const recurso  = document.getElementById("recurso").value;

    limpiarCamposAuto();

    if (!fecha || !contrato || !recurso) return;

    try {

        const params    = new URLSearchParams({ fecha, contrato, recurso });
        const respuesta = await fetch("/neo/datos-operativos?" + params);
        const datos     = await respuesta.json();

        if (!datos.success) {
            mostrarAlerta(
                "No se encontraron órdenes de trabajo para la combinación seleccionada.",
                "warning"
            );
            return;
        }

        limpiarAlerta();

        const selOrden = document.getElementById("orden_trabajo");
        selOrden.innerHTML = '<option value="">— Seleccione una orden —</option>';

        const naOpt = document.createElement("option");
        naOpt.value                  = "NA";
        naOpt.textContent            = "NA";
        naOpt.dataset.tipoActividad  = "NA";
        naOpt.dataset.tipoCuadrilla  = "";
        naOpt.dataset.placa          = "";
        naOpt.dataset.meta           = "";
        selOrden.appendChild(naOpt);

        datos.ordenes.forEach(function (o) {
            if (!o.orden_trabajo || o.orden_trabajo === "NA") {
                naOpt.dataset.tipoActividad = o.tipo_actividad || "NA";
                naOpt.dataset.tipoCuadrilla = o.tipo_cuadrilla || "";
                naOpt.dataset.placa         = o.placa          || "";
                naOpt.dataset.meta          = o.meta           || "";
                return;
            }
            const opt = document.createElement("option");
            opt.value                  = o.orden_trabajo;
            opt.textContent            = o.orden_trabajo;
            opt.dataset.tipoActividad  = o.tipo_actividad;
            opt.dataset.tipoCuadrilla  = o.tipo_cuadrilla;
            opt.dataset.placa          = o.placa;
            opt.dataset.meta           = o.meta;
            selOrden.appendChild(opt);
        });

        const totalOrdenes = selOrden.options.length - 1;
        if (totalOrdenes === 1) {
            selOrden.selectedIndex = 1;
            selOrden.dispatchEvent(new Event("change"));
        }

    } catch (err) {
        console.error(err);
    }

}

// =====================================
// LISTENERS: FECHA, CONTRATO, RECURSO
// =====================================

document.getElementById("fecha_reporte")
    .addEventListener("change", cargarRecursos);

document.getElementById("contrato")
    .addEventListener("change", cargarRecursos);

document.getElementById("recurso")
    .addEventListener("change", cargarDatosOperativos);

document.getElementById("orden_trabajo")
    .addEventListener("change", function () {
        const opt = this.options[this.selectedIndex];
        if (!opt || !opt.value) {
            setField("tipo_actividad", "");
            setField("placa",          "");
            setField("tipo_cuadrilla", "");
            setField("meta",           "");
            return;
        }
        const tipoAct = opt.dataset.tipoActividad || "";
        setField("tipo_actividad", tipoAct);
        setField("placa",          opt.dataset.placa         || "");
        setField("tipo_cuadrilla", opt.dataset.tipoCuadrilla || "");
        setField("meta",           opt.dataset.meta           || "");

        if (tipoAct.trim().toLowerCase() === "no aplica") {
            this.value = "NA";
            setField("tipo_actividad", "NA");
        }
    });

// =====================================
// CONTADOR DE CARACTERES
// =====================================

const obsArea  = document.getElementById("observacion");
const charCount = document.getElementById("charCount");

if (obsArea) {
    obsArea.addEventListener("input", function () {
        charCount.textContent = this.value.length + " caracteres";
    });
}

// =====================================
// DURACIÓN (HH:MM:SS)
// =====================================

function calcularDuracion() {

    const inicio = document.getElementById("hora_inicio").value;
    const fin    = document.getElementById("hora_fin").value;
    const chip   = document.getElementById("duracion_display");

    if (!inicio || !fin) {
        chip.textContent = "—";
        document.getElementById("duracion").value = "";
        const ha = document.getElementById("horas_afectadas");
        if (ha) ha.value = "";
        setField("impacto", "");
        return;
    }

    const inicioDate = new Date(`1970-01-01T${inicio}`);
    const finDate    = new Date(`1970-01-01T${fin}`);
    let   diferencia = (finDate - inicioDate) / 1000;

    if (diferencia < 0) {
        mostrarAlerta(
            "La hora de fin debe ser mayor que la hora de inicio.",
            "warning"
        );
        setField("impacto", "");
        return;
    }

    const horas    = Math.floor(diferencia / 3600);
    diferencia    %= 3600;
    const minutos  = Math.floor(diferencia / 60);
    const segundos = Math.floor(diferencia % 60);

    const formato =
        String(horas).padStart(2, "0") + ":" +
        String(minutos).padStart(2, "0") + ":" +
        String(segundos).padStart(2, "0");

    chip.textContent = formato;
    document.getElementById("duracion").value = formato;

    const horasDecimal =
        ((horas * 3600) + (minutos * 60) + segundos) / 3600;

    const ha = document.getElementById("horas_afectadas");
    if (ha) ha.value = horasDecimal.toFixed(6);

    determinarImpacto();

}

// =====================================
// IMPACTO (según tipo de incidencia)
// =====================================

function duracionAMinutos(hhmmss) {
    if (!hhmmss) return 0;
    const p = hhmmss.split(":");
    return (parseInt(p[0]) || 0) * 60 + (parseInt(p[1]) || 0);
}

function determinarImpacto() {

    const select = document.getElementById("tipo_incidencia");
    const option = select.options[select.selectedIndex];
    const impactoEl = document.getElementById("impacto");

    impactoEl.classList.remove("impacto-bajo", "impacto-medio", "impacto-alto");

    if (!option || !option.value) {
        impactoEl.value = "";
        return;
    }

    const tipoNombre = (option.dataset.nombre || option.textContent)
        .trim().toLowerCase();

    const duracionMin = duracionAMinutos(
        document.getElementById("duracion").value
    );

    const impactosAltos = [
        "fuera de ruta", "tiempo muerto", "inicio tardío de labores",
        "salida tardia", "finalización temprana",
        "error en la información", "mal enrutamiento"
    ];

    let impacto = "";

    if (impactosAltos.includes(tipoNombre)) {
        impacto = "Alto";
    } else if (tipoNombre.includes("excede tiempo")) {
        if      (duracionMin > 0  && duracionMin < 15)  impacto = "Bajo";
        else if (duracionMin >= 15 && duracionMin < 25)  impacto = "Medio";
        else if (duracionMin >= 25)                      impacto = "Alto";
    }

    impactoEl.value = impacto;

    if (impacto === "Alto")  impactoEl.classList.add("impacto-alto");
    if (impacto === "Medio") impactoEl.classList.add("impacto-medio");
    if (impacto === "Bajo")  impactoEl.classList.add("impacto-bajo");

    // Afectación económica
    const horas = parseFloat(
        document.getElementById("horas_afectadas")?.value || 0
    ) || 0;

    const tarifas = { "Bajo": 20000, "Medio": 50000, "Alto": 100000 };
    const afEl = document.getElementById("afectacion");
    if (afEl) afEl.value = ((tarifas[impacto] || 0) * horas).toFixed(2);

}

document.getElementById("hora_inicio")
    .addEventListener("input", calcularDuracion);
document.getElementById("hora_fin")
    .addEventListener("input", calcularDuracion);
document.getElementById("tipo_incidencia")
    .addEventListener("change", determinarImpacto);

// =====================================
// SUBIR EVIDENCIA AL SERVIDOR
// =====================================

async function subirEvidencia(numero) {

    const inputEl  = document.getElementById(`evidencia_${numero}`);
    const rutaEl   = document.getElementById(`ruta_evidencia_${numero}`);
    const prevEl   = document.getElementById(`prev${numero}`);
    const phEl     = document.getElementById(`placeholder${numero}`);
    const spinEl   = document.getElementById(`spinner${numero}`);
    const estadoEl = document.getElementById(`estado${numero}`);

    const archivo = inputEl.files[0];
    if (!archivo) return;

    // Mostrar spinner
    spinEl.classList.remove("d-none");
    estadoEl.className = "upload-estado mt-1";
    estadoEl.textContent = "";

    const formData = new FormData();
    formData.append("archivo", archivo);

    try {

        const resp     = await fetch("/neo/subir-evidencia", {
            method: "POST",
            body:   formData
        });
        const resultado = await resp.json();

        if (resultado.success) {

            rutaEl.value = resultado.ruta;

            // Vista previa
            prevEl.src = resultado.url;
            prevEl.classList.add("visible");
            if (phEl) phEl.style.display = "none";

            estadoEl.className   = "upload-estado mt-1 ok";
            estadoEl.innerHTML   =
                `<i class="bi bi-check-circle-fill me-1"></i>Subida correctamente`;

        } else {

            rutaEl.value = "";
            estadoEl.className   = "upload-estado mt-1 err";
            estadoEl.innerHTML   =
                `<i class="bi bi-exclamation-circle-fill me-1"></i>${resultado.mensaje}`;

        }

    } catch (err) {

        rutaEl.value = "";
        estadoEl.className   = "upload-estado mt-1 err";
        estadoEl.textContent = "Error de conexión al subir la imagen.";

    } finally {

        spinEl.classList.add("d-none");

    }

}

// Listeners de file inputs
document.getElementById("evidencia_1")
    .addEventListener("change", () => subirEvidencia(1));
document.getElementById("evidencia_2")
    .addEventListener("change", () => subirEvidencia(2));

// Drag & drop
document.querySelectorAll(".upload-area").forEach(function (area) {

    area.addEventListener("dragover", function (e) {
        e.preventDefault();
        area.classList.add("drag-over");
    });

    area.addEventListener("dragleave", function () {
        area.classList.remove("drag-over");
    });

    area.addEventListener("drop", function (e) {
        e.preventDefault();
        area.classList.remove("drag-over");
        const fileInput = area.querySelector("input[type=file]");
        if (fileInput && e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            fileInput.dispatchEvent(new Event("change"));
        }
    });

});

// =====================================
// GUARDAR REPORTE
// =====================================

function _textoOpcion(selectId) {
    const sel = document.getElementById(selectId);
    if (!sel || sel.selectedIndex < 0) return "";
    const opt = sel.options[sel.selectedIndex];
    return opt ? (opt.dataset.nombre || opt.textContent.trim()) : "";
}

document.getElementById("btnGuardarReporte")
.addEventListener("click", async function () {

    const faltantes = [];

    const fechaVal    = document.getElementById("fecha_reporte").value;
    const contratoVal = document.getElementById("contrato").value;
    const recursoVal  = document.getElementById("recurso").value;
    const ordenVal    = document.getElementById("orden_trabajo").value;
    const horaIVal    = document.getElementById("hora_inicio").value;
    const horaFVal    = document.getElementById("hora_fin").value;
    const tipoIncVal  = document.getElementById("tipo_incidencia").value;
    const obsVal      = document.getElementById("observacion").value.trim();
    const ev1Ruta     = document.getElementById("ruta_evidencia_1").value;

    if (!fechaVal)    faltantes.push("Fecha del Reporte");
    if (!contratoVal) faltantes.push("Contrato");
    if (!recursoVal)  faltantes.push("Recurso");
    if (!horaIVal)    faltantes.push("Hora Inicio");
    if (!horaFVal)    faltantes.push("Hora Fin");
    if (!tipoIncVal)  faltantes.push("Tipo de Incidencia");
    if (!obsVal)      faltantes.push("Observación");
    if (!ev1Ruta)     faltantes.push("Evidencia 1 (debe subirse antes de guardar)");

    if (faltantes.length > 0) {
        mostrarAlerta(
            "<strong>Campos requeridos incompletos:</strong> " +
            faltantes.join(", ") + ".",
            "danger"
        );
        return;
    }

    const payload = {
        fecha_reporte:          fechaVal,
        contrato:               contratoVal,
        recurso:                recursoVal,
        orden_trabajo:          ordenVal,
        placa:                  document.getElementById("placa").value,
        tipo_actividad:         document.getElementById("tipo_actividad").value,
        tipo_cuadrilla:         document.getElementById("tipo_cuadrilla").value,
        meta:                   document.getElementById("meta").value,
        hora_inicio:            horaIVal,
        hora_fin:               horaFVal,
        tipo_incidencia:        tipoIncVal,
        tipo_incidencia_nombre: _textoOpcion("tipo_incidencia"),
        parametro_neo:          document.getElementById("parametro_neo").value,
        parametro_neo_nombre:   document.getElementById("parametro_neo").value
                                    ? _textoOpcion("parametro_neo")
                                    : "",
        observacion:            obsVal,
        duracion:               document.getElementById("duracion").value,
        impacto:                document.getElementById("impacto").value,
        horas_afectadas:        document.getElementById("horas_afectadas").value,
        afectacion:             document.getElementById("afectacion")?.value || "",
        evidencia_1:            ev1Ruta,
        evidencia_2:            document.getElementById("ruta_evidencia_2").value || ""
    };

    const btn = document.getElementById("btnGuardarReporte");
    btn.disabled = true;
    btn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-2"></span>Guardando…';

    try {

        const resp     = await fetch("/neo/guardar-reporte", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify(payload)
        });
        const resultado = await resp.json();

        if (resultado.success) {
            mostrarAlerta(
                `<i class="bi bi-check-circle-fill me-2"></i>${resultado.mensaje}`,
                "success"
            );
            // Limpiar formulario después de 2 s
            setTimeout(() => location.reload(), 2000);
        } else {
            mostrarAlerta(resultado.mensaje, "danger");
        }

    } catch (err) {
        mostrarAlerta("Error de conexión al guardar el reporte.", "danger");
    } finally {
        btn.disabled = false;
        btn.innerHTML =
            '<i class="bi bi-floppy2-fill me-2"></i>Guardar Reporte';
    }

});
