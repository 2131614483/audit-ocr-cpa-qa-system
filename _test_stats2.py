import requests
r = requests.get('http://127.0.0.1:5001/api/stats')
print(r.json())
