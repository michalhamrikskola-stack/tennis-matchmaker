from flask import Flask, request, jsonify, render_template_string
import sqlite3
import os
import datetime
import requests

app = Flask(__name__)

# 🔥 FINÁLNÍ FIX DB (funguje všude)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "players.db")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://kurim.ithope.eu/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gemma3:27b")

HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Tennis AI</title>
</head>
<body>

<h1>🎾 Tennis Partner Finder AI</h1>

{% if message %}<p style="color:green">{{ message }}</p>{% endif %}
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}

<form method="post" action="/player-form">
<input name="nickname" placeholder="Jméno" required><br>
<input name="city" placeholder="Praha / Brno" required><br>
<input name="age" type="number" required><br>
<input name="level" placeholder="Úroveň" required><br>
<input name="available_time" type="datetime-local" required><br>
<input name="email" type="email" required><br>
<button>Uložit</button>
</form>

<h2>AI odpověď:</h2>
<pre>{{ match_message }}</pre>

<h2>Hráči:</h2>
<ul>
{% for p in players %}
<li>{{ p["nickname"] }} - {{ p["city"] }}</li>
{% endfor %}
</ul>

</body>
</html>
"""

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT,
        city TEXT,
        age INTEGER,
        level TEXT,
        available_time TEXT,
        email TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

def fetch_players():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM players").fetchall()
    conn.close()
    return [dict(zip(
        ["id","nickname","city","age","level","available_time","email","created_at"],
        r
    )) for r in rows]

def validate(data):
    for f in ["nickname","city","age","level","available_time","email"]:
        if not data.get(f):
            return f"Chybí {f}"
    return None

def find_match(player):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM players WHERE id != ?", (player["id"],)).fetchall()
    conn.close()

    pt = datetime.datetime.fromisoformat(player["available_time"])

    for r in rows:
        ct = datetime.datetime.fromisoformat(r[5])
        diff = abs((ct - pt).total_seconds()) / 60
        if diff <= 60:
            return dict(zip(
                ["id","nickname","city","age","level","available_time","email","created_at"],
                r
            ))
    return None

def ai_message(player, match):
    if not OPENAI_API_KEY:
        return "AI není aktivní."

    prompt = f"Hráč: {player}, match: {match}"

    try:
        r = requests.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=20
        )
        return r.json()["choices"][0]["message"]["content"]
    except:
        return "AI selhalo, ale app běží 👍"

@app.route("/")
def home():
    return render_template_string(
        HTML,
        players=fetch_players(),
        message=None,
        error=None,
        match_message=""
    )

@app.route("/ping")
def ping():
    return "pong"

@app.route("/player-form", methods=["POST"])
def add_player():
    data = request.form.to_dict()

    error = validate(data)
    if error:
        return render_template_string(HTML, players=fetch_players(), error=error)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO players (nickname, city, age, level, available_time, email, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data["nickname"],
        data["city"],
        int(data["age"]),
        data["level"],
        data["available_time"],
        data["email"],
        str(datetime.datetime.now())
    ))

    pid = cur.lastrowid
    conn.commit()

    player = conn.execute("SELECT * FROM players WHERE id = ?", (pid,)).fetchone()
    conn.close()

    player_dict = dict(zip(
        ["id","nickname","city","age","level","available_time","email","created_at"],
        player
    ))

    match = find_match(player_dict)
    msg = ai_message(player_dict, match)

    return render_template_string(
        HTML,
        players=fetch_players(),
        message="Uloženo",
        match_message=msg
    )

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
