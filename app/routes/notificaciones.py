from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models.notificacion import Notificacion
from app.models.reporte_operacional import ReporteOperacional
from app.models.user_contrato import UserContrato
from app.models.user import User

notif_bp = Blueprint("notif", __name__)


def crear_notificacion(usuario_destino, tipo, reporte):
    recurso   = reporte.recurso         or "—"
    contrato  = reporte.contrato        or "—"
    tipo_inc  = reporte.tipo_incidencia or "—"
    fecha     = str(reporte.fecha_reporte) if reporte.fecha_reporte else "—"
    reportado = reporte.reportado_por   or "—"
    respondido = getattr(reporte, "respondido_por", None) or "—"

    mensajes = {
        "nuevo_reporte":
            f"Hola, reporte realizado al {recurso}, del día {fecha}, "
            f"{tipo_inc}, reportado por {reportado}.",
        "reporte_respondido":
            f"Respuesta de {contrato}, al {recurso}, "
            f"{tipo_inc}, respondida por {respondido}.",
        "no_conforme":
            f"Su respuesta del {recurso}, del día {fecha} ha sido inconforme, validala.",
    }
    n = Notificacion(
        usuario_destino = usuario_destino,
        tipo            = tipo,
        reporte_id      = reporte.id,
        mensaje         = mensajes.get(tipo, "Nueva notificación"),
        contrato        = reporte.contrato,
        recurso         = reporte.recurso,
        fecha_reporte   = fecha,
        tipo_incidencia = tipo_inc,
    )
    db.session.add(n)


def coordinadores_de_contrato(contrato):
    """Devuelve los usernames de coordinadores asignados a un contrato."""
    ucs = UserContrato.query.filter_by(contrato=contrato).all()
    user_ids = [uc.user_id for uc in ucs]
    if not user_ids:
        return []
    coordinadores = User.query.filter(
        User.id.in_(user_ids),
        User.rol == "coordinador"
    ).all()
    return [u.username for u in coordinadores]


# ── Badge ─────────────────────────────────────────────────────────────────────

@notif_bp.route("/notificaciones/badge")
@login_required
def badge():
    count = Notificacion.query.filter_by(
        usuario_destino=current_user.username,
        gestionada=False
    ).count()
    return jsonify({"pendientes": count})


# ── Lista ─────────────────────────────────────────────────────────────────────

@notif_bp.route("/notificaciones")
@login_required
def lista():
    notifs = Notificacion.query.filter_by(
        usuario_destino=current_user.username
    ).order_by(Notificacion.fecha_creacion.desc()).limit(30).all()

    return jsonify([{
        "id":            n.id,
        "tipo":          n.tipo,
        "mensaje":       n.mensaje,
        "reporte_id":    n.reporte_id,
        "contrato":      n.contrato,
        "recurso":       n.recurso,
        "fecha_reporte": n.fecha_reporte,
        "tipo_incidencia": n.tipo_incidencia,
        "gestionada":    n.gestionada,
        "fecha":         n.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
    } for n in notifs])


# ── Gestionar (acción principal — lleva al reporte) ───────────────────────────

@notif_bp.route("/notificaciones/<int:nid>/gestionar", methods=["POST"])
@login_required
def gestionar(nid):
    n = Notificacion.query.filter_by(
        id=nid, usuario_destino=current_user.username
    ).first_or_404()
    n.gestionada = True
    db.session.commit()
    return jsonify({"ok": True, "reporte_id": n.reporte_id, "tipo": n.tipo})


# ── Visualizado (solo para no_conforme — cierra sin ir al reporte) ────────────

@notif_bp.route("/notificaciones/<int:nid>/visualizado", methods=["POST"])
@login_required
def visualizado(nid):
    n = Notificacion.query.filter_by(
        id=nid, usuario_destino=current_user.username
    ).first_or_404()
    n.gestionada = True
    db.session.commit()
    return jsonify({"ok": True})
