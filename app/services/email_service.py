import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText

from flask import current_app


def _cfg(key: str, default="") -> str:
    return current_app.config.get(key, default) or ""


def enviar_codigo_cambio_pwd(destinatario: str, username: str, codigo: str) -> None:
    """
    Envía el código de verificación al correo del usuario.
    Lanza RuntimeError si falta configuración SMTP o falla el envío.
    """
    host     = _cfg("SMTP_HOST")
    port     = int(_cfg("SMTP_PORT") or 587)
    user     = _cfg("SMTP_USER")
    password = _cfg("SMTP_PASSWORD")
    from_    = _cfg("SMTP_FROM") or user

    if not host or not user or not password:
        raise RuntimeError("El servidor de correo no está configurado. Contacta al administrador.")

    html = f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',system-ui,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 16px;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:16px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,.10);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#005f6b,#00b8c9);
                     padding:32px 32px 28px;text-align:center;">
            <div style="font-size:1.5rem;font-weight:800;color:#fff;letter-spacing:-.5px;">
              🔐 Cambio de contraseña
            </div>
            <div style="font-size:.85rem;color:rgba(255,255,255,.8);margin-top:6px;">
              Incidencias NEO — Hesego Ingeniería SAS
            </div>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px;">
            <p style="color:#374151;font-size:.95rem;margin:0 0 16px;">
              Hola <strong>{username}</strong>,
            </p>
            <p style="color:#374151;font-size:.9rem;line-height:1.6;margin:0 0 24px;">
              Recibimos una solicitud para cambiar tu contraseña en el sistema
              <strong>Incidencias NEO</strong>. Ingresa el siguiente código para confirmar:
            </p>

            <!-- Código -->
            <div style="background:#f8fafc;border:2px dashed #00b8c9;border-radius:12px;
                        padding:24px;text-align:center;margin:0 0 24px;">
              <div style="font-size:2.4rem;font-weight:900;letter-spacing:.35em;
                          color:#005f6b;font-family:'Courier New',monospace;">
                {codigo}
              </div>
              <div style="font-size:.78rem;color:#6b7280;margin-top:8px;">
                Este código es válido por <strong>10 minutos</strong>
              </div>
            </div>

            <p style="color:#6b7280;font-size:.82rem;line-height:1.6;margin:0 0 8px;">
              Si no solicitaste este cambio, ignora este correo. Tu contraseña actual
              seguirá siendo la misma.
            </p>
            <p style="color:#e53e3e;font-size:.82rem;font-weight:600;margin:0;">
              ⚠️ Nunca compartas este código con nadie.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f8fafc;border-top:1px solid #e5e7eb;
                     padding:16px 32px;text-align:center;">
            <p style="color:#9ca3af;font-size:.75rem;margin:0;">
              Hesego Ingeniería SAS · Sistema Incidencias NEO
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🔐 Código de verificación — Cambio de contraseña"
    msg["From"]    = from_
    msg["To"]      = destinatario
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.login(user, password)
            smtp.sendmail(from_, [destinatario], msg.as_string())
    except Exception as e:
        raise RuntimeError(f"No se pudo enviar el correo: {e}")
