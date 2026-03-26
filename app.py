from flask import Flask, request, jsonify
import sqlite3
import os
import datetime
import requests

app = Flask(__name__)

DB = "players.db"

API_KEY = os.environ.get("OPENAI_API_KEY")
BASE_URL = os.environ.get("OPENAI_BASE_URL")

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        city TEXT,
        age INTEGER,
        level TEXT,
        day TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/ping")
def ping():
    return "pong"

@app.route("/status")
def status():
    return jsonify({
        "status": "ok",
        "author": "Michal Hamřík",
        "time": str(datetime.datetime.now())
    })

@app.route("/player", methods=["POST"])
def add_player():
    data = request.json

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        INSERT INTO players (name, email, city, age, level, day)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data["name"],
        data["email"],
        data["city"],
        data["age"],
        data["level"],
        data["day"]
    ))
    conn.commit()
    conn.close()

    return jsonify({"message": "player added"})

@app.route("/players")
def get_players():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM players")
    rows = c.fetchall()
    conn.close()

    return jsonify(rows)

@app.route("/ai", methods=["POST"])
def match():
    data = request.json
    player_id = data.get("player_id")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT * FROM players WHERE id=?", (player_id,))
    player = c.fetchone()

    c.execute("""
        SELECT * FROM players
        WHERE id != ? AND day = ? AND city = ?
    """, (player_id, player[6], player[3]))

    candidates = c.fetchall()
    conn.close()

    if not candidates:
        return jsonify({"message": "no match found"})

    candidate_text = ""
    for cnd in candidates:
        candidate_text += f"{cnd[1]} ({cnd[5]}, email: {cnd[2]})\n"

    prompt = f"""
Najdi nejlepšího tenisového soupeře.

Hráč:
{player[1]}, úroveň {player[5]}, město {player[3]}, den {player[6]}

Kandidáti:
{candidate_text}

Vyber nejlepšího a napiš jednu větu včetně emailu.
"""

    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gemma3:27b",
            "messages": [{"role": "user", "content": prompt}]
        },
        verify=False
    )

    result = response.json()
    text = result["choices"][0]["message"]["content"]

    return jsonify({"match": text})

app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8081)))
