#!/usr/bin/env python3
"""
Push daily brief via email.
Supports QQ Mail (QQ邮箱), Gmail, 163, and generic SMTP.

First-time setup — do once:
  1. QQ邮箱: 设置 → 账户 → POP3/SMTP服务 → 开启 → 获取授权码
     Then: export FINANCE_EMAIL_SENDER="yourname@qq.com"
           export FINANCE_EMAIL_PASSWORD="授权码(不是QQ密码)"

  2. Gmail:  Google账户 → 安全性 → 应用专用密码 → 生成
     Then: export FINANCE_EMAIL_SENDER="yourname@gmail.com"
           export FINANCE_EMAIL_PASSWORD="应用专用密码"

  3. Add to ~/.zshrc so launchd picks it up:
     echo 'export FINANCE_EMAIL_SENDER="xxx@qq.com"' >> ~/.zshrc
     echo 'export FINANCE_EMAIL_PASSWORD="your_auth_code"' >> ~/.zshrc
"""

import os
import sys
import argparse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

# SMTP configs
SMTP_CONFIGS = {
    "qq.com":     {"host": "smtp.qq.com",       "port": 465, "ssl": True},
    "gmail.com":  {"host": "smtp.gmail.com",     "port": 465, "ssl": True},
    "163.com":    {"host": "smtp.163.com",       "port": 465, "ssl": True},
    "outlook.com": {"host": "smtp-mail.outlook.com", "port": 587, "ssl": False},
}


def detect_smtp(email):
    domain = email.split("@")[-1].lower()
    return SMTP_CONFIGS.get(domain, {"host": "smtp." + domain, "port": 465, "ssl": True})


def send_email(sender, password, to, subject, body, attachment_path=None):
    smtp_cfg = detect_smtp(sender)

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{os.path.basename(attachment_path)}"',
        )
        msg.attach(part)

    if smtp_cfg["ssl"]:
        server = smtplib.SMTP_SSL(smtp_cfg["host"], smtp_cfg["port"], timeout=30)
    else:
        server = smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=30)
        server.starttls()

    try:
        server.login(sender, password)
        server.sendmail(sender, [to], msg.as_string())
        print(f"  Email sent: {sender} -> {to}")
    finally:
        server.quit()


def main():
    parser = argparse.ArgumentParser(description="Push daily brief via email")
    parser.add_argument("--to", required=True, help="Recipient email")
    parser.add_argument("--subject", default="每日财经要闻", help="Email subject")
    parser.add_argument("--body-file", help="Text file for email body")
    parser.add_argument("--body", help="Inline email body")
    parser.add_argument("--attach", help="Attachment file path")
    args = parser.parse_args()

    sender = os.environ.get("FINANCE_EMAIL_SENDER", "")
    password = os.environ.get("FINANCE_EMAIL_PASSWORD", "")

    if not sender or not password:
        print("  Email config missing. Set env vars:", file=sys.stderr)
        print("    export FINANCE_EMAIL_SENDER='yourname@qq.com'", file=sys.stderr)
        print("    export FINANCE_EMAIL_PASSWORD='auth_code'", file=sys.stderr)
        sys.exit(1)

    # Read body from file or arg
    body = args.body or ""
    if args.body_file and os.path.exists(args.body_file):
        with open(args.body_file, "r", encoding="utf-8") as f:
            body = f.read()

    send_email(sender, password, args.to, args.subject, body, args.attach)


if __name__ == "__main__":
    main()
