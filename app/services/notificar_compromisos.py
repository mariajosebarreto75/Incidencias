"""
Envía a cada responsable un resumen de sus compromisos a las 4:00 pm.
Agrupa por correo (responsable_email); si no tiene correo registrado, omite.
"""
import smtplib
import ssl
from collections import defaultdict
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

from app.extensions import db
from app.models.compromiso import Compromiso


# ── helpers ──────────────────────────────────────────────────────────────────

def _cfg(key: str, default="") -> str:
    return current_app.config.get(key, default) or ""


def _fecha_es(d: date) -> str:
    meses = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    return f"{d.day} {meses[d.month - 1]} {d.year}"


def _estado_label(c: Compromiso) -> tuple[str, str]:
    """Devuelve (etiqueta, color_hex)."""
    if c.estado == "Cerrado":
        return "Cerrado", "#16a34a"
    if c.atrasado:
        return "Atrasado", "#dc2626"
    if c.cantidad_reprogramaciones > 0:
        return f"Reprogramado ({c.cantidad_reprogramaciones}x)", "#d97706"
    return "Pendiente", "#2563eb"


# ── email HTML ────────────────────────────────────────────────────────────────

def _html_resumen(nombre: str, compromisos: list[Compromiso]) -> str:
    hoy = date.today()

    pendientes    = [c for c in compromisos if c.estado != "Cerrado" and not c.atrasado and c.cantidad_reprogramaciones == 0]
    atrasados     = [c for c in compromisos if c.atrasado]
    reprogramados = [c for c in compromisos if c.estado != "Cerrado" and not c.atrasado and c.cantidad_reprogramaciones > 0]

    def filas(lista):
        if not lista:
            return '<tr><td colspan="4" style="padding:10px 12px;color:#9ca3af;font-size:.82rem;">— Ninguno —</td></tr>'
        rows = []
        for c in sorted(lista, key=lambda x: x.fecha_entrega):
            lbl, color = _estado_label(c)
            rows.append(f"""
            <tr style="border-bottom:1px solid #f1f5f9;">
              <td style="padding:9px 12px;font-size:.82rem;color:#374151;">{c.contrato.nombre if c.contrato else '—'}</td>
              <td style="padding:9px 12px;font-size:.82rem;color:#374151;">{c.compromiso[:80]}{'…' if len(c.compromiso) > 80 else ''}</td>
              <td style="padding:9px 12px;font-size:.82rem;white-space:nowrap;">{_fecha_es(c.fecha_entrega)}</td>
              <td style="padding:9px 12px;">
                <span style="background:{color}1a;color:{color};border-radius:20px;
                             padding:2px 10px;font-size:.75rem;font-weight:700;">{lbl}</span>
              </td>
            </tr>""")
        return "".join(rows)

    def seccion(titulo, color, icono, lista):
        return f"""
        <tr><td style="padding:20px 32px 6px;">
          <div style="font-size:.8rem;font-weight:700;color:{color};text-transform:uppercase;
                      letter-spacing:.6px;">{icono} {titulo} ({len(lista)})</div>
        </td></tr>
        <tr><td style="padding:0 32px 16px;">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border-collapse:collapse;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
            <thead>
              <tr style="background:#f8fafc;">
                <th style="padding:8px 12px;text-align:left;font-size:.75rem;color:#6b7280;font-weight:600;">Contrato</th>
                <th style="padding:8px 12px;text-align:left;font-size:.75rem;color:#6b7280;font-weight:600;">Compromiso</th>
                <th style="padding:8px 12px;text-align:left;font-size:.75rem;color:#6b7280;font-weight:600;">Fecha entrega</th>
                <th style="padding:8px 12px;text-align:left;font-size:.75rem;color:#6b7280;font-weight:600;">Estado</th>
              </tr>
            </thead>
            <tbody>{filas(lista)}</tbody>
          </table>
        </td></tr>"""

    nombre_corto = nombre.split("/")[0].strip()

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',system-ui,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:16px;overflow:hidden;
              box-shadow:0 4px 24px rgba(0,0,0,.10);">

  <!-- Header -->
  <tr>
    <td style="background:linear-gradient(135deg,#005f6b,#00b8c9);padding:28px 32px;">
      <div style="font-size:1.3rem;font-weight:800;color:#fff;">📋 Resumen de compromisos</div>
      <div style="font-size:.85rem;color:rgba(255,255,255,.8);margin-top:4px;">
        {_fecha_es(hoy)} · Hesego Ingeniería SAS
      </div>
    </td>
  </tr>

  <!-- Saludo -->
  <tr><td style="padding:24px 32px 8px;">
    <p style="margin:0;color:#374151;font-size:.95rem;">
      Hola <strong>{nombre_corto}</strong>, este es tu resumen de compromisos al cierre del día:
    </p>
  </td></tr>

  <!-- KPIs -->
  <tr><td style="padding:12px 32px 20px;">
    <table cellpadding="0" cellspacing="0" width="100%">
      <tr>
        <td align="center" style="padding:0 6px;">
          <div style="background:#fef2f2;border-radius:10px;padding:12px 8px;text-align:center;">
            <div style="font-size:1.6rem;font-weight:800;color:#dc2626;">{len(atrasados)}</div>
            <div style="font-size:.72rem;color:#dc2626;font-weight:600;">ATRASADOS</div>
          </div>
        </td>
        <td align="center" style="padding:0 6px;">
          <div style="background:#fffbeb;border-radius:10px;padding:12px 8px;text-align:center;">
            <div style="font-size:1.6rem;font-weight:800;color:#d97706;">{len(reprogramados)}</div>
            <div style="font-size:.72rem;color:#d97706;font-weight:600;">REPROGRAMADOS</div>
          </div>
        </td>
        <td align="center" style="padding:0 6px;">
          <div style="background:#eff6ff;border-radius:10px;padding:12px 8px;text-align:center;">
            <div style="font-size:1.6rem;font-weight:800;color:#2563eb;">{len(pendientes)}</div>
            <div style="font-size:.72rem;color:#2563eb;font-weight:600;">PENDIENTES</div>
          </div>
        </td>
      </tr>
    </table>
  </td></tr>

  {seccion("Atrasados", "#dc2626", "🔴", atrasados) if atrasados else ""}
  {seccion("Reprogramados", "#d97706", "🟡", reprogramados) if reprogramados else ""}
  {seccion("Pendientes", "#2563eb", "🔵", pendientes) if pendientes else ""}

  <!-- Footer -->
  <tr>
    <td style="background:#f8fafc;border-top:1px solid #e5e7eb;padding:16px 32px;text-align:center;">
      <p style="color:#9ca3af;font-size:.75rem;margin:0;">
        Hesego Ingeniería SAS · Sistema Incidencias NEO
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ── envío individual ──────────────────────────────────────────────────────────

def _enviar(destinatario: str, asunto: str, html: str) -> None:
    host     = _cfg("SMTP_HOST")
    port     = int(_cfg("SMTP_PORT") or 587)
    user     = _cfg("SMTP_USER")
    password = _cfg("SMTP_PASSWORD")
    from_    = _cfg("SMTP_FROM") or user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = from_
    msg["To"]      = destinatario
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ctx)
        smtp.ehlo()
        smtp.login(user, password)
        smtp.sendmail(from_, [destinatario], msg.as_string())


# ── función principal ─────────────────────────────────────────────────────────

def notificar_lista(por_responsable: dict) -> tuple[int, list]:
    """
    Recibe un dict {(nombre, correo): [Compromiso, ...]} y envía un correo
    a cada responsable. Devuelve (enviados, lista_errores).
    """
    enviados = 0
    errores  = []
    for (nombre, correo), comps in por_responsable.items():
        try:
            html   = _html_resumen(nombre, comps)
            asunto = f"📋 Compromisos asignados — {_fecha_es(date.today())}"
            _enviar(correo, asunto, html)
            enviados += 1
        except Exception as e:
            errores.append(f"{correo}: {e}")
    return enviados, errores
