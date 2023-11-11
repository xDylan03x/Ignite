from flask import Blueprint, render_template
from flask_login import current_user
from datetime import timedelta
from app.models import *


api = Blueprint('api', __name__)


@api.route('/fetch-notifications')
@api.route('/fetch-notifications/<notification_id>')
def fetch_notifications(notification_id=None):
    if notification_id:
        notification = Notification.query.get(notification_id)
        notification.seen = True
        db.session.commit()
    notifications = Notification.query.filter_by(user_id=current_user.id, seen=False).order_by(Notification.created.desc()).all()
    return render_template('fetch_notifications.html', notifications=notifications)


@api.route('/fetch-older-notifications')
def fetch_older_notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id, seen=True).order_by(Notification.created.desc()).filter(Notification.created < datetime.utcnow()+timedelta(days=15)).all()
    return render_template('fetch_older_notifications.html', notifications=notifications)
