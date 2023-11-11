from datetime import datetime, timedelta, timezone

import pytz
from fhir.resources.patient import Patient
from flask import Blueprint, render_template, flash, url_for, redirect, request, abort, session
from flask_login import login_user, logout_user, login_required, current_user

from app import db, app
from app.helpers import send_email, make_fhir_request
from app.models import User, Login, Setting, Notification, Token, Appointment, Request
from app.web.forms import LoginForm, SetupAccountForm, ChangePasswordForm, SettingsForm, NewUserForm, EditUserForm, \
    EditUserRolesForm, ForgotPasswordForm, TokenForm, NewAppointmentForm, UpdateMeetingLinkForm, ManagePatientsForm, \
    NewRequestForm

web = Blueprint('web', __name__, template_folder='templates')


@web.route('/')
def home():
    return render_template('home.html')


@web.route('/dashboard')
@login_required
def dashboard():
    patient = None
    if current_user.role == 'patient' and current_user.fhir_id != "NA":
        try:
            patient = Patient.parse_obj(make_fhir_request(f'Patient?_id={current_user.fhir_id}')['entry'][0]['resource'])
        except KeyError:
            patient=None
    appointments = Appointment.query.filter(Appointment.attendees.any(id=current_user.id)).order_by(
            Appointment.start_time).all()
    requests = []
    for appointmentRequest in Request.query.filter(Request.users.any(id=current_user.id)).all():
        if appointmentRequest.active:
            requests.append(appointmentRequest)
    return render_template('dashboard.html', patient=patient, appointments=appointments, requests=requests, pageTitle="Dashboard")


# Patient Portal #
@web.route('/patient-portal')
@login_required
def patient_portal():
    if current_user.role != "staff":
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    upcomingAppointments = []
    for appointment in Appointment.query.filter(Appointment.attendees.any(id=current_user.id)).order_by(Appointment.start_time).all():
        if appointment.start_time < datetime.utcnow() + timedelta(days=2) and appointment.start_time > datetime.utcnow() - timedelta(days=1):
            upcomingAppointments.append(appointment)
    requests = []
    for appointmentRequest in Request.query.filter(Request.users.any(id=current_user.id)).all():
        if appointmentRequest.active:
            requests.append(appointmentRequest)
    return render_template('patient_portal.html', pageTitle="Patient Portal", appointments=upcomingAppointments, requests=requests)


@web.route('/patient-portal/table')
@login_required
def patient_table():
    if current_user.role != "staff":
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    patients = current_user.patients
    return render_template('patient_table.html', patients=patients)


@web.route('/patient-portal/manage-patients', methods=['GET', 'POST'])
@login_required
def manage_patients():
    if current_user.role != "staff":
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    form = ManagePatientsForm()
    userList = []
    patientValues = []
    for user in User.query.filter(User.role != 'staff').all():
        userList.append((user.id, f"{user.username} - {user.email} - {user.name}"))
        if user in current_user.patients:
            patientValues.append(user.id)
    form.patients.choices = userList
    if form.validate_on_submit():
        current_user.patients.clear()
        for userid in form.patients.data:
            user = User.query.get(userid)
            current_user.patients.append(user)
        db.session.commit()
        return render_template('patients_updated.html')
    elif request.method == 'GET':
        form.patients.process_data(patientValues)
    return render_template('managePatients.html', form=form, patientValues=patientValues)


@web.route('/patient-portal/appointments')
@login_required
def appointments():
    if current_user.role != "staff":
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    return render_template('appointments.html')


@web.route('/patient-portal/appointments/table')
@login_required
def appointment_table():
    if current_user.role != "staff":
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    userAppointments = Appointment.query.filter(Appointment.attendees.any(id=current_user.id)).order_by(Appointment.start_time).all()
    return render_template('appointment_table.html', appointments=userAppointments)


@web.route('/patient-portal/appointments/new', methods=['GET', 'POST'])
@login_required
def new_appointment():
    if current_user.role != "staff":
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    form = NewAppointmentForm()
    userList = []
    for user in User.query.filter(User.account_status == 'active').all():
        userList.append((user.id, f"{user.username} - {user.email} - {user.name}"))
    form.attendees.choices = userList
    if form.validate_on_submit():

        local = pytz.timezone("America/New_York")
        local_st = local.localize(form.start_time.data)
        utc_st = local_st.astimezone(pytz.utc)
        local_et = local.localize(form.end_time.data)
        utc_et = local_et.astimezone(pytz.utc)

        appointment = Appointment(start_time=utc_st, end_time=utc_et)
        db.session.add(appointment)
        emailList = []
        nameList = []
        formattedStart = local_st.strftime("%B %d, %Y at %I:%M %p")
        formattedEnd = local_et.strftime("%B %d, %Y at %I:%M %p")
        db.session.commit()
        for userid in form.attendees.data:
            user = User.query.get(userid)
            emailList.append(user.email)
            nameList.append(user.name)
            appointment.attendees.append(user)
        for userid in form.attendees.data:
            user = User.query.get(userid)
            user.create_notification('Appointment Confirmation', f'This is a confirmation for your appointment on Ignite.<br>When: {formattedStart} - {formattedEnd} (EST)<br>Attendees: {", ".join(nameList)}', email=True, link=url_for('web.appointment', appointment_id=appointment.id))
        db.session.commit()

        return render_template('appointment_created.html')
    return render_template('new_appointment.html', form=form)


@web.route('/patient-portal/appointments/<appointment_id>', methods=['GET', 'POST'])
@login_required
def appointment(appointment_id):
    form = UpdateMeetingLinkForm()
    appointment = Appointment.query.get_or_404(appointment_id)
    patients = []
    for person in appointment.attendees:
        if person.role == 'patient':
            patients.append(person)
    patients_fhir = []
    for patient in patients:
        if patient.fhir_id != 'NA':
            try:
                patients_fhir.append([patient, Patient.parse_obj(make_fhir_request(f'Patient?_id={patient.fhir_id}')['entry'][0]['resource'])])
            except KeyError:
                patients_fhir.append([patient, None])
    if form.validate_on_submit():
        appointment.meeting_link = form.meeting_link.data
        db.session.commit()
        flash('Meeting link updated.', 'success')
    elif request.method == 'GET':
        form.meeting_link.data = appointment.meeting_link
    return render_template('appointment.html', appointment=appointment, form=form, patients=patients_fhir, pageTitle="Appointment")


@web.route('/requests/<request_id>')
@login_required
def requests(request_id):
    appointmentRequest = Request.query.get_or_404(request_id)
    return render_template('request.html', request=appointmentRequest, pageTitle='Request')


@web.route('/requests/new', methods=['GET', 'POST'])
@login_required
def new_request():
    form = NewRequestForm()
    userList = []
    for user in User.query.filter(User.patients.any(id=current_user.id)):
        userList.append((user.id, f"{user.name}"))
    form.users.choices = userList
    if form.validate_on_submit():

        local = pytz.timezone("America/New_York")
        local_st = local.localize(form.date.data)
        utc_st = local_st.astimezone(pytz.utc)

        appointmentRequest = Request(date=utc_st, subject=form.subject.data)
        db.session.add(appointmentRequest)
        emailList = []
        nameList = []
        formattedStart = local_st.strftime("%B %d, %Y")
        db.session.commit()
        for userid in form.users.data:
            user = User.query.get(userid)
            emailList.append(user.email)
            nameList.append(user.name)
            appointmentRequest.users.append(user)
        appointmentRequest.users.append(current_user)
        nameList.append(current_user.name)
        emailList.append(current_user.email)
        for user in appointmentRequest.users:
            user.create_notification('Request Confirmation',
                                     f'A new appointment request has been submitted<br>When: {formattedStart} (EST)<br>Attendees: {", ".join(nameList)}',
                                     email=True, link=url_for('web.requests', request_id=appointmentRequest.id))
        db.session.commit()

        return render_template('request_created.html')
    return render_template('new_request.html', form=form)


@web.route('/requests/accept/<request_id>')
@login_required
def accept_request(request_id):
    request = Request.query.get_or_404(request_id)
    request.active = False
    db.session.commit()
    form = NewAppointmentForm()
    userList = []
    for user in User.query.filter(User.account_status == 'active').all():
        userList.append((user.id, f"{user.username} - {user.email} - {user.name}"))
    form.attendees.choices = userList
    return render_template('new_appointment.html', form=form)


@web.route('/requests/reject/<request_id>')
@login_required
def reject_request(request_id):
    request = Request.query.get_or_404(request_id)
    request.active = False
    db.session.commit()
    return render_template('request_updated.html')


# Users #
@web.route('/users')
@login_required
def users():
    if not current_user.get_setting("manage_users", True):
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    return render_template('users.html', pageTitle="Users")


@web.route('/users/table')
@login_required
def user_table():
    if not current_user.get_setting("manage_users", True):
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    allUsers = User.query.all()
    return render_template('user_table.html', users=allUsers)


@web.route('/users/edit/<user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.get_setting("manage_users", True):
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    user = User.query.get(user_id)
    form = EditUserForm()
    if user.account_status == "active":
        choices = [("active", "Active"), ("inactive", "Inactive")]
    else:
        choices = [("inactive", "Inactive"), ("active", "Active")]
    form.account_status.choices = choices

    if user.role == "staff":
        choices2 = [("staff", "Staff"), ("patient", "Patient")]
    else:
        choices2 = [("patient", "Patient"), ("staff", "Staff")]
    form.role.choices = choices2
    if form.validate_on_submit():
        if form.name.data != user.name:
            user.name = form.name.data
        if form.role.data != user.role:
            user.role = form.role.data
        if form.account_status.data != user.account_status:
            user.account_status = form.account_status.data
        db.session.commit()
        return render_template('user_updated.html')
    elif request.method == 'GET':
        form.name.data = user.name
    return render_template('edit_user.html', user=user, form=form)


@web.route('/users/roles/<user_id>', methods=['GET', 'POST'])
@login_required
def edit_user_roles(user_id):
    if not current_user.get_setting("manage_users", True):
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    user = User.query.get(user_id)
    form = EditUserRolesForm()
    if form.validate_on_submit():
        if form.manage_users.data != user.get_setting("manage_users"):
            user.set_setting("manage_users", str(form.manage_users.data))
        return render_template('user_updated.html')
    elif request.method == 'GET':
        form.manage_users.data = user.get_setting("manage_users", True)
    return render_template('edit_user_roles.html', user=user, form=form)


@web.route('/users/activity/<user_id>', methods=['GET', 'POST'])
@login_required
def user_activity(user_id):
    if not current_user.get_setting("manage_users", True):
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    user = User.query.get(user_id)
    activity = Login.query.filter_by(user_id=user.id).order_by(Login.timestamp.desc()).all()
    return render_template('user_activity.html', user=user, activity=activity)


@web.route('/users/reset-password/<user_id>')
@login_required
def reset_password(user_id):
    if not current_user.get_setting("manage_users", True):
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    user = User.query.get(user_id)
    user.reset_password()
    db.session.commit()
    return render_template('user_updated.html')


@web.route('/users/new', methods=['GET', 'POST'])
@login_required
def new_user():
    if not current_user.get_setting("manage_users", True):
        flash("You do not have permission to access this page.", "danger")
        abort(403)
    form = NewUserForm()
    form.role.choices = [('patient', 'Patient'), ('staff', 'Staff')]
    if form.validate_on_submit():
        user = User(name=form.name.data, username=form.username.data.lower().replace(" ", ""), email=form.email.data, role=form.role.data, account_status="active")
        if form.send_email.data:
            send_email('Account Setup', form.email.data, 'Your Ignite account has been created, please visit http://127.0.0.1:5000/setup-password to get started.')  #TODO: change url
        db.session.add(user)
        db.session.commit()
        user.set_setting(name='account_setup', value='False')
        user.get_fhir_id()
        db.session.commit()
        flash('The user has been created.', 'success')
        return redirect(url_for('web.users'))
    return render_template('new_user.html', form=form, pageTitle='New User')


@web.route('/users/refresh-patient-id/<user_id>')
@login_required
def refresh_patient_id(user_id):
    user = User.query.get_or_404(user_id)
    if user.role=='patient':
        user.get_fhir_id()
        db.session.commit()
    return render_template('user_updated.html')


@web.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    form = SettingsForm()
    if form.validate_on_submit():
        if current_user.role == 'staff':
            if form.name.data != current_user.name:
                current_user.name = form.name.data
        db.session.commit()
        flash('Your settings have been updated.', 'success')
    elif request.method == "GET":
        form.name.data = current_user.name
    return render_template('settings.html', form=form, pageTitle="Settings")


@web.route('/settings/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            current_user.set_password(form.password.data)
            db.session.commit()
            flash('Your password has been updated.', 'success')
            return redirect(url_for('web.settings'))
        else:
            flash('Invalid password', 'danger')
    return render_template('change_password.html', form=form, pageTitle="Change Password")


@web.route('/settings/setup-password', methods=['GET', 'POST'])
def setup_password():
    form = SetupAccountForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.lower()).first()
        if user:
            if user.account_status != 'active':
                flash('Your account is not active.', 'danger')
            elif not user.password_hash or user.get_setting('account_setup') == "False":
                user.set_password(form.password.data)
                login_user(user)
                user_login = Login(timestamp=datetime.utcnow(), user_id=user.id, ip=request.remote_addr)
                db.session.add(user_login)
                if user.get_setting('account_setup') == "False":
                    user.create_notification("Welcome", "Your account has been created.")
                user.set_setting('account_setup', "True")
                db.session.commit()
                flash('Your password has been saved.', 'success')
                return redirect(url_for('web.settings'))
            else:
                flash('You have already setup your password.', 'info')
        else:
            flash('You may not have an account.', 'danger')
    return render_template('setup_password.html', form=form, pageTitle="Setup Account")


@web.route('/settings/forgot-password', methods=['GET', 'POST'])
@web.route('/settings/forgot-password/<user_id>', methods=['GET', 'POST'])
def forgot_password(user_id=None):
    if user_id is None:
        form = ForgotPasswordForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data.lower().replace(" ", "")).first()
            if user and user.email:
                return redirect(url_for('web.forgot_password', user_id=user.id))
            flash('You do not have an email associated with your account. Ask an administrator to reset your password.',
                  'danger')
        return render_template('forgot_password.html', form=form, pageTitle="Forgot Password")

    form = TokenForm()
    user = User.query.get(user_id)
    if form.validate_on_submit():
        token = Token.query.filter_by(value=form.value.data.upper(), used=False, user_id=user.id).first()
        if token:
            token.used = True
            user.reset_password()
            db.session.commit()
            logout_user()
            flash('Your password has been reset.', 'success')
            user.create_notification("Password Reset", "Your password was reset. If this action was not done by you, please secure your account.", email=True)
            return redirect(url_for('web.setup_password'))
        flash('Invalid authentication token.', 'danger')
    token = Token.query.filter_by(used=False, user_id=user.id).order_by(
        Token.id.desc()).first()
    resend = request.args.get('resend', default=False, type=bool)
    if resend:
        token.used = True
        db.session.commit()
        return redirect(url_for('web.forgot_password', user_id=user.id))
    if not token:
        token = Token(user_id=user.id)
        value = token.generate_value()
        db.session.add(token)
        db.session.commit()

        if send_email('Password Reset', user.email, f"Your authentication code is <b>{value}<b>"):
            flash('An authentication code has been sent via email.', 'info')
        else:
            flash('An authentication code could not be sent. Ask an administrator to reset your password.', 'danger')
            return redirect(url_for('web.forgot_password'))

    return render_template('forgot_password_auth.html', form=form, user=user, pageTitle="Forgot Password")


@web.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.lower().replace(" ", "")).first()
        if user:
            if user.account_status != 'active':
                flash('Your account is not active.', 'danger')
            elif not user.password_hash or user.get_setting('account_setup') == "False":
                flash('You have not setup your password yet. Click on "Setup Password" to get started.', 'info')
            elif user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                session['username'] = user.username
                user_login = Login(timestamp=datetime.utcnow(), user_id=user.id, ip=request.remote_addr)
                db.session.add(user_login)
                db.session.commit()
                next = request.args.get('next')
                return redirect(next or url_for('web.dashboard'))
            else:
                flash('Invalid username or password.', 'danger')
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form, pageTitle="Login")


@web.route('/app-setup')
def app_setup():
    user = User.query.filter_by(username="nkpratt").first()
    if not user:
        dr1 = User(name="Dr. Dylan Caldwell", username="jacaldwell", email="jacaldwell@valdosta.edu", account_status="active", role="staff")
        db.session.add(dr1)
        dr2 = User(name="Dr. Nathaniel Bare", username="nathanielbare", email="nathaniel.d.bare@gmail.com", account_status="active",
                    role="staff")
        db.session.add(dr2)
        p1 = User(name="Carol Stevens", username="rushpatel", email="rushpatel@valdosta.edu",
                   account_status="active",
                   role="patient")
        db.session.add(p1)
        p2 = User(name="Leo Roberson", username="jacarlstrom", email="jacarlstrom@valdosta.edu",
                  account_status="active",
                  role="patient")
        db.session.add(p2)
        p3 = User(name="Kay Garza", username="nkpratt", email="nkpratt@valdosta.edu",
                  account_status="active",
                  role="patient")
        db.session.add(p3)
        db.session.commit()
        dr1.set_setting(name='account_setup', value='False')
        dr1.set_setting("manage_users", "True")

        dr2.set_setting(name='account_setup', value='False')
        dr2.set_setting("manage_users", "True")

        p1.set_setting(name='account_setup', value='False')
        p1.set_setting("manage_users", "False")

        p2.set_setting(name='account_setup', value='False')
        p2.set_setting("manage_users", "False")

        p3.set_setting(name='account_setup', value='False')
        p3.set_setting("manage_users", "False")
        db.session.commit()
        flash('The users have been created.', 'success')
        return redirect(url_for('web.login'))
    else:
        flash('The app has already been setup.', 'danger')
        return redirect(url_for('web.home'))


@web.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('web.home'))


@web.errorhandler(403)
def not_found_error(error):
    return render_template('403.html'), 403


@web.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@web.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
