import sqlite3
import pandas as pd
c = sqlite3.connect('rag.db')
u = pd.read_sql_query('SELECT * FROM users WHERE email="aaravmehta123@gmail.com"', c)
print(u.to_string())
d = pd.read_sql_query('SELECT * FROM departments WHERE id="' + u.iloc[0]['department_id'] + '"', c)
print(d.to_string())
