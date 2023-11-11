import math
from datetime import datetime, timezone
from random import random

from fhir.resources.patient import Patient

from app import db, login
from app.helpers import send_email, make_fhir_request
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

patient = db.Table(
    'patient',
    db.Column('doctor_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('patient_id', db.Integer, db.ForeignKey('user.id'))
)

appointments = db.Table(
    'appointments',
    db.Column('appointment_id', db.Integer, db.ForeignKey('appointment.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'))
)

requests = db.Table(
    'requests',
    db.Column('request_id', db.Integer, db.ForeignKey('request.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'))
)



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Sign In Info
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(256), unique=True)
    password_hash = db.Column(db.String(256))
    # Personal Information
    name = db.Column(db.String(128))
    # System Information
    fhir_id = db.Column(db.String(32))
    account_status = db.Column(db.String(32))
    role = db.Column(db.String(32))
    settings = db.relationship("Setting", backref="user_setting", lazy="subquery")
    notifications = db.relationship("Notification", backref="user_notification", lazy="subquery")
    logins = db.relationship("Login", backref="user_login", lazy="subquery")
    tokens = db.relationship("Token", backref="user_token", lazy="subquery")
    patients = db.relationship('User',
                               secondary=patient,
                               primaryjoin=(patient.c.doctor_id == id),
                               secondaryjoin=(patient.c.patient_id == id),
                               backref='doctors')

    def __repr__(self):
        return f"User <{self.username}>"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_setting(self, name, bool_form=False):
        setting = Setting.query.filter_by(user_id=self.id, name=name).first()
        if setting:
            if bool_form:
                if setting.value == "True":
                    return True
                else:
                    return False
            else:
                return setting.value
        return None

    def set_setting(self, name, value):
        setting = Setting.query.filter_by(user_id=self.id, name=name).first()
        if setting:
            setting.value = value
            setting.last_updated = datetime.utcnow()
            db.session.commit()
        else:
            setting = Setting(name=name, value=value, last_updated=datetime.utcnow(), user_id=self.id)
            db.session.add(setting)
            db.session.commit()

    def create_notification(self, subject, message, sender="Ignite", link=None,
                            created=datetime.utcnow(), email=False):
        notification = Notification(subject=subject, message=message, sender=sender, link=link, created=created,
                                    user_id=self.id)
        db.session.add(notification)
        db.session.commit()
        if email:
            send_email(subject, self.email, message, sender)

    def reset_password(self):
        self.password_hash = None

    def get_fhir_id(self):
        try:
            p = Patient.parse_obj(make_fhir_request(f'Patient?name={self.name}')['entry'][0]['resource'])
            self.fhir_id = p.id
            print(p.id)
        except KeyError:
            self.fhir_id = "NA"


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notes = db.Column(db.Text)
    meeting_link = db.Column(db.Text)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    attendees = db.relationship('User', secondary=appointments, backref='appointments')

    def __repr__(self):
        return f"Appointment <{self.id}>"


class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.Text)
    date = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    users = db.relationship('User', secondary=requests, backref='requests')

    def __repr__(self):
        return f"Request <{self.id}>"


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    value = db.Column(db.String(128))
    last_updated = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    def __repr__(self):
        return f"Setting <{self.id}>"


class Token(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(32))
    created = db.Column(db.DateTime, default=datetime.utcnow())
    used = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    def __repr__(self):
        return f"Token <{self.id}>"

    def generate_value(self, length=6):
        valueString = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        value = ""
        for i in range(length):
            value += valueString[math.floor(random() * len(valueString))]
        self.value = value
        return value


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(128))
    message = db.Column(db.String(256))
    link = db.Column(db.Text)
    seen = db.Column(db.Boolean, default=False)
    created = db.Column(db.DateTime)
    sender = db.Column(db.String(64))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    def __repr__(self):
        return f"Notification <{self.id}>"


class Login(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    ip = db.Column(db.String(64))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    def __repr__(self):
        return f"Login <{self.id}>"


@login.user_loader
def load_user(id):
    return User.query.get(int(id))
