# app.py – NMIT Alumni Portal
# Uses only: Flask (already installed) + Python stdlib sqlite3
# No Flask-SQLAlchemy, no Flask-Login needed.

import sqlite3
import os
import functools
from datetime import datetime
from flask import (Flask, render_template, redirect, url_for,
                   request, flash, session, g)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'nmit-alumni-secret-key-2024'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'alumni_portal.db')

# ── DB helpers ──────────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop('db', None)
    if db: db.close()

def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rv  = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def execute(sql, args=()):
    db  = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid

# ── Auth helper ─────────────────────────────────────────────────────────────
def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_current_user():
    user = None
    if 'user_id' in session:
        user = query("SELECT * FROM user WHERE id=?", (session['user_id'],), one=True)
    return dict(current_user=user)

# ── Template filters ─────────────────────────────────────────────────────────
def _todt(v):
    if isinstance(v, datetime): return v
    try: return datetime.fromisoformat(str(v))
    except Exception: return None

@app.template_filter('datefmt')
def datefmt_filter(dt, fmt='%d %b %Y'):
    dt = _todt(dt)
    return dt.strftime(fmt) if dt else ''

@app.template_filter('timeago')
def timeago_filter(dt):
    dt = _todt(dt)
    if not dt: return ''
    delta = datetime.utcnow() - dt
    if delta.days == 0:  return 'Today'
    if delta.days == 1:  return 'Yesterday'
    if delta.days < 7:   return f'{delta.days} days ago'
    if delta.days < 30:  return f'{delta.days // 7} weeks ago'
    return dt.strftime('%d %b %Y')

@app.template_filter('isodate')
def isodate_filter(s):
    return _todt(s) or s

# ── HOME ─────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    events        = query("SELECT * FROM event ORDER BY date ASC LIMIT 3")
    alumni_count  = query("SELECT COUNT(*) FROM user WHERE role='alumni'",  one=True)[0]
    student_count = query("SELECT COUNT(*) FROM user WHERE role='student'", one=True)[0]
    job_count     = query("SELECT COUNT(*) FROM job", one=True)[0]
    return render_template('home.html', events=events,
                           alumni_count=alumni_count, student_count=student_count, job_count=job_count)

# ── REGISTER ─────────────────────────────────────────────────────────────────
@app.route('/register', methods=['GET','POST'])
def register():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name     = request.form.get('name','').strip()
        email    = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        confirm  = request.form.get('confirm_password','')
        role     = request.form.get('role','student')
        if not name or not email or not password:
            flash('All fields are required.','danger'); return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.','danger'); return render_template('register.html')
        if query("SELECT id FROM user WHERE email=?", (email,), one=True):
            flash('Email already registered.','danger'); return render_template('register.html')
        uid = execute("INSERT INTO user (name,email,password,role,created_at) VALUES (?,?,?,?,?)",
                      (name, email, generate_password_hash(password), role, datetime.utcnow().isoformat()))
        if role == 'alumni':
            execute("INSERT INTO alumni_profile (user_id,batch,department) VALUES (?,?,?)",
                    (uid, request.form.get('batch','N/A') or 'N/A',
                         request.form.get('department','N/A') or 'N/A'))
        flash('Account created! Please log in.','success')
        return redirect(url_for('login'))
    return render_template('register.html')

# ── LOGIN / LOGOUT ────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email    = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        user     = query("SELECT * FROM user WHERE email=?", (email,), one=True)
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            flash(f"Welcome back, {user['name']}!",'success')
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Invalid email or password.','danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.','info')
    return redirect(url_for('home'))

# ── DASHBOARD ────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    recent_jobs   = query("SELECT j.*, u.name as poster_name FROM job j JOIN user u ON j.posted_by=u.id ORDER BY j.posted_at DESC LIMIT 5")
    recent_events = query("SELECT * FROM event ORDER BY date ASC LIMIT 5")
    return render_template('dashboard.html',
        recent_jobs=recent_jobs, recent_events=recent_events,
        alumni_count  = query("SELECT COUNT(*) FROM user WHERE role='alumni'",  one=True)[0],
        student_count = query("SELECT COUNT(*) FROM user WHERE role='student'", one=True)[0],
        job_count     = query("SELECT COUNT(*) FROM job",   one=True)[0],
        event_count   = query("SELECT COUNT(*) FROM event", one=True)[0])

# ── ALUMNI DIRECTORY ─────────────────────────────────────────────────────────
@app.route('/alumni')
@login_required
def alumni_directory():
    search     = request.args.get('search','').strip()
    batch      = request.args.get('batch','').strip()
    department = request.args.get('department','').strip()
    company    = request.args.get('company','').strip()

    sql  = "SELECT p.*, u.name, u.email, u.id as user_id FROM alumni_profile p JOIN user u ON p.user_id=u.id WHERE u.role='alumni'"
    args = []
    if search:     sql += " AND u.name LIKE ?";         args.append(f'%{search}%')
    if batch:      sql += " AND p.batch=?";             args.append(batch)
    if department: sql += " AND p.department LIKE ?";   args.append(f'%{department}%')
    if company:    sql += " AND p.company LIKE ?";      args.append(f'%{company}%')
    sql += " ORDER BY p.batch DESC"

    return render_template('alumni.html',
        alumni      = query(sql, args),
        all_batches = [r[0] for r in query("SELECT DISTINCT batch FROM alumni_profile ORDER BY batch DESC")],
        all_depts   = [r[0] for r in query("SELECT DISTINCT department FROM alumni_profile ORDER BY department")],
        search=search, batch=batch, department=department, company=company)

@app.route('/alumni/profile/<int:user_id>')
@login_required
def alumni_profile(user_id):
    user    = query("SELECT * FROM user WHERE id=?",            (user_id,), one=True)
    profile = query("SELECT * FROM alumni_profile WHERE user_id=?", (user_id,), one=True)
    if not user or not profile:
        flash('Profile not found.','warning'); return redirect(url_for('alumni_directory'))
    jobs = query("SELECT * FROM job WHERE posted_by=? ORDER BY posted_at DESC", (user_id,))
    return render_template('alumni_profile.html', user=user, profile=profile, jobs=jobs)

@app.route('/alumni/edit', methods=['GET','POST'])
@login_required
def edit_alumni_profile():
    user = query("SELECT * FROM user WHERE id=?", (session['user_id'],), one=True)
    if user['role'] not in ('alumni','admin'):
        flash('Only alumni can edit profiles.','warning'); return redirect(url_for('dashboard'))
    profile = query("SELECT * FROM alumni_profile WHERE user_id=?", (session['user_id'],), one=True)
    if not profile:
        execute("INSERT INTO alumni_profile (user_id,batch,department) VALUES (?,?,?)",(session['user_id'],'N/A','N/A'))
        profile = query("SELECT * FROM alumni_profile WHERE user_id=?", (session['user_id'],), one=True)
    if request.method == 'POST':
        execute("UPDATE alumni_profile SET batch=?,department=?,company=?,designation=?,location=?,linkedin=?,bio=? WHERE user_id=?",
                (request.form.get('batch',profile['batch']), request.form.get('department',profile['department']),
                 request.form.get('company',''), request.form.get('designation',''),
                 request.form.get('location',''), request.form.get('linkedin',''),
                 request.form.get('bio',''), session['user_id']))
        flash('Profile updated!','success')
        return redirect(url_for('alumni_profile', user_id=session['user_id']))
    return render_template('edit_profile.html', profile=profile)

# ── JOBS ─────────────────────────────────────────────────────────────────────
@app.route('/jobs')
@login_required
def jobs():
    job_type = request.args.get('type','').strip()
    search   = request.args.get('search','').strip()
    sql  = "SELECT j.*, u.name as poster_name FROM job j JOIN user u ON j.posted_by=u.id WHERE 1=1"
    args = []
    if job_type: sql += " AND j.job_type=?";                              args.append(job_type)
    if search:   sql += " AND (j.title LIKE ? OR j.company LIKE ?)";      args += [f'%{search}%',f'%{search}%']
    sql += " ORDER BY j.posted_at DESC"
    return render_template('jobs.html', jobs=query(sql,args), job_type=job_type, search=search)

@app.route('/jobs/post', methods=['GET','POST'])
@login_required
def post_job():
    user = query("SELECT * FROM user WHERE id=?", (session['user_id'],), one=True)
    if user['role'] not in ('alumni','admin'):
        flash('Only alumni can post jobs.','warning'); return redirect(url_for('jobs'))
    if request.method == 'POST':
        title=request.form.get('title','').strip(); description=request.form.get('description','').strip()
        company=request.form.get('company','').strip()
        if not title or not description or not company:
            flash('Title, description, and company are required.','danger'); return render_template('post_job.html')
        execute("INSERT INTO job (title,description,company,location,job_type,apply_link,posted_by,posted_at) VALUES (?,?,?,?,?,?,?,?)",
                (title, description, company, request.form.get('location',''), request.form.get('job_type','Full-time'),
                 request.form.get('apply_link',''), session['user_id'], datetime.utcnow().isoformat()))
        flash('Job posted!','success'); return redirect(url_for('jobs'))
    return render_template('post_job.html')

@app.route('/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    job = query("SELECT j.*, u.name as poster_name FROM job j JOIN user u ON j.posted_by=u.id WHERE j.id=?",(job_id,),one=True)
    if not job: flash('Job not found.','warning'); return redirect(url_for('jobs'))
    return render_template('job_detail.html', job=job)

@app.route('/jobs/delete/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    job  = query("SELECT * FROM job WHERE id=?",  (job_id,), one=True)
    user = query("SELECT * FROM user WHERE id=?", (session['user_id'],), one=True)
    if not job: flash('Not found.','warning'); return redirect(url_for('jobs'))
    if job['posted_by'] != session['user_id'] and user['role'] != 'admin':
        flash('Not authorised.','danger'); return redirect(url_for('jobs'))
    execute("DELETE FROM job WHERE id=?", (job_id,))
    flash('Job deleted.','info'); return redirect(url_for('jobs'))

# ── EVENTS ───────────────────────────────────────────────────────────────────
@app.route('/events')
@login_required
def events():
    now = datetime.utcnow().isoformat()
    organizers = {u['id']: u for u in query("SELECT * FROM user")}
    return render_template('events.html',
        upcoming   = query("SELECT * FROM event WHERE date >= ? ORDER BY date ASC",  (now,)),
        past       = query("SELECT * FROM event WHERE date <  ? ORDER BY date DESC", (now,)),
        organizers = organizers)

@app.route('/events/post', methods=['GET','POST'])
@login_required
def post_event():
    user = query("SELECT * FROM user WHERE id=?", (session['user_id'],), one=True)
    if user['role'] not in ('alumni','admin'):
        flash('Only alumni or admin can post events.','warning'); return redirect(url_for('events'))
    if request.method == 'POST':
        title=request.form.get('title','').strip(); description=request.form.get('description','').strip()
        date_str=request.form.get('date','')
        if not title or not description or not date_str:
            flash('Title, description, and date are required.','danger'); return render_template('post_event.html')
        try: event_date = datetime.strptime(date_str,'%Y-%m-%dT%H:%M')
        except ValueError: flash('Invalid date.','danger'); return render_template('post_event.html')
        execute("INSERT INTO event (title,description,date,venue,image_url,posted_by,created_at) VALUES (?,?,?,?,?,?,?)",
                (title, description, event_date.isoformat(), request.form.get('venue',''),
                 request.form.get('image_url',''), session['user_id'], datetime.utcnow().isoformat()))
        flash('Event posted!','success'); return redirect(url_for('events'))
    return render_template('post_event.html')

@app.route('/events/<int:event_id>')
@login_required
def event_detail(event_id):
    event = query("SELECT * FROM event WHERE id=?", (event_id,), one=True)
    if not event: flash('Event not found.','warning'); return redirect(url_for('events'))
    organizer = query("SELECT * FROM user WHERE id=?", (event['posted_by'],), one=True)
    return render_template('event_detail.html', event=event, organizer=organizer)

@app.route('/events/delete/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    event = query("SELECT * FROM event WHERE id=?", (event_id,), one=True)
    user  = query("SELECT * FROM user WHERE id=?", (session['user_id'],), one=True)
    if not event: flash('Not found.','warning'); return redirect(url_for('events'))
    if event['posted_by'] != session['user_id'] and user['role'] != 'admin':
        flash('Not authorised.','danger'); return redirect(url_for('events'))
    execute("DELETE FROM event WHERE id=?", (event_id,))
    flash('Event deleted.','info'); return redirect(url_for('events'))

# ── ADMIN ────────────────────────────────────────────────────────────────────
@app.route('/admin')
@login_required
def admin_panel():
    user = query("SELECT * FROM user WHERE id=?", (session['user_id'],), one=True)
    if user['role'] != 'admin': flash('Access denied.','danger'); return redirect(url_for('dashboard'))
    return render_template('admin.html', users=query("SELECT * FROM user ORDER BY created_at DESC"))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    current = query("SELECT * FROM user WHERE id=?", (session['user_id'],), one=True)
    if current['role'] != 'admin': flash('Access denied.','danger'); return redirect(url_for('dashboard'))
    if user_id == session['user_id']: flash("Can't delete yourself.",'warning'); return redirect(url_for('admin_panel'))
    execute("DELETE FROM user WHERE id=?", (user_id,))
    flash('User deleted.','info'); return redirect(url_for('admin_panel'))

# ── DB INIT + SEED ────────────────────────────────────────────────────────────
def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'student',
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS alumni_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
            batch TEXT NOT NULL, department TEXT NOT NULL,
            company TEXT, designation TEXT, location TEXT, linkedin TEXT, bio TEXT);
        CREATE TABLE IF NOT EXISTS job (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, description TEXT NOT NULL,
            company TEXT NOT NULL, location TEXT,
            job_type TEXT NOT NULL DEFAULT 'Full-time',
            apply_link TEXT, posted_by INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
            posted_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, description TEXT NOT NULL,
            date TEXT NOT NULL, venue TEXT, image_url TEXT,
            posted_by INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL);
    """)
    db.commit()
    existing = db.execute("SELECT COUNT(*) FROM user").fetchone()[0]
    if existing == 0:
        now = datetime.utcnow().isoformat()
        admin_id = db.execute("INSERT INTO user (name,email,password,role,created_at) VALUES (?,?,?,?,?)",
            ('Admin NMIT','admin@nmit.ac.in',generate_password_hash('admin123'),'admin',now)).lastrowid
        a1 = db.execute("INSERT INTO user (name,email,password,role,created_at) VALUES (?,?,?,?,?)",
            ('Priya Sharma','priya@example.com',generate_password_hash('alumni123'),'alumni',now)).lastrowid
        db.execute("INSERT INTO alumni_profile (user_id,batch,department,company,designation,location,bio) VALUES (?,?,?,?,?,?,?)",
            (a1,'2020','Computer Science & Engineering','Google','Software Engineer','Bangalore',
             'Passionate about scalable systems. Love mentoring juniors.'))
        a2 = db.execute("INSERT INTO user (name,email,password,role,created_at) VALUES (?,?,?,?,?)",
            ('Rahul Nair','rahul@example.com',generate_password_hash('alumni123'),'alumni',now)).lastrowid
        db.execute("INSERT INTO alumni_profile (user_id,batch,department,company,designation,location,bio) VALUES (?,?,?,?,?,?,?)",
            (a2,'2019','Electronics & Communication','Infosys','Senior Consultant','Hyderabad',
             'Working on digital transformation projects.'))
        db.execute("INSERT INTO user (name,email,password,role,created_at) VALUES (?,?,?,?,?)",
            ('Ananya Rao','ananya@example.com',generate_password_hash('student123'),'student',now))
        db.execute("INSERT INTO job (title,description,company,location,job_type,apply_link,posted_by,posted_at) VALUES (?,?,?,?,?,?,?,?)",
            ('Software Engineering Intern',
             'Work on backend APIs using Python and Django.\n\nResponsibilities:\n- Design REST APIs\n- Write unit tests\n- Collaborate with product team\n\nRequirements:\n- Python basics\n- Good communication skills',
             'Google','Bangalore','Internship','https://careers.google.com',a1,now))
        db.execute("INSERT INTO job (title,description,company,location,job_type,apply_link,posted_by,posted_at) VALUES (?,?,?,?,?,?,?,?)",
            ('Full Stack Developer',
             'Build and maintain web applications using React and Node.js.\n\nResponsibilities:\n- Develop front-end with React\n- Build REST APIs with Node.js\n\nRequirements:\n- 2+ years experience\n- Proficiency in JavaScript',
             'Infosys','Hyderabad','Full-time','https://careers.infosys.com',a2,now))
        db.execute("INSERT INTO event (title,description,date,venue,posted_by,created_at) VALUES (?,?,?,?,?,?)",
            ('Annual Alumni Meet 2025',
             'Join us for the annual alumni gathering!\n\nAgenda:\n10:00 AM – Registration & Welcome\n11:00 AM – Keynote by Distinguished Alumni\n01:00 PM – Lunch\n02:00 PM – Panel Discussion\n04:00 PM – Networking',
             '2025-12-15T10:00','NMIT Campus Auditorium',admin_id,now))
        db.execute("INSERT INTO event (title,description,date,venue,posted_by,created_at) VALUES (?,?,?,?,?,?)",
            ('Tech Talk: Future of AI',
             'Insightful session by NMIT alumni working in AI/ML.\n\nSpeakers:\n- Priya Sharma (Google) – LLMs in Production\n\nFollowed by Q&A and networking tea.',
             '2025-11-20T14:00','Seminar Hall, Block A',a1,now))
        db.commit()
        print("\n✅  Database seeded.")
        print("    Admin:   admin@nmit.ac.in   / admin123")
        print("    Alumni:  priya@example.com  / alumni123")
        print("    Student: ananya@example.com / student123\n")
    db.close()

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
