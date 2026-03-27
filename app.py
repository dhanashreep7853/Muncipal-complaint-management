from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DB CONNECTION ----------------
def connect():
    conn = sqlite3.connect("complaints.db", timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- GENERATE COMPLAINT ID ----------------
def generate_complaint_id():
    chars = string.ascii_uppercase + string.digits
    return "CMP-" + "".join(random.choices(chars, k=8))

# ---------------- INIT DB ----------------
def init_db():
    with connect() as conn:
        cur = conn.cursor()

        # complaints table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS complaints(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT,
            name TEXT,
            category TEXT,
            priority TEXT,
            description TEXT,
            status TEXT,
            timestamp TEXT
        )
        """)

        # users table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
        """)

# ---------------- DASHBOARD ----------------
@app.route("/")
def dashboard():
    cid = request.args.get("cid")

    with connect() as conn:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM complaints")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'")
        pending = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'")
        resolved = cur.fetchone()[0]

    return render_template("dashboard.html",
                           total=total,
                           pending=pending,
                           resolved=resolved,
                           cid=cid)

# ---------------- SUBMIT ----------------
@app.route("/submit", methods=["GET","POST"])
def submit():
    if not session.get("user"):
        return redirect("/login")

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        priority = request.form["priority"]
        description = request.form["description"]

        complaint_id = generate_complaint_id()

        with connect() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO complaints
            (complaint_id,name,category,priority,description,status,timestamp)
            VALUES(?,?,?,?,?,?,?)
            """,(complaint_id,name,category,priority,description,"Pending",str(datetime.now())))

        return redirect(f"/?cid={complaint_id}")

    return render_template("submit.html")

# ---------------- TRACK ----------------
@app.route("/track", methods=["GET","POST"])
def track():
    if not session.get("user"):
        return redirect("/login")

    complaint = None

    if request.method == "POST":
        cid = request.form["cid"]

        with connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM complaints WHERE complaint_id=?",(cid,))
            complaint = cur.fetchone()

    return render_template("track.html", complaint=complaint)

# ---------------- ADMIN ----------------
@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return redirect("/")

    with connect() as conn:
        cur = conn.cursor()

        cur.execute("""
        SELECT * FROM complaints
        ORDER BY 
            CASE priority
                WHEN 'High' THEN 1
                WHEN 'Medium' THEN 2
                WHEN 'Low' THEN 3
            END
        """)

        data = cur.fetchall()

    return render_template("admin.html", data=data)

# ---------------- UPDATE STATUS ----------------
@app.route("/update/<int:id>/<status>")
def update_status(id, status):
    if session.get("role") != "admin":
        return redirect("/")

    new_status = "In Progress" if status == "progress" else "Resolved"

    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE complaints SET status=? WHERE id=?",(new_status,id))

    return redirect("/admin")

# ---------------- SIGNUP ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        admin_code = request.form.get('admin_code')
        hashed_pw = generate_password_hash(password)
        
        # 🔒 Admin security
        if role == "admin" and admin_code != "ADMIN@123":
            return "Invalid Admin Code!"

        try:
            with connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                    (name, email, password, role)
                )
            return redirect('/login')

        except sqlite3.IntegrityError:
            return "Email already exists!"

    return render_template("signup.html")

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        with connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email=?", (email,))
            user = cur.fetchone()

        # Check the hashed password
        if user and check_password_hash(user['password'], password):
            session['user'] = user['name']
            session['role'] = user['role']
            return redirect('/') 
        
        else:
            return "Invalid Email or Password!"

    return render_template("login.html")

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)