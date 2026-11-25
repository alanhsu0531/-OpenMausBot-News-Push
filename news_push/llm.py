"""呼叫免費的大型語言模型。

優先順序：
1. OpenRouter 免費模型（OPENROUTER_API_KEY）。先試 OPENROUTER_MODELS 指定的模型，
   都失敗時自動從 OpenRouter 模型清單挑其他 :free 模型。
2. GitHub Models（用 Actions 內建的 GITHUB_TOKEN，免費但有每日次數限制）。
"""

from __future__ import annotations

import os
import sys
import time

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
DEFAULT_OPENROUTER_MODELS = [
    "deepseek/deepseek-chat-v3.1:free",
    "qwen/qwen3-235b-a22b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]
GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"
DEFAULT_GITHUB_MODEL = "openai/gpt-4.1-mini"
MAX_AUTO_FREE_MODELS = 4


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
    """回傳 (內容, 使用的模型)。所有模型都失敗時丟出 RuntimeError。"""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    errors = []

    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        headers = {"Authorization": f"Bearer {key}", "X-Title": "Daily AI Digest"}
        preferred = [m.strip() for m in os.environ.get("OPENROUTER_MODELS", "").split(",") if m.strip()]
        candidates = preferred or DEFAULT_OPENROUTER_MODELS
        tried: set[str] = set()
        for phase in ("preferred", "auto"):
            if phase == "auto":
                candidates = _auto_free_models(headers, tried)
            for model in candidates:
                tried.add(model)
                try:
                    log(f"[llm] 嘗試 OpenRouter {model}")
                    out = _post(OPENROUTER_URL, headers, {
                        "model": model, "messages": messages, "temperature": temperature,
                    })
                    return out, f"openrouter:{model}"
                except Exception as exc:
                    errors.append(f"{model}: {exc}"[:200])
                    log(f"[llm] 失敗 {model}: {exc}")
    else:
        log("[llm] 沒有設定 OPENROUTER_API_KEY，直接使用 GitHub Models")

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        model = os.environ.get("GITHUB_MODEL", DEFAULT_GITHUB_MODEL)
        try:
            log(f"[llm] 嘗試 GitHub Models {model}")
            out = _post(GITHUB_MODELS_URL, {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            }, {
                "model": model, "messages": messages, "temperature": temperature,
            })
            return out, f"github:{model}"
        except Exception as exc:
            errors.append(f"github {model}: {exc}"[:200])
            log(f"[llm] 失敗 GitHub Models: {exc}")

    raise RuntimeError("所有模型都失敗：\n" + "\n".join(errors))
