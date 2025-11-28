from flask import Flask, render_template, request, redirect, session, flash
import pymysql
pymysql.install_as_MySQLdb()
import MySQLdb
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

def get_db_connection():
    return MySQLdb.connect(
        host="localhost",
        user="root",
        password="123456",    # change to your DB password
        database="student_management",
        cursorclass=MySQLdb.cursors.DictCursor
    )

# ---------------- Helper Functions ----------------
def get_all_students(user_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE user_id=%s ORDER BY name", (user_id,))
    students = cur.fetchall()
    cur.close(); conn.close()
    return students

def get_all_teachers(user_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM teachers WHERE user_id=%s ORDER BY name", (user_id,))
    teachers = cur.fetchall()
    cur.close(); conn.close()
    return teachers

def get_all_subjects(user_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM subjects WHERE user_id=%s ORDER BY name", (user_id,))
    subjects = cur.fetchall()
    cur.close(); conn.close()
    return subjects

# ---------------- Routes ----------------
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        role = request.form['role'].strip()
        if not all([name,email,password,role]):
            flash("All fields required!", "danger")
            return redirect('/register')
        if role == "Teacher":
            flash("Teacher registration not enabled.", "danger")
            return redirect('/register')
        pw_hash = generate_password_hash(password)
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            flash("Email already exists!", "danger")
            cur.close(); conn.close()
            return redirect('/register')
        cur.execute("INSERT INTO users (name,email,password,role) VALUES (%s,%s,%s,%s)",
                    (name,email,pw_hash,role))
        conn.commit(); cur.close(); conn.close()
        flash("Registered successfully!", "success")
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password_input = request.form['password'].strip()
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close(); conn.close()
        if not user: flash("Email not found!", "danger"); return redirect('/login')
        if not check_password_hash(user['password'], password_input):
            flash("Incorrect password!", "danger"); return redirect('/login')
        session['user_id'] = user['id']
        session['name'] = user['name']
        session['email'] = user['email']
        session['role'] = user['role']
        return redirect('/dashboard')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    if session['role'] != "Principal":
        flash("Teacher dashboard not enabled.", "danger")
        return redirect('/logout')
    return render_template('principal_dashboard.html', name=session['name'])

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

# ---------------- Students CRUD ----------------
@app.route('/students')
def students_list():
    if 'user_id' not in session: return redirect('/login')
    students = get_all_students(session['user_id'])
    return render_template('students.html', students=students)

@app.route('/add_student', methods=['GET','POST'])
def add_student():
    if 'user_id' not in session: return redirect('/login')
    teachers = get_all_teachers(session['user_id'])
    if request.method == 'POST':
        name = request.form['name'].strip()
        grade = request.form['grade'].strip()
        teacher_id = request.form.get('teacher_id') or None
        if teacher_id == '': teacher_id = None
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO students (user_id,name,grade,teacher_id) VALUES (%s,%s,%s,%s)",
                    (session['user_id'],name,grade,teacher_id))
        conn.commit(); cur.close(); conn.close()
        flash("Student added.", "success")
        return redirect('/students')
    return render_template('add_student.html', teachers=teachers)

@app.route('/edit_student/<int:id>', methods=['GET','POST'])
def edit_student(id):
    if 'user_id' not in session: return redirect('/login')
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE id=%s AND user_id=%s", (id,session['user_id']))
    student = cur.fetchone()
    if not student: cur.close(); conn.close(); flash("Student not found.", "danger"); return redirect('/students')
    teachers = get_all_teachers(session['user_id'])
    if request.method == 'POST':
        name = request.form['name'].strip()
        grade = request.form['grade'].strip()
        teacher_id = request.form.get('teacher_id') or None
        if teacher_id == '': teacher_id = None
        cur.execute("UPDATE students SET name=%s, grade=%s, teacher_id=%s WHERE id=%s",
                    (name,grade,teacher_id,id))
        conn.commit(); cur.close(); conn.close(); flash("Student updated.", "success")
        return redirect('/students')
    cur.close(); conn.close()
    return render_template('edit_student.html', student=student, teachers=teachers)

@app.route('/delete_student/<int:id>', methods=['POST'])
def delete_student(id):
    if 'user_id' not in session: return redirect('/login')
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE id=%s AND user_id=%s", (id,session['user_id']))
    conn.commit(); cur.close(); conn.close()
    flash("Student deleted.", "success")
    return redirect('/students')

# ---------------- Teachers CRUD ----------------
@app.route('/teachers')
def teachers_list():
    if 'user_id' not in session: return redirect('/login')
    teachers = get_all_teachers(session['user_id'])
    return render_template('teachers.html', teachers=teachers)

@app.route('/add_teacher', methods=['GET','POST'])
def add_teacher():
    if 'user_id' not in session: return redirect('/login')
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO teachers (user_id,name,email,phone) VALUES (%s,%s,%s,%s)",
                    (session['user_id'],name,email,phone))
        conn.commit(); cur.close(); conn.close()
        flash("Teacher added.", "success")
        return redirect('/teachers')
    return render_template('add_teacher.html')

@app.route('/edit_teacher/<int:id>', methods=['GET','POST'])
def edit_teacher(id):
    if 'user_id' not in session: return redirect('/login')
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM teachers WHERE id=%s AND user_id=%s", (id,session['user_id']))
    teacher = cur.fetchone()
    if not teacher: cur.close(); conn.close(); flash("Teacher not found.", "danger"); return redirect('/teachers')
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        cur.execute("UPDATE teachers SET name=%s,email=%s,phone=%s WHERE id=%s",
                    (name,email,phone,id))
        conn.commit(); cur.close(); conn.close(); flash("Teacher updated.", "success")
        return redirect('/teachers')
    cur.close(); conn.close()
    return render_template('edit_teacher.html', teacher=teacher)

@app.route('/delete_teacher/<int:id>', methods=['POST'])
def delete_teacher(id):
    if 'user_id' not in session: return redirect('/login')
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM teachers WHERE id=%s AND user_id=%s", (id,session['user_id']))
    conn.commit(); cur.close(); conn.close()
    flash("Teacher deleted.", "success")
    return redirect('/teachers')

# ---------------- Subjects CRUD ----------------
@app.route('/subjects')
def subjects_list():
    if 'user_id' not in session: return redirect('/login')
    subjects = get_all_subjects(session['user_id'])
    return render_template('subjects.html', subjects=subjects)

@app.route('/add_subject', methods=['GET','POST'])
def add_subject():
    if 'user_id' not in session: return redirect('/login')
    if request.method == 'POST':
        name = request.form['name'].strip()
        if not name: flash("Subject name required.", "danger"); return redirect('/add_subject')
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO subjects (user_id,name) VALUES (%s,%s)", (session['user_id'],name))
        conn.commit(); cur.close(); conn.close()
        flash("Subject added.", "success")
        return redirect('/subjects')
    return render_template('add_subject.html')

@app.route('/delete_subject/<int:id>', methods=['POST'])
def delete_subject(id):
    if 'user_id' not in session: return redirect('/login')
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM subjects WHERE id=%s AND user_id=%s", (id,session['user_id']))
    conn.commit(); cur.close(); conn.close()
    flash("Subject deleted.", "success")
    return redirect('/subjects')

# ---------------- Marks ----------------
@app.route('/marks')
def marks_list():
    if 'user_id' not in session: return redirect('/login')
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT m.id, s.name AS student_name, sub.name AS subject_name, m.marks
        FROM marks m
        JOIN students s ON m.student_id = s.id
        JOIN subjects sub ON m.subject_id = sub.id
        WHERE s.user_id=%s
        ORDER BY m.id DESC
    """, (session['user_id'],))
    rows = cur.fetchall(); cur.close(); conn.close()
    return render_template('marks.html', marks=rows)

@app.route('/add_marks', methods=['GET','POST'])
def add_marks():
    if 'user_id' not in session: return redirect('/login')
    students = get_all_students(session['user_id'])
    subjects = get_all_subjects(session['user_id'])
    if request.method == 'POST':
        student_id = request.form['student_id']
        conn = get_db_connection(); cur = conn.cursor()
        for subject in subjects:
            mark_value = request.form.get(f'marks_{subject["id"]}', 0)
            mark_value = int(mark_value) if mark_value else 0
            cur.execute("INSERT INTO marks (student_id,subject_id,marks) VALUES (%s,%s,%s)",
                        (student_id,subject['id'],mark_value))
        conn.commit(); cur.close(); conn.close()
        flash("Marks added.", "success")
        return redirect('/marks')
    return render_template('add_marks.html', students=students, subjects=subjects)

@app.route('/student_marks/<int:student_id>')
def student_marks(student_id):
    if 'user_id' not in session: return redirect('/login')
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE id=%s AND user_id=%s", (student_id,session['user_id']))
    student = cur.fetchone()
    cur.execute("""
        SELECT m.id, sub.name AS subject_name, m.marks
        FROM marks m
        JOIN subjects sub ON m.subject_id = sub.id
        WHERE m.student_id=%s
    """, (student_id,))
    marks = cur.fetchall(); cur.close(); conn.close()
    return render_template('student_marks.html', student=student, marks=marks)

# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)
