from datetime import datetime
from functools import wraps
import os
import networkx as nx
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret-key-before-deployment')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE, 'campus.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(100), default='Computer Science')
    roll_no = db.Column(db.String(40))
    @property
    def password(self): return self.password_hash
    def set_password(self, value): self.password_hash = generate_password_hash(value)
    def check_password(self, value): return check_password_hash(self.password_hash, value)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    teacher = db.relationship('User', foreign_keys=[teacher_id])
    student_group = db.Column(db.String(50), default='CSE-3A')
    sessions_per_week = db.Column(db.Integer, default=3)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=60)
    room_type = db.Column(db.String(30), default='Classroom')

class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    slot = db.Column(db.String(30), nullable=False)
    available = db.Column(db.Boolean, default=True)
    teacher = db.relationship('User')

class Timetable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    slot = db.Column(db.String(30), nullable=False)
    subject = db.relationship('Subject')
    room = db.relationship('Room')

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
SLOTS = ['09:00 - 10:00', '10:00 - 11:00', '11:15 - 12:15', '12:15 - 01:15', '02:00 - 03:00']

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles: abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

@app.context_processor
def inject_globals(): return {'DAYS': DAYS, 'SLOTS': SLOTS}

@app.route('/')
def index(): return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email','').strip().lower()).first()
        if user and user.check_password(request.form.get('password','')):
            login_user(user)
            flash('Welcome back. You are now signed in.', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); flash('You have been signed out.', 'success'); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        stats = {'Students': User.query.filter_by(role='student').count(), 'Teachers': User.query.filter_by(role='teacher').count(), 'Subjects': Subject.query.count(), 'Rooms': Room.query.count()}
        return render_template('admin.html', stats=stats, timetable_count=Timetable.query.count(), users=User.query.order_by(User.id.desc()).limit(6).all())
    if current_user.role == 'teacher':
        subjects = Subject.query.filter_by(teacher_id=current_user.id).all()
        entries = Timetable.query.join(Subject).filter(Subject.teacher_id == current_user.id).all()
    else:
        group = current_user.department or 'CSE-3A'
        subjects = Subject.query.filter_by(student_group=group).all()
        entries = Timetable.query.join(Subject).filter(Subject.student_group == group).all()
    return render_template('portal.html', subjects=subjects, entries=entries)

@app.route('/admin/users', methods=['GET','POST'])
@role_required('admin')
def users():
    if request.method == 'POST':
        email=request.form['email'].strip().lower()
        if User.query.filter_by(email=email).first(): flash('That email is already registered.', 'danger')
        else:
            u=User(name=request.form['name'].strip(), email=email, role=request.form['role'], department=request.form.get('department','Computer Science'), roll_no=request.form.get('roll_no'))
            u.set_password(request.form['password']); db.session.add(u); db.session.commit(); flash('User account created.', 'success')
        return redirect(url_for('users'))
    return render_template('users.html', users=User.query.order_by(User.role,User.name).all())

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@role_required('admin')
def delete_user(user_id):
    u=User.query.get_or_404(user_id)
    if u.id == current_user.id: flash('You cannot delete your own admin account.', 'danger')
    elif u.role == 'teacher' and Subject.query.filter_by(teacher_id=u.id).first(): flash('Reassign this teacher’s subjects before deleting the account.', 'danger')
    else: db.session.delete(u); db.session.commit(); flash('User deleted.', 'success')
    return redirect(url_for('users'))

@app.route('/admin/resources', methods=['GET','POST'])
@role_required('admin')
def resources():
    if request.method == 'POST':
        kind=request.form.get('kind')
        if kind == 'room':
            db.session.add(Room(name=request.form['name'], capacity=int(request.form['capacity']), room_type=request.form['room_type']))
        else:
            teacher_id=int(request.form['teacher_id']) if request.form.get('teacher_id') else None
            db.session.add(Subject(code=request.form['code'].upper(), name=request.form['subject_name'], teacher_id=teacher_id, student_group=request.form['student_group'], sessions_per_week=int(request.form['sessions_per_week'])))
        try: db.session.commit(); flash('Resource saved successfully.', 'success')
        except Exception: db.session.rollback(); flash('Could not save. Check for duplicate subject codes or room names.', 'danger')
        return redirect(url_for('resources'))
    return render_template('resources.html', rooms=Room.query.all(), subjects=Subject.query.all(), teachers=User.query.filter_by(role='teacher').all())

@app.route('/admin/optimize', methods=['GET','POST'])
@role_required('admin')
def optimize():
    result=None
    if request.method == 'POST':
        subjects=Subject.query.all(); rooms=Room.query.all()
        if not subjects or not rooms:
            flash('Add at least one subject and one room before generating a timetable.', 'warning')
        else:
            Timetable.query.delete(); db.session.commit()
            # Graph colouring: each required class session is a node; edges connect sessions that share a teacher or student group.
            tasks=[]
            for sub in subjects:
                for n in range(sub.sessions_per_week): tasks.append({'subject':sub,'n':n})
            graph=nx.Graph(); graph.add_nodes_from(range(len(tasks)))
            for i in range(len(tasks)):
                for j in range(i+1,len(tasks)):
                    a,b=tasks[i]['subject'],tasks[j]['subject']
                    if (a.teacher_id and a.teacher_id==b.teacher_id) or a.student_group==b.student_group: graph.add_edge(i,j)
            colors=nx.coloring.greedy_color(graph, strategy='largest_first')
            used=set(); placed=0
            ordered=sorted(range(len(tasks)), key=lambda i: colors[i])
            for i in ordered:
                sub=tasks[i]['subject']; placed_ok=False
                preferred=rooms
                if any(r.room_type.lower() in ('lab','laboratory') for r in rooms) and ('lab' in sub.name.lower()): preferred=[r for r in rooms if r.room_type.lower() in ('lab','laboratory')]
                for day in DAYS:
                    for slot in SLOTS:
                        key=(day,slot)
                        if (i,key) in used: continue
                        conflict=Timetable.query.filter_by(day=day,slot=slot).join(Subject).filter(((Subject.teacher_id==sub.teacher_id) if sub.teacher_id else False) | (Subject.student_group==sub.student_group)).first()
                        if conflict: continue
                        unavailable=Availability.query.filter_by(teacher_id=sub.teacher_id,day=day,slot=slot,available=False).first() if sub.teacher_id else None
                        if unavailable: continue
                        room=next((r for r in preferred if not Timetable.query.filter_by(day=day,slot=slot,room_id=r.id).first()),None)
                        if room:
                            db.session.add(Timetable(subject_id=sub.id,room_id=room.id,day=day,slot=slot)); used.add((i,key)); placed+=1; placed_ok=True; break
                    if placed_ok: break
            db.session.commit()
            flash(f'Timetable generated: {placed} of {len(tasks)} sessions successfully scheduled.', 'success' if placed==len(tasks) else 'warning')
            result={'placed':placed,'total':len(tasks)}
    entries=Timetable.query.order_by(Timetable.day,Timetable.slot).all()
    return render_template('optimize.html', entries=entries, result=result)

@app.route('/teacher/availability', methods=['GET','POST'])
@role_required('teacher')
def availability():
    if request.method=='POST':
        day=request.form['day']; slot=request.form['slot']; available=request.form['available']=='yes'
        item=Availability.query.filter_by(teacher_id=current_user.id,day=day,slot=slot).first()
        if item: item.available=available
        else: db.session.add(Availability(teacher_id=current_user.id,day=day,slot=slot,available=available))
        db.session.commit(); flash('Availability updated.', 'success'); return redirect(url_for('availability'))
    return render_template('availability.html', items=Availability.query.filter_by(teacher_id=current_user.id).all())

@app.route('/timetable')
@login_required
def timetable():
    if current_user.role=='admin': entries=Timetable.query.all()
    elif current_user.role=='teacher': entries=Timetable.query.join(Subject).filter(Subject.teacher_id==current_user.id).all()
    else: entries=Timetable.query.join(Subject).filter(Subject.student_group==(current_user.department or 'CSE-3A')).all()
    return render_template('timetable.html', entries=entries)

@app.errorhandler(403)
def forbidden(e): return render_template('error.html', code=403, message='You do not have permission to access this page.'),403

@app.cli.command('init-db')
def init_db():
    db.create_all()
    if not User.query.filter_by(email='admin@campus.local').first():
        a=User(name='Campus Administrator',email='admin@campus.local',role='admin'); a.set_password('Admin@123'); db.session.add(a)
        t=User(name='Dr. A. Mehta',email='teacher@campus.local',role='teacher',department='Computer Science'); t.set_password('Teacher@123'); db.session.add(t)
        s=User(name='Demo Student',email='student@campus.local',role='student',department='CSE-3A',roll_no='CSE3A001'); s.set_password('Student@123'); db.session.add(s)
        db.session.flush()
        db.session.add_all([Subject(code='CS301',name='Database Management Systems',teacher_id=t.id,student_group='CSE-3A',sessions_per_week=3),Subject(code='CS302',name='Data Structures',teacher_id=t.id,student_group='CSE-3A',sessions_per_week=2),Room(name='Room 204',capacity=60,room_type='Classroom'),Room(name='Computer Lab 1',capacity=50,room_type='Lab')])
        db.session.commit()
    print('Database initialized. Demo accounts: admin@campus.local / Admin@123, teacher@campus.local / Teacher@123, student@campus.local / Student@123')

if __name__=='__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)
