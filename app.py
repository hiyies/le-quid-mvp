from flask import Flask, Response, render_template, request, redirect, url_for, flashimport sqlite3, os
from datetime import datetime
# Chemins
DB_PATH = os.environ.get("DB_PATH", "/tmp/quid.db")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-key")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# ---------- DB ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # prologues
    c.execute("""
      CREATE TABLE IF NOT EXISTS prologue(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        intro TEXT,
        category TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );
    """)
    # replies (avec alias)
    c.execute("""
      CREATE TABLE IF NOT EXISTS reply(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prologue_id INTEGER NOT NULL,
        alias TEXT,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        ip TEXT,
        FOREIGN KEY(prologue_id) REFERENCES prologue(id)
      );
    """)
    conn.commit()
    conn.close()

# Initialise la DB sur le boot (pas de before_first_request en Flask 3)
init_db()

# ---------- ROUTES ----------
@app.get("/_health")
def _health():
    return "ok", 200

@app.get("/")
def index():
    category = request.args.get("category")
    conn = get_db()
    c = conn.cursor()
    if category:
        c.execute("SELECT * FROM prologue WHERE category = ? ORDER BY id DESC", (category,))
    else:
        c.execute("SELECT * FROM prologue ORDER BY id DESC")
    prologues = c.fetchall()
    conn.close()
    return render_template("home.html", prologues=prologues, current_category=category)

@app.get("/p/<int:prologue_id>")
def prologue(prologue_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM prologue WHERE id = ?", (prologue_id,))
    p = c.fetchone()
    c.execute("SELECT * FROM reply WHERE prologue_id = ? ORDER BY id ASC", (prologue_id,))
    replies = c.fetchall()
    conn.close()
    if not p:
        return redirect(url_for("index"))
    return render_template("prologue.html", p=p, replies=replies)

@app.post("/reply")
def post_reply():
    prologue_id = int(request.form["prologue_id"])
    alias = request.form.get("alias", "").strip() or "anonyme"
    content = request.form.get("content", "").strip()
    if not content:
        flash("réplique vide.")
        return redirect(url_for("prologue", prologue_id=prologue_id))
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO reply(prologue_id, alias, content, created_at, ip) VALUES(?,?,?,?,?)",
        (prologue_id, alias, content, datetime.utcnow().isoformat(), ip)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("prologue", prologue_id=prologue_id))

# Petite page pour créer 1–2 prologues (temporaire, accessible par URL)
def _admin_auth_required():
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        return Response("admin credentials not configured", 403)
    auth = request.authorization
    if not auth or auth.username != ADMIN_USERNAME or auth.password != ADMIN_PASSWORD:
        return Response(
            "auth required",
            401,
            {"WWW-Authenticate": 'Basic realm="admin"'},
        )


@app.post("/admin/new")
@app.get("/admin/new")
def admin_new():
    auth_response = _admin_auth_required()
    if auth_response:
    return auth_response
    if request.method == "POST":
        title = request.form.get("title","").strip()
        intro = request.form.get("intro","").strip()
        category = request.form.get("category","").strip() or None
        if title:
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO prologue(title,intro,category) VALUES(?,?,?)",
                      (title,intro,category))
            conn.commit()
            new_id = c.lastrowid
            conn.close()
            return redirect(url_for("prologue", prologue_id=new_id))
        flash("titre requis.")
    return render_template("login.html")  # on recycle le gabarit simple de formulaire

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
