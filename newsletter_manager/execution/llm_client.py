"""
llm_client.py — `from google import genai` 대체용 LLM 프로바이더 스위치

사용법 (기존 코드):
    from google import genai          →   from llm_client import genai
    client = genai.Client(api_key=...)    (그대로)
    client.models.generate_content(model=..., contents=...)  (그대로)
    response.text                         (그대로)

.env 설정:
    LLM_PROVIDER=ollama        # 'gemini'(기본) 또는 'ollama'
    OLLAMA_MODEL=qwen2.5:7b    # 로컬 모델 이름
    OLLAMA_HOST=http://localhost:11434
    OLLAMA_NUM_CTX=32768       # 컨텍스트 길이 (긴 후보 리스트 프롬프트 대응)
    OLLAMA_TIMEOUT=1800        # 1회 호출 최대 대기(초) — CPU 추론은 느림
    LLM_MAX_CANDIDATES=80      # 로컬 모드에서 큐레이션 프롬프트에 넣을 최대 후보 수

로컬 모드 제약:
    - 이미지 생성(response_modalities=IMAGE)은 지원하지 않음 → 예외 발생 (호출부가 스킵 처리)
    - 이미지 입력(Part.from_bytes)은 무시하고 텍스트만 전달
"""
import os
import json
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:
    pass

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "32768"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "1800"))


def is_local() -> bool:
    return LLM_PROVIDER == "ollama"


def max_candidates():
    """로컬 모드일 때 큐레이션 후보 최대 개수 (Gemini 모드면 None = 제한 없음)."""
    if not is_local():
        return None
    return int(os.getenv("LLM_MAX_CANDIDATES", "80"))


def trim_candidates(candidates: list) -> list:
    """로컬 모드에서 프롬프트가 너무 길어지지 않도록 후보를 줄인다.
    교차출현 수가 많은 기사를 우선하고, 국가별로 번갈아 뽑아 KR/IN/JP/GLOBAL 균형을 유지한다.
    Gemini 모드에서는 원본 그대로 반환."""
    cap = max_candidates()
    if not cap or len(candidates) <= cap:
        return candidates
    ranked = sorted(candidates, key=lambda c: c.get("cross_reference_count", 0) or 0, reverse=True)
    buckets = {}
    for c in ranked:
        buckets.setdefault(c.get("country", "?"), []).append(c)
    picked = []
    while len(picked) < cap and any(buckets.values()):
        for key in list(buckets.keys()):
            if buckets[key]:
                picked.append(buckets[key].pop(0))
                if len(picked) >= cap:
                    break
    return picked


# ── Ollama 응답을 google-genai 응답처럼 보이게 하는 래퍼 ──────────────────

class _Part:
    def __init__(self, text):
        self.text = text
        self.inline_data = None


class _Content:
    def __init__(self, text):
        self.parts = [_Part(text)]


class _Candidate:
    def __init__(self, text):
        self.content = _Content(text)


class _Response:
    def __init__(self, text):
        self.text = text
        self.candidates = [_Candidate(text)]


def _contents_to_text(contents) -> str:
    if isinstance(contents, str):
        return contents
    if isinstance(contents, (list, tuple)):
        texts = []
        for c in contents:
            if isinstance(c, str):
                texts.append(c)
            elif getattr(c, "text", None):
                texts.append(c.text)
            # 이미지 등 바이너리 Part는 로컬 텍스트 모델에서 무시
        return "\n\n".join(texts)
    return str(contents)


def _config_get(config, key):
    if config is None:
        return None
    if isinstance(config, dict):
        return config.get(key)
    return getattr(config, key, None)


class _OllamaModels:
    def generate_content(self, model=None, contents=None, config=None, **kwargs):
        modalities = _config_get(config, "response_modalities") or []
        if any(str(m).upper() == "IMAGE" for m in modalities):
            raise RuntimeError("Local LLM (Ollama) does not support image generation")

        prompt = _contents_to_text(contents)
        options = {"num_ctx": OLLAMA_NUM_CTX}
        temp = _config_get(config, "temperature")
        if temp is not None:
            options["temperature"] = temp

        payload = {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": options,
            "keep_alive": "30m",
        }
        sys_inst = _config_get(config, "system_instruction")
        if sys_inst:
            payload["messages"].insert(0, {"role": "system", "content": str(sys_inst)})

        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (data.get("message") or {}).get("content", "").strip()
        if not text:
            raise RuntimeError(f"Empty response from Ollama ({OLLAMA_MODEL})")
        return _Response(text)


class _OllamaClient:
    def __init__(self, *args, **kwargs):
        self.models = _OllamaModels()


class _OllamaGenaiModule:
    Client = _OllamaClient


if is_local():
    genai = _OllamaGenaiModule()
else:
    from google import genai  # noqa: F401
