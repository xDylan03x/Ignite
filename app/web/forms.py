from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField, EmailField, SelectField, SelectMultipleField, \
    DateTimeField, DateTimeLocalField
from wtforms.validators import DataRequired, EqualTo, ValidationError
import random

from wtforms.widgets import CheckboxInput

from app import db
from app.models import User


def username_is_unique(form, field):
    usernameExists = db.session.query(User.id).filter_by(username=field.data.lower().replace(" ", "")).first() is not None
    if usernameExists:
        error = "This username is already in use. Consider one of these: "
        while True:
            prefix = form.name.data.strip().replace(" ", "").lower()
            suffix = str(random.randint(100, 10000))
            possibleUsername = prefix + suffix
            possibleUsernameExists = db.session.query(User.id).filter_by(username=possibleUsername).first() is not None
            if not possibleUsernameExists:
                error += f"{possibleUsername}"
                break
        while True:
            prefix = field.data.lower()
            suffix = str(random.randint(100, 10000))
            possibleUsername = prefix + suffix
            possibleUsernameExists = db.session.query(User.id).filter_by(username=possibleUsername).first() is not None
            if not possibleUsernameExists:
                error += f", {possibleUsername}"
                break
        raise ValidationError(error)


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired("Please enter your username")])
    password = PasswordField('Password', validators=[DataRequired("Please enter your password")])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class NewUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired("Please enter a username"), username_is_unique])
    email = EmailField('Email', validators=[DataRequired("Please enter an email")])
    name = StringField('Name', validators=[DataRequired("Please enter a name")])
    role = SelectField('Role', coerce=str, validators=[DataRequired("Please choose an role")])
    send_email = BooleanField('Send confirmation email')
    submit = SubmitField('Create User')


class EditUserForm(FlaskForm):
    name = StringField('Name')
    role = SelectField('Role', coerce=str, validators=[DataRequired("Please choose an role")])
    account_status = SelectField('Account Status', coerce=str, validators=[DataRequired("Please choose an account type")])
    submit = SubmitField('Update User')


class EditUserRolesForm(FlaskForm):
    manage_users = BooleanField('Manage Users')
    submit = SubmitField('Update User')


class SetupAccountForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired("Please enter your username")])
    password = PasswordField('Password', validators=[DataRequired("Please enter your password")])
    password_check = PasswordField('Password Confirm', validators=[DataRequired("Please confirm your password"),
                                                                   EqualTo("password", message="Passwords must match")])
    submit = SubmitField('Submit')


class SettingsForm(FlaskForm):
    name = StringField('Name')
    email = EmailField('Email')
    submit = SubmitField('Save Settings')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password',
                                     validators=[DataRequired("Please enter your current password")])
    password = PasswordField('Password', validators=[DataRequired("Please enter your password")])
    password_check = PasswordField('Password Confirm', validators=[DataRequired("Please confirm your password"),
                                                                   EqualTo("password", message="Passwords must match")])
    submit = SubmitField('Submit')


class ForgotPasswordForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired("Please enter your username")])
    submit = SubmitField('Submit')


class TokenForm(FlaskForm):
    value = StringField('Authentication Code', validators=[DataRequired("Please enter your verification code")])
    submit = SubmitField('Submit')


class NewAppointmentForm(FlaskForm):
    start_time = DateTimeLocalField('Start Time')
    end_time = DateTimeLocalField('End Time')
    attendees = SelectMultipleField('Attendees', coerce=int, option_widget=CheckboxInput())
    submit = SubmitField('Create Appointment')


class UpdateMeetingLinkForm(FlaskForm):
    meeting_link = StringField('Meeting Link')
    submit = SubmitField('Update Meeting Link')


class ManagePatientsForm(FlaskForm):
    patients = SelectMultipleField('Patients', coerce=int, option_widget=CheckboxInput())
    submit = SubmitField('Update Patients')


class NewRequestForm(FlaskForm):
    subject = StringField('Subject', validators=[DataRequired("Please enter a subject")])
    date = DateTimeLocalField('Date')
    users = SelectMultipleField('Users', coerce=int, option_widget=CheckboxInput())
    submit = SubmitField('Submit Request')

