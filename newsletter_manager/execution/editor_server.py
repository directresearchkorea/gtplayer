"""
editor_server.py — 에디터용 로컬 서버

실행: py newsletter_manager/execution/editor_server.py
접속: http://localhost:7080/editor.html

기능:
 - web/ 폴더의 정적 파일 서빙
 - POST /api/save-edition → JSON을 web/editions/에 저장
 - POST /api/send-draft   → 정적 사이트(dist/) 로컬 빌드 및 에디션 저장
"""
import http.server, json, os, re, socket
from pathlib import Path
from urllib.parse import urlparse
from socketserver import ThreadingMixIn

PORT = 7080
NEWSLETTER_EXEC_DIR = Path(__file__).parent
WEB_DIR = NEWSLETTER_EXEC_DIR.parent.parent / 'web'
EDITIONS_DIR = WEB_DIR / 'editions'


def sanitize_edition_num(num_val):
    """Validate and sanitize edition number to prevent path traversal."""
    num_str = str(num_val or '').strip()
    if not re.match(r'^\d{1,4}$', num_str):
        return None
    return f"{int(num_str):03d}"


class ThreadingHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class EditorHandler(http.server.SimpleHTTPRequestHandler):
    # Disable DNS lookups for speed
    def address_string(self):
        return self.client_address[0]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def _send_cors_headers(self):
        origin = self.headers.get('Origin', '')
        allowed_origins = [
            f'http://localhost:{PORT}',
            f'http://127.0.0.1:{PORT}'
        ]
        if origin in allowed_origins:
            self.send_header('Access-Control-Allow-Origin', origin)
        else:
            self.send_header('Access-Control-Allow-Origin', f'http://localhost:{PORT}')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def do_GET(self):
        if self.path == '/api/published':
            published = []
            if EDITIONS_DIR.exists():
                for f in EDITIONS_DIR.glob('edition_*.json'):
                    try:
                        with open(f, 'r', encoding='utf-8') as fp:
                            data = json.load(fp)
                        if data.get('status') == 'published':
                            published.append(data.get('num', ''))
                    except: pass
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'published': published}).encode())
        else:
            super().do_GET()
    
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        if self.path == '/api/save-edition':
            try:
                data = json.loads(body)
                num = sanitize_edition_num(data.get('num', '000'))
                if not num:
                    self._json_response(400, {'ok': False, 'error': '유효하지 않은 에디션 번호입니다.'})
                    return
                EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
                out = EDITIONS_DIR / f'edition_{num}.json'
                with open(out, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                TMP_DIR = Path(__file__).parent.parent.parent / '.tmp'
                TMP_DIR.mkdir(exist_ok=True)
                current_path = TMP_DIR / 'edition_current.json'
                with open(current_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f'💾 저장: {out.name} + edition_current.json')
                self._json_response(200, {'ok': True, 'file': out.name})
            except Exception as e:
                self._json_response(500, {'ok': False, 'error': str(e)})

        elif self.path == '/api/delete-edition':
            try:
                data = json.loads(body)
                num = sanitize_edition_num(data.get('num', ''))
                if not num:
                    self._json_response(400, {'ok': False, 'error': '유효하지 않은 에디션 번호입니다.'})
                    return
                target_file = EDITIONS_DIR / f'edition_{num}.json'
                if target_file.exists():
                    try:
                        with open(target_file, 'r', encoding='utf-8') as f:
                            ed_data = json.load(f)
                        ed_data['status'] = 'draft'
                        if 'schedule' in ed_data:
                            del ed_data['schedule']
                        with open(target_file, 'w', encoding='utf-8') as f:
                            json.dump(ed_data, f, ensure_ascii=False, indent=2)
                        print(f'🚫 에디션 예약 해제 (파일 보존됨): {target_file.name}')
                    except Exception as e:
                        print(f'오류 발생 (예약 해제): {e}')
                self._json_response(200, {'ok': True})
            except Exception as e:
                self._json_response(500, {'ok': False, 'error': str(e)})

        elif self.path == '/api/send-draft':
            try:
                data = json.loads(body)
                num = sanitize_edition_num(data.get('num', '000'))
                if not num:
                    self._json_response(400, {'ok': False, 'error': '유효하지 않은 에디션 번호입니다.'})
                    return
                EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
                out = EDITIONS_DIR / f'edition_{num}.json'
                if 'status' not in data:
                    data['status'] = 'draft'
                with open(out, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                import sys, subprocess
                BASE_DIR = NEWSLETTER_EXEC_DIR.parent.parent
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                result = subprocess.run(
                    [sys.executable, str(NEWSLETTER_EXEC_DIR / 'build_site.py')],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, cwd=str(BASE_DIR)
                )
                if result.returncode == 0:
                    self._json_response(200, {'ok': True})
                else:
                    error_msg = result.stderr[-300:] if result.stderr else result.stdout[-300:]
                    self._json_response(500, {'ok': False, 'error': error_msg})
            except Exception as e:
                self._json_response(500, {'ok': False, 'error': str(e)})

        elif self.path == '/api/test-send':
            try:
                data = json.loads(body)
                import sys, subprocess
                EXEC_DIR = Path(__file__).parent
                TMP_DIR = Path(__file__).parent.parent.parent / '.tmp'
                TMP_DIR.mkdir(exist_ok=True)
                
                tmp_json = TMP_DIR / '_test_send.json'
                with open(tmp_json, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                result = subprocess.run(
                    [sys.executable, str(NEWSLETTER_EXEC_DIR / 'publish_edition.py'), str(tmp_json), '--preview'],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, cwd=str(EXEC_DIR.parent)
                )
                
                num = sanitize_edition_num(data.get('num', '000')) or '000'
                html_file = TMP_DIR / f'edition_{num}_ko.html'
                if not html_file.exists():
                    self._json_response(500, {'ok': False, 'error': f'HTML 생성 실패: {result.stderr[:200]}'})
                    return
                
                with open(html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                from dotenv import load_dotenv
                load_dotenv(dotenv_path=str(Path(__file__).parent.parent.parent / '.env'))
                
                sg_key = os.getenv('SENDGRID_API_KEY')
                from_email = os.getenv('FROM_EMAIL', 'noreply@gtplayer.net')
                from_name = os.getenv('FROM_NAME', 'GTPlayer 뉴스레터')
                to_email = os.getenv('TO_EMAIL', 'admin@gtplayer.net')
                
                if not sg_key:
                    self._json_response(500, {'ok': False, 'error': 'SENDGRID_API_KEY가 .env에 없습니다'})
                    return
                
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Mail
                
                message = Mail(
                    from_email=(from_email, from_name),
                    to_emails=to_email,
                    subject=f'[GTPlayer TEST] 에디션 #{num} — 테스트 발송',
                    html_content=html_content,
                )
                sg = SendGridAPIClient(api_key=sg_key)
                response = sg.send(message)
                
                print(f'📧 테스트 발송: #{num} → {to_email} (status: {response.status_code})')
                tmp_json.unlink(missing_ok=True)
                
                self._json_response(200, {'ok': True, 'to': to_email, 'status': response.status_code})
            except Exception as e:
                print(f'❌ 테스트 발송 오류: {e}')
                self._json_response(500, {'ok': False, 'error': str(e)})
        elif self.path == '/api/preview':
            try:
                data = json.loads(body)
                edition = data.get('edition', {})
                lang = data.get('lang', 'ko')
                
                import sys, importlib
                EXEC_DIR = Path(__file__).parent
                if str(EXEC_DIR) not in sys.path:
                    sys.path.insert(0, str(EXEC_DIR))
                import publish_edition
                importlib.reload(publish_edition)
                from publish_edition import render_newsletter_html
                
                html = render_newsletter_html(edition, lang)
                full = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Preview #{edition.get("num","")}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>body{{font-family:'Inter',sans-serif;background:#f0f4f8;display:flex;justify-content:center;padding:40px;margin:0}}.wrap{{width:640px;max-width:100%}}</style></head>
<body><div class="wrap">{html}</div></body></html>'''
                
                print(f'👁 미리보기 생성: #{edition.get("num","")} ({lang})')
                self._json_response(200, {'ok': True, 'html': full})
            except Exception as e:
                print(f'❌ 미리보기 오류: {e}')
                self._json_response(500, {'ok': False, 'error': str(e)})
        elif self.path == '/api/translate':
            try:
                data = json.loads(body)
                from dotenv import load_dotenv
                load_dotenv(dotenv_path=str(Path(__file__).parent.parent.parent / '.env'))
                
                api_key = os.getenv('GEMINI_API_KEY')
                if not api_key:
                    self._json_response(500, {'ok': False, 'error': 'GEMINI_API_KEY가 .env에 없습니다'})
                    return
                
                from llm_client import genai
                client = genai.Client(api_key=api_key)
                
                sections = data.get('sections', {})
                texts = {}
                
                # Calendar
                cal = sections.get('calendar', {})
                for i, r in enumerate(cal.get('releases', [])):
                    texts[f'calendar.releases.{i}.game'] = r.get('game', '')
                    texts[f'calendar.releases.{i}.note'] = r.get('note', '')
                    texts[f'calendar.releases.{i}.dev'] = r.get('dev', '')
                for i, ev in enumerate(cal.get('events', [])):
                    texts[f'calendar.events.{i}.name'] = ev.get('name', '')
                    texts[f'calendar.events.{i}.note'] = ev.get('note', '')
                    texts[f'calendar.events.{i}.venue'] = ev.get('venue', '')
                
                # Briefing
                for i, item in enumerate(sections.get('briefing', {}).get('items', [])):
                    texts[f'briefing.items.{i}.title'] = item.get('title', '')
                    texts[f'briefing.items.{i}.source'] = item.get('source', '')
                    texts[f'briefing.items.{i}.time'] = item.get('time', '')
                
                # Feedback (single & multi-item support)
                fb = sections.get('feedback', {})
                if 'game' in fb: texts['feedback.game'] = fb.get('game', '')
                if 'period' in fb: texts['feedback.period'] = fb.get('period', '')
                if 'sources' in fb: texts['feedback.sources'] = fb.get('sources', '')
                for i, kw in enumerate(fb.get('keywords', [])):
                    texts[f'feedback.keywords.{i}.text'] = kw.get('text', '')
                for i, c in enumerate(fb.get('comments', [])):
                    texts[f'feedback.comments.{i}.text'] = c.get('text', '')
                for j, item in enumerate(fb.get('items', [])):
                    texts[f'feedback.items.{j}.game'] = item.get('game', '')
                    texts[f'feedback.items.{j}.period'] = item.get('period', '')
                    texts[f'feedback.items.{j}.sources'] = item.get('sources', '')
                    for i, kw in enumerate(item.get('keywords', [])):
                        texts[f'feedback.items.{j}.keywords.{i}.text'] = kw.get('text', '')
                    for i, c in enumerate(item.get('comments', [])):
                        texts[f'feedback.items.{j}.comments.{i}.text'] = c.get('text', '')
                
                # DrK
                drk = sections.get('drk', {})
                texts['drk.title'] = drk.get('title', '')
                texts['drk.intro'] = drk.get('intro', '')
                texts['drk.points'] = drk.get('points', '')

                # Meme
                meme = sections.get('meme', {})
                if 'what_happened' in meme:
                    texts['meme.what_happened'] = meme.get('what_happened', '')
                if 'one_liner' in meme:
                    texts['meme.one_liner'] = meme.get('one_liner', '')
                if 'items' in meme:
                    for i, item in enumerate(meme.get('items', [])):
                        texts[f'meme.items.{i}.comment'] = item.get('comment', '')
                
                # Soundtrack
                st = sections.get('soundtrack', {})
                if 'game' in st: texts['soundtrack.game'] = st.get('game', '')
                texts['soundtrack.title'] = st.get('title', '')
                texts['soundtrack.comment'] = st.get('comment', '')
                
                # Trailer
                tr = sections.get('trailer', {})
                if 'game' in tr: texts['trailer.game'] = tr.get('game', '')
                texts['trailer.title'] = tr.get('title', '')
                texts['trailer.comment'] = tr.get('comment', '')
                
                # Epic
                ep = sections.get('epic', {})
                if 'game' in ep: texts['epic.game'] = ep.get('game', '')
                texts['epic.title'] = ep.get('title', '')
                texts['epic.comment'] = ep.get('comment', '')
                
                # Newsletter Feedback
                nl = sections.get('newsletter_feedback', {})
                texts['newsletter_feedback.question'] = nl.get('question', '')
                texts['newsletter_feedback.upLabel'] = nl.get('upLabel', '')
                texts['newsletter_feedback.downLabel'] = nl.get('downLabel', '')

                # Chart
                chart = sections.get('chart', {})
                if 'game' in chart: texts['chart.game'] = chart.get('game', '')
                if 'title' in chart: texts['chart.title'] = chart.get('title', '')
                if 'comment' in chart: texts['chart.comment'] = chart.get('comment', '')

                texts = {k: str(v) for k, v in texts.items() if v and str(v).strip()}
                
                translations = {'en': {}, 'ja': {}}
                keep_existing = data.get('keepExisting', True)
                old_translations = data.get('translations', {})
                
                for lang, lang_name in [('en', 'English'), ('ja', 'Japanese')]:
                    old_lang = old_translations.get(lang, {})
                    old_flat = {}
                    for sec, sec_data in old_lang.items():
                        for field, v in sec_data.items():
                            old_flat[f"{sec}.{field}"] = v
                            
                    to_translate = {}
                    for key, val in texts.items():
                        if keep_existing and old_flat.get(key) and str(old_flat[key]).strip():
                            parts = key.split('.', 1)
                            sec = parts[0]
                            field = parts[1] if len(parts) > 1 else ''
                            if sec not in translations[lang]:
                                translations[lang][sec] = {}
                            translations[lang][sec][field] = old_flat[key]
                        else:
                            to_translate[key] = val
                    
                    if not to_translate:
                        print(f'🌐 {lang_name} 번역할 새 항목 없음')
                        continue
                    
                    json_payload = json.dumps(to_translate, ensure_ascii=False, indent=2)
                    prompt = f"""아래 JSON의 한국어 값들을 {lang_name}로 번역해주세요.
키는 그대로 유지하고, 값만 {lang_name}로 번역하세요.
게임 이름, 고유명사는 공식 {lang_name} 표기를 사용하세요.
JSON만 출력하세요.

```json
{json_payload}
```"""
                    response = client.models.generate_content(
                        model="gemini-flash-latest",
                        contents=prompt,
                    )
                    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                    if json_match:
                        flat = json.loads(json_match.group(0))
                        for key, val in flat.items():
                            parts = key.split('.', 1)
                            sec = parts[0]
                            field = parts[1] if len(parts) > 1 else ''
                            if sec not in translations[lang]:
                                translations[lang][sec] = {}
                            translations[lang][sec][field] = val
                    
                    print(f'🌐 {lang_name} 번역 완료 ({len(to_translate)}개 필드)')
                
                self._json_response(200, {'ok': True, 'translations': translations})
            except Exception as e:
                print(f'❌ 번역 오류: {e}')
                self._json_response(500, {'ok': False, 'error': str(e)})

        else:
            self.send_response(404)
            self.end_headers()
    
    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()
    
    def log_message(self, format, *args):
        if 'POST' in str(args[0]):
            super().log_message(format, *args)


if __name__ == '__main__':
    print(f'🚀 GTPlayer Editor Server (Multi-threaded)')
    print(f'   http://127.0.0.1:{PORT}/editor.html')
    print(f'   Ctrl+C로 종료\n')
    server = ThreadingHTTPServer(('127.0.0.1', PORT), EditorHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n🛑 서버 종료')
