from flask import render_template
from sendgrid import SendGridAPIClient, From
from sendgrid.helpers.mail import Mail
from app import app
import requests


def send_email(subject, to_emails, content, from_name="Ignite"):
    message = Mail(
        from_email=From('xdylan2003x@gmail.com', from_name),
        to_emails=to_emails,
        subject=subject+' | Ignite',
        html_content=render_template('email_template.html', content=content)
    )
    try:
        sg = SendGridAPIClient(app.config['SENDGRID_KEY'])
        sg.send(message)
        return True
    except Exception as e:
        return False


def get_fhir_access_token():
    client_id = "213"
    client_secret = "596461a15dd0ab743440c87b5aaf08c5"
    scope = "system/*.*"
    form_params = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': scope
    }
    url = "https://app.azaleahealth.com/fhir/R4/142437/oauth/token"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, data=form_params, headers=headers)
    return response.json().get('access_token')


def make_fhir_request(url, base_url='https://app.azaleahealth.com/fhir/R4/142437/'):
    access_token = get_fhir_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(base_url+url, headers=headers)
    return response.json()
