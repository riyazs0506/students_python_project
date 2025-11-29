"""
Premium Student Management System — app.py
Run: python app.py

Configure database via environment variables:
DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
"""

import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from functools import wraps

# ---------- CONFIG ----------
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "123456")
DB_NAME = os.environ.get("DB_NAME", "student_management")

SECRET_KEY = os.environ.get("FLASK_SECRET", "change_me_in_prod_please")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = SECRET_KEY

# ---------- DB HELPERS ----------
def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        auth_plugin="mysql_native_password"
    )

def fetchall(query, params=()):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def fetchone(query, params=()):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def execute(query, params=()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    lastid = cur.lastrowid
    cur.close()
    conn.close()
    return lastid

# ---------- SCHEMA ENSURE ----------
def ensure_schema():
    # Attempt to create core tables if missing
    conn = get_connection()
    cur = conn.cursor()
    statements = []
    statements.append("""CREATE TABLE IF NOT EXISTS users (
      id INT AUTO_INCREMENT PRIMARY KEY,
      name VARCHAR(150),
      email VARCHAR(200) UNIQUE,
      password VARCHAR(255),
      role ENUM('Principal','Teacher') DEFAULT 'Teacher',
      must_change_password TINYINT(1) DEFAULT 0,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    statements.append("""CREATE TABLE IF NOT EXISTS teachers (
      id INT AUTO_INCREMENT PRIMARY KEY,
      user_id INT,
      principal_id INT,
      name VARCHAR(150),
      phone VARCHAR(30),
      qualification VARCHAR(255),
      specialization VARCHAR(255),
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    statements.append("""CREATE TABLE IF NOT EXISTS students (
      id INT AUTO_INCREMENT PRIMARY KEY,
      principal_id INT,
      teacher_id INT,
      name VARCHAR(150) NOT NULL,
      roll_no VARCHAR(80),
      class_name VARCHAR(80),
      standard VARCHAR(50),
      section VARCHAR(20),
      dob DATE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    statements.append("""CREATE TABLE IF NOT EXISTS subjects (
      id INT AUTO_INCREMENT PRIMARY KEY,
      principal_id INT,
      name VARCHAR(255) NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    statements.append("""CREATE TABLE IF NOT EXISTS teacher_subjects (
      id INT AUTO_INCREMENT PRIMARY KEY,
      principal_id INT,
      teacher_id INT,
      subject_id INT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    statements.append("""CREATE TABLE IF NOT EXISTS subject_proposals (
      id INT AUTO_INCREMENT PRIMARY KEY,
      principal_id INT,
      teacher_id INT,
      name VARCHAR(255) NOT NULL,
      status ENUM('Pending','Approved','Declined') DEFAULT 'Pending',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    statements.append("""CREATE TABLE IF NOT EXISTS exams (
      id INT AUTO_INCREMENT PRIMARY KEY,
      principal_id INT,
      name VARCHAR(255) NOT NULL,
      max_marks INT NOT NULL DEFAULT 100,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    statements.append("""CREATE TABLE IF NOT EXISTS exam_marks (
      id INT AUTO_INCREMENT PRIMARY KEY,
      exam_id INT,
      student_id INT,
      subject_name VARCHAR(255),
      marks INT,
      status ENUM('Pending','Approved','Declined') DEFAULT 'Pending',
      created_by INT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    for s in statements:
        try:
            cur.execute(s)
        except Exception as e:
            print("Schema ensure error:", e)
    conn.commit()
    cur.close()
    conn.close()

# Ensure schema on startup
try:
    ensure_schema()
except Exception as e:
    print("Warning: ensure_schema failed:", e)

# ---------- UTILITIES ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session and 'student_id' not in session:
            flash("Please login first.", "danger")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return wrapper

def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get('role') != role:
                flash("Access denied.", "danger")
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

def grade_from_total(total, max_total):
    if max_total == 0:
        return "-"
    perc = (total / max_total) * 100
    if perc >= 90:
        return "A+"
    if perc >= 80:
        return "A"
    if perc >= 70:
        return "B+"
    if perc >= 60:
        return "B"
    if perc >= 50:
        return "C"
    if perc >= 40:
        return "D"
    return "F"

def mark_color_class(marks, max_marks=100):
    try:
        m = int(marks)
    except:
        return ""
    perc = (m / max_marks) * 100 if max_marks else 0
    if perc >= 90:
        return "mark-topper"
    if perc >= 40:
        return "mark-pass"
    return "mark-fail"

# ---------- ROUTES ----------
@app.route('/')
def home():
    return render_template('home.html')

# LOGIN CHOICE
@app.route('/login_choice')
def login_choice():
    return render_template('login_choice.html')

# ------------------- Principal Registration + Login -------------------
@app.route('/register/principal', methods=['GET','POST'])
def register_principal():
    if request.method == 'POST':
        name = request.form.get('name','').strip() or None
        email = request.form.get('email','').strip()
        password = request.form.get('password','').strip()
        if not (email and password):
            flash("Email and password are required.", "danger")
            return redirect(url_for('register_principal'))
        if fetchone("SELECT id FROM users WHERE email=%s", (email,)):
            flash("Email already exists.", "danger")
            return redirect(url_for('register_principal'))
        pw_hash = generate_password_hash(password)
        execute("INSERT INTO users (name,email,password,role) VALUES (%s,%s,%s,'Principal')", (name, email, pw_hash))
        flash("Principal registered. You may login now.", "success")
        return redirect(url_for('login_principal'))
    return render_template('register_principal.html')

@app.route('/login/principal', methods=['GET','POST'])
def login_principal():
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        password = request.form.get('password','').strip()
        user = fetchone("SELECT * FROM users WHERE email=%s AND role='Principal'", (email,))
        if not user or not check_password_hash(user['password'], password):
            flash("Invalid credentials.", "danger")
            return redirect(url_for('login_principal'))
        session.clear()
        session['user_id'] = user['id']
        session['role'] = 'Principal'
        session['name'] = user.get('name') or user.get('email')
        return redirect(url_for('principal_dashboard'))
    return render_template('login_principal.html')

# ------------------- Teacher Login + Password change -------------------
@app.route('/login/teacher', methods=['GET','POST'])
def login_teacher():
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        password = request.form.get('password','').strip()
        user = fetchone("SELECT * FROM users WHERE email=%s AND role='Teacher'", (email,))
        if not user or not check_password_hash(user['password'], password):
            flash("Invalid credentials.", "danger")
            return redirect(url_for('login_teacher'))
        session.clear()
        session['user_id'] = user['id']
        session['role'] = 'Teacher'
        session['name'] = user.get('name') or user.get('email')
        if user.get('must_change_password'):
            flash("Please change your temporary password.", "warning")
            return redirect(url_for('teacher_change_password'))
        return redirect(url_for('teacher_dashboard'))
    return render_template('login_teacher.html')

@app.route('/teacher/change_password', methods=['GET','POST'])
def teacher_change_password():
    if 'user_id' not in session or session.get('role') != 'Teacher':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        old = request.form.get('old','').strip()
        new = request.form.get('new','').strip()
        user = fetchone("SELECT * FROM users WHERE id=%s", (session['user_id'],))
        if not user or not check_password_hash(user['password'], old):
            flash("Old password incorrect.", "danger")
            return redirect(url_for('teacher_change_password'))
        execute("UPDATE users SET password=%s, must_change_password=0 WHERE id=%s", (generate_password_hash(new), session['user_id']))
        flash("Password changed. Please login again.", "success")
        return redirect(url_for('login_teacher'))
    return render_template('teacher_change_password.html')

# ------------------- Logout -------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login_choice"))


# ------------------- Principal Dashboard -------------------
@app.route('/principal/dashboard')
def principal_dashboard():
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))

    pid = session['user_id']

    total_students = fetchone("SELECT COUNT(*) AS c FROM students WHERE principal_id=%s", (pid,))['c'] or 0
    total_teachers = fetchone("SELECT COUNT(*) AS c FROM teachers WHERE principal_id=%s", (pid,))['c'] or 0
    total_subjects = fetchone("SELECT COUNT(*) AS c FROM subjects WHERE principal_id=%s", (pid,))['c'] or 0
    pending_marks = fetchone("""
        SELECT COUNT(em.id) AS c 
        FROM exam_marks em 
        JOIN exams ex ON em.exam_id = ex.id 
        WHERE ex.principal_id=%s AND em.status='Pending'
    """, (pid,))['c'] or 0

    recent_exams = fetchall(
        "SELECT * FROM exams WHERE principal_id=%s ORDER BY id DESC",
        (pid,)
    )

    return render_template(
        'principal_dashboard.html',
        students_count=total_students,
        teachers_count=total_teachers,
        subjects_count=total_subjects,
        pending_marks=pending_marks,
        recent_exams=recent_exams
    )


# ------------------- Teacher Dashboard -------------------
@app.route('/teacher/dashboard')
def teacher_dashboard():
    if session.get('role') != 'Teacher':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    user = fetchone("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    teacher = fetchone("SELECT * FROM teachers WHERE user_id=%s", (session['user_id'],))
    students = []
    subjects = []
    new_exams = []
    if teacher:
        students = fetchall("SELECT * FROM students WHERE teacher_id=%s ORDER BY id DESC", (teacher['id'],))
        subjects = fetchall("SELECT s.* FROM subjects s JOIN teacher_subjects ts ON ts.subject_id=s.id WHERE ts.teacher_id=%s AND ts.principal_id=%s", (teacher['id'], teacher['principal_id']))
        new_exams = fetchall("SELECT * FROM exams WHERE principal_id=%s ORDER BY created_at DESC", (teacher['principal_id'],))
    return render_template('teacher_dashboard.html', teacher=teacher, students=students, subjects=subjects, new_exams=new_exams)


# Teacher view: see marks for a specific student
@app.route("/teacher/student/<int:student_id>/marks")
@login_required
def student_marks(student_id):

    # Fetch student
    student = fetchone("""
        SELECT *
        FROM students
        WHERE id=%s
    """, (student_id,))

    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for('teacher_dashboard'))

    # Fetch marks WITHOUT subject (subject not stored in your DB)
    marks = fetchall("""
        SELECT 
            ex.name AS exam_name,
            ex.max_marks,
            em.marks
        FROM exam_marks em
        JOIN exams ex ON ex.id = em.exam_id
        WHERE em.student_id=%s
          AND em.status='Approved'
        ORDER BY ex.id DESC
    """, (student_id,))

    return render_template("teacher_student_marks.html",
                           student=student,
                           marks=marks)



# ------------------- Teachers CRUD (Principal) -------------------
@app.route('/teachers')
def teachers_list():
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    teachers = fetchall("SELECT t.*, u.email FROM teachers t LEFT JOIN users u ON t.user_id=u.id WHERE t.principal_id=%s ORDER BY t.id DESC", (session['user_id'],))
    return render_template('teachers.html', teachers=teachers)

@app.route('/teacher/add', methods=['GET','POST'])
def add_teacher():
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        name = request.form.get('name','').strip() or None
        email = request.form.get('email','').strip() or None
        phone = request.form.get('phone','').strip() or None
        qualification = request.form.get('qualification','').strip() or None
        specialization = request.form.get('specialization','').strip() or None
        default_pw = "teacher123"
        pw_hash = generate_password_hash(default_pw)
        user_id = execute("INSERT INTO users (name,email,password,role,must_change_password) VALUES (%s,%s,%s,'Teacher',1)", (name, email, pw_hash))
        execute("INSERT INTO teachers (user_id, principal_id, name, phone, qualification, specialization) VALUES (%s,%s,%s,%s,%s,%s)", (user_id, session['user_id'], name, phone, qualification, specialization))
        flash(f"Teacher added. Default password: {default_pw}", "success")
        return redirect(url_for('teachers_list'))
    return render_template('add_teacher.html')

@app.route('/teacher/edit/<int:teacher_id>', methods=['GET','POST'])
def edit_teacher(teacher_id):
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    t = fetchone("SELECT * FROM teachers WHERE id=%s AND principal_id=%s", (teacher_id, session['user_id']))
    if not t:
        flash("Teacher not found.", "danger")
        return redirect(url_for('teachers_list'))
    if request.method == 'POST':
        name = request.form.get('name','').strip() or None
        phone = request.form.get('phone','').strip() or None
        qualification = request.form.get('qualification','').strip() or None
        specialization = request.form.get('specialization','').strip() or None
        execute("UPDATE teachers SET name=%s, phone=%s, qualification=%s, specialization=%s WHERE id=%s", (name, phone, qualification, specialization, teacher_id))
        flash("Teacher updated.", "success")
        return redirect(url_for('teachers_list'))
    return render_template('edit_teacher.html', teacher=t)

@app.route('/teacher/delete/<int:teacher_id>', methods=['POST'])
def delete_teacher(teacher_id):
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    t = fetchone("SELECT * FROM teachers WHERE id=%s AND principal_id=%s", (teacher_id, session['user_id']))
    if not t:
        flash("Teacher not found.", "danger")
        return redirect(url_for('teachers_list'))
    # remove teacher and associated user record
    try:
        execute("DELETE FROM teachers WHERE id=%s", (teacher_id,))
        if t.get('user_id'):
            execute("DELETE FROM users WHERE id=%s", (t['user_id'],))
    except Exception:
        pass
    flash("Teacher deleted.", "success")
    return redirect(url_for('teachers_list'))

# ------------------- Students CRUD -------------------
@app.route('/students')
def students_list():
    if session.get('role') == 'Principal':
        students = fetchall("SELECT s.*, t.name AS teacher_name FROM students s LEFT JOIN teachers t ON s.teacher_id=t.id WHERE s.principal_id=%s ORDER BY s.id DESC", (session['user_id'],))
    elif session.get('role') == 'Teacher':
        teacher = fetchone("SELECT * FROM teachers WHERE user_id=%s", (session['user_id'],))
        if not teacher:
            flash("Please complete your teacher profile.", "danger")
            return redirect(url_for('teacher_profile'))
        students = fetchall("SELECT s.*, t.name AS teacher_name FROM students s LEFT JOIN teachers t ON s.teacher_id=t.id WHERE s.teacher_id=%s ORDER BY s.id DESC", (teacher['id'],))
    else:
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    return render_template('students.html', students=students)

@app.route('/student/add', methods=['GET','POST'])
def add_student():
    # Principal can assign teacher; teacher auto-assigns self
    teachers = []
    if session.get('role') == 'Principal':
        teachers = fetchall("SELECT id, name FROM teachers WHERE principal_id=%s", (session['user_id'],))
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        roll_no = request.form.get('roll_no','').strip() or None
        class_name = request.form.get('class_name','').strip() or None
        standard = request.form.get('standard','').strip() or None
        section = request.form.get('section','').strip() or None
        dob = request.form.get('dob') or None
        if session.get('role') == 'Principal':
            teacher_id = request.form.get('teacher_id') or None
            if teacher_id == '':
                teacher_id = None
            principal_id = session['user_id']
        elif session.get('role') == 'Teacher':
            teacher = fetchone("SELECT * FROM teachers WHERE user_id=%s", (session['user_id'],))
            if not teacher:
                flash("Complete teacher profile first.", "danger")
                return redirect(url_for('teacher_profile'))
            teacher_id = teacher['id']
            principal_id = teacher['principal_id']
        else:
            flash("Access denied.", "danger")
            return redirect(url_for('home'))
        if not name:
            flash("Student name is required.", "danger")
            return redirect(url_for('add_student'))
        execute("INSERT INTO students (principal_id, teacher_id, name, roll_no, class_name, standard, section, dob) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (principal_id, teacher_id, name, roll_no, class_name, standard, section, dob))
        flash("Student added.", "success")
        return redirect(url_for('students_list'))
    return render_template('add_student.html', teachers=teachers)

@app.route('/student/edit/<int:student_id>', methods=['GET','POST'])
def edit_student(student_id):
    student = None
    if session.get('role') == 'Principal':
        student = fetchone("SELECT * FROM students WHERE id=%s AND principal_id=%s", (student_id, session['user_id']))
    elif session.get('role') == 'Teacher':
        teacher = fetchone("SELECT * FROM teachers WHERE user_id=%s", (session['user_id'],))
        if not teacher:
            flash("Complete profile.", "danger")
            return redirect(url_for('teacher_profile'))
        student = fetchone("SELECT * FROM students WHERE id=%s AND teacher_id=%s", (student_id, teacher['id']))
    if not student:
        flash("Student not found or access denied.", "danger")
        return redirect(url_for('students_list'))
    teachers = fetchall("SELECT id,name FROM teachers WHERE principal_id=%s", (student['principal_id'],)) if student.get('principal_id') else []
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        roll_no = request.form.get('roll_no','').strip() or None
        class_name = request.form.get('class_name','').strip() or None
        standard = request.form.get('standard','').strip() or None
        section = request.form.get('section','').strip() or None
        dob = request.form.get('dob') or None
        teacher_id = request.form.get('teacher_id') or None
        if teacher_id == '':
            teacher_id = None
        execute("UPDATE students SET name=%s, roll_no=%s, class_name=%s, standard=%s, section=%s, dob=%s, teacher_id=%s WHERE id=%s", (name, roll_no, class_name, standard, section, dob, teacher_id, student_id))
        flash("Student updated.", "success")
        return redirect(url_for('students_list'))
    return render_template('edit_student.html', student=student, teachers=teachers)

@app.route('/student/delete/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    if session.get('role') == 'Principal':
        execute("DELETE FROM students WHERE id=%s AND principal_id=%s", (student_id, session['user_id']))
    elif session.get('role') == 'Teacher':
        teacher = fetchone("SELECT * FROM teachers WHERE user_id=%s", (session['user_id'],))
        if not teacher:
            flash("Access denied.", "danger")
            return redirect(url_for('students_list'))
        execute("DELETE FROM students WHERE id=%s AND teacher_id=%s", (student_id, teacher['id']))
    else:
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    flash("Student deleted.", "success")
    return redirect(url_for('students_list'))

# ------------------- Subjects & Proposals -------------------
@app.route('/subjects')
def subjects_list():
    if session.get('role') == 'Principal':
        pid = session['user_id']
    elif session.get('role') == 'Teacher':
        teacher = fetchone("SELECT principal_id FROM teachers WHERE user_id=%s", (session['user_id'],))
        pid = teacher['principal_id'] if teacher else None
    else:
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    subjects = fetchall("SELECT * FROM subjects WHERE principal_id=%s ORDER BY id DESC", (pid,))
    return render_template('subjects.html', subjects=subjects)

@app.route('/subject/add', methods=['GET','POST'])
def add_subject():
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        if not name:
            flash("Subject name required.", "danger")
            return redirect(url_for('add_subject'))
        execute("INSERT INTO subjects (principal_id, name) VALUES (%s,%s)", (session['user_id'], name))
        flash("Subject added.", "success")
        return redirect(url_for('subjects_list'))
    return render_template('add_subject.html')

@app.route('/teacher/propose_subject', methods=['POST'])
def teacher_propose_subject():
    if session.get('role') != 'Teacher':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    teacher = fetchone("SELECT * FROM teachers WHERE user_id=%s", (session['user_id'],))
    if not teacher:
        flash("Please complete profile first.", "danger")
        return redirect(url_for('teacher_profile'))
    name = request.form.get('subject_name','').strip()
    if not name:
        flash("Subject name required.", "danger")
        return redirect(url_for('teacher_profile'))
    execute("INSERT INTO subject_proposals (principal_id, teacher_id, name, status) VALUES (%s,%s,%s,'Pending')", (teacher['principal_id'], teacher['id'], name))
    flash("Subject proposed for approval.", "success")
    return redirect(url_for('teacher_profile'))

@app.route('/proposals')
def proposals_list():
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    proposals = fetchall("SELECT p.*, t.name AS teacher_name FROM subject_proposals p JOIN teachers t ON p.teacher_id=t.id WHERE p.principal_id=%s ORDER BY p.id DESC", (session['user_id'],))
    return render_template('proposals.html', proposals=proposals)

@app.route('/proposal/approve/<int:pid>', methods=['POST'])
def proposal_approve(pid):
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    prop = fetchone("SELECT * FROM subject_proposals WHERE id=%s AND principal_id=%s", (pid, session['user_id']))
    if not prop:
        flash("Not found.", "danger")
        return redirect(url_for('proposals_list'))
    sub_id = execute("INSERT INTO subjects (principal_id, name) VALUES (%s,%s)", (session['user_id'], prop['name']))
    execute("INSERT INTO teacher_subjects (principal_id, teacher_id, subject_id) VALUES (%s,%s,%s)", (session['user_id'], prop['teacher_id'], sub_id))
    execute("UPDATE subject_proposals SET status='Approved' WHERE id=%s", (pid,))
    flash("Proposal approved and subject created.", "success")
    return redirect(url_for('proposals_list'))

@app.route('/proposal/decline/<int:pid>', methods=['POST'])
def proposal_decline(pid):
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    execute("UPDATE subject_proposals SET status='Declined' WHERE id=%s", (pid,))
    flash("Proposal declined.", "success")
    return redirect(url_for('proposals_list'))

# ------------------- Exams -------------------
@app.route('/exam/create', methods=['GET','POST'])
def create_exam():
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        max_marks = int(request.form.get('max_marks') or 100)
        if not name:
            flash("Exam name required.", "danger")
            return redirect(url_for('create_exam'))
        execute("INSERT INTO exams (principal_id, name, max_marks) VALUES (%s,%s,%s)", (session['user_id'], name, max_marks))
        flash("Exam created.", "success")
        return redirect(url_for('exam_list'))
    return render_template('exam_create.html')

@app.route('/exams')
def exam_list():
    if session.get('role') == 'Principal':
        pid = session['user_id']
    elif session.get('role') == 'Teacher':
        t = fetchone("SELECT principal_id FROM teachers WHERE user_id=%s", (session['user_id'],))
        if not t:
            flash("Complete profile.", "danger")
            return redirect(url_for('teacher_profile'))
        pid = t['principal_id']
    else:
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    exams = fetchall("SELECT * FROM exams WHERE principal_id=%s ORDER BY id DESC", (pid,))
    return render_template('exam_list.html', exams=exams)

@app.route('/exam/<int:exam_id>/enter', methods=['GET','POST'])
def exam_enter_marks(exam_id):
    if session.get('role') != 'Teacher':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    teacher = fetchone("SELECT * FROM teachers WHERE user_id=%s", (session['user_id'],))
    if not teacher:
        flash("Complete teacher profile.", "danger")
        return redirect(url_for('teacher_profile'))
    exam = fetchone("SELECT * FROM exams WHERE id=%s", (exam_id,))
    if not exam or exam['principal_id'] != teacher['principal_id']:
        flash("Exam not found or permission denied.", "danger")
        return redirect(url_for('exam_list'))
    # approved subjects for teacher
    subjects = fetchall("SELECT s.* FROM subjects s JOIN teacher_subjects ts ON ts.subject_id=s.id WHERE ts.teacher_id=%s AND ts.principal_id=%s", (teacher['id'], teacher['principal_id']))
    students = fetchall("SELECT * FROM students WHERE teacher_id=%s ORDER BY name", (teacher['id'],))
    if request.method == 'POST':
        subject_name = request.form.get('subject_name','').strip()
        if not subject_name:
            flash("Select subject.", "danger")
            return redirect(url_for('exam_enter_marks', exam_id=exam_id))
        for stu in students:
            v = request.form.get(f"marks_{stu['id']}", "").strip()
            if v == "":
                continue
            try:
                m = int(v)
            except:
                m = 0
            execute("INSERT INTO exam_marks (exam_id, student_id, subject_name, marks, status, created_by) VALUES (%s,%s,%s,%s,'Pending',%s)", (exam_id, stu['id'], subject_name, m, teacher['id']))
        flash("Marks submitted and are pending approval.", "success")
        return redirect(url_for('teacher_dashboard'))
    return render_template('exam_enter_marks.html', exam=exam, subjects=subjects, students=students)

@app.route('/exam/<int:exam_id>/pending')
def exam_pending_approval(exam_id):
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    exam = fetchone("SELECT * FROM exams WHERE id=%s AND principal_id=%s", (exam_id, session['user_id']))
    if not exam:
        flash("Exam not found.", "danger")
        return redirect(url_for('exam_list'))
    marks = fetchall("SELECT em.*, s.name AS student_name, t.name AS teacher_name FROM exam_marks em JOIN students s ON em.student_id=s.id LEFT JOIN teachers t ON em.created_by=t.id WHERE em.exam_id=%s AND em.status='Pending' ORDER BY em.created_at", (exam_id,))
    return render_template('exam_pending_approval.html', exam=exam, marks=marks)

@app.route('/exam/approve/<int:mark_id>', methods=['POST'])
def exam_approve_mark(mark_id):
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    row = fetchone("SELECT em.* FROM exam_marks em JOIN exams ex ON em.exam_id=ex.id WHERE em.id=%s AND ex.principal_id=%s", (mark_id, session['user_id']))
    if not row:
        flash("Not found or permission denied.", "danger")
        return redirect(url_for('principal_dashboard'))
    execute("UPDATE exam_marks SET status='Approved' WHERE id=%s", (mark_id,))
    flash("Mark approved.", "success")
    return redirect(request.referrer or url_for('principal_dashboard'))

@app.route('/exam/reject/<int:mark_id>', methods=['POST'])
def exam_reject_mark(mark_id):
    if session.get('role') != 'Principal':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    row = fetchone("SELECT em.* FROM exam_marks em JOIN exams ex ON em.exam_id=ex.id WHERE em.id=%s AND ex.principal_id=%s", (mark_id, session['user_id']))
    if not row:
        flash("Not found or permission denied.", "danger")
        return redirect(url_for('principal_dashboard'))
    execute("UPDATE exam_marks SET status='Declined' WHERE id=%s", (mark_id,))
    flash("Mark declined.", "success")
    return redirect(request.referrer or url_for('principal_dashboard'))

# ------------------- Student Login & Dashboard & Result -------------------
@app.route('/student/login', methods=['GET','POST'])
def student_login():
    if request.method == 'POST':
        roll = request.form.get('roll_no','').strip()
        dob = request.form.get('dob','').strip()
        student = fetchone("SELECT * FROM students WHERE roll_no=%s AND dob=%s", (roll, dob))
        if not student:
            flash("Invalid roll number or DOB.", "danger")
            return redirect(url_for('student_login'))
        session.clear()
        session['student_id'] = student['id']
        session['name'] = student['name']
        return redirect(url_for('student_dashboard'))
    return render_template('student_login.html')

@app.route('/student/dashboard')
def student_dashboard():
    if 'student_id' not in session:
        flash("Please login as student.", "danger")
        return redirect(url_for('student_login'))
    student = fetchone("SELECT s.*, t.name AS teacher_name FROM students s LEFT JOIN teachers t ON s.teacher_id=t.id WHERE s.id=%s", (session['student_id'],))
    return render_template('student_dashboard.html', student=student)

@app.route('/student/result')
def student_result():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    sid = session['student_id']

    rows = fetchall("""
        SELECT em.*, ex.name AS exam_name, ex.max_marks 
        FROM exam_marks em
        JOIN exams ex ON em.exam_id = ex.id
        WHERE em.student_id = %s AND em.status = 'Approved'
        ORDER BY ex.created_at DESC, em.subject_name
    """, (sid,))

    exams = {}
    for r in rows:
        eid = r['exam_id']
        if eid not in exams:
            exams[eid] = {
                'exam_name': r['exam_name'],
                'max_marks': r['max_marks'],
                'items': [],
                'total': 0
            }
        exams[eid]['items'].append({'subject': r['subject_name'], 'marks': r['marks']})
        exams[eid]['total'] += r['marks']

    exam_list = []
    for eid, info in exams.items():
        exam_list.append({
            'exam_id': eid,
            'exam_name': info['exam_name'],
            'max_marks': info['max_marks'],
            'items': info['items'],
            'total': info['total']
        })

    student = fetchone("SELECT * FROM students WHERE id=%s", (sid,))

    return render_template(
        'student_result.html',
        student=student,
        exams=exam_list,
        grade_from_total=grade_from_total,
        mark_color_class=mark_color_class     # ✅ FIXED
    )


@app.route("/subjects/delete/<int:id>", methods=["POST"])
@login_required
@role_required('Principal')
def delete_subject(id):
    execute("DELETE FROM subjects WHERE id=%s", (id,))
    flash("Subject deleted.", "success")
    return redirect(url_for('subjects_list'))



# ------------------- Teacher Profile -------------------
@app.route('/teacher/profile', methods=['GET','POST'])
def teacher_profile():
    if session.get('role') != 'Teacher':
        flash("Access denied.", "danger")
        return redirect(url_for('home'))
    teacher = fetchone("SELECT * FROM teachers WHERE user_id=%s", (session['user_id'],))
    if request.method == 'POST':
        name = request.form.get('name','').strip() or None
        phone = request.form.get('phone','').strip() or None
        qualification = request.form.get('qualification','').strip() or None
        specialization = request.form.get('specialization','').strip() or None
        if teacher:
            execute("UPDATE teachers SET name=%s, phone=%s, qualification=%s, specialization=%s WHERE id=%s", (name, phone, qualification, specialization, teacher['id']))
        else:
            principal_row = fetchone("SELECT id FROM users WHERE role='Principal' ORDER BY id LIMIT 1")
            principal_id = principal_row['id'] if principal_row else None
            execute("INSERT INTO teachers (user_id, principal_id, name, phone, qualification, specialization) VALUES (%s,%s,%s,%s,%s,%s)", (session['user_id'], principal_id, name, phone, qualification, specialization))
            teacher = fetchone("SELECT * FROM teachers WHERE user_id=%s", (session['user_id'],))
        flash("Profile updated.", "success")
        return redirect(url_for('teacher_profile'))
    proposals = fetchall("SELECT * FROM subject_proposals WHERE teacher_id=%s ORDER BY id DESC", (teacher['id'],)) if teacher else []
    return render_template('teacher_profile.html', teacher=teacher, proposals=proposals)

# ------------------- Errors -------------------
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

# ------------------- Run -------------------
if __name__ == '__main__':
    app.run(debug=True)
