import json
import sys

sys.path.insert(0, '.')
from app.router import get_db_connection, hash_prompt

payload = {'choices': [{'message': {'content': 'cached reply'}}]}
key = hash_prompt({'model': 'gpt-4o', 'messages': [{'role': 'user', 'content': 'hello'}]})

conn = get_db_connection()
conn.execute('DELETE FROM prompt_cache')
conn.execute('INSERT INTO prompt_cache (prompt_hash, response_json) VALUES (?, ?)', (key, json.dumps(payload, ensure_ascii=False, sort_keys=True)))
conn.commit()
row = conn.execute('SELECT response_json FROM prompt_cache WHERE prompt_hash = ? LIMIT 1', (key,)).fetchone()
print('FOUND', bool(row), row['response_json'] if row else None)
conn.close()
