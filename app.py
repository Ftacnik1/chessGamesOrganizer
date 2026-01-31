from flask import Flask, render_template, redirect, url_for, request
from db import init_db, get_all_emails, get_unprocessed_emails, get_conn, get_generated_roster, get_roster, get_candidates, manual_to_db
from main import run_import, previous_and_next_day, create_manual, send_mass_email, check_next, load_players, get_priority
from datetime import datetime, date
import locale
import requests
import os
from dotenv import load_dotenv

load_dotenv()

CAPTAIN_NAME = os.getenv("CAPTAIN_NAME")


#Generování zpráv
DNY = ["pondělí", "úterý", "středu", "čtvrtek",
       "pátek", "sobotu", "neděli"]

MESICE = [
    "ledna", "února", "března", "dubna", "května", "června",
    "července", "srpna", "září", "října", "listopadu", "prosince"
]
 
DNY_RADOVE = {
    1: "prvního", 2: "druhého", 3: "třetího", 4: "čtvrtého", 5: "pátého",
    6: "šestého", 7: "sedmého", 8: "osmého", 9: "devátého",
    10: "desátého", 11: "jedenáctého", 12: "dvanáctého",
    13: "třináctého", 14: "čtrnáctého", 15: "patnáctého",
    16: "šestnáctého", 17: "sedmnáctého", 18: "osmnáctého",
    19: "devatenáctého", 20: "dvacátého",
    21: "dvacátého prvního", 22: "dvacátého druhého",
    23: "dvacátého třetího", 24: "dvacátého čtvrtého",
    25: "dvacátého pátého", 26: "dvacátého šestého",
    27: "dvacátého sedmého", 28: "dvacátého osmého",
    29: "dvacátého devátého", 30: "třicátého",
    31: "třicátého prvního",
}

def predlozka(d):
    """Vrátí správnou předložku v/ve podle začátečního písmene dne"""
    return "ve" if d[0] in "sšzžcč" else "v"

def ceske_datum_slovy(iso):
    d = date.fromisoformat(iso)
    den_tydne = DNY[d.weekday()]
    den_radove = DNY_RADOVE[d.day]
    mesic = MESICE[d.month - 1]
    pre = predlozka(den_tydne)
    return f"{pre} {den_tydne} {den_radove} {mesic}"

def build_lineup_html(names):
    items = "".join(f"<li>{name}</li>" for name in names)

    return f"""
    <p>Vážení spoluhráči,<br>posílám finální soupisku pro přísští utkání<br><strong>Finální soupiska:</strong></p>
    <ol>
        {items}
    </ol>
    <br>
    {CAPTAIN_NAME}
    """

RECIPIENTS=[]
pdict=load_players()
for i in pdict:
    if pdict[i]["email"]!=None:
        RECIPIENTS.append(pdict[i]["email"])



def is_online():
    try:
        requests.head("https://www.google.com", timeout=3)
        return True
    except requests.ConnectionError:
        return False

app = Flask(__name__)
init_db()
today_str = datetime.today().strftime("%m/%d/%Y")
prev_game,next_game=previous_and_next_day(today_str)
create_manual()
if prev_game==None:
    prev_time=datetime.strptime("12/24/2025", "%m/%d/%Y")
else:
    prev_time=prev_game[2]
if next_game==None:
    next_game=["Konec soutěže","Konec soutěže",datetime.strptime("12/1/2050", "%m/%d/%Y"),"17.30","Doma"]
if(is_online()):
    print("Zahajuji import mailů")
    run_import()
    print("Generuji aktuální soupisku")
    get_generated_roster(prev_time)
    print("Soupiska k odeslání:")
    final_team=get_roster()
    team_before_sending=[]
    for i in final_team:
        if len(team_before_sending)<=7:
            team_before_sending.append(i["from_name"])
    players_priority=get_priority()
    team_before_sending.sort(key=lambda x: players_priority[x])


    print("team")
    print("Odesílání mailů")

    htmla=f"""
        <p><strong>{(next_game[2]).date().isoformat()} {next_game[3]} — {next_game[4]}</strong></p>
        <p>Vážení spoluhráči, {ceske_datum_slovy((next_game[2]).date().isoformat())} budeme hrát zápas <strong>{next_game[0]} X {next_game[1]}</strong>.</p>
        <p>Utkání začíná v {next_game[3]}, hrací místnost je {next_game[4]}. Prosím napište mi co nejdříve jestli přijdete</p>
        <p>Děkuji<br>{CAPTAIN_NAME}</p>
        """
    htmlb=build_lineup_html(team_before_sending)
    check_next(next_game,RECIPIENTS,htmla,htmlb)





@app.route("/import", methods=["POST"])
def import_now():
    run_import()
    return redirect(url_for("mails_to_check"))

@app.route("/")
def index():
    emails = get_unprocessed_emails(prev_time)
    
    return render_template("index.html",first=next_game[0],second=next_game[1], when=next_game[2],exact_time=next_game[3],where=next_game[4],num_to_check=len(emails))


@app.route("/mails_to_check")
def mails_to_check():
    emails = get_unprocessed_emails(prev_time)
    return render_template("mails_to_check.html", emails=emails)

@app.route("/all_mails")
def all_mails():
    emails = get_all_emails()
    return render_template("mails_to_check.html", emails=emails)

@app.route("/edit/<int:email_id>", methods=["POST"])
def edit(email_id):
    # zatím jen placeholder
    print("Kliknuto na email ID:", email_id)
    return redirect(url_for("index"))


@app.route("/process/<int:email_id>", methods=["POST"])
def process_mail(email_id):
    action = request.form.get("action")  # 'ano', 'ne', 'nechci', 'potvrdit'
    if not action:
        return redirect(url_for("mails_to_check"))

    with get_conn() as conn:
        if action in ["ANO", "NE", "NECHCI"]:
            conn.execute("""
                UPDATE emails
                SET processed = 1,
                    auto_result = ?
                WHERE id = ?
            """, (action, email_id))
        elif action == "potvrdit":
            # člověk souhlasí s automatickým rozhodnutím
            conn.execute("""
                UPDATE emails
                SET processed = 1
                WHERE id = ?
            """, (email_id,))

    return redirect(url_for("mails_to_check"))

@app.route("/generate_team", methods=["POST"])
def generate_team():
    get_generated_roster(prev_time)
    return redirect(url_for("current_team"))


@app.route("/show_team")
def current_team():
    team=get_roster()
    return render_template("team.html", team=team)

@app.route("/manual_override")
def manual_page():
    candidates = get_candidates()
    return render_template("manual.html", candidates=candidates)


@app.route("/write_email")
def write_email_page():
    return render_template("email.html")


@app.route("/add_manual", methods=["POST"])
def adding_manual():
    from_name = request.form.get("from_name")
    decision = request.form.get("decision")
    manual_to_db(from_name,decision)
    return redirect(url_for("manual_page"))

@app.post("/send-broadcast")
def send_broadcast():
    text = request.form.get("message", "").strip()
    if not text:
        return "Zpráva je prázdná", 400

    send_mass_email(
        subject="Šachy organizace týmů",
        body=text,
        recipients=RECIPIENTS
    )
    return redirect(url_for("index"))   # nebo potvrzovací stránka

if __name__ == "__main__":
    app.run(debug=True)
