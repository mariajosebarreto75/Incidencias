// REPORTE_ID viene inyectado desde el template como variable global

// ---- Upload evidencia coordinador (prefijo "" = formulario inicial, "edit_" = corrección) ----
async function subirEvidenciaCoor(numero, prefijo) {
    prefijo = prefijo || "";
    const inputEl  = document.getElementById(`${prefijo}ev_coor_${numero}`);
    const rutaEl   = document.getElementById(`${prefijo}ruta_ev_coor_${numero}`);
    const prevEl   = document.getElementById(`${prefijo}prev_coor${numero}`);
    const phEl     = document.getElementById(`${prefijo}ph_coor${numero}`);
    const spinEl   = document.getElementById(`${prefijo}spin_coor${numero}`);
    const estadoEl = document.getElementById(`${prefijo}est_coor${numero}`);
    const archivo  = inputEl.files[0];
    if (!archivo) return;

    spinEl.classList.remove("d-none");
    estadoEl.className   = "upload-estado mt-1";
    estadoEl.textContent = "";

    const fd = new FormData();
    fd.append("archivo", archivo);

    try {
        const resp = await fetch("/coordinador/subir-evidencia-coor", { method: "POST", body: fd });
        const res  = await resp.json();

        if (res.success) {
            rutaEl.value = res.ruta;
            prevEl.src   = res.url;
            prevEl.classList.add("visible");
            phEl.style.display = "none";
            estadoEl.className = "upload-estado mt-1 ok";
            estadoEl.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i>Subida correctamente';
        } else {
            rutaEl.value       = "";
            estadoEl.className = "upload-estado mt-1 err";
            estadoEl.innerHTML = `<i class="bi bi-exclamation-circle-fill me-1"></i>${res.mensaje}`;
        }
    } catch {
        rutaEl.value         = "";
        estadoEl.className   = "upload-estado mt-1 err";
        estadoEl.textContent = "Error de conexión.";
    } finally {
        spinEl.classList.add("d-none");
    }
}

function activarUploadCoor(prefijo) {
    prefijo = prefijo || "";
    const ev1 = document.getElementById(`${prefijo}ev_coor_1`);
    const ev2 = document.getElementById(`${prefijo}ev_coor_2`);
    if (ev1) ev1.addEventListener("change", () => subirEvidenciaCoor(1, prefijo));
    if (ev2) ev2.addEventListener("change", () => subirEvidenciaCoor(2, prefijo));
}

activarUploadCoor("");
activarUploadCoor("edit_");

// Drag & drop
document.querySelectorAll(".upload-area-coor").forEach(function (area) {
    area.addEventListener("dragover",  e => { e.preventDefault(); area.classList.add("drag-over"); });
    area.addEventListener("dragleave", ()  => area.classList.remove("drag-over"));
    area.addEventListener("drop", function (e) {
        e.preventDefault();
        area.classList.remove("drag-over");
        const inp = area.querySelector("input[type=file]");
        if (inp && e.dataTransfer.files.length) {
            inp.files = e.dataTransfer.files;
            inp.dispatchEvent(new Event("change"));
        }
    });
});

// ---- Guardar respuesta ----
const btnResponder = document.getElementById("btnResponder");
if (btnResponder) {
    btnResponder.addEventListener("click", async function () {

        const respuesta     = document.getElementById("respuesta").value.trim();
        const estadoConf    = document.getElementById("estado_conformidad").value;
        const accion        = document.getElementById("accion_a_tomar").value;
        const ev1Ruta       = document.getElementById("ruta_ev_coor_1").value;
        const ev2Ruta       = document.getElementById("ruta_ev_coor_2").value;
        const parametroCoor = document.getElementById("parametro_coor").value;

        const faltantes = [];
        if (!respuesta)  faltantes.push("Respuesta");
        if (!estadoConf) faltantes.push("Estado de conformidad");
        if (!accion)     faltantes.push("Acción a tomar");
        if (!ev1Ruta)    faltantes.push("Evidencia 1 (debe subirse antes de guardar)");

        const alerta = document.getElementById("rptAlerta");

        if (faltantes.length) {
            alerta.innerHTML = `<div class="alert alert-danger alert-dismissible fade show">
                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                <strong>Campos requeridos:</strong> ${faltantes.join(", ")}.
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>`;
            window.scrollTo({ top: 0, behavior: "smooth" });
            return;
        }

        btnResponder.disabled  = true;
        btnResponder.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando…';

        try {
            const resp = await fetch(`/coordinador/reporte/${REPORTE_ID}/responder`, {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    respuesta,
                    parametro_coordinador: parametroCoor,
                    estado_conformidad:    estadoConf,
                    accion_a_tomar:        accion,
                    evidencia_coor_1:      ev1Ruta,
                    evidencia_coor_2:      ev2Ruta,
                })
            });
            const res = await resp.json();

            if (res.success) {
                alerta.innerHTML = `<div class="alert alert-success fade show">
                    <i class="bi bi-check-circle-fill me-2"></i>${res.mensaje}
                </div>`;
                setTimeout(() => location.reload(), 1500);
            } else {
                alerta.innerHTML = `<div class="alert alert-danger alert-dismissible fade show">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>${res.mensaje}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>`;
                btnResponder.disabled  = false;
                btnResponder.innerHTML = '<i class="bi bi-patch-check-fill me-2"></i>Guardar Respuesta';
            }
        } catch {
            alerta.innerHTML = `<div class="alert alert-danger">Error de conexión.</div>`;
            btnResponder.disabled  = false;
            btnResponder.innerHTML = '<i class="bi bi-patch-check-fill me-2"></i>Guardar Respuesta';
        }
    });
}

// ---- Mostrar / cancelar formulario de edición de respuesta ----
const btnMostrarEditar = document.getElementById("btnMostrarEditarRespuesta");
const btnCancelarEditar = document.getElementById("btnCancelarEdicionRespuesta");
const viewLectura = document.getElementById("viewRespuestaLectura");
const formEditar = document.getElementById("formEditarRespuesta");

if (btnMostrarEditar) {
    btnMostrarEditar.addEventListener("click", function () {
        viewLectura.classList.add("d-none");
        formEditar.classList.remove("d-none");
        window.scrollTo({ top: formEditar.offsetTop - 100, behavior: "smooth" });
    });
}
if (btnCancelarEditar) {
    btnCancelarEditar.addEventListener("click", function () {
        formEditar.classList.add("d-none");
        viewLectura.classList.remove("d-none");
    });
}

// ---- Guardar corrección de respuesta (solo una vez) ----
const btnGuardarEdicion = document.getElementById("btnGuardarEdicionRespuesta");
if (btnGuardarEdicion) {
    btnGuardarEdicion.addEventListener("click", async function () {

        const respuesta     = document.getElementById("edit_respuesta").value.trim();
        const estadoConf    = document.getElementById("edit_estado_conformidad").value;
        const accion        = document.getElementById("edit_accion_a_tomar").value;
        const ev1Ruta       = document.getElementById("edit_ruta_ev_coor_1").value;
        const ev2Ruta       = document.getElementById("edit_ruta_ev_coor_2").value;
        const parametroCoor = document.getElementById("edit_parametro_coor").value;

        const faltantes = [];
        if (!respuesta)  faltantes.push("Respuesta");
        if (!estadoConf) faltantes.push("Estado de conformidad");
        if (!accion)     faltantes.push("Acción a tomar");
        if (!ev1Ruta)    faltantes.push("Evidencia 1 (debe subirse antes de guardar)");

        const alerta = document.getElementById("rptAlerta");

        if (faltantes.length) {
            alerta.innerHTML = `<div class="alert alert-danger alert-dismissible fade show">
                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                <strong>Campos requeridos:</strong> ${faltantes.join(", ")}.
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>`;
            window.scrollTo({ top: 0, behavior: "smooth" });
            return;
        }

        if (!confirm("Esta es tu única corrección permitida sobre esta respuesta. ¿Deseas guardarla?")) {
            return;
        }

        btnGuardarEdicion.disabled  = true;
        btnGuardarEdicion.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando…';

        try {
            const resp = await fetch(`/coordinador/reporte/${REPORTE_ID}/editar-respuesta`, {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    respuesta,
                    parametro_coordinador: parametroCoor,
                    estado_conformidad:    estadoConf,
                    accion_a_tomar:        accion,
                    evidencia_coor_1:      ev1Ruta,
                    evidencia_coor_2:      ev2Ruta,
                })
            });
            const res = await resp.json();

            if (res.success) {
                alerta.innerHTML = `<div class="alert alert-success fade show">
                    <i class="bi bi-check-circle-fill me-2"></i>${res.mensaje}
                </div>`;
                setTimeout(() => location.reload(), 1500);
            } else {
                alerta.innerHTML = `<div class="alert alert-danger alert-dismissible fade show">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>${res.mensaje}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>`;
                btnGuardarEdicion.disabled  = false;
                btnGuardarEdicion.innerHTML = '<i class="bi bi-save-fill me-2"></i>Guardar corrección';
            }
        } catch {
            alerta.innerHTML = `<div class="alert alert-danger">Error de conexión.</div>`;
            btnGuardarEdicion.disabled  = false;
            btnGuardarEdicion.innerHTML = '<i class="bi bi-save-fill me-2"></i>Guardar corrección';
        }
    });
}

// ---- Apelar No Conformidad ----
const btnMostrarApelar = document.getElementById("btnMostrarApelar");
const formApelar       = document.getElementById("formApelar");
if (btnMostrarApelar) {
    btnMostrarApelar.addEventListener("click", function () {
        btnMostrarApelar.classList.add("d-none");
        formApelar.classList.remove("d-none");
    });
}

const btnEnviarApelar = document.getElementById("btnEnviarApelar");
if (btnEnviarApelar) {
    btnEnviarApelar.addEventListener("click", async function () {

        const texto = document.getElementById("apelacion_texto").value.trim();
        const alerta = document.getElementById("rptAlerta");

        if (!texto) {
            alerta.innerHTML = `<div class="alert alert-danger alert-dismissible fade show">
                <i class="bi bi-exclamation-triangle-fill me-2"></i>Escriba el motivo de la apelación.
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>`;
            return;
        }

        if (!confirm("Al enviar la apelación el reporte quedará cerrado definitivamente. ¿Deseas continuar?")) {
            return;
        }

        btnEnviarApelar.disabled  = true;
        btnEnviarApelar.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando…';

        try {
            const resp = await fetch(`/coordinador/reporte/${REPORTE_ID}/apelar`, {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ apelacion: texto })
            });
            const res = await resp.json();

            if (res.success) {
                alerta.innerHTML = `<div class="alert alert-success fade show">
                    <i class="bi bi-check-circle-fill me-2"></i>${res.mensaje}
                </div>`;
                setTimeout(() => location.reload(), 1500);
            } else {
                alerta.innerHTML = `<div class="alert alert-danger alert-dismissible fade show">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>${res.mensaje}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>`;
                btnEnviarApelar.disabled  = false;
                btnEnviarApelar.innerHTML = '<i class="bi bi-send-fill me-1"></i>Enviar apelación y cerrar reporte';
            }
        } catch {
            alerta.innerHTML = `<div class="alert alert-danger">Error de conexión.</div>`;
            btnEnviarApelar.disabled  = false;
            btnEnviarApelar.innerHTML = '<i class="bi bi-send-fill me-1"></i>Enviar apelación y cerrar reporte';
        }
    });
}
