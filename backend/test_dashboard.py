import urllib.request
import json
import os

req = urllib.request.Request("http://127.0.0.1:8000/api/admin/dashboard")
try:
    with open("token.txt") as f:
        req.add_header("Cookie", f"access_token={f.read().strip()}")
except FileNotFoundError:
    pass
try:
    with urllib.request.urlopen(req) as resp:
        print(resp.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())
except Exception as e:
    print(e)
