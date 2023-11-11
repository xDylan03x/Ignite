from fhir.resources.patient import Patient
from app.helpers import make_fhir_request

print(make_fhir_request('Patient'))
p = Patient.parse_obj(make_fhir_request('Patient?name=Carol Stevens')['entry'][0]['resource'])
print(p.name[0].text)
print(p.telecom[0].value)
print(p.gender[0])
print(p.birthDate)
print(p.address[0].line[0], p.address[0].city, p.address[0].state, p.address[0].postalCode, p.address[0].country)
print(p.id)
