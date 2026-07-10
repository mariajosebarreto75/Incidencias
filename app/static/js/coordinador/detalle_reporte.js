// REPORTE_ID viene inyectado desde el template como variable global

// ---- Upload evidencia coordinador ----
async function subirEvidenciaCoor(numero) {
    const inputEl  = document.getElementById(`ev_coor_${numero}`);
    const rutaEl   = document.getElementById(`ruta_ev_coor_${numero}`);
    const prevEl   = document.getElementById(`prev_coor${numero}`);
    const phEl     = document.getElementById(`ph_coor${numero}`);
    const spinEl   = document.getElementById(`spin_coor${numero}`);
    const estadoEl = document.getElementById(`est_coor${numero}`);
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

// Listeners file inputs
const ev1 = document.getElementById("ev_coor_1");
const ev2 = document.getElementById("ev_coor_2");
if (ev1) ev1.addEventListener("change", () => subirEvidenciaCoor(1));
if (ev2) ev2.addEventListener("change", () => subirEvidenciaCoor(2));

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
