import sqlite3
from pathlib import Path
from main import get_priority
from datetime import datetime
# ---------------------------------------
# Konfigurace databáze
# ---------------------------------------
DB_PATH = Path("data.db")


def get_conn():
    """Vrátí spojení k DB, vždy jako string pro sqlite3."""
    return sqlite3.connect(str(DB_PATH))


# ---------------------------------------
# Inicializace tabulek
# ---------------------------------------
def init_db():
    """Vytvoří potřebné tabulky, pokud neexistují."""
    with get_conn() as conn:
        # tabulka e-mailů
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_name TEXT,
                from_email TEXT,
                subject TEXT,
                body TEXT,
                auto_result TEXT,
                processed INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # tabulka finální soupisky
        conn.execute("""
            CREATE TABLE IF NOT EXISTS roster (
                from_name TEXT PRIMARY KEY,
                auto_result TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                from_name TEXT PRIMARY KEY,
                auto_result TEXT NOT NULL
            )
        """)
        conn.commit()
        cur = conn.cursor()

        cur.executescript("""
            DROP TABLE IF EXISTS candidates;

            CREATE TABLE candidates (
                from_name TEXT PRIMARY KEY)
        """)

        conn.commit()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_name TEXT NOT NULL,
            decision TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()




# ---------------------------------------
# Funkce pro práci s e-maily
# ---------------------------------------
def get_all_emails():
    """Vrátí všechny e-maily, seřazené podle času sestupně."""
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("""
            SELECT * FROM emails
            ORDER BY created_at DESC
        """).fetchall()


def get_unprocessed_emails(target_date):
    """Vrátí všechny e-maily, které ještě nebyly zpracovány."""
    start_dt = datetime.combine(target_date, datetime.min.time())
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("""
            SELECT * FROM emails
            WHERE processed = 0
            AND created_at > ?
            ORDER BY created_at ASC
        """, (start_dt.isoformat(),)).fetchall()


def insert_email(from_name, from_email, subject, body, auto_result):
    """Vloží nový e-mail do DB, defaultně jako nezpracovaný."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO emails (from_name, from_email, subject, body, auto_result, processed)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (from_name, from_email, subject, body, auto_result))
        conn.commit()


# ---------------------------------------
# Funkce pro generování soupisky
# ---------------------------------------
def get_last_messages(prev_time):
    """
    Vrátí poslední zprávu každého hráče podle created_at.
    Výsledek je list dictů: [{"name": ..., "answer": ..., "created_at": ...}, ...]
    """
    query = """
        SELECT m.from_name,
               m.auto_result,
               m.created_at
        FROM emails m
        JOIN (
            SELECT from_name, MAX(created_at) AS last_time
            FROM emails
            WHERE created_at > ?
            GROUP BY from_name
        ) last
        ON m.from_name = last.from_name
        AND m.created_at = last.last_time
        WHERE m.created_at > ?
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, (prev_time.isoformat(), prev_time.isoformat()))
        rows = cur.fetchall()

    return [
        {"name": r[0], "answer": r[1], "created_at": r[2]}
        for r in rows
    ]

def get_last_votes(prev_time):
    query = """
        SELECT v.from_name,
               v.decision,
               v.created_at
        FROM votes v
        JOIN (
            SELECT from_name, MAX(created_at) AS last_time
            FROM votes
            WHERE created_at > ?
            GROUP BY from_name
        ) last
        ON v.from_name = last.from_name
        AND v.created_at = last.last_time
        WHERE v.created_at > ?
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, (prev_time.isoformat(), prev_time.isoformat()))
        rows = cur.fetchall()

    print("Hlasy")
    print(rows)
    return [
        {"name": r[0], "answer": r[1], "created_at": r[2]}
        for r in rows
    ]


def build_rosters(last_answers):
    """
    Vytvoří finální soupisku:
    - ANO se ukládá jako první
    - NECHCI jako druhé
    - NE se ignoruje
    Současně uloží soupisku do tabulky roster.
    """
    ano_list = []
    nechci_list = []

    for item in last_answers:
        ans = (item["answer"] or "").lower()
        if ans == "ano":
            ano_list.append(item["name"])
        elif ans == "nechci":
            nechci_list.append(item["name"])
        elif ans == "ne":
            continue

    
    players_priority=get_priority()
    ano_list.sort(key=lambda x: players_priority[x])
    nechci_list.sort(key=lambda x: players_priority[x])
    save_final_roster(ano_list, nechci_list)
    final_roster = ano_list + nechci_list
    print(final_roster)
    return ano_list, nechci_list, final_roster


def get_generated_roster(prev_time):
    """
    High-level funkce: načte poslední zprávy a vrátí generovanou soupisku.
    """
    last = get_last_messages(prev_time)
    votes = get_last_votes(prev_time)
    answers=votes
    check_set=set()
    for i in votes:
        check_set.add(i["name"])
    for  i in last:
        if i["name"] not in check_set:
           check_set.add(i["name"])
           answers.append(i)
    print(votes)

        
        
    return build_rosters(answers)


# ---------------------------------------
# Funkce pro uložení finální soupisky
# ---------------------------------------
def save_final_roster(ano_list, nechci_list):
    """
    Uloží finální soupisku do tabulky 'roster' s sloupci:
    - from_name
    - auto_result ('ano' / 'ne')
    Tabulka se vytvoří, pokud neexistuje, a stará data se smažou.
    """
    roster_data = []
    for name in ano_list:
        roster_data.append((name, "ano"))
    for name in nechci_list:
        roster_data.append((name, "nechci"))

    with get_conn() as conn:
        cur = conn.cursor()
        # vytvoření tabulky, pokud neexistuje
        cur.execute("""
            CREATE TABLE IF NOT EXISTS roster (
                from_name TEXT PRIMARY KEY,
                auto_result TEXT NOT NULL
            )
        """)
        # vyprázdnit stará data
        cur.execute("DELETE FROM roster")
        # vložit nové
        cur.executemany(
            "INSERT INTO roster (from_name, auto_result) VALUES (?, ?)",
            roster_data
        )
        conn.commit()


# ---------------------------------------
# Funkce pro načtení finální soupisky
# ---------------------------------------
def get_roster():
    """
    Vrátí obsah tabulky roster jako list sqlite3.Row.
    """
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM roster").fetchall()




def update_candidates(player_list):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM candidates")
        cur.executemany(
            "INSERT INTO candidates (from_name) VALUES (?)",
            player_list
        )
        conn.commit()

def get_candidates():
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT from_name FROM candidates"
        ).fetchall()


def manual_to_db(from_name,decision):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO votes (from_name, decision) VALUES (?, ?)",
            (from_name, decision)
        )
        conn.commit()









