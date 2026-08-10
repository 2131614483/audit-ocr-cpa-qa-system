import urllib.request, json

# Check if any audit records exist with chat history
r = urllib.request.urlopen('http://localhost:5001/api/audit_data', timeout=5)
data = json.loads(r.read())
print('Total audit records:', len(data))

# Pick a record and test its history
test_id = data[0]['id'] if data else 150
print('Testing record id:', test_id)

r2 = urllib.request.urlopen('http://localhost:5001/api/audit_chat_history/' + str(test_id), timeout=5)
d2 = json.loads(r2.read())
print('Chat history items:', d2.get('total', 0))
for item in d2.get('items', [])[:3]:
    print('  q:', (item.get('question') or '')[:40])
    print('  a:', (item.get('answer') or '')[:40])
    print('  a_len:', len(item.get('answer') or ''))
