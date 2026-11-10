import os
import json
import urllib.request
import ssl
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import Config

# Servicio de envío de correo transaccional utilizando la API v3 y SMTP de Brevo (Sendinblue)
def enviar_correo_html_brevo(
    destinatario_email: str,
    destinatario_nombre: str,
    asunto: str,
    html_content: str,
    sender_name: str = "AuroraStore"
) -> bool:
    """
    Envía un correo HTML mediante la API REST v3 de Brevo con fallback a SMTP Relay.
    """
    api_key = os.getenv("BREVO_API_KEY") or os.getenv("MAIL_PASSWORD")
    sender_email = os.getenv("MAIL_DEFAULT_SENDER", "toledoquirogaeddy@gmail.com")

    # 1. Intentar mediante la API HTTP v3 de Brevo (Inmune a bloqueos de puertos SMTP en nubes/hosts)
    if api_key:
        try:
            url = "https://api.brevo.com/v3/smtp/email"
            payload = {
                "sender": {
                    "name": sender_name,
                    "email": sender_email
                },
                "to": [
                    {
                        "email": destinatario_email,
                        "name": destinatario_nombre or destinatario_email
                    }
                ],
                "subject": asunto,
                "htmlContent": html_content
            }

            data_bytes = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data_bytes, method='POST')
            req.add_header('Accept', 'application/json')
            req.add_header('Content-Type', 'application/json')
            req.add_header('api-key', api_key)

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, timeout=8, context=ctx) as response:
                if response.status in (200, 201, 202):
                    print(f"[BREVO API SUCCESS] Correo enviado exitosamente a {destinatario_email}")
                    return True
        except Exception as api_err:
            print(f"[BREVO API WARNING] Falló API REST de Brevo: {api_err}. Intentando SMTP Relay...")

    # 2. Fallback por SMTP Relay de Brevo
    try:
        mail_server = os.getenv("MAIL_SERVER", "smtp-relay.brevo.com")
        mail_port = int(os.getenv("MAIL_PORT", 587))
        mail_user = os.getenv("MAIL_USERNAME") or sender_email
        mail_pass = os.getenv("MAIL_PASSWORD") or api_key

        if mail_user and mail_pass:
            msg = MIMEMultipart("alternative")
            msg['Subject'] = asunto
            msg['From'] = f"{sender_name} <{sender_email}>"
            msg['To'] = destinatario_email

            part_html = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(part_html)

            with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
                server.starttls()
                server.login(mail_user, mail_pass)
                server.sendmail(sender_email, [destinatario_email], msg.as_string())
                print(f"[BREVO SMTP] Correo enviado exitosamente vía SMTP a {destinatario_email}")
                return True
    except Exception as smtp_err:
        print(f"[BREVO SMTP ERROR] No se pudo enviar el correo por SMTP: {smtp_err}")

    return False


def enviar_correo_recuperacion_brevo(destinatario_email: str, destinatario_nombre: str, codigo_recuperacion: str) -> bool:
    sender_email = os.getenv("MAIL_DEFAULT_SENDER", "toledoquirogaeddy@gmail.com")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Código de Recuperación — AURA Atelier</title>
    </head>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0c0c0e; color: #f4f4f5; margin: 0; padding: 40px 20px;">
      <div style="max-width: 520px; margin: 0 auto; background-color: #121216; border: 1px solid rgba(212, 175, 55, 0.25); border-radius: 20px; padding: 36px; box-shadow: 0 20px 50px rgba(0,0,0,0.5);">
        
        <div style="text-align: center; margin-bottom: 24px;">
          <h1 style="font-family: Georgia, serif; font-size: 28px; color: #ffffff; margin: 0; letter-spacing: 2px;">
            AURA <span style="color: #d4af37; font-weight: 300; font-style: italic;">ATELIER</span>
          </h1>
          <p style="font-size: 11px; text-transform: uppercase; tracking: 3px; color: #a1a1aa; margin-top: 6px;">Recuperación de Contraseña Segura</p>
        </div>

        <div style="border-top: 1px solid #27272a; border-bottom: 1px solid #27272a; padding: 24px 0; margin-bottom: 24px; text-align: center;">
          <p style="font-size: 14px; color: #d4d4d8; margin-bottom: 16px;">
            Hola <strong>{destinatario_nombre}</strong>, hemos recibido una solicitud para restablecer la contraseña de tu cuenta.
          </p>
          
          <div style="background-color: #09090b; border: 1px solid #3f3f46; border-radius: 12px; padding: 16px; margin: 20px 0; display: inline-block; width: 80%;">
            <span style="font-size: 11px; text-transform: uppercase; color: #d4af37; display: block; margin-bottom: 6px; letter-spacing: 1px;">Código de Verificación (15 Minutos)</span>
            <span style="font-family: monospace; font-size: 32px; font-weight: bold; color: #ffffff; letter-spacing: 8px;">{codigo_recuperacion}</span>
          </div>

          <p style="font-size: 12px; color: #a1a1aa; margin-top: 16px; line-height: 1.5;">
            Ingresa este código de 6 dígitos en el panel de la tienda para crear tu nueva contraseña. Si no solicitaste este cambio, puedes ignorar este correo de forma segura.
          </p>
        </div>

        <div style="text-align: center; font-size: 11px; color: #71717a;">
          <p>© 2026 AURA Atelier — Cadena de Tiendas de Moda & Alta Costura</p>
        </div>

      </div>
    </body>
    </html>
    """

    return enviar_correo_html_brevo(
        destinatario_email=destinatario_email,
        destinatario_nombre=destinatario_nombre,
        asunto=f"✦ {codigo_recuperacion} es tu Código de Recuperación — AURA Atelier",
        html_content=html_content,
        sender_name="AURA Atelier Security"
    )

def enviar_correo_comprobante(
    destinatario_email: str,
    destinatario_nombre: str,
    tipo_documento: str,
    numero_documento: str,
    total_bs: float,
    pdf_bytes: bytes,
    nombre_archivo: str = "Comprobante_Venta.pdf",
    nombre_tienda: str = "Tienda Oficial"
) -> bool:
    """
    W29: Envía por correo el comprobante o factura electrónica en PDF adjunto.
    Si el correo falla, captura la excepción y no interrumpe la venta ya confirmada.
    """
    import base64
    from email.mime.application import MIMEApplication

    if not destinatario_email or '@' not in destinatario_email:
        print(f"[W29 EMAIL NOTICE] No se proporcionó un correo válido para el cliente ({destinatario_email}).")
        return False

    api_key = os.getenv("MAIL_PASSWORD") or os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("MAIL_DEFAULT_SENDER", "toledoquirogaeddy@gmail.com")

    doc_label = "Factura Electrónica" if "FACTURA" in tipo_documento.upper() else (
        "Comprobante de Reserva" if "RESERVA" in tipo_documento.upper() else "Comprobante de Venta"
    )

    tienda_label = (nombre_tienda or "Tienda Oficial").strip()
    brand_display = f"AURORA — {tienda_label}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>{doc_label} — {brand_display}</title>
    </head>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0c0c0e; color: #f4f4f5; margin: 0; padding: 40px 20px;">
      <div style="max-width: 560px; margin: 0 auto; background-color: #121216; border: 1px solid rgba(212, 175, 55, 0.35); border-radius: 20px; padding: 36px; box-shadow: 0 20px 50px rgba(0,0,0,0.5);">
        
        <div style="text-align: center; margin-bottom: 24px;">
          <h1 style="font-family: Georgia, serif; font-size: 26px; color: #ffffff; margin: 0; letter-spacing: 2px;">
            AURORA <span style="color: #d4af37; font-weight: 300; font-size: 18px;">| {tienda_label}</span>
          </h1>
          <p style="font-size: 11px; text-transform: uppercase; letter-spacing: 3px; color: #a1a1aa; margin-top: 6px;">Comprobante de Operación Oficial</p>
        </div>

        <div style="border-top: 1px solid #27272a; border-bottom: 1px solid #27272a; padding: 24px 0; margin-bottom: 24px;">
          <p style="font-size: 14px; color: #d4d4d8; margin-bottom: 14px;">
            Estimado/a <strong>{destinatario_nombre}</strong>, tu compra en <strong>{tienda_label}</strong> ha sido confirmada con éxito.
          </p>
          
          <div style="background-color: #09090b; border: 1px solid #27272a; border-radius: 12px; padding: 18px; margin: 16px 0;">
            <table style="width: 100%; font-size: 12px; color: #d4d4d8;">
              <tr>
                <td style="padding: 4px 0; color: #a1a1aa;">Tienda Emisora:</td>
                <td style="padding: 4px 0; font-weight: bold; text-align: right; color: #ffffff;">{tienda_label}</td>
              </tr>
              <tr>
                <td style="padding: 4px 0; color: #a1a1aa;">Documento:</td>
                <td style="padding: 4px 0; font-weight: bold; text-align: right; color: #d4af37;">{doc_label}</td>
              </tr>
              <tr>
                <td style="padding: 4px 0; color: #a1a1aa;">N° Operación:</td>
                <td style="padding: 4px 0; font-family: monospace; font-weight: bold; text-align: right; color: #ffffff;">{numero_documento}</td>
              </tr>
              <tr>
                <td style="padding: 4px 0; color: #a1a1aa;">Monto Total:</td>
                <td style="padding: 4px 0; font-weight: bold; text-align: right; color: #10b981; font-size: 14px;">Bs. {total_bs:.2f}</td>
              </tr>
            </table>
          </div>

          <p style="font-size: 12px; color: #a1a1aa; line-height: 1.5; margin-top: 16px;">
            Adjuntamos a este correo tu comprobante oficial en formato PDF con todos los detalles de la compra, prendas adquiridas y datos de facturación.
          </p>
        </div>

        <div style="text-align: center; font-size: 11px; color: #71717a;">
          <p>© 2026 AURORA — Red de Boutiques & Tiendas Oficiales</p>
          <p style="font-size: 10px; color: #52525b; margin-top: 4px;">Este correo contiene información fiscal y de entrega confidencial.</p>
        </div>

      </div>
    </body>
    </html>
    """

    # 1. Intentar mediante la API HTTP v3 de Brevo con adjunto Base64
    try:
        b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        url = "https://api.brevo.com/v3/smtp/email"
        payload = {
            "sender": {
                "name": f"AURORA — {tienda_label}",
                "email": sender_email
            },
            "to": [
                {
                    "email": destinatario_email,
                    "name": destinatario_nombre
                }
            ],
            "subject": f"✦ Tu {doc_label} {numero_documento} — AURORA ({tienda_label})",
            "htmlContent": html_content,
            "attachment": [
                {
                    "name": nombre_archivo,
                    "content": b64_pdf
                }
            ]
        }

        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data_bytes, method='POST')
        req.add_header('Accept', 'application/json')
        req.add_header('Content-Type', 'application/json')
        req.add_header('api-key', api_key)

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=8, context=ctx) as response:
            if response.status in (200, 201, 202):
                print(f"[BREVO API SUCCESS] Comprobante PDF enviado a {destinatario_email}")
                return True
    except Exception as api_err:
        print(f"[BREVO API WARNING] Falló envío REST de comprobante: {api_err}. Intentando SMTP Relay...")

    # 2. Fallback por SMTP Relay de Brevo con MIMEApplication
    try:
        mail_server = os.getenv("MAIL_SERVER", "smtp-relay.brevo.com")
        mail_port = int(os.getenv("MAIL_PORT", 587))
        mail_user = os.getenv("MAIL_USERNAME")
        mail_pass = os.getenv("MAIL_PASSWORD")

        msg = MIMEMultipart()
        msg['Subject'] = f"✦ Tu {doc_label} {numero_documento} — AURORA ({tienda_label})"
        msg['From'] = f"AURORA — {tienda_label} <{sender_email}>"
        msg['To'] = destinatario_email

        part_html = MIMEText(html_content, 'html')
        msg.attach(part_html)

        pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=nombre_archivo)
        msg.attach(pdf_attachment)

        with smtplib.SMTP(mail_server, mail_port, timeout=12) as server:
            server.starttls()
            server.login(mail_user, mail_pass)
            server.sendmail(sender_email, [destinatario_email], msg.as_string())
            print(f"[BREVO SMTP SUCCESS] Comprobante PDF enviado exitosamente a {destinatario_email}")
            return True
    except Exception as smtp_err:
        print(f"[BREVO SMTP ERROR] No se pudo enviar comprobante por SMTP: {smtp_err}")
        return False


def enviar_correo_reserva(
    destinatario_email: str,
    destinatario_nombre: str,
    codigo_reserva: str,
    nombre_tienda: str,
    nombre_sucursal: str,
    direccion_sucursal: str,
    fecha_hora_visita: str,
    con_pago: bool,
    monto_pagado: float,
    prendas: list,
    pdf_bytes: bytes,
    nombre_archivo: str = "Comprobante_Reserva.pdf"
) -> bool:
    """
    Envía la confirmación oficial de cita y reserva de prendas con el PDF adjunto.
    """
    import base64
    from email.mime.application import MIMEApplication

    if not destinatario_email or '@' not in destinatario_email:
        print(f"[RESERVA EMAIL NOTICE] Correo inválido ({destinatario_email}).")
        return False

    api_key = os.getenv("MAIL_PASSWORD") or os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("MAIL_DEFAULT_SENDER", "toledoquirogaeddy@gmail.com")

    tienda_label = (nombre_tienda or "Tienda Oficial").strip()
    brand_display = f"AURORA — {tienda_label}"

    modalidad_badge = (
        f'<span style="color: #10b981; font-weight: bold;">PAGADA ONLINE (Bs. {monto_pagado:.2f})</span>'
        if con_pago else
        '<span style="color: #f59e0b; font-weight: bold;">GRATUITA (Pago en Tienda)</span>'
    )

    items_html = ""
    for it in prendas:
        nombre_p = it.get('producto_nombre', 'Prenda')
        talla_p = it.get('talla_nombre', '-')
        color_p = it.get('color_nombre', '-')
        cant_p = it.get('cantidad', 1)
        items_html += f"""
        <tr>
          <td style="padding: 6px 0; color: #ffffff;">{nombre_p}</td>
          <td style="padding: 6px 0; color: #d4af37; text-align: center;">Talla: {talla_p} | Color: {color_p}</td>
          <td style="padding: 6px 0; color: #a1a1aa; text-align: right;">Cant: {cant_p}</td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Confirmación de Reserva — {brand_display}</title>
    </head>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0c0c0e; color: #f4f4f5; margin: 0; padding: 40px 20px;">
      <div style="max-width: 560px; margin: 0 auto; background-color: #121216; border: 1px solid rgba(212, 175, 55, 0.35); border-radius: 20px; padding: 36px; box-shadow: 0 20px 50px rgba(0,0,0,0.5);">
        
        <div style="text-align: center; margin-bottom: 24px;">
          <h1 style="font-family: Georgia, serif; font-size: 26px; color: #ffffff; margin: 0; letter-spacing: 2px;">
            AURORA <span style="color: #d4af37; font-weight: 300; font-size: 18px;">| {tienda_label}</span>
          </h1>
          <p style="font-size: 11px; text-transform: uppercase; letter-spacing: 3px; color: #a1a1aa; margin-top: 6px;">Cita en Sucursal & Reserva de Prendas</p>
        </div>

        <div style="border-top: 1px solid #27272a; border-bottom: 1px solid #27272a; padding: 24px 0; margin-bottom: 24px;">
          <p style="font-size: 14px; color: #d4d4d8; margin-bottom: 14px;">
            Estimado/a <strong>{destinatario_nombre}</strong>, tu cita en <strong>{tienda_label}</strong> ha sido agendada con éxito y tus prendas se encuentran apartadas.
          </p>
          
          <div style="background-color: #09090b; border: 1px solid #27272a; border-radius: 12px; padding: 18px; margin: 16px 0;">
            <table style="width: 100%; font-size: 12px; color: #d4d4d8;">
              <tr>
                <td style="padding: 4px 0; color: #a1a1aa;">Código de Reserva:</td>
                <td style="padding: 4px 0; font-family: monospace; font-weight: bold; text-align: right; color: #d4af37; font-size: 13px;">{codigo_reserva}</td>
              </tr>
              <tr>
                <td style="padding: 4px 0; color: #a1a1aa;">Sucursal de Visita:</td>
                <td style="padding: 4px 0; font-weight: bold; text-align: right; color: #ffffff;">{nombre_sucursal}</td>
              </tr>
              <tr>
                <td style="padding: 4px 0; color: #a1a1aa;">Dirección:</td>
                <td style="padding: 4px 0; text-align: right; color: #a1a1aa;">{direccion_sucursal}</td>
              </tr>
              <tr>
                <td style="padding: 4px 0; color: #a1a1aa;">Fecha y Hora de Cita:</td>
                <td style="padding: 4px 0; font-weight: bold; text-align: right; color: #38bdf8;">{fecha_hora_visita}</td>
              </tr>
              <tr>
                <td style="padding: 4px 0; color: #a1a1aa;">Modalidad:</td>
                <td style="padding: 4px 0; text-align: right;">{modalidad_badge}</td>
              </tr>
            </table>
          </div>

          <div style="margin-top: 18px;">
            <p style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #d4af37; margin-bottom: 8px;">Prendas Apartadas:</p>
            <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
              {items_html}
            </table>
          </div>

          <p style="font-size: 12px; color: #a1a1aa; line-height: 1.5; margin-top: 18px;">
            ✦ Presenta tu código <strong>{codigo_reserva}</strong> o el comprobante PDF adjunto al presentarte en la sucursal para que nuestro equipo prepare tu vestidor.
          </p>
        </div>

        <div style="text-align: center; font-size: 11px; color: #71717a;">
          <p>© 2026 AURORA — Red de Boutiques & Tiendas Oficiales</p>
        </div>

      </div>
    </body>
    </html>
    """

    # 1. Intentar mediante la API HTTP v3 de Brevo con adjunto Base64
    try:
        b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        url = "https://api.brevo.com/v3/smtp/email"
        payload = {
            "sender": {
                "name": f"AURORA — {tienda_label}",
                "email": sender_email
            },
            "to": [
                {
                    "email": destinatario_email,
                    "name": destinatario_nombre
                }
            ],
            "subject": f"✦ Tu Cita y Reserva {codigo_reserva} — AURORA ({tienda_label})",
            "htmlContent": html_content,
            "attachment": [
                {
                    "name": nombre_archivo,
                    "content": b64_pdf
                }
            ]
        }

        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data_bytes, method='POST')
        req.add_header('Accept', 'application/json')
        req.add_header('Content-Type', 'application/json')
        req.add_header('api-key', api_key)

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=8, context=ctx) as response:
            if response.status in (200, 201, 202):
                print(f"[BREVO API SUCCESS] Reserva enviada por correo a {destinatario_email}")
                return True
    except Exception as api_err:
        print(f"[BREVO API WARNING] Falló envío REST de reserva: {api_err}. Intentando SMTP Relay...")

    # 2. Fallback por SMTP Relay de Brevo con MIMEApplication
    try:
        mail_server = os.getenv("MAIL_SERVER", "smtp-relay.brevo.com")
        mail_port = int(os.getenv("MAIL_PORT", 587))
        mail_user = os.getenv("MAIL_USERNAME")
        mail_pass = os.getenv("MAIL_PASSWORD")

        msg = MIMEMultipart()
        msg['Subject'] = f"✦ Tu Cita y Reserva {codigo_reserva} — AURORA ({tienda_label})"
        msg['From'] = f"AURORA — {tienda_label} <{sender_email}>"
        msg['To'] = destinatario_email

        part_html = MIMEText(html_content, 'html')
        msg.attach(part_html)

        pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=nombre_archivo)
        msg.attach(pdf_attachment)

        with smtplib.SMTP(mail_server, mail_port, timeout=12) as server:
            server.starttls()
            server.login(mail_user, mail_pass)
            server.sendmail(sender_email, [destinatario_email], msg.as_string())
            print(f"[BREVO SMTP SUCCESS] Reserva enviada por SMTP a {destinatario_email}")
            return True
    except Exception as smtp_err:
        print(f"[BREVO SMTP ERROR] No se pudo enviar reserva por SMTP: {smtp_err}")
        return False

