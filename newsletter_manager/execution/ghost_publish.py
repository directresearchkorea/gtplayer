"""
ghost_publish.py — Ghost Admin API를 통한 뉴스레터 포스트 자동 발행

사용법:
  python execution/ghost_publish.py                # 실제 발행 + 이메일 발송
  python execution/ghost_publish.py --dry-run      # API 연결 테스트만 (발행 안 함)
  python execution/ghost_publish.py --draft         # 드래프트로 저장 (이메일 안 보냄)

필요 환경 변수 (.env):
  GHOST_API_URL=https://gtplayer.ghost.io
  GHOST_ADMIN_API_KEY=<id>:<secret>
  GHOST_NEWSLETTER_SLUG=<newsletter-slug>
"""

import os
import sys
import json
import argparse
import datetime
import requests

# JWT 생성을 위한 라이브러리
try:
    import jwt
except ImportError:
    print("❌ PyJWT가 설치되어 있지 않습니다.")
    print("   설치: pip install PyJWT")
    sys.exit(1)

# .env 로드
from pathlib import Path

def load_env():
    """프로젝트 루트의 .env 파일에서 환경 변수 로드"""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

def create_jwt_token(api_key: str) -> str:
    """
    Ghost Admin API 인증용 JWT 토큰 생성.
    api_key 형식: '<id>:<secret>'
    """
    # API key를 id와 secret으로 분리
    parts = api_key.split(":")
    if len(parts) != 2:
        raise ValueError("GHOST_ADMIN_API_KEY 형식이 올바르지 않습니다. '<id>:<secret>' 형식이어야 합니다.")
    
    key_id, secret = parts
    
    # secret을 bytes로 변환 (hex 디코딩)
    secret_bytes = bytes.fromhex(secret)
    
    # JWT payload
    iat = int(datetime.datetime.now().timestamp())
    payload = {
        "iat": iat,
        "exp": iat + 300,  # 5분 후 만료
        "aud": "/admin/"
    }
    
    # JWT 헤더
    headers = {
        "kid": key_id,
        "alg": "HS256",
        "typ": "JWT"
    }
    
    token = jwt.encode(payload, secret_bytes, algorithm="HS256", headers=headers)
    return token


def test_connection(api_url: str, token: str) -> bool:
    """Ghost Admin API 연결 테스트"""
    url = f"{api_url}/ghost/api/admin/site/"
    headers = {"Authorization": f"Ghost {token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            site = data.get("site", {})
            print(f"✅ Ghost 연결 성공!")
            print(f"   사이트: {site.get('title', 'N/A')}")
            print(f"   URL: {site.get('url', 'N/A')}")
            print(f"   버전: {site.get('version', 'N/A')}")
            return True
        else:
            print(f"❌ Ghost 연결 실패 (HTTP {resp.status_code})")
            print(f"   응답: {resp.text[:300]}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 네트워크 오류: {e}")
        return False


def get_newsletters(api_url: str, token: str) -> list:
    """사용 가능한 뉴스레터 목록 조회"""
    url = f"{api_url}/ghost/api/admin/newsletters/"
    headers = {"Authorization": f"Ghost {token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            newsletters = resp.json().get("newsletters", [])
            return newsletters
        else:
            print(f"⚠ 뉴스레터 조회 실패 (HTTP {resp.status_code})")
            return []
    except requests.exceptions.RequestException as e:
        print(f"⚠ 뉴스레터 조회 오류: {e}")
        return []


def read_html_content() -> str:
    """ghost_post_content.html 파일 읽기"""
    content_path = Path(__file__).parent.parent.parent / ".tmp" / "ghost_post_content.html"
    
    if not content_path.exists():
        print(f"❌ 콘텐츠 파일이 없습니다: {content_path}")
        sys.exit(1)
    
    with open(content_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    # HTML 주석 제거 (맨 위의 사용법 코멘트)
    if html.startswith("<!--"):
        end_comment = html.find("-->")
        if end_comment != -1:
            html = html[end_comment + 3:].strip()
    
    print(f"✅ 콘텐츠 로드 완료 ({len(html):,} bytes)")
    return html


def publish_post(
    api_url: str,
    token: str,
    title: str,
    html: str,
    tags: list,
    newsletter_slug: str = None,
    status: str = "published",
    slug: str = None,
    published_at: str = None,
    feature_image: str = None
) -> dict:
    """
    Ghost Admin API로 포스트 생성 및 발행.
    
    2단계 발행 방식:
      Step 1: 드래프트로 생성
      Step 2: PUT으로 published 상태로 변경 + 뉴스레터 발송
    
    이렇게 해야 Ghost가 newsletter 파라미터를 제대로 인식합니다.
    """
    base_url = f"{api_url}/ghost/api/admin/posts/"
    headers = {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json"
    }

    # 기존 동일 슬러그의 포스트가 이미 발행되었는지 확인
    if slug:
        check_url = f"{api_url}/ghost/api/admin/posts/slug/{slug}/"
        try:
            resp = requests.get(check_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                existing_post = resp.json()["posts"][0]
                if existing_post.get("status") == "published" and status == "published":
                    print(f"   ⚠️ 포스트(슬러그: {slug})가 이미 Ghost에 발행(published)되어 있습니다. 중복 생성을 건너뜁니다.")
                    return existing_post
        except Exception as e:
            print(f"   (경고) 기존 포스트 확인 중 오류 (무시하고 진행): {e}")
    
    # Ghost v6.22 Lexical 포맷: 가장 확실한 방법은 Lexical JSON을 직접 박는 것입니다.
    # HTML 파서(source=html)를 거치지 않고, Lexical의 "HTML 노드"를 직접 정의하여
    # 인라인 스타일과 테이블/div 구조가 100% 보존되도록 합니다.
    lexical = json.dumps({
        "root": {
            "children": [
                {
                    "type": "html",
                    "version": 1,
                    "html": html
                }
            ],
            "direction": None,
            "format": "",
            "indent": 0,
            "type": "root",
            "version": 1
        }
    })
    
    # ── Step 1: 드래프트로 생성 (source 파라미터 제외, 순수 Lexical 주입) ──
    print("   Step 1/2: 드래프트 생성...")
    draft_data = {
        "title": title,
        "lexical": lexical,
        "status": "draft",
        "tags": [{"name": t} for t in tags],
    }
    if slug:
        draft_data["slug"] = slug
    if feature_image:
        draft_data["feature_image"] = feature_image
    
    try:
        # source=html을 빼고 직접 lexical 데이터를 전송합니다
        resp = requests.post(base_url, headers=headers, json={"posts": [draft_data]}, timeout=30)
        
        if resp.status_code != 201:
            print(f"\n❌ 드래프트 생성 실패 (HTTP {resp.status_code})")
            error_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            for err in error_data.get("errors", []):
                print(f"   에러: {err.get('message', 'unknown')}")
            return None
        
        post = resp.json()["posts"][0]
        post_id = post["id"]
        updated_at = post["updated_at"]
        print(f"   ✅ 드래프트 생성 (ID: {post_id})")
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 네트워크 오류: {e}")
        return None
    
    # draft 모드면 여기서 종료
    if status == "draft":
        print(f"\n✅ 드래프트 저장 성공!")
        print(f"   제목: {post['title']}")
        print(f"   URL: {post['url']}")
        print(f"   ID: {post_id}")
        return post
    
    # ── Step 2: PUT으로 발행 + 뉴스레터 발송 ──
    print("   Step 2/2: 발행 + 이메일 발송...")
    
    put_url = f"{base_url}{post_id}/"
    put_data = {
        "posts": [{
            "status": status,
            "updated_at": updated_at
        }]
    }
    if status == "scheduled" and published_at:
        put_data["posts"][0]["published_at"] = published_at
    
    params = {}
    if newsletter_slug:
        params["newsletter"] = newsletter_slug
        params["email_segment"] = "all"
    
    try:
        resp2 = requests.put(put_url, headers=headers, json=put_data, params=params, timeout=30)
        
        if resp2.status_code == 200:
            post = resp2.json()["posts"][0]
            print(f"\n✅ 포스트 발행 성공!")
            print(f"   제목: {post['title']}")
            print(f"   URL: {post['url']}")
            print(f"   상태: {post['status']}")
            print(f"   ID: {post['id']}")
            
            # 이메일 발송 상태 확인
            email = post.get("email")
            if email:
                print(f"   📧 이메일 상태: {email.get('status', 'unknown')}")
                print(f"   📧 수신자 수: {email.get('email_count', 'unknown')}")
            else:
                newsletter_info = post.get("newsletter")
                if newsletter_info:
                    print(f"   📧 뉴스레터: {newsletter_info.get('name', newsletter_slug)}")
                else:
                    print(f"   ⚠ 이메일 발송이 연결되지 않았습니다")
            
            return post
        else:
            print(f"\n❌ 발행 실패 (HTTP {resp2.status_code})")
            error_data = resp2.json() if resp2.headers.get("content-type", "").startswith("application/json") else {}
            for err in error_data.get("errors", []):
                print(f"   에러: {err.get('message', 'unknown')}")
                if err.get("context"):
                    print(f"   컨텍스트: {err['context']}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 네트워크 오류: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Ghost Admin API 뉴스레터 자동 발행")
    parser.add_argument("--dry-run", action="store_true", help="API 연결 테스트만 (발행 안 함)")
    parser.add_argument("--draft", action="store_true", help="드래프트로 저장 (이메일 발송 안 함)")
    parser.add_argument("--title", default="GTPlayer #001 | 게임 산업 인사이트", help="포스트 제목")
    parser.add_argument("--tags", nargs="*", default=["#lang-ko", "#edition-001"], help="태그 목록")
    args = parser.parse_args()
    
    # .env 로드
    load_env()
    
    # 환경 변수 확인
    api_url = os.environ.get("GHOST_API_URL", "").rstrip("/")
    api_key = os.environ.get("GHOST_ADMIN_API_KEY", "")
    newsletter_slug = os.environ.get("GHOST_NEWSLETTER_SLUG", "")
    
    if not api_url or not api_key:
        print("❌ .env 파일에 Ghost API 설정이 없습니다.")
        print("   필요한 환경 변수:")
        print("   GHOST_API_URL=https://your-ghost-site.ghost.io")
        print("   GHOST_ADMIN_API_KEY=<id>:<secret>")
        print("   GHOST_NEWSLETTER_SLUG=<slug> (선택, 이메일 발송 시 필요)")
        sys.exit(1)
    
    print("=" * 50)
    print("  GTPlayer — Ghost 뉴스레터 자동 발행")
    print("=" * 50)
    print(f"  API URL: {api_url}")
    print(f"  모드: {'DRY RUN' if args.dry_run else ('DRAFT' if args.draft else 'PUBLISH + EMAIL')}")
    print("=" * 50)
    print()
    
    # 1. JWT 토큰 생성
    print("🔑 JWT 토큰 생성 중...")
    try:
        token = create_jwt_token(api_key)
        print("✅ JWT 토큰 생성 성공")
    except Exception as e:
        print(f"❌ JWT 토큰 생성 실패: {e}")
        sys.exit(1)
    
    # 2. 연결 테스트
    print("\n🔌 Ghost API 연결 테스트...")
    if not test_connection(api_url, token):
        sys.exit(1)
    
    # 3. 뉴스레터 목록 확인
    print("\n📋 뉴스레터 목록:")
    newsletters = get_newsletters(api_url, token)
    for nl in newsletters:
        marker = " ← 사용" if nl.get("slug") == newsletter_slug else ""
        print(f"   - {nl.get('name')} (slug: {nl.get('slug')}){marker}")
    
    if not newsletters:
        print("   (뉴스레터 없음)")
    
    # dry-run이면 여기서 종료
    if args.dry_run:
        print("\n🏁 DRY RUN 완료 — 연결 테스트 성공!")
        return
    
    # 4. 콘텐츠 로드
    print("\n📄 콘텐츠 로드 중...")
    html = read_html_content()
    
    # 5. 포스트 발행
    status = "draft" if args.draft else "published"
    nl_slug = newsletter_slug if not args.draft else None
    
    if not args.draft and not newsletter_slug:
        print("\n⚠ GHOST_NEWSLETTER_SLUG이 설정되지 않아 이메일 발송 없이 발행합니다.")
    
    mode_str = '저장' if args.draft else '발행'
    print(f"\n🚀 포스트 {mode_str} 중...")
    result = publish_post(
        api_url=api_url,
        token=token,
        title=args.title,
        html=html,
        tags=args.tags,
        newsletter_slug=nl_slug,
        status=status
    )
    
    if result:
        print(f"\n🏁 완료!")
    else:
        print(f"\n💥 실패 — 위의 에러 메시지를 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
