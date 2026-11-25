"""呼叫免費的大型語言模型，依序嘗試多家服務，有一家成功就停。

優先順序（沒設定 key 的服務會自動略過）：
1. OpenRouter 免費模型（OPENROUTER_API_KEY）。先試 OPENROUTER_MODELS 指定的模型，
   沒指定或都失敗時，自動從 OpenRouter 模型清單挑目前可用的 :free 模型。
2. Google Gemini API 免費額度（GEMINI_API_KEY）
3. NVIDIA NIM 免費端點（NVIDIA_API_KEY）
4. Groq 免費方案（GROQ_API_KEY）。每分鐘只有 8,000 tokens，提示太長時會失敗，所以放最後。

每家的模型都可用 Repository variables 覆寫：GEMINI_MODEL、NVIDIA_MODEL、GROQ_MODEL。
GitHub Models 已於 2026-07-30 停止服務；Hugging Face 免費帳號已無推論額度，所以都不使用。
"""

from __future__ import annotations

import os
import sys
import time

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
MAX_AUTO_FREE_MODELS = 5

# (名稱, API key 環境變數, 網址, 模型環境變數, 預設模型)
BACKUP_PROVIDERS = [
    ("Gemini", "GEMINI_API_KEY",
     "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
     "GEMINI_MODEL", "gemini-flash-latest"),
    ("NVIDIA", "NVIDIA_API_KEY",
     "https://integrate.api.nvidia.com/v1/chat/completions",
     "NVIDIA_MODEL", "moonshotai/kimi-k3.1-pro"),
    ("Groq", "GROQ_API_KEY",
     "https://api.groq.com/openai/v1/chat/completions",
     "GROQ_MODEL", "openai/gpt-oss-120b"),
]


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _post(url: str, headers: dict, payload: dict) -> str:
    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    if resp.status_code == 429:
        time.sleep(20)
        resp = requests.post(url, headers=headers, json=payload, timeout=180)
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(f"HTTP {resp.status_code} 非 JSON 回應：{resp.text[:300]!r}")
    if "error" in data:
        raise RuntimeError(str(data["error"])[:300])
    content = data["choices"][0]["message"]["content"]
    if not content or not content.strip():
        raise RuntimeError("模型回傳空白內容")
    return content


def _auto_free_models(headers: dict, exclude: set[str]) -> list[str]:
    try:
        models = requests.get(OPENROUTER_MODELS_URL, headers=headers, timeout=30).json()["data"]
    except Exception as exc:
        log(f"[llm] 無法取得 OpenRouter 模型清單：{exc}")
        return []
    free = [m for m in models if m["id"].endswith(":free") and m["id"] not in exclude
            and (m.get("context_length") or 0) >= 32000]
    free.sort(key=lambda m: m.get("context_length") or 0, reverse=True)
    return [m["id"] for m in free[:MAX_AUTO_FREE_MODELS]]


def chat(system: str, user: str, temperature: float = 0.3) -> tuple[str, str]:
    """回傳 (內容, 使用的模型)。所有服務都失敗時丟出 RuntimeError。"""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    errors: list[str] = []

    def attempt(label: str, url: str, key: str, model: str) -> str | None:
        try:
            log(f"[llm] 嘗試 {label} {model}")
            return _post(url, {"Authorization": f"Bearer {key}", "X-Title": "Daily AI Digest"},
                         {"model": model, "messages": messages, "temperature": temperature})
        except Exception as exc:
            errors.append(f"{label} {model}: {exc}"[:200])
            log(f"[llm] 失敗 {label} {model}: {exc}")
            return None

    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        preferred = [m.strip() for m in os.environ.get("OPENROUTER_MODELS", "").split(",") if m.strip()]
        tried: set[str] = set()
        for model in preferred:
            tried.add(model)
            if (out := attempt("OpenRouter", OPENROUTER_URL, key, model)):
                return out, f"openrouter:{model}"
        for model in _auto_free_models({"Authorization": f"Bearer {key}"}, tried):
            if (out := attempt("OpenRouter", OPENROUTER_URL, key, model)):
                return out, f"openrouter:{model}"

    for name, key_env, url, model_env, default_model in BACKUP_PROVIDERS:
        key = os.environ.get(key_env)
        if not key:
            continue
        model = os.environ.get(model_env) or default_model
        if (out := attempt(name, url, key, model)):
            return out, f"{name.lower()}:{model}"

    raise RuntimeError("所有模型都失敗：\n" + "\n".join(errors))
