"""Send the daily report email via Gmail SMTP (app password).

A standalone cron script cannot use the Gmail connection inside Claude, so we
send through Gmail's SMTP server using a Gmail App Password. Create one at
https://myaccount.google.com/apppasswords (requires 2-Step Verification).
"""

import smtplib
import ssl
from email.message import EmailMessage


def send_email(*, host, port, username, app_password, sender, to, subject, text_body, html_body):
    """Send a multipart (plain text + HTML) email through an SMTP server."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(username, app_password)
        server.send_message(msg)
