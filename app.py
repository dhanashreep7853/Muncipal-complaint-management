from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime 
import random
import string
from flask import session

# Generate unique complaint ID
def generate_complaint_id():
    chars = string.ascii_uppercase + string.digits + "@#"
    return "CMP-" + "".join(random.choices(chars, k=10))

# connect database.py
app = Flask(__name__)
app.secret_key = "your_secret_key"

def connect():
    return sqlite3.connect("complaints.db", timeout=10)

# Initialize DB
def init_db():
    conn = connect()
    cur = conn.cursor()
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)
    conn.commit()
    conn.close()

# ---------------- DASHBOARD ----------------
@app.route("/")
def dashboard():
    cid = request.args.get("cid")

    conn = connect()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM complaints")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'")
    pending = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'")
    resolved = cur.fetchone()[0]

    conn.close()

    return render_template("dashboard.html",
                           total=total,
                           pending=pending,
                           resolved=resolved,
                           cid=cid)

# ---------------- SUBMIT ----------------
@app.route("/submit", methods=["GET","POST"])
def submit():
    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        priority = request.form["priority"]
        description = request.form["description"]

        complaint_id = generate_complaint_id()

        conn = connect()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO complaints
        (complaint_id,name,category,priority,description,status,timestamp)
        VALUES(?,?,?,?,?,?,?)
        """,(complaint_id,name,category,priority,description,"Pending",str(datetime.now())))

        conn.commit()
        conn.close()

        return redirect(f"/?cid={complaint_id}")

    return render_template("submit.html")

# ---------------- TRACK ----------------
@app.route("/track", methods=["GET","POST"])
def track():
    complaint = None

    if request.method == "POST":
        cid = request.form["cid"]

        conn = connect()
        cur = conn.cursor()

        cur.execute("SELECT * FROM complaints WHERE complaint_id=?",(cid,))
        complaint = cur.fetchone()

        conn.close()

    return render_template("track.html", complaint=complaint)

# ---------------- ADMIN ----------------
@app.route("/admin")
def admin():
    conn = connect()
    cur = conn.cursor()

    # Sort priority properly
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
    conn.close()

    return render_template("admin.html", data=data)

# ---------------- UPDATE ----------------
@app.route("/update/<int:id>/<status>")
def update_status(id, status):
    conn = connect()
    cur = conn.cursor()

    if status == "progress":
        new_status = "In Progress"
    else:
        new_status = "Resolved"

    cur.execute("UPDATE complaints SET status=? WHERE id=?",(new_status,id))
    conn.commit()
    conn.close()

    return redirect("/admin")

# ---------------- Signup ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        admin_code = request.form.get('admin_code')
        # 🔒 Admin Security
        if role == "admin":
            if admin_code != "ADMIN@123":
                return "Invalid Admin Code!"
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                (name, email, password, role)
            )
            conn.commit()
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            return "Email already exists!"
        except Exception as e:
            return f"Error: {e}"
    # ✅ VERY IMPORTANT (handles GET request)
    return render_template("signup.html")

# ---------------- login ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user'] = user[1]   # name
            session['role'] = user[4]   # role
            return redirect('/')
        else:
            return "Invalid Email or Password!"
    return render_template("login.html")    

# ---------------- logout ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- RUN ----------------
if __name__=="__main__":
    init_db()
    app.run(debug=True)