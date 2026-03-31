from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
from datetime import datetime, timedelta
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "municipal_secret_2025"

# ─── CONFIGURATION ──────────────────────────────────────────────────────
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

EMAIL_HOST     = "smtp.gmail.com"
EMAIL_PORT     = 587
EMAIL_USER     = "pdhanshree84@gmail.com"
EMAIL_PASSWORD = "lytrftcbckmcgpfe"

# ─── STATE ADMIN CODES ───────────────────────────────────────────────────
STATE_ADMIN_CODES = {
    "Andhra Pradesh": "AP@ADMIN2026", "Arunachal Pradesh": "AR@ADMIN2026",
    "Assam": "AS@ADMIN2026", "Bihar": "BR@ADMIN2026", "Chhattisgarh": "CG@ADMIN2026",
    "Goa": "GA@ADMIN2026", "Gujarat": "GJ@ADMIN2026", "Haryana": "HR@ADMIN2026",
    "Himachal Pradesh": "HP@ADMIN2026", "Jharkhand": "JH@ADMIN2026",
    "Karnataka": "KA@ADMIN2026", "Kerala": "KL@ADMIN2026", "Madhya Pradesh": "MP@ADMIN2026",
    "Maharashtra": "MH@ADMIN2026", "Manipur": "MN@ADMIN2026", "Meghalaya": "ML@ADMIN2026",
    "Mizoram": "MZ@ADMIN2026", "Nagaland": "NL@ADMIN2026", "Odisha": "OD@ADMIN2026",
    "Punjab": "PB@ADMIN2026", "Rajasthan": "RJ@ADMIN2026", "Sikkim": "SK@ADMIN2026",
    "Tamil Nadu": "TN@ADMIN2026", "Telangana": "TG@ADMIN2026", "Tripura": "TR@ADMIN2026",
    "Uttar Pradesh": "UP@ADMIN2026", "Uttarakhand": "UK@ADMIN2026", "West Bengal": "WB@ADMIN2026",
    "Delhi": "DL@ADMIN2026", "Jammu & Kashmir": "JK@ADMIN2026", "Ladakh": "LA@ADMIN2026",
    "Puducherry": "PY@ADMIN2026", "Chandigarh": "CH@ADMIN2026",
}

# ─── SLA SETTINGS ────────────────────────────────────────────────────────
SLA_DAYS = {
    "Garbage": 2, "Road Damage": 7, "Streetlight": 5, "Water Supply": 3,
    "Drainage": 4, "Mosquito": 3, "Construction": 10, "Encroachment": 10,
    "Hoardings": 7, "Buildings": 7, "Tree Cutting": 5, "Garden": 7,
    "air Pollution": 5, "Dead Animal": 1, "Toilet": 3, "Food Safety": 3,
    "Stray Cattle": 3, "Noise Pollution": 3, "Manhole": 2, "Dog": 3,
    "Tax": 14, "Fire": 1, "other": 7,
}

# ─── HELPERS ─────────────────────────────────────────────────────────────

def connect():
    conn = sqlite3.connect("complaints.db", timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_complaint_id():
    return "CMP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def send_otp_email(to_email, otp, name):
    if not EMAIL_USER or not EMAIL_PASSWORD:
        return True
    try:
        msg = MIMEText(
            f"Dear {name},\n\n"
            f"Your OTP for the Municipal Complaint System is: {otp}\n\n"
            f"This OTP is valid for 10 minutes."
        )
        msg["Subject"] = "Email Verification - Municipal System"
        msg["From"]    = EMAIL_USER
        msg["To"]      = to_email
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Mail Error: {e}")
        return False

def get_sla_info(complaint):
    """Returns (sla_days, deadline_str, remaining_days) for a complaint row."""
    category   = complaint["category"]
    sla_days   = SLA_DAYS.get(category, 7)
    submit_dt  = datetime.strptime(complaint["timestamp"], "%Y-%m-%d %H:%M:%S")
    deadline   = submit_dt + timedelta(days=sla_days)
    deadline_str = deadline.strftime("%d %b %Y")
    remaining_days = None
    if complaint["status"] != "Resolved":
        remaining_days = (deadline - datetime.now()).days
    return sla_days, deadline_str, remaining_days

# ─── DATABASE INIT ───────────────────────────────────────────────────────

def init_db():
    with connect() as conn:
        # complaints table — no lat/lng, mobile included
        conn.execute("""CREATE TABLE IF NOT EXISTS complaints(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT, name TEXT, mobile TEXT, category TEXT,
            description TEXT, status TEXT, timestamp TEXT,
            image TEXT, address TEXT, state TEXT)""")
        # users table — only essential columns
        conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT UNIQUE, password TEXT,
            role TEXT, state TEXT, verified INTEGER DEFAULT 0)""")
        # Safe migrations for existing DBs
        for col in ["mobile"]:
            try:
                conn.execute(f"ALTER TABLE complaints ADD COLUMN {col} TEXT DEFAULT ''")
            except Exception:
                pass
        conn.commit()

# ─── ROUTES ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("home_page"))


@app.route("/home")
def home_page():
    with connect() as conn:
        total    = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0]
        citizens = conn.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0]
    return render_template("home.html", total=total, resolved=resolved, citizens=citizens)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    states = list(STATE_ADMIN_CODES.keys())
    if request.method == "POST":
        role  = request.form["role"]
        state = request.form.get("state", "")

        if role == "admin" and request.form.get("admin_code") != STATE_ADMIN_CODES.get(state):
            return render_template("signup.html", states=states,
                                   error="Invalid Admin Code for the selected state!")

        otp = str(random.randint(100000, 999999))
        session["pending_signup"] = {
            "name":     request.form["name"],
            "email":    request.form["email"],
            "password": generate_password_hash(request.form["password"]),
            "role":     role,
            "state":    state,
            "otp":      otp,
            "otp_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        if send_otp_email(request.form["email"], otp, request.form["name"]):
            return redirect(url_for("verify_otp"))
        else:
            return render_template("signup.html", states=states,
                                   error="Failed to send OTP. Check internet connection.")

    return render_template("signup.html", states=states)


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    pending = session.get("pending_signup")
    if not pending:
        return redirect(url_for("signup"))

    if request.method == "POST":
        entered_otp = request.form.get("otp")
        otp_time    = datetime.strptime(pending["otp_time"], "%Y-%m-%d %H:%M:%S")

        if datetime.now() - otp_time > timedelta(minutes=10):
            session.pop("pending_signup", None)
            return render_template("signup.html",
                                   error="OTP expired. Please try again.",
                                   states=list(STATE_ADMIN_CODES.keys()))

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
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                return render_template("verifyOTP.html", email=pending["email"],
                                       error="User with this email already exists!")

        return render_template("verifyOTP.html", email=pending["email"],
                               error="Wrong OTP! Please check again.")

    return render_template("verifyOTP.html", email=pending["email"])


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]

        with connect() as conn:
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session.update({
                "user_id": user["id"],
                "user":    user["name"],
                "role":    user["role"],
                "state":   user["state"],
            })
            return redirect(url_for("admin") if user["role"] == "admin" else url_for("home_page"))

        return render_template("login.html", error="Invalid Email or Password.")

    return render_template("login.html")


@app.route("/submit", methods=["GET", "POST"])
def submit():
    if not session.get("user"):
        return redirect(url_for("login"))

    if request.method == "POST":
        # ── Image upload ──
        file     = request.files.get("image")
        img_name = ""
        if file and allowed_file(file.filename):
            img_name = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], img_name))

        # ── Save complaint ──
        cid = generate_complaint_id()
        with connect() as conn:
            conn.execute(
                """INSERT INTO complaints
                   (complaint_id, name, category, description, status,
                    timestamp, image, address, state, mobile)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid,
                    request.form["name"],
                    request.form["category"],
                    request.form["description"],
                    "Pending",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    img_name,
                    request.form.get("address", ""),
                    session.get("state", ""),
                    request.form.get("mobile", ""),
                ),
            )

        # Show success alert on submit page with CMP ID for user to copy
        return render_template("submit.html", success_cid=cid)

    return render_template("submit.html")


@app.route("/track", methods=["GET", "POST"])
def track():
    complaint      = None
    sla_days       = 0
    remaining_days = None
    deadline_str   = ""

    # ── FIX: unified CID resolution ──
    # GET  → comes from redirect after submit  (?cid=CMP-XXXXX)
    # POST → comes from manual search form
    if request.method == "POST":
        cid = request.form.get("cid", "").strip()
    else:
        cid = request.args.get("cid", "").strip()

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
        cid=cid,                    # pass back so the input stays filled
        sla_days=sla_days,
        remaining_days=remaining_days,
        deadline_str=deadline_str,
    )


@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    state  = session.get("state")
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

        # Summary counts for stat cards
        total    = conn.execute("SELECT COUNT(*) FROM complaints WHERE state=?", (state,)).fetchone()[0]
        pending  = conn.execute("SELECT COUNT(*) FROM complaints WHERE state=? AND status='Pending'", (state,)).fetchone()[0]
        progress = conn.execute("SELECT COUNT(*) FROM complaints WHERE state=? AND status='In Progress'", (state,)).fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM complaints WHERE state=? AND status='Resolved'", (state,)).fetchone()[0]

    # ── Sort: unresolved first (by remaining SLA days asc — most urgent first)
    #         resolved complaints sink to the bottom
    def sort_key(c):
        if c["status"] == "Resolved":
            return (1, 9999)   # always last
        sla  = SLA_DAYS.get(c["category"], 7)
        sub  = datetime.strptime(c["timestamp"], "%Y-%m-%d %H:%M:%S")
        dead = sub + timedelta(days=sla)
        remaining = (dead - datetime.now()).days
        return (0, remaining)  # unresolved, sorted by days remaining asc

    complaints = sorted(rows, key=sort_key)

    # ── Attach deadline info to each complaint for the template
    complaints_with_deadline = []
    for c in complaints:
        sla  = SLA_DAYS.get(c["category"], 7)
        sub  = datetime.strptime(c["timestamp"], "%Y-%m-%d %H:%M:%S")
        dead = sub + timedelta(days=sla)
        remaining = (dead - datetime.now()).days if c["status"] != "Resolved" else None
        deadline_str = dead.strftime("%d %b %Y")
        complaints_with_deadline.append({
            "c": c,
            "deadline_str": deadline_str,
            "remaining": remaining
        })

    return render_template("admin.html",
                           data=complaints_with_deadline,
                           admin_state=state,
                           search=search,
                           total=total,
                           pending=pending,
                           progress=progress,
                           resolved=resolved)


@app.route("/update/<int:id>/<string:status>")
def update_status(id, status):
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    new_status = "In Progress" if status == "progress" else "Resolved"
    with connect() as conn:
        conn.execute("UPDATE complaints SET status=? WHERE id=?", (new_status, id))

    return redirect(url_for("admin"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home_page"))


# ─── MAIN ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True)