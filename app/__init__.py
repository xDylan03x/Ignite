from flask import Flask
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_moment import Moment
import os

# Configuration
app = Flask(__name__)
app.config.from_pyfile('config.py')
app._static_folder = os.path.join(os.getcwd(), 'app', 'web', 'static')  #'/home/xDylan03x/mysite/SITENAME/app/web/static/'

login = LoginManager(app)
login.login_view = "web.login"
login.login_message = "You must login to view this page."
login.login_message_category = "danger"


db = SQLAlchemy(app)
moment = Moment(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

# Initialization
login.init_app(app)
migrate.init_app(app, db)

# Blueprint Registering
from .web.views import web, not_found_error
app.register_blueprint(web, url_prefix='/')
app.register_error_handler(404, not_found_error)
from .api.routes import api
app.register_blueprint(api, url_prefix='/api')

with app.app_context():
    db.create_all()
