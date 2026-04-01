"""
app.py — Municipal Complaint Management System (Flask Backend)
==============================================================

HOW TO RUN:
    1. Install dependencies first:
          pip install -r requirements.txt

    2. Create a .env file in the same folder with:
          GEMINI_API_KEY=your_gemini_api_key_here
          EMAIL_USER=your_gmail@gmail.com
          EMAIL_PASSWORD=your_gmail_app_password
          SECRET_KEY=any_long_random_string

    3. Run:
          python app.py

WHY IT WASN'T STARTING:
    - CRASH 1 (line 8): `from google import genai` — the `google-genai`
      package was not installed. Python crashed immediately with
      ImportError before Flask even started, so the terminal showed nothing.

    - CRASH 2 (line 18): Even if genai was installed, `genai.Client(api_key=None)`
      crashes when GEMINI_API_KEY is missing from .env.

    Both are now fixed with a safe lazy-import + guard below.
"""

from flask import Flask, jsonify, render_template, request, redirect, session, url_for, flash
import sqlite3
from datetime import datetime, timedelta
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import json
import tempfile

# ─── LOAD .env FILE ──────────────────────────────────────────────────────────
# Must be called before any os.getenv() so .env values are available.
load_dotenv()

# ─── GEMINI AI — SAFE IMPORT ─────────────────────────────────────────────────
# FIX: The original code imported genai at module level.
# If `google-genai` is not installed, Python crashes instantly with ImportError
# and Flask never starts — the terminal shows nothing at all.
#
# Fix: wrap in try/except so the app still starts even without the package.
# The /analyse-complaint route checks `AI_AVAILABLE` before using it.
AI_AVAILABLE = False
genai_client = None

try:
    from google import genai
    from google.genai import types as genai_types

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    if GEMINI_API_KEY:
        # FIX: genai.Client(api_key=None) crashes — guard with explicit check
        genai_client  = genai.Client(api_key=GEMINI_API_KEY)
        AI_AVAILABLE  = True
        print("[Gemini] AI client initialized successfully.")
    else:
        print("[Gemini] WARNING: GEMINI_API_KEY not set in .env — AI features disabled.")

except ImportError:
    print("[Gemini] WARNING: 'google-genai' package not installed.")
    print("[Gemini] Run:  pip install google-genai")
    print("[Gemini] AI features will be disabled until the package is installed.")

# ─── FLASK APP ───────────────────────────────────────────────────────────────
app = Flask(__name__)

# FIX: Secret key must come from .env in production — never hardcode it.
# If SECRET_KEY is missing from .env, we fall back to a dev-only default
# and print a clear warning instead of silently using a weak key.
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    SECRET_KEY = "municipal_dev_key_CHANGE_IN_PRODUCTION"
    print("[Security] WARNING: SECRET_KEY not set in .env — using insecure dev key.")
    print("[Security] Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"")
app.secret_key = SECRET_KEY

# ─── FILE UPLOAD CONFIGURATION ───────────────────────────────────────────────
UPLOAD_FOLDER      = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_AUDIO      = {"wav", "mp3", "m4a", "ogg", "webm"}

app.config["UPLOAD_FOLDER"]      = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload

# Create the upload directory if it doesn't exist yet
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ───Email CONFIGURATION ──────────────────────────────────────────────────────
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_AUDIO = {"wav", "mp3", "m4a", "ogg", "webm"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

EMAIL_HOST     = "smtp.gmail.com"
EMAIL_PORT     = 587

# --- CONFIGURATION ---
load_dotenv() # This must be at the top of your file

# Pulling values from .env file
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# For debugging ONLY (remove this before presentation):
print(f"DEBUG: System is using email: {EMAIL_USER}")

# ─── STATE → ADMIN AUTHORIZATION CODES ───────────────────────────────────────
# Each state has a unique admin code. Admins must enter the correct
# code during signup. Rotate these regularly in production.
STATE_ADMIN_CODES = {
    "Andhra Pradesh":    "AP@ADMIN2026",
    "Arunachal Pradesh": "AR@ADMIN2026",
    "Assam":             "AS@ADMIN2026",
    "Bihar":             "BR@ADMIN2026",
    "Chhattisgarh":      "CG@ADMIN2026",
    "Goa":               "GA@ADMIN2026",
    "Gujarat":           "GJ@ADMIN2026",
    "Haryana":           "HR@ADMIN2026",
    "Himachal Pradesh":  "HP@ADMIN2026",
    "Jharkhand":         "JH@ADMIN2026",
    "Karnataka":         "KA@ADMIN2026",
    "Kerala":            "KL@ADMIN2026",
    "Madhya Pradesh":    "MP@ADMIN2026",
    "Maharashtra":       "MH@ADMIN2026",
    "Manipur":           "MN@ADMIN2026",
    "Meghalaya":         "ML@ADMIN2026",
    "Mizoram":           "MZ@ADMIN2026",
    "Nagaland":          "NL@ADMIN2026",
    "Odisha":            "OD@ADMIN2026",
    "Punjab":            "PB@ADMIN2026",
    "Rajasthan":         "RJ@ADMIN2026",
    "Sikkim":            "SK@ADMIN2026",
    "Tamil Nadu":        "TN@ADMIN2026",
    "Telangana":         "TG@ADMIN2026",
    "Tripura":           "TR@ADMIN2026",
    "Uttar Pradesh":     "UP@ADMIN2026",
    "Uttarakhand":       "UK@ADMIN2026",
    "West Bengal":       "WB@ADMIN2026",
    "Delhi":             "DL@ADMIN2026",
    "Jammu & Kashmir":   "JK@ADMIN2026",
    "Ladakh":            "LA@ADMIN2026",
    "Puducherry":        "PY@ADMIN2026",
    "Chandigarh":        "CH@ADMIN2026",
}

# ─── SLA DAYS PER COMPLAINT CATEGORY ─────────────────────────────────────────
# How many days the authority has to resolve each category.
# FIX: "air Pollution" → "Air Pollution" to match submit.html option value exactly.
# A mismatched key causes all Air Pollution complaints to silently use 7-day SLA.
SLA_DAYS = {
    "Garbage":         2,
    "Road Damage":     7,
    "Streetlight":     5,
    "Water Supply":    3,
    "Drainage":        4,
    "Mosquito":        3,
    "Construction":    10,
    "Encroachment":    10,
    "Hoardings":       7,
    "Buildings":       7,
    "Tree Cutting":    5,
    "Garden":          7,
    "Air Pollution":   5,   # FIX: was "air Pollution" — key must match submit.html exactly
    "Dead Animal":     1,
    "Toilet":          3,
    "Food Safety":     3,
    "Stray Cattle":    3,
    "Noise Pollution": 3,
    "Manhole":         2,
    "Dog":             3,
    "Tax":             14,
    "Fire":            1,
    "other":           7,
}

# Whitelist for /update route — prevents arbitrary status injection via URL
VALID_STATUS_MAP = {
    "progress": "In Progress",
    "resolved": "Resolved",
}

# ─── GEMINI MODEL FALLBACK LIST ───────────────────────────────────────────────
# Models are tried in order. On quota (429) or not-found (404), the next is tried.
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

# ─── DATABASE HELPERS ─────────────────────────────────────────────────────────

def connect():
    """Open SQLite connection. row_factory lets us access columns by name."""
    conn = sqlite3.connect("complaints.db", timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Create tables if they don't exist and safely add any missing columns.
    Called at module load (not just inside __main__) so it runs under
    Gunicorn/uWSGI in production too.
    """
    with connect() as conn:
        # Complaints table — includes latitude/longitude for GPS data from form
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_id TEXT    NOT NULL,
                name         TEXT    NOT NULL,
                mobile       TEXT    DEFAULT '',
                category     TEXT    NOT NULL,
                description  TEXT    NOT NULL,
                status       TEXT    NOT NULL DEFAULT 'Pending',
                timestamp    TEXT    NOT NULL,
                image        TEXT    DEFAULT '',
                address      TEXT    DEFAULT '',
                latitude     TEXT    DEFAULT '',
                longitude    TEXT    DEFAULT '',
                state        TEXT    NOT NULL DEFAULT ''
            )
        """)

        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT    NOT NULL,
                email    TEXT    UNIQUE NOT NULL,
                password TEXT    NOT NULL,
                role     TEXT    NOT NULL DEFAULT 'user',
                state    TEXT    DEFAULT '',
                verified INTEGER DEFAULT 0
            )
        """)

        # Safe migrations: add columns that may be missing in existing databases.
        # ALTER TABLE fails silently if the column already exists — that's intentional.
        safe_columns = [
            ("complaints", "mobile",    "TEXT DEFAULT ''"),
            ("complaints", "latitude",  "TEXT DEFAULT ''"),
            ("complaints", "longitude", "TEXT DEFAULT ''"),
            ("complaints", "address",   "TEXT DEFAULT ''"),
        ]
        for table, col, col_def in safe_columns:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            except Exception:
                pass  # Column already exists — skip silently

        conn.commit()


# ─── FILE VALIDATION ──────────────────────────────────────────────────────────

def allowed_file(filename):
    """Return True if the filename has an allowed image extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_audio(filename):
    """Return True if the filename has an allowed audio extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AUDIO


# ─── COMPLAINT ID GENERATOR ───────────────────────────────────────────────────

def generate_complaint_id():
    """Generate a unique complaint ID like CMP-A3X9KPLZQR (10 random chars)."""
    return "CMP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))


# ─── EMAIL OTP SENDER ─────────────────────────────────────────────────────────

def send_otp_email(to_email, otp, name):
    """
    Send a 6-digit OTP via Gmail SMTP.
    Returns True on success, False on any failure.

    FIX: Original returned True when credentials were missing — this masked
    config errors. Now returns False and prints a clear warning.
    """
    if not EMAIL_USER or not EMAIL_PASSWORD:
        print("[Email] WARNING: EMAIL_USER or EMAIL_PASSWORD not set in .env — OTP not sent.")
        return False

    try:
        body = (
            f"Dear {name},\n\n"
            f"Your OTP for the Municipal Complaint System is:\n\n"
            f"    {otp}\n\n"
            f"This OTP is valid for 10 minutes. Do not share it with anyone.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"– Municipal Complaint System"
        )
        msg = MIMEText(body)
        msg["Subject"] = "Email Verification OTP – Municipal Complaint System"
        msg["From"]    = EMAIL_USER
        msg["To"]      = to_email

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, to_email, msg.as_string())
        return True

    except Exception as e:
        err_msg = str(e)
        if "535" in err_msg or "BadCredentials" in err_msg or "Username and Password not accepted" in err_msg:
            print("[Email] GMAIL AUTH FAILED: You must use a Gmail App Password, not your regular password.")
            print("[Email] Steps to fix:")
            print("[Email]   1. Go to https://myaccount.google.com/apppasswords")
            print("[Email]   2. Create an App Password for 'Mail'")
            print("[Email]   3. Copy the 16-character code into EMAIL_PASSWORD in your .env file")
            print(f"[Email] Raw error: {e}")
        else:
            print(f"[Email] Error sending OTP: {e}")
        return False


# ─── SLA DEADLINE CALCULATOR ──────────────────────────────────────────────────

def get_sla_info(complaint):
    """
    Returns (sla_days, deadline_str, remaining_days) for a complaint.

    FIX: Wrapped timestamp parsing in try/except — a malformed or NULL
    timestamp in the DB would previously crash the entire admin/track page.
    """
    category = complaint["category"]
    sla_days = SLA_DAYS.get(category, 7)  # Default 7 days if category not in map

    try:
        submit_dt = datetime.strptime(complaint["timestamp"], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        submit_dt = datetime.now()  # Fallback: treat as submitted now

    deadline     = submit_dt + timedelta(days=sla_days)
    deadline_str = deadline.strftime("%d %b %Y")

    remaining_days = None
    if complaint["status"] != "Resolved":
        remaining_days = (deadline - datetime.now()).days

    return sla_days, deadline_str, remaining_days


# ─── GEMINI CALL WITH MODEL FALLBACK ─────────────────────────────────────────

def call_gemini(contents):
    """
    Try each Gemini model in GEMINI_MODELS order until one succeeds.
    Only retries on quota (429) or not-found (404) errors.
    All other errors are re-raised immediately.
    """
    last_error = None
    for model in GEMINI_MODELS:
        try:
            print(f"[Gemini] Trying model: {model}")
            resp = genai_client.models.generate_content(model=model, contents=contents)
            print(f"[Gemini] Success with: {model}")
            return resp
        except Exception as e:
            err_str = str(e)
            print(f"[Gemini] Model {model} failed: {e}")
            last_error = e
            if "429" not in err_str and "RESOURCE_EXHAUSTED" not in err_str and "404" not in err_str:
                raise e
    raise last_error


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Root URL — redirect to home page."""
    return redirect(url_for("home_page"))


# ── HOME ──────────────────────────────────────────────────────────────────────

@app.route("/home")
def home_page():
    """Public home page with live stats. No login required."""
    with connect() as conn:
        total    = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0]
        citizens = conn.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0]
    return render_template("home.html", total=total, resolved=resolved, citizens=citizens)


# ── SIGNUP ────────────────────────────────────────────────────────────────────

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """
    Register a new user with email OTP verification.
    Validates admin code if role=admin.
    Stores pending signup in session until OTP is verified.
    """
    states = list(STATE_ADMIN_CODES.keys())

    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role     = request.form.get("role", "user")
        state    = request.form.get("state", "")

        # Validate admin authorization code before doing anything else
        if role == "admin":
            entered_code = request.form.get("admin_code", "").strip()
            if entered_code != STATE_ADMIN_CODES.get(state, ""):
                return render_template("signup.html", states=states,
                                       error="Invalid Admin Code for the selected state!")

        # Check for duplicate email early — gives clearer error than post-OTP IntegrityError
        with connect() as conn:
            existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            return render_template("signup.html", states=states,
                                   error="An account with this email already exists. Please log in.")

        # Generate 6-digit OTP and store pending signup data in session
        otp = str(random.randint(100000, 999999))
        session["pending_signup"] = {
            "name":     name,
            "email":    email,
            "password": generate_password_hash(password),
            "role":     role,
            "state":    state,
            "otp":      otp,
            "otp_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        if send_otp_email(email, otp, name):
            return redirect(url_for("verify_otp"))
        else:
            session.pop("pending_signup", None)
            return render_template("signup.html", states=states,
                                   error="Failed to send OTP. Gmail rejected the credentials — use a Gmail App Password (not your regular password). See terminal for steps.")

    return render_template("signup.html", states=states)


# ── OTP VERIFICATION ──────────────────────────────────────────────────────────

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    """
    Verify the 6-digit OTP entered by the user.
    On success: create user in DB, redirect to login.
    On expiry: redirect back to signup with error.
    """
    pending = session.get("pending_signup")
    if not pending:
        # No pending signup in session — user navigated here directly
        return redirect(url_for("signup"))

    if request.method == "POST":
        entered_otp = request.form.get("otp", "").strip()

        # Parse OTP timestamp safely
        try:
            otp_time = datetime.strptime(pending["otp_time"], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            session.pop("pending_signup", None)
            return redirect(url_for("signup"))

        # Check if OTP has expired (10-minute window)
        if datetime.now() - otp_time > timedelta(minutes=10):
            session.pop("pending_signup", None)
            return render_template("signup.html",
                                   error="OTP expired. Please register again.",
                                   states=list(STATE_ADMIN_CODES.keys()))

        # Validate entered OTP
        if entered_otp == pending["otp"]:
            try:
                with connect() as conn:
                    conn.execute(
                        "INSERT INTO users (name, email, password, role, state, verified) VALUES(?,?,?,?,?,1)",
                        (pending["name"], pending["email"], pending["password"],
                         pending["role"], pending["state"]),
                    )
                session.pop("pending_signup", None)
                flash("Account verified! You can now log in.")
                return redirect(url_for("login") + "?verified=1")
            except sqlite3.IntegrityError:
                # Race condition — account created between check and insert
                session.pop("pending_signup", None)
                return render_template("verifyOTP.html", email=pending["email"],
                                       error="An account with this email already exists.")

        return render_template("verifyOTP.html", email=pending["email"],
                               error="Wrong OTP! Please check again.")

    return render_template("verifyOTP.html", email=pending["email"])


# ── RESEND OTP ────────────────────────────────────────────────────────────────

@app.route("/resend-otp")
def resend_otp():
    """
    Resend a fresh OTP to the user's pending signup email.
    FIX: This route was completely missing — verifyOTP.html links to /resend-otp
    which caused a 404 every time the user clicked "Resend Code".
    """
    pending = session.get("pending_signup")
    if not pending:
        return redirect(url_for("signup"))

    # Generate new OTP and reset the 10-minute timer
    new_otp = str(random.randint(100000, 999999))
    pending["otp"]      = new_otp
    pending["otp_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session["pending_signup"] = pending  # Write updated data back to session

    send_otp_email(pending["email"], new_otp, pending["name"])
    return redirect(url_for("verify_otp") + "?resent=1")


# ── LOGIN ─────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Authenticate user by email + hashed password.
    Sets session: user_id, user (name), role, state.
    Admin → /admin, User → /home.
    """
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with connect() as conn:
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if user and check_password_hash(user["password"], password):
            # FIX: Block unverified accounts — user must complete OTP step before logging in.
            # Without this check, a user who never verified their email could still log in
            # if they somehow reached the login page after partial signup.
            if not user["verified"]:
                return render_template("login.html",
                                       error="Your email is not verified. Please complete OTP verification.")

            # All checks passed — populate session and redirect by role
            session.update({
                "user_id": user["id"],
                "user":    user["name"],
                "role":    user["role"],
                "state":   user["state"],
            })
            return redirect(url_for("admin") if user["role"] == "admin" else url_for("home_page"))

        # Wrong email or password — intentionally vague to prevent user enumeration
        return render_template("login.html", error="Invalid Email or Password.")

    return render_template("login.html")


# ── SUBMIT COMPLAINT ──────────────────────────────────────────────────────────

@app.route("/submit", methods=["GET", "POST"])
def submit():
    """
    File a new complaint. Login required.
    Saves image upload and GPS coordinates (latitude/longitude) if provided.
    """
    if not session.get("user"):
        return redirect(url_for("login"))

    if request.method == "POST":
        # Handle optional image upload
        img_name = ""
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename):
            img_name = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], img_name))

        cid = generate_complaint_id()

        with connect() as conn:
            conn.execute(
                """INSERT INTO complaints
                   (complaint_id, name, category, description, status,
                    timestamp, image, address, latitude, longitude, state, mobile)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid,
                    request.form.get("name", "").strip(),
                    request.form.get("category", "other"),
                    request.form.get("description", "").strip(),
                    "Pending",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    img_name,
                    request.form.get("address", "").strip(),
                    request.form.get("latitude", "").strip(),   # GPS lat from form
                    request.form.get("longitude", "").strip(),  # GPS lng from form
                    session.get("state", ""),
                    request.form.get("mobile", "").strip(),
                ),
            )

        return render_template("submit.html", success_cid=cid)

    return render_template("submit.html")


# ── AI COMPLAINT ANALYSER ─────────────────────────────────────────────────────

@app.route("/analyse-complaint", methods=["POST"])
def analyse_complaint():
    """
    Analyses a voice recording or image using Gemini AI.
    Returns JSON: {"category": "...", "description": "..."}

    Returns a clear error (not a crash) if AI_AVAILABLE is False,
    so the rest of the app keeps working even without the AI package.
    """
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401

    # Return a helpful error instead of crashing if genai is not installed
    if not AI_AVAILABLE:
        return jsonify({
            "error": "AI features not available. Install google-genai and set GEMINI_API_KEY in .env"
        }), 503

    try:
        response = None

        # ── AUDIO MODE ────────────────────────────────────────────────────────
        if "audio" in request.files:
            audio = request.files["audio"]
            if not audio or not audio.filename:
                return jsonify({"error": "No audio file provided"}), 400

            audio_bytes = audio.read()
            mime_type   = audio.mimetype or "audio/webm"
            ext_map = {
                "audio/wav": ".wav", "audio/wave": ".wav",
                "audio/webm": ".webm", "audio/ogg": ".ogg",
                "audio/mp3": ".mp3", "audio/mpeg": ".mp3",
                "audio/m4a": ".m4a", "audio/mp4": ".m4a",
            }
            ext = ext_map.get(mime_type, ".webm")

            # Audio must be uploaded via Gemini File API (inline bytes not supported for audio)
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                uploaded_file = genai_client.files.upload(
                    file=tmp_path,
                    config=genai_types.UploadFileConfig(mime_type=mime_type)
                )
            finally:
                os.unlink(tmp_path)  # Always delete temp file

            prompt = (
                "User is reporting a municipal issue in India.\n"
                "Language may be Marathi, Hindi, or English.\n\n"
                "1. Detect language automatically\n"
                "2. Translate to English\n"
                "3. Identify category from:\n"
                "[Garbage, Road Damage, Streetlight, Water Supply, Drainage, Mosquito, "
                "Construction, Encroachment, Dead Animal, Fire, Manhole, Dog, Other]\n\n"
                "4. Return ONLY valid JSON, no markdown, no explanation:\n"
                '{"category": "...", "description": "..."}'
            )
            response = call_gemini([prompt, uploaded_file])

        # ── IMAGE MODE ────────────────────────────────────────────────────────
        elif "image" in request.files:
            image = request.files["image"]
            if not image or not image.filename:
                return jsonify({"error": "No image provided"}), 400

            image_bytes = image.read()

            # 3-layer MIME type resolution: browser header → extension → magic bytes
            raw_mime    = image.mimetype or ""
            ext_to_mime = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png",  "webp": "image/webp",
                "gif": "image/gif",  "bmp":  "image/bmp",
            }

            if raw_mime and raw_mime not in ("application/octet-stream", ""):
                mime_type = raw_mime
            else:
                ext = (image.filename or "").rsplit(".", 1)[-1].lower()
                mime_type = ext_to_mime.get(ext, "")

            # Magic bytes fallback — identify format from first 12 bytes of file data
            if not mime_type or mime_type == "application/octet-stream":
                header = image_bytes[:12]
                if header[:8] == b'\x89PNG\r\n\x1a\n':   mime_type = "image/png"
                elif header[:3] == b'\xff\xd8\xff':       mime_type = "image/jpeg"
                elif header[:4] == b'RIFF' and header[8:12] == b'WEBP': mime_type = "image/webp"
                elif header[:6] in (b'GIF87a', b'GIF89a'): mime_type = "image/gif"
                elif header[:2] == b'BM':                  mime_type = "image/bmp"
                else: mime_type = "image/jpeg"  # Safe default

            print(f"[Image] Resolved MIME type: {mime_type}")

            prompt = (
                "Analyze this image of a municipal issue.\n\n"
                "1. Identify category from:\n"
                "[Garbage, Road Damage, Streetlight, Water Supply, Drainage, Mosquito, "
                "Construction, Encroachment, Dead Animal, Fire, Manhole, Dog, Other]\n\n"
                "2. Write a concise one-sentence English description.\n\n"
                "Return ONLY valid JSON, no markdown, no explanation:\n"
                '{"category": "...", "description": "..."}'
            )
            response = call_gemini([
                prompt,
                genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            ])

        else:
            return jsonify({"error": "No file provided"}), 400

        # ── SAFE JSON PARSE ────────────────────────────────────────────────────
        raw_text = (response.text or "").strip()
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        print(f"[Gemini] Raw response: {raw_text}")

        try:
            start     = raw_text.find("{")
            end       = raw_text.rfind("}") + 1
            data      = json.loads(raw_text[start:end])
        except Exception:
            data = {"category": "Other", "description": raw_text[:200]}

        return jsonify(data)

    except Exception as e:
        print(f"[AI ERROR] {e}")
        return jsonify({"error": f"AI processing failed: {str(e)}"}), 500


# ── TRACK COMPLAINT ───────────────────────────────────────────────────────────

@app.route("/track", methods=["GET", "POST"])
def track():
    """
    Look up a complaint by ID. Accepts both POST (form) and GET (?cid=...) for URL sharing.
    FIX: Input normalized to uppercase so CMP-abc123 matches CMP-ABC123.
    """
    complaint      = None
    sla_days       = 0
    remaining_days = None
    deadline_str   = ""

    if request.method == "POST":
        cid = request.form.get("cid", "").strip().upper()
    else:
        cid = request.args.get("cid", "").strip().upper()

    if cid:
        with connect() as conn:
            complaint = conn.execute(
                "SELECT * FROM complaints WHERE complaint_id=?", (cid,)
            ).fetchone()

        if complaint:
            sla_days, deadline_str, remaining_days = get_sla_info(complaint)

    return render_template(
        "track.html",
        complaint=complaint,
        cid=cid,
        sla_days=sla_days,
        remaining_days=remaining_days,
        deadline_str=deadline_str,
    )


# ── ADMIN PANEL ───────────────────────────────────────────────────────────────

@app.route("/admin")
def admin():
    """
    Admin dashboard for a specific state.
    Shows all complaints sorted by urgency (overdue first, resolved last).
    FIX: timestamp parsing wrapped in try/except — malformed timestamps
    no longer crash the entire page.
    """
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    state  = session.get("state", "")
    search = request.args.get("search", "").strip()

    with connect() as conn:
        if search:
            like = f"%{search}%"
            rows = conn.execute(
                """SELECT * FROM complaints
                   WHERE state=?
                   AND (complaint_id LIKE ? OR name LIKE ? OR category LIKE ?
                        OR status LIKE ? OR description LIKE ? OR mobile LIKE ?)
                   ORDER BY timestamp DESC""",
                (state, like, like, like, like, like, like)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM complaints WHERE state=? ORDER BY timestamp DESC", (state,)
            ).fetchall()

        total    = conn.execute("SELECT COUNT(*) FROM complaints WHERE state=?", (state,)).fetchone()[0]
        pending  = conn.execute("SELECT COUNT(*) FROM complaints WHERE state=? AND status='Pending'", (state,)).fetchone()[0]
        progress = conn.execute("SELECT COUNT(*) FROM complaints WHERE state=? AND status='In Progress'", (state,)).fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM complaints WHERE state=? AND status='Resolved'", (state,)).fetchone()[0]

    def sort_key(c):
        """Resolved go last; non-resolved sorted by days remaining (most urgent first)."""
        if c["status"] == "Resolved":
            return (1, 9999)
        sla = SLA_DAYS.get(c["category"], 7)
        try:
            sub  = datetime.strptime(c["timestamp"], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            sub  = datetime.now()
        dead = sub + timedelta(days=sla)
        return (0, (dead - datetime.now()).days)

    complaints_sorted = sorted(rows, key=sort_key)

    # Attach SLA deadline info to each row for the template
    complaints_with_deadline = []
    for c in complaints_sorted:
        sla = SLA_DAYS.get(c["category"], 7)
        try:
            sub = datetime.strptime(c["timestamp"], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            sub = datetime.now()
        dead         = sub + timedelta(days=sla)
        remaining    = (dead - datetime.now()).days if c["status"] != "Resolved" else None
        deadline_str = dead.strftime("%d %b %Y")
        complaints_with_deadline.append({
            "c":            c,
            "deadline_str": deadline_str,
            "remaining":    remaining,
        })

    return render_template(
        "admin.html",
        data=complaints_with_deadline,
        admin_state=state,
        search=search,
        total=total,
        pending=pending,
        progress=progress,
        resolved=resolved,
    )


# ── UPDATE COMPLAINT STATUS ───────────────────────────────────────────────────

@app.route("/update/<int:id>/<string:status>")
def update_status(id, status):
    """
    Update a complaint's status. Admin only.
    FIX: Previously accepted any string via URL (e.g. /update/1/anything).
    Now uses a whitelist — only 'progress' and 'resolved' are valid.
    """
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    new_status = VALID_STATUS_MAP.get(status)
    if not new_status:
        return f"Invalid status: {status}", 400

    with connect() as conn:
        conn.execute("UPDATE complaints SET status=? WHERE id=?", (new_status, id))

    return redirect(url_for("admin"))


# ── LOGOUT ────────────────────────────────────────────────────────────────────

@app.route("/logout")
def logout():
    """Clear session and redirect to home page."""
    session.clear()
    return redirect(url_for("home_page"))


# ─── STARTUP ──────────────────────────────────────────────────────────────────

# FIX: init_db() is called at module level so it runs under Gunicorn/uWSGI too.
# Original code only called it inside `if __name__ == "__main__"` which meant
# tables were never created when using a production WSGI server.
init_db()

if __name__ == "__main__":
    app.run(debug=True)