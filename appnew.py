from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
ADMIN_EMAIL = "admin@gmail.com"

# ================= DATABASE =================
def get_db():
    return sqlite3.connect("grievance.db")

def create_tables():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS grievances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_email TEXT,
        student_name TEXT,
        department TEXT,
        section TEXT,
        category TEXT,
        complaint TEXT,
        authority TEXT,
        status TEXT,
        delay_reason TEXT,
        delay_days TEXT,
        rating INTEGER,
        feedback TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        message TEXT,
        time TEXT,
        is_read INTEGER DEFAULT 0
    )
    """)

    con.commit()
    con.close()

create_tables()

# ================= HELPERS =================
def authority_map(category):
    return {
        "Hostel": "Warden",
        "Academics": "HOD",
        "Fees": "Accounts",
        "Infrastructure": "Maintenance"
    }.get(category, "Admin")

def notify(email, msg):
    con = get_db()
    con.execute(
        "INSERT INTO notifications (user_email, message, time) VALUES (?,?,?)",
        (email, msg, datetime.now().strftime("%d-%m-%Y %H:%M"))
    )
    con.commit()
    con.close()

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        role = request.form["role"]

        if role == "admin" and email == ADMIN_EMAIL:
            return redirect(url_for("admin", email=email))
        return redirect(url_for("student", email=email))

    return render_template("login.html")

# ================= STUDENT =================
@app.route("/student/<email>", methods=["GET", "POST"])
def student(email):
    con = get_db()
    cur = con.cursor()

    if request.method == "POST":
        cur.execute("""
        INSERT INTO grievances
        (student_email, student_name, department, section, category,
         complaint, authority, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            email,
            request.form["name"],
            request.form["department"],
            request.form["section"],
            request.form["category"],
            request.form["complaint"],
            authority_map(request.form["category"]),
            "Submitted",
            datetime.now().strftime("%d-%m-%Y %H:%M")
        ))
        con.commit()

        notify(email, "Your complaint has been submitted.")
        notify(ADMIN_EMAIL, "New complaint received.")

    cur.execute("SELECT * FROM grievances WHERE student_email=? ORDER BY id DESC", (email,))
    complaints = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM notifications WHERE user_email=? AND is_read=0", (email,))
    notif_count = cur.fetchone()[0]

    con.close()
    return render_template("student.html", email=email, complaints=complaints, notif_count=notif_count)

# ================= ADMIN =================
@app.route("/admin/<email>")
def admin(email):
    con = get_db()
    cur = con.cursor()

    cur.execute("SELECT * FROM grievances ORDER BY id DESC")
    data = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM notifications WHERE user_email=? AND is_read=0", (email,))
    notif_count = cur.fetchone()[0]

    con.close()
    return render_template("admin.html", data=data, email=email, notif_count=notif_count)

# ================= ADMIN VIEW =================
@app.route("/admin/view/<int:id>/<email>")
def admin_view(id, email):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT * FROM grievances WHERE id=?", (id,))
    g = cur.fetchone()
    con.close()
    return render_template("admin_view.html", g=g, email=email)

# ================= RESOLVE (IMPORTANT) =================
@app.route("/update/<int:id>/<email>")
def update(id, email):
    con = get_db()
    cur = con.cursor()

    cur.execute("SELECT student_email FROM grievances WHERE id=?", (id,))
    student_email = cur.fetchone()[0]

    cur.execute("UPDATE grievances SET status='Resolved' WHERE id=?", (id,))
    con.commit()
    con.close()

    notify(student_email, "Your complaint has been resolved.")
    return redirect(url_for("admin", email=email))

# ================= DELAY =================
@app.route("/delay/<int:id>/<email>", methods=["GET", "POST"])
def delay(id, email):
    if request.method == "POST":
        reason = request.form["reason"]
        days = request.form["days"]

        con = get_db()
        cur = con.cursor()

        cur.execute("""
        UPDATE grievances
        SET status='Delayed', delay_reason=?, delay_days=?
        WHERE id=?
        """, (reason, days, id))

        cur.execute("SELECT student_email FROM grievances WHERE id=?", (id,))
        student_email = cur.fetchone()[0]

        con.commit()
        con.close()

        notify(student_email, f"Complaint delayed: {reason} ({days} days)")
        return redirect(url_for("admin", email=email))

    return render_template("delay.html")

# ================= FEEDBACK =================
@app.route("/feedback/<int:id>/<email>", methods=["POST"])
def feedback(id, email):
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    UPDATE grievances
    SET rating=?, feedback=?
    WHERE id=?
    """, (
        request.form["rating"],
        request.form["comment"],
        id
    ))

    con.commit()
    con.close()

    notify(ADMIN_EMAIL, f"Feedback submitted for complaint ID {id}")
    return redirect(url_for("student", email=email))

# ================= NOTIFICATIONS =================
@app.route("/notifications/<email>")
def notifications(email):
    con = get_db()
    cur = con.cursor()

    cur.execute("SELECT message, time FROM notifications WHERE user_email=? ORDER BY id DESC", (email,))
    notes = cur.fetchall()

    cur.execute("UPDATE notifications SET is_read=1 WHERE user_email=?", (email,))
    con.commit()
    con.close()

    return render_template("notifications.html", notes=notes)

if __name__ == "__main__":
    app.run(debug=True)
