from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)

def connect():
    return sqlite3.connect("complaints.db")

def init_db():
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS complaints(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        category TEXT,
        priority TEXT,
        description TEXT,
        status TEXT,
        timestamp TEXT
    )
    """)
    conn.commit()
    conn.close()

@app.route("/")
def dashboard():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM complaints")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'")
    pending = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'")
    resolved = cur.fetchone()[0]
    conn.close()
    return render_template("dashboard.html", total=total, pending=pending, resolved=resolved)

@app.route("/submit", methods=["GET","POST"])
def submit():
    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        priority = request.form["priority"]
        description = request.form["description"]
        conn = connect()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO complaints
        (name,category,priority,description,status,timestamp)
        VALUES(?,?,?,?,?,?)
        """,(name,category,priority,description,"Pending",datetime.now()))
        conn.commit()
        conn.close()
        return redirect("/")
    return render_template("submit.html")

@app.route("/track", methods=["GET","POST"])
def track():
    complaint=None
    if request.method=="POST":
        cid=request.form["cid"]
        conn=connect()
        cur=conn.cursor()
        cur.execute("SELECT * FROM complaints WHERE id=?",(cid,))
        complaint=cur.fetchone()
        conn.close()
    return render_template("track.html",complaint=complaint)

@app.route("/admin")
def admin():
    conn=connect()
    cur=conn.cursor()
    cur.execute("SELECT * FROM complaints ORDER BY priority DESC")
    data=cur.fetchall()
    conn.close()
    return render_template("admin.html",data=data)

@app.route("/update/<int:id>/<status>")
def update_status(id,status):
    conn=connect()
    cur=conn.cursor()
    if status=="progress":
        new_status="In Progress"
    else:
        new_status="Resolved"
    cur.execute("UPDATE complaints SET status=? WHERE id=?",(new_status,id))
    conn.commit()
    conn.close()
    return redirect("/admin")

if __name__=="__main__":
    init_db()
    app.run(debug=True)