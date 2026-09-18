import requests

session = requests.Session()

r_login = session.post("http://localhost:8000/api/auth/login", json={
    "identifier": "aaravmehta123@gmail.com",
    "password": "Aarav@2024",  # Let's hope I reset it correctly? No I didn't. I'll just change the db directly.
    "company_name": "Nexora Technologies Pvt. Ltd."
})
print(r_login.json())

r_me = session.get("http://localhost:8000/api/auth/me")
print(r_me.json())
