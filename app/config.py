import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get('SECRET_KEY') or 'secret'
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'ignite.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False
SENDGRID_KEY = ""  # https://app.sendgrid.com/settings/api_keys create a new key with full access
REMEMBER_COOKIE_DURATION = timedelta(days=10)
PERMANENT_SESSION_LIFETIME = timedelta(days=10)
