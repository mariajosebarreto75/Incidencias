"""
Servicio de escalamiento de incidencias críticas.
Gestiona el ciclo: NEO → Supervisor → Coordinador → Director → Gerencia
con notificaciones en app y WhatsApp (Twilio).
"""
import logging
from datetime import datetime, timedelta

from flask import current_app

from app.extensions import db
from app.models.escalamiento import EscalamientoIncidencia, TIPOS_ESCALABLES
from app.models.notificacion import Notificacion
from app.models.user import User
from app.models.user_contrato import UserContrato

log = logging.getLogger(__name__)

TIMEOUT_MINUTOS = 10  # minutos antes de escalar


# ─────────────────────────────────────────────
# WhatsApp (Twilio)
# ─────────────────────────────────────────────

def _enviar_whatsapp(numero: str, mensaje: str) -> bool:
    """Envía mensaje WhatsApp por Twilio. Retorna True si fue exitoso."""
    sid   = current_app.config.get("TWILIO_ACCOUNT_SID")
    token = current_app.config.get("TWILIO_AUTH_TOKEN")
    from_ = current_app.config.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    if not sid or not token:
        log.warning("Twilio no configurado — mensaje no enviado a %s", numero)
        return False

    if not numero or not numero.startswith("+"):
        log.warning("Número WhatsApp inválido: %s", numero)
        return False

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        client.messages.create(
            from_=from_,
            to=f"whatsapp:{numero}",
            body=mensaje,
        )
        log.info("WhatsApp enviado a %s", numero)
        return True
    except Exception as exc:
        log.error("Error Twilio: %s", exc)
        return False


# ─────────────────────────────────────────────
# Notificaciones en app
# ─────────────────────────────────────────────

def _notif_app(username: str, reporte, tipo: str, mensaje: str):
    """Crea notificación en app para un usuario."""
    n = Notificacion(
        usuario_destino = username,
        tipo            = tipo,
        reporte_id      = reporte.id,
        mensaje         = mensaje,
        contrato        = reporte.contrato,
        recurso         = reporte.recurso,
        fecha_reporte   = str(reporte.fecha_reporte),
        tipo_incidencia = reporte.tipo_incidencia,
    )
    db.session.add(n)


# ─────────────────────────────────────────────
# Lookup de usuarios por rol y contrato
# ─────────────────────────────────────────────

def _usuarios_rol_contrato(rol: str, contrato: str) -> list[User]:
    """Devuelve usuarios activos con el rol dado asignados al contrato."""
    ucs = UserContrato.query.filter_by(contrato=contrato).all()
    ids = [uc.user_id for uc in ucs]
    if not ids:
        return []
    return User.query.filter(
        User.id.in_(ids),
        User.rol == rol,
        User.activo == True,
    ).all()


def _usuarios_rol_global(rol: str) -> list[User]:
    """Devuelve usuarios activos con el rol dado (sin filtro de contrato)."""
    return User.query.filter_by(rol=rol, activo=True).all()


# ─────────────────────────────────────────────
# Texto de los mensajes
# ─────────────────────────────────────────────

def _texto_incidencia(reporte) -> str:
    duracion = f"{reporte.duracion} min" if reporte.duracion else "duración no registrada"
    return (
        f"*{reporte.tipo_incidencia}* en recurso *{reporte.recurso}*"
        f" ({reporte.placa or 'sin placa'}), contrato {reporte.contrato}."
        f" Duración: {duracion}. Reportado por: {reporte.reportado_por or 'NEO'}."
    )


# ─────────────────────────────────────────────
# Inicio del escalamiento
# ─────────────────────────────────────────────

def iniciar_escalamiento(reporte) -> EscalamientoIncidencia | None:
    """
    Llama esto cuando NEO crea un reporte con tipo escalable.
    Notifica a supervisores del contrato y crea el registro de escalamiento.
    """
    if reporte.tipo_incidencia not in TIPOS_ESCALABLES:
        return None

    # ¿Ya existe un escalamiento activo para este reporte?
    existente = EscalamientoIncidencia.query.filter_by(reporte_id=reporte.id).first()
    if existente:
        return existente

    esc = EscalamientoIncidencia(
        reporte_id   = reporte.id,
        estado       = "supervisor_notificado",
        notificado_at = datetime.utcnow(),
    )
    db.session.add(esc)

    info = _texto_incidencia(reporte)
    supervisores = _usuarios_rol_contrato("supervisor", reporte.contrato)

    for sup in supervisores:
        _notif_app(
            sup.username, reporte,
            tipo    = "escalamiento_supervisor",
            mensaje = f"🚨 Incidencia activa: {info} Ingresa a la app para gestionar.",
        )
        if sup.telefono_whatsapp:
            _enviar_whatsapp(
                sup.telefono_whatsapp,
                f"🚨 INCIDENCIA ACTIVA\n{info}\nIngresa a la app para gestionar: "
                f"{current_app.config.get('APP_URL', 'http://localhost:5000')}/neo/reporte/{reporte.id}",
            )

    if not supervisores:
        log.warning("No hay supervisores para contrato %s — escalando a coordinador", reporte.contrato)
        _escalar_a_coordinador(esc, reporte, "No hay supervisores asignados al contrato.")

    db.session.commit()
    return esc


# ─────────────────────────────────────────────
# Acciones de escalamiento interno
# ─────────────────────────────────────────────

def _preguntar_neo(esc: EscalamientoIncidencia, reporte, nuevo_estado: str):
    """Envía mensaje en app a NEO preguntando si la incidencia sigue activa."""
    esc.estado = nuevo_estado
    esc.notificado_at = datetime.utcnow()
    esc.respuesta_neo = None

    neo_users = _usuarios_rol_contrato("neo", reporte.contrato)
    if not neo_users:
        neo_users = _usuarios_rol_global("neo")

    info = _texto_incidencia(reporte)
    for neo in neo_users:
        _notif_app(
            neo.username, reporte,
            tipo    = "escalamiento_check_neo",
            mensaje = (
                f"⚠️ El supervisor no respondió a la incidencia: {info} "
                f"¿La incidencia SIGUE presentándose? "
                f"Responde en: /neo/escalamiento/{esc.id}/responder"
            ),
        )


def _escalar_a_coordinador(esc: EscalamientoIncidencia, reporte, motivo: str = ""):
    esc.estado = "coordinador_notificado"
    esc.notificado_at = datetime.utcnow()

    coordinadores = _usuarios_rol_contrato("coordinador", reporte.contrato)
    info = _texto_incidencia(reporte)
    msg_app = (
        f"🔴 Incidencia no gestionada por supervisor: {info} {motivo}"
    )
    msg_wa = (
        f"🔴 INCIDENCIA NO GESTIONADA\n{info}\n"
        f"El supervisor no respondió. Requiere tu gestión.\n"
        f"{current_app.config.get('APP_URL','')}/neo/reporte/{reporte.id}"
    )
    for coord in coordinadores:
        _notif_app(coord.username, reporte, "escalamiento_coordinador", msg_app)
        if coord.telefono_whatsapp:
            _enviar_whatsapp(coord.telefono_whatsapp, msg_wa)

    if not coordinadores:
        log.warning("No hay coordinadores para contrato %s", reporte.contrato)


def _escalar_a_director(esc: EscalamientoIncidencia, reporte, motivo: str = ""):
    esc.estado = "director_notificado"
    esc.notificado_at = datetime.utcnow()

    directores = _usuarios_rol_global("director")
    info = _texto_incidencia(reporte)
    msg_app = f"🚨 Incidencia sin gestión de supervisor ni coordinador: {info} {motivo}"
    msg_wa = (
        f"🚨 INCIDENCIA SIN GESTIÓN\n{info}\n"
        f"Ni supervisor ni coordinador han gestionado esta incidencia.\n"
        f"{current_app.config.get('APP_URL','')}/neo/reporte/{reporte.id}"
    )
    for dir_ in directores:
        _notif_app(dir_.username, reporte, "escalamiento_director", msg_app)
        if dir_.telefono_whatsapp:
            _enviar_whatsapp(dir_.telefono_whatsapp, msg_wa)


def _escalar_a_gerencia(esc: EscalamientoIncidencia, reporte):
    esc.estado = "gerencia_notificada"
    esc.notificado_at = datetime.utcnow()

    gerentes = _usuarios_rol_global("gerente") + _usuarios_rol_global("subgerente")
    info = _texto_incidencia(reporte)
    msg_wa = (
        f"⛔ INCIDENCIA SIN GESTIÓN DIRECTIVA\n{info}\n"
        f"Supervisor, coordinador y director no gestionaron esta incidencia.\n"
        f"Reporte: {current_app.config.get('APP_URL','')}/neo/reporte/{reporte.id}"
    )
    for ger in gerentes:
        _notif_app(
            ger.username, reporte,
            "escalamiento_gerencia",
            f"⛔ Incidencia no gestionada en ningún nivel: {info}",
        )
        if ger.telefono_whatsapp:
            _enviar_whatsapp(ger.telefono_whatsapp, msg_wa)


# ─────────────────────────────────────────────
# Respuesta de NEO
# ─────────────────────────────────────────────

def registrar_respuesta_neo(esc_id: int, sigue_activa: bool, username: str) -> dict:
    """
    Llama esto cuando NEO responde si la incidencia sigue activa.
    Retorna {"ok": True/False, "mensaje": str}
    """
    esc = EscalamientoIncidencia.query.get(esc_id)
    if not esc:
        return {"ok": False, "mensaje": "Escalamiento no encontrado"}

    if esc.estado not in ("esperando_neo_1", "esperando_neo_2"):
        return {"ok": False, "mensaje": "Este escalamiento no está esperando respuesta de NEO"}

    esc.respuesta_neo    = sigue_activa
    esc.respuesta_neo_at = datetime.utcnow()
    reporte = esc.reporte

    if sigue_activa:
        if esc.estado == "esperando_neo_1":
            _escalar_a_coordinador(esc, reporte, "NEO confirma que sigue activa.")
        else:  # esperando_neo_2
            _escalar_a_director(esc, reporte, "NEO confirma que sigue activa. Coordinador no gestionó.")
    else:
        # Ya no se presenta — notificar al nivel correspondiente que quedó sin gestión
        esc.estado = "cerrado_sin_gestion"
        _notificar_cierre_sin_gestion(esc, reporte)

    db.session.commit()
    return {"ok": True, "mensaje": "Respuesta registrada"}


def _notificar_cierre_sin_gestion(esc: EscalamientoIncidencia, reporte):
    """Notifica al coordinador/director que la incidencia ya no se presenta pero no fue gestionada."""
    info = _texto_incidencia(reporte)
    if esc.respuesta_neo_at:
        # determinar a quién notificar según el estado anterior
        pass  # la notificación al coordinador de que hay un reporte pendiente ya existe en el flujo

    coordinadores = _usuarios_rol_contrato("coordinador", reporte.contrato)
    for coord in coordinadores:
        _notif_app(
            coord.username, reporte,
            "escalamiento_pendiente",
            f"📋 Incidencia ya no activa pero SIN gestión de supervisor: {info} Queda pendiente de cierre.",
        )


# ─────────────────────────────────────────────
# Gestión por supervisor/coordinador/director
# ─────────────────────────────────────────────

def gestionar_escalamiento(esc_id: int, usuario: User, notas: str = "") -> dict:
    """El supervisor, coordinador o director cierra el escalamiento."""
    esc = EscalamientoIncidencia.query.get(esc_id)
    if not esc:
        return {"ok": False, "mensaje": "No encontrado"}

    estados_activos = (
        "supervisor_notificado", "coordinador_notificado",
        "director_notificado", "gerencia_notificada",
        "esperando_neo_1", "esperando_neo_2", "cerrado_sin_gestion",
    )
    if esc.estado not in estados_activos:
        return {"ok": False, "mensaje": "Ya está cerrado"}

    esc.estado         = "cerrado_gestionado"
    esc.gestionado_por = usuario.username
    esc.gestionado_at  = datetime.utcnow()
    esc.notas_gestion  = notas
    db.session.commit()
    return {"ok": True, "mensaje": "Escalamiento cerrado exitosamente"}


# ─────────────────────────────────────────────
# Job periódico (APScheduler)
# ─────────────────────────────────────────────

def verificar_timeouts():
    """
    Corre cada 2 minutos. Revisa escalamientos activos y escala
    si el timeout de 10 minutos se cumplió sin respuesta.
    """
    limite = datetime.utcnow() - timedelta(minutes=TIMEOUT_MINUTOS)

    activos = EscalamientoIncidencia.query.filter(
        EscalamientoIncidencia.estado.in_([
            "supervisor_notificado",
            "coordinador_notificado",
            "director_notificado",
        ]),
        EscalamientoIncidencia.notificado_at <= limite,
    ).all()

    for esc in activos:
        reporte = esc.reporte
        try:
            if esc.estado == "supervisor_notificado":
                _preguntar_neo(esc, reporte, "esperando_neo_1")

            elif esc.estado == "coordinador_notificado":
                _preguntar_neo(esc, reporte, "esperando_neo_2")

            elif esc.estado == "director_notificado":
                _escalar_a_gerencia(esc, reporte)

        except Exception as exc:
            log.error("Error escalando id=%s: %s", esc.id, exc)

    if activos:
        db.session.commit()
        log.info("verificar_timeouts: %d escalamientos procesados", len(activos))
