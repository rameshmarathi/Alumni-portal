# models.py - Database models for the Alumni Portal
# Each class represents a table in the SQLite database

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Create the SQLAlchemy instance (will be initialized with the app later)
db = SQLAlchemy()

# ─────────────────────────────────────────────
# USER MODEL
# Stores all registered users (students, alumni, admin)
# ─────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(150), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)          # hashed password
    role       = db.Column(db.String(20), nullable=False, default='student')  # 'student' | 'alumni' | 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships – one user can have one alumni profile, many jobs, many events
    alumni_profile = db.relationship('AlumniProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    jobs           = db.relationship('Job',   backref='poster', lazy=True, cascade='all, delete-orphan')
    events         = db.relationship('Event', backref='organizer', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.email}>'


# ─────────────────────────────────────────────
# ALUMNI PROFILE MODEL
# Extra details only alumni fill in after registering
# ─────────────────────────────────────────────
class AlumniProfile(db.Model):
    __tablename__ = 'alumni_profile'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    batch       = db.Column(db.String(10), nullable=False)          # e.g. "2019"
    department  = db.Column(db.String(100), nullable=False)         # e.g. "CSE"
    company     = db.Column(db.String(100), nullable=True)
    designation = db.Column(db.String(100), nullable=True)
    location    = db.Column(db.String(100), nullable=True)
    linkedin    = db.Column(db.String(200), nullable=True)
    bio         = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<AlumniProfile user_id={self.user_id}>'


# ─────────────────────────────────────────────
# JOB MODEL
# Jobs / internships posted by alumni
# ─────────────────────────────────────────────
class Job(db.Model):
    __tablename__ = 'job'

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    company     = db.Column(db.String(100), nullable=False)
    location    = db.Column(db.String(100), nullable=True)
    job_type    = db.Column(db.String(50), nullable=False, default='Full-time')  # Full-time | Internship | Part-time
    apply_link  = db.Column(db.String(300), nullable=True)
    posted_by   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    posted_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Job {self.title}>'


# ─────────────────────────────────────────────
# EVENT MODEL
# Events posted by admin or alumni
# ─────────────────────────────────────────────
class Event(db.Model):
    __tablename__ = 'event'

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    date        = db.Column(db.DateTime, nullable=False)
    venue       = db.Column(db.String(200), nullable=True)
    image_url   = db.Column(db.String(300), nullable=True)
    posted_by   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Event {self.title}>'
