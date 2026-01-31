import json
import imaplib
import email
import smtplib
import base
import db
import re
from datetime import datetime, timedelta
from email.message import EmailMessage
import smtplib

from email.message import EmailMessage
from email.header import decode_header


# =====================
# KONFIGURACE
# =====================

from dotenv import load_dotenv
import os

load_dotenv()

IMAP_SERVER = os.getenv("IMAP_SERVER")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))

RAW_MAIL = os.getenv("RAW_MAIL")
RAW_PASS = os.getenv("RAW_PASS")
CLUB_NAME = os.getenv("CLUB_NAME")


# =====================
# DATA – HRÁČI
# =====================

def check_next(next_game,RECIPIENTS,htmla,htmlb):
    termin=(next_game[2]).date().isoformat()
    befter = ((next_game[2]).date() - timedelta(days=1)).isoformat()
    today_str = datetime.today().date().isoformat()    

    with open("log_day.txt","r")as f:
        first=f.readline()

    with open("log_day_two.txt","r")as f:
        second=f.readline()

    if first!=termin:
        with open("log_day.txt","w")as f:
            f.write(termin)
        send_mass_email_html(
            f"{CLUB_NAME} zápas info",
            htmla,
            RECIPIENTS
        )
    else:
        print("Informační e-mail byl již odeslán")

    if befter==today_str:
        if second!=today_str:
            with open("log_day_two.txt","w")as f:
                f.write(today_str)
            send_mass_email_html(
                f"{CLUB_NAME} zápas soupiska",
                htmlb,
                RECIPIENTS
            )
        else:
            print("Log se soupiskou byl již zapsán")
    else:
        print("Není den před dalším zápasem")
    
def html_to_text(html):
    """Jednoduchý převod HTML → plain text (pro fallback)."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<.*?>", "", text)   # odstraní zbytek tagů
    return text.strip()


def send_mass_email_html(subject, html_body, recipients):
    msg = EmailMessage()
    msg["From"] = RAW_MAIL
    msg["To"] = RAW_MAIL
    msg["Bcc"] = ", ".join(recipients)
    msg["Subject"] = subject

    # fallback: plain-text z HTML
    text_body = html_to_text(html_body)
    msg.set_content(text_body)

    # hlavní varianta: HTML
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
        s.starttls()
        s.login(RAW_MAIL, RAW_PASS)
        s.send_message(msg)   
        
        
    
    





def load_players(path="players.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)



def make_calendar(path="days.txt"):
    with open(path, "r", encoding="utf-8") as f:
        raw_calendar=f.readlines()
    calendar=[]
    for i in raw_calendar:
        parts = i.split(";")
        date = datetime.strptime(parts[5], "%m/%d/%Y")
        hours, minutes = map(int, parts[6].split("."))

        combined_datetime = datetime(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=hours,
            minute=minutes
        )
        calendar.append([parts[3],parts[4],combined_datetime, parts[6],parts[7]])
    return(calendar)

def previous_and_next_day(target_date_str):
    target = datetime.strptime(target_date_str, "%m/%d/%Y")
    prev_day = None
    next_day = None
    calendar=make_calendar()

    for d in calendar:
        if d[2] <= target:
            prev_day = d
        if d[2] >= target and next_day is None:
            next_day = d


    return prev_day, next_day
        

def get_priority():
    contacts=load_players()
    prior_dict={}
    prior=0
    for i in contacts:
        prior+=1
        prior_dict[i]=prior
    return prior_dict
        
def build_who_mail():
    contacts = load_players()
    who_mail = {}

    for key, data in contacts.items():
        if data.get("email"):
            who_mail[data["email"]] = key

    return who_mail


# =====================
# IMAP
# =====================

def connect_imap(user, password):
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(user, password)
    mail.select("INBOX")
    return mail


def mark_as_read(mail_connect, msg_id):
    mail_connect.store(msg_id, "+FLAGS", "\\Seen")


# =====================
# MAIL PARSING
# =====================

def decode_mime_header(value):
    if not value:
        return ""

    parts = decode_header(value)
    decoded = ""

    for part, encoding in parts:
        if isinstance(part, bytes):
            decoded += part.decode(encoding or "utf-8", errors="ignore")
        else:
            decoded += part

    return decoded


def fetch_unread_filtered_emails(mail_connect, who_mail):
    mails = []

    status, messages = mail_connect.search(
        None,
        '(UNSEEN)'
    )

    if status != "OK" or not messages[0]:
        return mails

    for msg_id in messages[0].split():

        status, msg_data = mail_connect.fetch(
            msg_id,
            "(BODY.PEEK[])"
        )
        if status != "OK":
            continue

        msg = email.message_from_bytes(msg_data[0][1])

        from_header = decode_mime_header(msg.get("From", ""))
        subject = decode_mime_header(msg.get("Subject", ""))

        from_email = email.utils.parseaddr(from_header)[1].lower()
        if from_email not in who_mail:
            continue

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(errors="ignore")
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors="ignore")

        mails.append({
            "imap_id": msg_id,
            "from_email": from_email,
            "from_name": who_mail[from_email],
            "subject": subject,
            "body": body.strip(),
        })

    return mails
def create_manual():
    players=load_players()
    name_list=[]
    for i in players:
        new_tuple=(i,)
        name_list.append(new_tuple)
    db.update_candidates(name_list)
        


# =====================
# HLAVNÍ IMPORT FUNKCE
# =====================

def run_import():

    who_mail = build_who_mail()
    mail = connect_imap(RAW_MAIL, RAW_PASS)

    try:
        mails = fetch_unread_filtered_emails(mail, who_mail)

        for m in mails:
            db.insert_email(
                from_name=m["from_name"],
                from_email=m["from_email"],
                subject=m["subject"],
                body=m["body"],
                auto_result=base.classify(m["body"])
            )

            mark_as_read(mail, m["imap_id"])

        return len(mails)

    finally:
        mail.logout()

def send_mass_email(subject, body, recipients): 
    msg = EmailMessage()
    msg["From"] = RAW_MAIL
    msg["To"] = RAW_MAIL
    msg["Bcc"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
        s.starttls()
        s.login(RAW_MAIL, RAW_PASS)
        s.send_message(msg)



if __name__ == "__main__":
    count = run_import()
    print(f"Importováno {count} mailů")
        

