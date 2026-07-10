// ====================================
// CONTROL DE CAMBIOS
// ====================================
 
let filasNuevas     = [];
let filasEditadas   = [];
let filasEliminadas = [];
const cuadrillasCache = {}; // { contrato: [cuadrilla1, cuadrilla2, ...] }
 
function marcarCambios() {
 
    const estado = document.getElementById(
        "estadoCambios"
    );
 
    if (estado) {
 
        estado.innerHTML =
            "Cambios sin guardar";
 
        estado.className =
            "badge bg-warning ms-3";
    }
}
async function obtenerCuadrillas(contrato){

    try{

        const respuesta = await fetch(
            "/coordinador/cuadrillas/" +
            encodeURIComponent(contrato)
        );

        return await respuesta.json();

    }
    catch(error){

        console.error(error);

        return [];

    }

}
async function obtenerMeta(
    contrato,
    cuadrilla
){

    try{

        const respuesta =
            await fetch(

                "/coordinador/meta/"
                + encodeURIComponent(
                    contrato
                )
                + "/"
                + encodeURIComponent(
                    cuadrilla
                )

            );

        const resultado =
            await respuesta.json();

        return resultado.meta;

    }
    catch(error){

        console.error(
            error
        );

        return "";

    }

}
 
 
// ====================================
// HORAS (cada 30 minutos)
// ====================================

function generarOpcionesHora() {

    const opciones = [];

    for (let h = 0; h < 24; h++) {

        for (let m = 0; m < 60; m += 30) {

            const periodo = h < 12 ? "a.m." : "p.m.";
            const hora12  = h === 0 ? 12 : h > 12 ? h - 12 : h;
            const minStr  = String(m).padStart(2, "0");
            const horaVal = String(h).padStart(2, "0");

            opciones.push({
                label: `${hora12}:${minStr}:00 ${periodo}`,
                value: `${horaVal}:${minStr}:00`
            });

        }

    }

    return opciones;

}

const opcionesHora = generarOpcionesHora();

function filtroHora(headerValue, rowValue) {
    if (!headerValue) return true;
    const h   = headerValue.toLowerCase().trim();
    const raw = String(rowValue || "").toLowerCase();
    if (raw.includes(h)) return true;
    // Buscar también en formato mostrado "7:00:00 a.m."
    const partes = raw.split(":");
    if (partes.length >= 2) {
        const hr      = parseInt(partes[0]) || 0;
        const min     = partes[1] || "00";
        const sec     = partes[2] || "00";
        const periodo = hr < 12 ? "a.m." : "p.m.";
        const hr12    = hr === 0 ? 12 : hr > 12 ? hr - 12 : hr;
        return `${hr12}:${min}:${sec} ${periodo}`.includes(h);
    }
    return false;
}

function formatearHora(cell) {

    const val = cell.getValue();

    if (!val) return "";

    const partes = String(val).split(":");

    if (partes.length < 2) return val;

    const h       = parseInt(partes[0]);
    const m       = partes[1];
    const s       = partes[2] || "00";
    const periodo = h < 12 ? "a.m." : "p.m.";
    const hora12  = h === 0 ? 12 : h > 12 ? h - 12 : h;

    return `${hora12}:${m}:${s} ${periodo}`;

}

// ====================================
// TABLA
// ====================================

let tabla = new Tabulator(
    "#tablaDistribucion",
    {
 
        data: datosDistribucion,
 
        layout: "fitDataStretch",
 
        height: "75vh",
 
        pagination: true,
 
        paginationSize: 50,
 
        resizableColumns: true,

        movableColumns: true,

        selectableRows: true,
 
        clipboard: true,
 
        clipboardPasteAction: "update",

        tabEndNewRow: true,

        clipboardCopyStyled:false,

        clipboardCopyConfig:{
            rowHeaders:false,
            columnHeaders:true
        },
 
        addRowPos: "top",

        columns: [

            {
                title: "",
                formatter: "rowSelection",
                titleFormatter: "rowSelection",
                hozAlign: "center",
                headerSort: false,
                width: 44,
                resizable: false,
                frozen: true
            },

            {
                title: "ID",
                field: "id",
                headerFilter: true
            },
 
            {
                title: "Fecha",
                field: "fecha",
                frozen: true,

                editor: function(cell, onRendered, success, cancel) {

                    const input = document.createElement("input");
                    input.type  = "date";

                    const hoy    = new Date();
                    const ayer   = new Date(hoy);
                    ayer.setDate(ayer.getDate() - 1);
                    const manana = new Date(hoy);
                    manana.setDate(manana.getDate() + 1);

                    const fmt = d => d.toISOString().split("T")[0];
                    input.min = fmt(ayer);
                    input.max = fmt(manana);

                    input.value = cell.getValue() || fmt(hoy);

                    input.style.cssText =
                        "width:100%;height:100%;box-sizing:border-box;" +
                        "padding:0 4px;border:none;font-size:13px;";

                    onRendered(function() { input.focus(); });

                    input.addEventListener("change", function() {
                        success(input.value);
                    });
                    input.addEventListener("blur", function() {
                        success(input.value);
                    });
                    input.addEventListener("keydown", function(e) {
                        if (e.key === "Escape") cancel();
                    });

                    return input;

                },

                formatter: function(cell) {
                    const val = cell.getValue();
                    if (!val) return "";
                    const p = String(val).split("-");
                    return p.length === 3
                        ? `${p[2]}/${p[1]}/${p[0]}`
                        : val;
                },

                headerFilter: true,
                headerFilterPlaceholder: "DD/MM/AAAA",
                headerFilterFunc: function(headerValue, rowValue) {
                    if (!headerValue) return true;
                    const h   = headerValue.trim();
                    const raw = String(rowValue || "");
                    if (raw.includes(h)) return true;
                    const p = raw.split("-");
                    return p.length === 3
                        ? `${p[2]}/${p[1]}/${p[0]}`.includes(h)
                        : false;
                }
            },

            {
                title: "Contrato",
                field: "contrato",

                editor: "list",

                editorParams: {

                    values: contratosUsuario

                },

                headerFilter: true
            },
 
            {
                title: "Recurso",
                field: "recurso",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Placa",
                field: "placa",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Orden Trabajo",
                field: "orden_trabajo",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Tipo Actividad",
                field: "tipo_actividad",
                editor: "input",
                headerFilter: true,
                cellEdited: function(cell) {
                    const val = (cell.getValue() || "").trim().toLowerCase();
                    if (val === "no aplica") {
                        cell.getRow().getCell("orden_trabajo").setValue("NA");
                    }
                }
            },

            {
                title: "Tipo Cuadrilla",
                field: "tipo_cuadrilla",
                editor: "list",
                editorParams: function(cell) {
                    const contrato = cell.getRow().getData().contrato;
                    const cached   = cuadrillasCache[contrato];
                    const params = { values: null, autocomplete: true, freetext: true, allowEmpty: true, clearable: true, listOnEmpty: true };
                    if (cached) {
                        params.values = cached;
                        return params;
                    }
                    // Carga síncrona usando XMLHttpRequest
                    const xhr = new XMLHttpRequest();
                    xhr.open("GET", "/coordinador/cuadrillas/" + encodeURIComponent(contrato), false);
                    xhr.send();
                    const lista = xhr.status === 200 ? JSON.parse(xhr.responseText) : [];
                    cuadrillasCache[contrato] = lista;
                    params.values = lista;
                    return params;
                },
                headerFilter: true
            },

            {
                title: "Hora Salida",
                field: "hora_salida_sede",
                editor: "list",
                editorParams: {
                    values: opcionesHora,
                    clearable: true
                },
                formatter: formatearHora,
                headerFilter: true,
                headerFilterPlaceholder: "ej: 7:00, a.m.",
                headerFilterFunc: filtroHora
            },

            {
                title: "Hora Llegada",
                field: "hora_llegada_sede",
                editor: "list",
                editorParams: {
                    values: opcionesHora,
                    clearable: true
                },
                formatter: formatearHora,
                headerFilter: true,
                headerFilterPlaceholder: "ej: 16:00, p.m.",
                headerFilterFunc: filtroHora
            },
 
            {
                title: "Cedula 1",
                field: "cedula_1",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Nombre 1",
                field: "nombre_1",
                headerFilter: true
            },
 
 
            {
                title: "Cedula 2",
                field: "cedula_2",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Cedula 3",
                field: "cedula_3",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Cedula 4",
                field: "cedula_4",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Cedula 5",
                field: "cedula_5",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Celular",
                field: "numero_celular",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Latitud",
                field: "latitud",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Longitud",
                field: "longitud",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Duración (min)",
                field: "duracion_actividad",
                editor: "number",
                editorParams: {
                    min: 1,
                    step: 1
                },
                validator: ["integer", "min:1"],
                formatter: function(cell) {
                    const val = cell.getValue();
                    if (!val && val !== 0) return "";
                    return `${val} min`;
                },
                headerFilter: true,
                headerFilterPlaceholder: "ej: 60",
                headerFilterFunc: function(headerValue, rowValue) {
                    if (!headerValue) return true;
                    const h = String(headerValue).toLowerCase().trim();
                    const raw = String(rowValue || "").toLowerCase();
                    return raw.includes(h) || `${raw} min`.includes(h);
                }
            },
 
            {
                title: "Observación",
                field: "observacion",
                editor: "input",
                headerFilter: true
            },
 
            {
                title: "Meta",
                field: "meta",
                headerFilter: true
            }
 
        ]
 
    }
);
 
 
// ====================================
// FORMATO DE COORDENADAS
// ====================================

function formatearCoordenada(valor, posicionComa) {

    if (!valor && valor !== 0) return valor;

    const str = String(valor).trim();

    // Ya tiene coma → formato correcto, no tocar
    if (str.includes(",")) return str;

    // Tiene punto decimal → convertir a coma (4.8893 → 4,8893)
    if (str.includes(".")) return str.replace(".", ",");

    const negativo = str.startsWith("-");
    const digitos  = negativo ? str.slice(1) : str;

    // Solo aplica si son puramente dígitos
    if (!/^\d+$/.test(digitos)) return str;

    if (digitos.length <= posicionComa) return str;

    const formateado =
        digitos.slice(0, posicionComa) + "," + digitos.slice(posicionComa);

    return negativo ? "-" + formateado : formateado;

}

// ====================================
// EVENTO EDICION
// ====================================

tabla.on(
    "cellEdited",
    function(cell){

        let campo =
            cell.getField();

        // Formatear coordenadas antes de capturar fila
        if (campo === "latitud" || campo === "longitud") {

            const posicion = campo === "latitud" ? 1 : 2;
            const valorActual = cell.getValue();
            const formateado  = formatearCoordenada(valorActual, posicion);

            if (formateado !== String(valorActual || "")) {
                cell.getRow().update({ [campo]: formateado });
            }

        }

        let fila =
            structuredClone(
                cell.getRow().getData()
            );

        console.log(
            "CELDA EDITADA"
        );

        console.log(
            fila
        );

        // Buscar persona al editar cedula_1
        if (campo === "cedula_1") {
            buscarYmostrarPersona(cell.getRow(), 1);
        }

        if(
            campo === "tipo_cuadrilla"
        ){
            const nuevaCuadrilla = cell.getValue();
            const contratoFila   = fila.contrato;
            const row            = cell.getRow(); // guardar ref antes del async

            console.log("[meta] contrato:", contratoFila, "| cuadrilla:", nuevaCuadrilla);

            if (nuevaCuadrilla && contratoFila) {
                obtenerMeta(contratoFila, nuevaCuadrilla)
                    .then(function(meta){
                        console.log("[meta] resultado:", meta);
                        row.update({ meta: meta });
                    });
            }
        }
        if(
            fila.nueva
        ){
            return;
        }
        


        let existe =
            filasEditadas.find(
                x => x.id === fila.id
            );
 
        if(!existe){
 
            filasEditadas.push(
                fila
            );
 
        }else{
 
            let indice =
                filasEditadas.findIndex(
                    x => x.id === fila.id
                );
 
            filasEditadas[indice] =
                fila;
        }
 
        console.log(
            "FILAS EDITADAS:"
        );
 
        console.log(
            filasEditadas
        );
 
        marcarCambios();
 
    }
);
 
 
// ====================================
// AGREGAR FILA
// ====================================
 
document
.getElementById("btnAgregarFila")
.addEventListener(
    "click",
    function(){
 
        let nuevaFila = {
 
            nueva: true
 
        };
 
        tabla.addRow(
            nuevaFila,
            true
        );
 
        filasNuevas.push(
            nuevaFila
        );
 
        marcarCambios();
 
    }
);
 
 
// ====================================
// ELIMINAR FILAS
// ====================================
 
document
.getElementById("btnEliminar")
.addEventListener(
    "click",
    function(){
 
        let filas =
            tabla.getSelectedRows();
 
        filas.forEach(
            function(fila){
 
                let datos =
                    fila.getData();
 
                filasEliminadas.push(
                    datos
                );
 
                fila.delete();
 
            }
        );
 
        marcarCambios();
 
    }
);
 
 
// ====================================
// VALIDACIÓN VISUAL DE FILAS NUEVAS
// ====================================

const REGEX_PLACA = /^[A-Za-z]{3}[A-Za-z0-9]{2,3}$/;

function resaltarCeldaError(fila, campo) {

    const celda = fila.getCell(campo);

    if (celda) {
        celda.getElement().classList.add("celda-error");
    }

}

function limpiarErroresCeldas() {

    tabla.getRows().forEach(function(fila) {

        fila.getCells().forEach(function(celda) {

            celda.getElement().classList.remove("celda-error");

        });

    });

}

function mostrarAlertaGuardar(mensaje, tipo) {

    const contenedor =
        document.getElementById("alertaGuardar");

    if (!contenedor) return;

    contenedor.innerHTML =
        `<div class="alert alert-${tipo} alert-dismissible fade show py-2 mb-0" role="alert">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>${mensaje}
            <button type="button" class="btn-close btn-sm" data-bs-dismiss="alert"></button>
        </div>`;

}

function limpiarAlertaGuardar() {

    const contenedor =
        document.getElementById("alertaGuardar");

    if (contenedor) contenedor.innerHTML = "";

}

function validarFilasNuevas() {

    const errores = [];

    tabla.getRows().forEach(function(fila) {

        const datos = fila.getData();

        if (!datos.nueva) return;

        if (!datos.recurso) {
            errores.push({ fila, campo: "recurso" });
        }

        const placa = String(datos.placa || "").trim();

        if (!placa || !REGEX_PLACA.test(placa)) {
            errores.push({ fila, campo: "placa" });
        }

        if (!datos.fecha) {
            errores.push({ fila, campo: "fecha" });
        }

        if (datos.duracion_actividad !== "" && datos.duracion_actividad != null) {

            const dur = Number(datos.duracion_actividad);

            if (!Number.isInteger(dur) || dur <= 0) {
                errores.push({ fila, campo: "duracion_actividad" });
            }

        }

    });

    return errores;

}

// ====================================
// GUARDAR
// ====================================

document
.getElementById(
    "btnGuardar"
)
.addEventListener(
    "click",
    async function(){

        limpiarAlertaGuardar();
        limpiarErroresCeldas();

        // Validación cliente: campos obligatorios y formatos
        const errores = validarFilasNuevas();

        if (errores.length > 0) {

            errores.forEach(function(e) {
                resaltarCeldaError(e.fila, e.campo);
            });

            mostrarAlertaGuardar(
                "Corrige los campos marcados en rojo antes de guardar.",
                "danger"
            );

            return;

        }

        const respuesta =
            await fetch(
                "/coordinador/guardar-distribucion",
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json"
                    },

                    body: JSON.stringify({
                        filasNuevas,
                        filasEditadas,
                        filasEliminadas
                    })
                }
            );

        const resultado = await respuesta.json();

        if (resultado.success) {

            location.reload();

        } else {

            mostrarAlertaGuardar(resultado.mensaje, "danger");

        }

    }
);
// ====================================
// EXPORTAR EXCEL
// ====================================

document
.getElementById("btnExportar")
.addEventListener(
    "click",
    function(){

        tabla.download(
            "xlsx",
            "distribucion_operativa.xlsx",
            {},
            "active"
        );

    }
);

// ====================================
// BUSCAR PERSONA
// ====================================

async function buscarYmostrarPersona(row, numero) {

    const datos  = row.getData();
    const cedula = datos["cedula_" + numero];

    if (!cedula) return;

    try {

        const respuesta = await fetch(
            "/coordinador/buscar-persona/" +
            encodeURIComponent(cedula)
        );

        const resultado = await respuesta.json();

        if (resultado.success) {

            row.update({
                ["nombre_" + numero]: resultado.nombre,
                ["cargo_"  + numero]: resultado.cargo
            });

        } else {

            mostrarAlertaGuardar(
                `La cédula <strong>${cedula}</strong> no está registrada en el sistema. ` +
                `Comuníquese con el administrador para que agregue la persona. ` +
                `El nombre aparecerá automáticamente una vez registrada.`,
                "warning"
            );

        }

    } catch (error) {
        console.error(error);
    }

}

