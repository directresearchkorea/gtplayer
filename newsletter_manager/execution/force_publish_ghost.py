import os
import sys
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

import jwt # PyJWT

def create_jwt_token(api_key):
    id, secret = api_key.split(':')
    iat = int(datetime.now().timestamp())
    header = {'alg': 'HS256', 'typ': 'JWT', 'kid': id}
    payload = {'iat': iat, 'exp': iat + 5 * 60, 'aud': '/admin/'}
    return jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers=header)

def force_publish_scheduled():
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
    api_url = os.environ.get('GHOST_API_URL', '').rstrip('/')
    api_key = os.environ.get('GHOST_ADMIN_API_KEY', '')
    if not api_url or not api_key:
        print("Missing GHOST_API_URL or GHOST_ADMIN_API_KEY")
        return
        
    token = create_jwt_token(api_key)
    headers = {
        'Authorization': f'Ghost {token}',
        'Accept-Version': 'v5.0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Get scheduled posts
    url = f"{api_url}/ghost/api/admin/posts/?filter=status:scheduled"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch posts: {resp.status_code}")
        print(resp.text[:500])
        return
        
    try:
        data = resp.json()
    except Exception as e:
        print(f"JSON Decode Error: {e}")
        print(resp.text[:500])
        return
        
    posts = data.get('posts', [])
    print(f"Found {len(posts)} scheduled posts.")
    
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    for p in posts:
        pub_at = p.get('published_at')
        if not pub_at: continue
        
        # Simple string comparison works for ISO dates
        if pub_at < now:
            print(f"Force publishing past-due post: {p['title']} (scheduled for {pub_at})")
            
            # Update status to published
            update_url = f"{api_url}/ghost/api/admin/posts/{p['id']}/"
            payload = {
                "posts": [{
                    "id": p['id'],
                    "updated_at": p['updated_at'],
                    "status": "published"
                }]
            }
            res = requests.put(update_url, headers=headers, json=payload)
            if res.status_code in [200, 201]:
                print(f"  ✅ Published!")
            else:
                print(f"  ❌ Failed: {res.text}")

if __name__ == '__main__':
    force_publish_scheduled()
