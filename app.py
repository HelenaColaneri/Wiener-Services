
import os
import re
import sqlite3
from pathlib import Path
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, send_file
)
from werkzeug.utils import secure_filename

from export_to_csv import exportar_excel_master

# =========================
# CONFIG
# =========================
BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "repuestos.db"

IMAGES_DIR = BASE_DIR / "static" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp"}

SERVICE_PASSWORD = os.getenv("WS_PASSWORD", "wiener123")
SECRET_KEY = os.getenv("WS_SECRET_KEY", "change-me-please")

app = Flask(__name__)
app.secret_key = SECRET_KEY


# =========================
# DATABASE
# =========================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS repuestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_wiener TEXT UNIQUE NOT NULL,
            codigo_original TEXT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            equipo TEXT,
            notas TEXT,
            imagen TEXT,
            estado TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


# =========================
# HELPERS
# =========================
def require_login():
    return session.get("logged_in") is True


def safe_code_for_filename(code: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", code.strip())


# =========================
# ROUTES
# =========================
@app.get("/")
def home():
    if require_login():
        return redirect(url_for("search_get"))
    return redirect(url_for("login_get"))


# -------- LOGIN --------
@app.get("/login")
def login_get():
    return render_template("login.html")


@app.post("/login")
def login_post():
    pwd = request.form.get("password", "")
    if pwd == SERVICE_PASSWORD:
        session["logged_in"] = True
        flash("Ingreso correcto ✅", "ok")
        return redirect(url_for("search_get"))

    flash("Contraseña incorrecta.", "error")
    return redirect(url_for("login_get"))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_get"))


# -------- SEARCH --------
@app.get("/search")
def search_get():
    if not require_login():
        return redirect(url_for("login_get"))
    return render_template("search.html", part=None, q="")


@app.post("/search")
def search_post():
    if not require_login():
        return redirect(url_for("login_get"))

    q = (request.form.get("query") or "").strip()

    if not q:
        flash("Ingresá un código para buscar.", "error")
        return render_template("search.html", part=None, q="")

    conn = get_db()
    part = conn.execute("""
        SELECT * FROM repuestos
        WHERE codigo_wiener = ?
           OR codigo_original = ?
    """, (q, q)).fetchone()
    conn.close()

    if part is None:
        flash("No se encontró ese código.", "error")
        return render_template("search.html", part=None, q=q)

    flash("Repuesto encontrado ✅", "ok")
    return render_template("search.html", part=part, q=q)


# -------- DELETE --------
@app.post("/delete/<int:part_id>")
def delete_part(part_id):
    if not require_login():
        return redirect(url_for("login_get"))

    conn = get_db()
    conn.execute("DELETE FROM repuestos WHERE id = ?", (part_id,))
    conn.commit()
    conn.close()

    # 🔥 Actualiza Excel maestro
    exportar_excel_master()

    flash("Repuesto eliminado", "ok")
    return redirect(url_for("search_get"))


# -------- ADD --------
@app.get("/add")
def add_part_get():
    if not require_login():
        return redirect(url_for("login_get"))
    return render_template("add.html", error=None, ok=None)


@app.post("/add")
def add_part_post():
    if not require_login():
        return redirect(url_for("login_get"))

    codigo_wiener = (request.form.get("codigo_wiener") or "").strip()
    codigo_original = (request.form.get("codigo_original") or "").strip()
    nombre = (request.form.get("nombre") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()
    equipo = (request.form.get("equipo") or "").strip()
    notas = (request.form.get("notas") or "").strip()
    estado = (request.form.get("estado") or "Activo").strip()

    if not codigo_wiener or not nombre:
        return render_template(
            "add.html",
            error="Falta Código Wiener o Nombre.",
            ok=None
        )

    image = request.files.get("image")
    image_rel_path = None

    if image and image.filename:
        fname = secure_filename(image.filename)
        ext = Path(fname).suffix.lower()

        if ext not in ALLOWED_EXT:
            return render_template(
                "add.html",
                error="Formato de imagen no permitido.",
                ok=None
            )

        safe_code = safe_code_for_filename(codigo_wiener)
        final_name = f"{safe_code}{ext}"
        image.save(IMAGES_DIR / final_name)
        image_rel_path = f"images/{final_name}"

    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO repuestos (
                codigo_wiener,
                codigo_original,
                nombre,
                descripcion,
                equipo,
                notas,
                imagen,
                estado
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            codigo_wiener,
            codigo_original,
            nombre,
            descripcion,
            equipo,
            notas,
            image_rel_path,
            estado
        ))
        conn.commit()
        conn.close()

        # 🔥 Actualiza Excel maestro
        exportar_excel_master()

    except sqlite3.IntegrityError:
        return render_template(
            "add.html",
            error="Ese código ya existe.",
            ok=None
        )

    return render_template(
        "add.html",
        error=None,
        ok="Repuesto guardado. Ya se puede buscar en el sistema."
    )


# -------- EXCEL MASTER --------
@app.get("/excel")
def abrir_excel_master():
    if not require_login():
        return redirect(url_for("login_get"))

    # Siempre genera el Excel antes de abrirlo
    excel_path = exportar_excel_master()

    return send_file(
        excel_path,
        as_attachment=False
    )


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)
