import requests
session = requests.Session()
r = session.post('http://localhost:8000/api/auth/login', json={'identifier': 'riteeritee251@gmail.com', 'password': 'TempPassw0rd!x'})
print('Login:', r.status_code, r.text)
r2 = session.get('http://localhost:8000/api/admin/users')
print('Get Users:', r2.status_code, r2.text)
r3 = session.get('http://localhost:8000/api/admin/documents')
print('Get Docs:', r3.status_code, r3.text)
