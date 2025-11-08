# app.py
import os
import io
import csv
import qrcode
import hashlib
import uuid
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, send_file, abort, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask_talisman import Talisman

load_dotenv()  # charge .env si présent

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.getenv("DB_PATH", "db.sqlite3")
DB_URI = f"sqlite:///{os.path.join(BASE_DIR, DB_PATH)}"

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change_this_long_random_key")
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Security headers + basic config (disable CSP here for simplicity; customise for prod)
Talisman(app, content_security_policy=None)

db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# -------------------------
# Models
# -------------------------
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120))
    last_name = db.Column(db.String(120))
    filiere = db.Column(db.String(120))
    number = db.Column(db.String(50))
    age = db.Column(db.Integer)
    bio = db.Column(db.Text)
    photo_filename = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    published = db.Column(db.Boolean, default=False)
    votes = db.relationship("Vote", backref="candidate", lazy=True)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate.id"), nullable=False)
    voter_name = db.Column(db.String(200), nullable=False)
    voter_token = db.Column(db.String(200), nullable=True)   # token unique lié au navigateur
    voter_ip = db.Column(db.String(80), nullable=True)
    voter_ua_hash = db.Column(db.String(200), nullable=True) # hash user-agent fingerprint
    voter_meta = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# -------------------------
# Helpers
# -------------------------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file_storage):
    if not file_storage:
        return None
    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename):
        return None
    name, ext = os.path.splitext(filename)
    new_name = f"{name}_{int(datetime.utcnow().timestamp())}{ext}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], new_name)
    file_storage.save(path)
    return new_name

def generate_qr_bytes(url):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def export_votes_csv_sendfile():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Candidat", "Votant", "Infos votant", "Date du vote"])
    votes = Vote.query.order_by(Vote.created_at.asc()).all()
    for v in votes:
        candidate = v.candidate
        writer.writerow([
            f"{candidate.first_name} {candidate.last_name}" if candidate else "N/A",
            v.voter_name,
            v.voter_meta or "",
            v.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv",
                     as_attachment=True, download_name="votes_export.csv")

def make_voter_token():
    # retourne un token stable pour ce navigateur (crée cookie s'il n'existe pas)
    token = request.cookies.get("voter_token")
    if token:
        return token
    token = str(uuid.uuid4())
    return token

def fingerprint_hash(token: str, ip: str, user_agent: str) -> str:
    # crée un hash stable combinant token + ip + ua
    data = "|".join([token or "", ip or "", user_agent or ""])
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

# -------------------------
# Auth helpers
# -------------------------
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            flash("Vous devez être connecté pour accéder à cette page.", "warning")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

# -------------------------
# Routes - Public (voters)
# -------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/vote")
def vote_list():
    candidates = Candidate.query.filter_by(published=True).all()
    return render_template("vote_list.html", candidates=candidates)

@app.route("/vote/<int:candidate_id>", methods=["GET", "POST"])
def vote_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    if request.method == "POST":
        voter_name = (request.form.get("voter_name") or "").strip()
        voter_meta = (request.form.get("voter_meta") or "").strip()

        if not voter_name:
            flash("Veuillez renseigner votre nom.", "warning")
            return redirect(url_for("vote_candidate", candidate_id=candidate_id))

        # Build token & fingerprint
        token = make_voter_token()
        ip = request.remote_addr or ""
        ua = request.headers.get("User-Agent", "")
        ua_hash = fingerprint_hash(token, ip, ua)

        # check duplicates: prevent same voter_token or same fingerprint from voting more than once
        duplicate = Vote.query.filter(
            (Vote.voter_token == token) | (Vote.voter_ua_hash == ua_hash) | (Vote.voter_ip == ip)
        ).first()
        if duplicate:
            flash("Vous avez déjà voté ou votre appareil a déjà été utilisé pour voter.", "danger")
            return redirect(url_for("vote_list"))

        v = Vote(candidate_id=candidate.id, voter_name=voter_name,
                 voter_token=token, voter_ip=ip, voter_ua_hash=ua_hash,
                 voter_meta=voter_meta)
        db.session.add(v)
        db.session.commit()

        # set cookie to persist token
        resp = render_template("success.html", candidate=candidate)
        response = app.make_response(resp)
        response.set_cookie("voter_token", token, max_age=60*60*24*365)  # 1 an
        return response

    return render_template("voter_form.html", candidate=candidate)

# -------------------------
# Admin routes
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session["admin_id"] = admin.id
            flash("Connexion réussie ✅", "success")
            return redirect(url_for("dashboard"))
        flash("Nom d'utilisateur ou mot de passe incorrect.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin_id", None)
    flash("Déconnecté.", "info")
    return redirect(url_for("login"))

@app.route("/admin/register", methods=["GET", "POST"])
def register_admin():
    # si un admin existe déjà on bloque la création (désactiver cette route en prod)
    if Admin.query.first():
        flash("Administrateur déjà présent. Création désactivée.", "danger")
        return redirect(url_for("login"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        if not username or not password:
            flash("Remplissez tous les champs.", "warning")
            return redirect(url_for("register_admin"))
        hashed = generate_password_hash(password)
        a = Admin(username=username, password_hash=hashed)
        db.session.add(a)
        db.session.commit()
        flash("Admin créé. Connectez-vous.", "success")
        return redirect(url_for("login"))
    return render_template("register_admin.html")

@app.route("/dashboard")
@login_required
def dashboard():
    candidates = Candidate.query.order_by(Candidate.created_at.desc()).all()
    return render_template("dashboard.html", candidates=candidates)

@app.route("/admin/add", methods=["GET", "POST"])
@login_required
def admin_add():
    if request.method == "POST":
        first = request.form.get("first_name") or ""
        last = request.form.get("last_name") or ""
        filiere = request.form.get("filiere") or ""
        number = request.form.get("number") or ""
        age = request.form.get("age") or None
        bio = request.form.get("bio") or ""
        photo = request.files.get("photo")
        filename = save_upload(photo) if photo and allowed_file(photo.filename) else None
        c = Candidate(first_name=first, last_name=last, filiere=filiere,
                      number=number, age=int(age) if age else None,
                      bio=bio, photo_filename=filename)
        db.session.add(c)
        db.session.commit()
        flash("Candidat ajouté (non publié).", "success")
        return redirect(url_for("dashboard"))
    return render_template("add_candidate.html")

@app.route("/publish", methods=["GET", "POST"])
@login_required
def publish():
    if request.method == "POST":
        ids = request.form.getlist("candidate_ids")
        for sid in ids:
            c = Candidate.query.get(int(sid))
            if c:
                c.published = True
        db.session.commit()
        flash("Candidats publiés.", "success")
        return redirect(url_for("dashboard"))
    candidates = Candidate.query.filter_by(published=False).all()
    return render_template("publish.html", candidates=candidates)

@app.route("/results")
@login_required
def results():
    # compute counts + percentages + winner
    published = Candidate.query.filter_by(published=True).all()
    total_votes = Vote.query.count()
    data = []
    max_votes = -1
    winner = None
    for c in published:
        cnt = Vote.query.filter_by(candidate_id=c.id).count()
        pct = (cnt / total_votes * 100) if total_votes > 0 else 0
        data.append({"candidate": c, "votes": cnt, "pct": round(pct, 2)})
        if cnt > max_votes:
            max_votes = cnt
            winner = c
    return render_template("results.html", data=data, total_votes=total_votes, winner=winner)

@app.route("/export")
@login_required
def export_votes():
    return export_votes_csv_sendfile()

@app.route("/qr/<int:candidate_id>")
@login_required
def qr(candidate_id):
    c = Candidate.query.get_or_404(candidate_id)
    link = url_for("vote_candidate", candidate_id=c.id, _external=True)
    buf = generate_qr_bytes(link)
    return send_file(buf, mimetype="image/png", as_attachment=True,
                     download_name=f"candidate_{c.id}_qr.png")

# -------------------------
# CLI helper endpoint (optional)
# -------------------------
@app.cli.command("init-db")
def init_db():
    db.create_all()
    if not Admin.query.first():
        default_admin = Admin(username="admin", password_hash=generate_password_hash("admin123"))
        db.session.add(default_admin)
        db.session.commit()
        print("✅ DB initialisée et admin créé (login=admin / pass=admin123)")
    else:
        print("DB déjà initialisée (admin existant).")
# --- QR Code du site ---
from flask import current_app
from utils import generate_qr_bytes

@app.route('/admin/qr-site')
def admin_qr_site():
    """Affiche le QR code du site de vote"""
    site_url = "https://escoget-vote.onrender.com/"  # 🔹 Mets ici ton URL Render (ou localhost en test)
    qr_img = generate_qr_bytes(site_url)
    return send_file(qr_img, mimetype='image/png')

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    with app.app_context():
        db.drop_all()   # 🧹 supprime tout
        db.create_all() # 🔄 recrée tout proprement
    # dev server for tests
    app.run(debug=False, host="0.0.0.0", port=5000)
