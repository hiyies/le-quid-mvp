
from flask import Flask, render_template, request, redirect, url_for, flash, make_response, session
import sqlite3, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key")
ADMIN_CODE = os.environ.get("ADMIN_CODE", "letmein")

DB_PATH = os.path.join(os.path.dirname(__file__), "quid.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS category(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS prologue(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT,
        category_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY(category_id) REFERENCES category(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS reply(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prologue_id INTEGER NOT NULL,
        alias TEXT,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(prologue_id) REFERENCES prologue(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS interest_email(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS alias_ip(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT NOT NULL,
        alias TEXT NOT NULL,
        last_seen TEXT NOT NULL
    )""")
    conn.commit()
    # seed default categories
    for name in ["aujourd’hui","politique","sport","théories","divulgacheur","ce jour-là dans l'histoire"]:
        c.execute("INSERT OR IGNORE INTO category(name) VALUES (?)", (name,))
    conn.commit()
    # seed a few example prologues if none
    count = c.execute("SELECT COUNT(*) AS n FROM prologue").fetchone()["n"]
    if count == 0:
        cat_map = {row["name"]: row["id"] for row in c.execute("SELECT id,name FROM category").fetchall()}
        examples = [
            ("ce jour-là, l’arrestation de marcel petiot", "rappel des faits et débat sur le climat moral de l’après-guerre", cat_map.get("ce jour-là dans l'histoire")),
            ("faut-il un service civique universel ?", "points de vue croisés : civisme, liberté, cohésion", cat_map.get("politique")),
            ("le sport est-il encore populaire ?", "prix des billets, médiatisation, clubs amateurs", cat_map.get("sport")),
        ]
        for t, body, cid in examples:
            c.execute("INSERT INTO prologue(title, content, category_id, created_at) VALUES(?,?,?,?)",
                      (t, body, cid, datetime.utcnow().isoformat()))
        conn.commit()
    conn.close()

# Initialize DB at import time (Flask 3 removed before_first_request)
with app.app_context():
    init_db()

@app.context_processor
def inject_categories():
    conn = get_db()
    cats = conn.execute("SELECT id, name FROM category ORDER BY name").fetchall()
    conn.close()
    return {"nav_categories": cats}

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        code = request.form.get("code","").strip()
        if code == ADMIN_CODE:
            session["admin"] = True
            flash("mode créateur activé", "ok")
            return redirect(url_for("index"))
        else:
            flash("code incorrect", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    flash("mode créateur désactivé", "ok")
    return redirect(url_for("index"))

@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()
    category = request.args.get("category")
    selected_id = request.args.get("p")

    # create prologue (admin only)
    if request.method == "POST":
        if not session.get("admin"):
            flash("seule la fondatrice peut créer un prologue (connectez-vous)", "error")
            return redirect(url_for("login"))
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        category_id = request.form.get("category_id")
        if not title:
            flash("titre obligatoire", "error")
        else:
            conn.execute(
                "INSERT INTO prologue(title, content, category_id, created_at) VALUES(?,?,?,?)",
                (title, content, category_id or None, datetime.utcnow().isoformat())
            )
            conn.commit()
            flash("prologue ajouté", "ok")
            return redirect(url_for("index"))

    # list
    if category:
        rows = conn.execute("""
            SELECT p.*, c.name as category_name
            FROM prologue p LEFT JOIN category c ON p.category_id=c.id
            WHERE c.name = ?
            ORDER BY p.id DESC
        """, (category,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT p.*, c.name as category_name
            FROM prologue p LEFT JOIN category c ON p.category_id=c.id
            ORDER BY p.id DESC
            LIMIT 100
        """).fetchall()

    # detail
    selected = replies = None
    if selected_id:
        selected = conn.execute("""
            SELECT p.*, c.name as category_name
            FROM prologue p LEFT JOIN category c ON p.category_id=c.id
            WHERE p.id=?
        """, (selected_id,)).fetchone()
        if selected:
            replies = conn.execute("""
                SELECT * FROM reply WHERE prologue_id=? ORDER BY id ASC
            """, (selected_id,)).fetchall()

    conn.close()
    return render_template("home.html", prologues=rows, current_category=category, selected=selected, replies=replies)

@app.route("/p/<int:pid>", methods=["POST","GET"])
def prologue(pid):
    conn = get_db()
    if request.method == "POST":
        alias = request.form.get("alias","").strip() or request.cookies.get("alias","").strip() or "anonyme"
        content = request.form.get("content","").strip()
        if content:
            conn.execute("INSERT INTO reply(prologue_id, alias, content, created_at) VALUES(?,?,?,?)",
                         (pid, alias, content, datetime.utcnow().isoformat()))
            # log alias by IP for very-light recognition
            try:
                ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "0.0.0.0"
                conn.execute("INSERT INTO alias_ip(ip, alias, last_seen) VALUES(?,?,?)",
                             (ip, alias, datetime.utcnow().isoformat()))
            except Exception:
                pass
            conn.commit()
            resp = make_response(redirect(url_for("prologue", pid=pid)))
            # remember alias for 180 days
            resp.set_cookie("alias", alias, max_age=60*60*24*180, httponly=True, samesite="Lax")
            flash("réplique ajoutée", "ok")
            conn.close()
            return resp
        flash("le contenu est vide", "error")
        return redirect(url_for("prologue", pid=pid))

    row = conn.execute("""
        SELECT p.*, c.name as category_name
        FROM prologue p LEFT JOIN category c ON p.category_id=c.id
        WHERE p.id=?
    """,(pid,)).fetchone()
    replies = conn.execute("""
        SELECT * FROM reply WHERE prologue_id=? ORDER BY id ASC
    """,(pid,)).fetchall()
    conn.close()
    if not row:
        return "prologue introuvable", 404
    return render_template("prologue.html", p=row, replies=replies)

@app.route("/interest", methods=["POST"])
def interest():
    email = request.form.get("email","").strip()
    if email:
        conn = get_db()
        conn.execute("INSERT INTO interest_email(email, created_at) VALUES(?,?)",
                     (email, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        flash("merci, on vous tient au courant", "ok")
    else:
        flash("email invalide", "error")
    return redirect(request.referrer or url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
