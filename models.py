from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120))
    last_name = db.Column(db.String(120))
    filiere = db.Column(db.String(120))
    number = db.Column(db.String(50))
    age = db.Column(db.Integer)
    bio = db.Column(db.Text)
    photo_filename = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    published = db.Column(db.Boolean, default=False)
    votes = db.relationship("Vote", backref="candidate", lazy=True)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate.id"), nullable=False)
    voter_name = db.Column(db.String(200))
    voter_meta = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
