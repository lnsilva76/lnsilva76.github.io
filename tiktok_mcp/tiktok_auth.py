"""Troca o `code` do redirect do TikTok Shop por access/refresh token e salva localmente.

Uso:
    set TIKTOK_APP_KEY=...  &  set TIKTOK_APP_SECRET=...
    python tiktok_auth.py <code>

Os tokens ficam em ~/.eld-tiktok/tokens.json (fora do repositório, que é público).
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

AUTH_URL = "https://auth.tiktok-shops.com/api/v2/token"
TOKENS_PATH = Path(os.environ.get("TIKTOK_TOKENS_PATH", Path.home() / ".eld-tiktok" / "tokens.json"))


def _token_call(endpoint, params):
    query = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{AUTH_URL}/{endpoint}?{query}", timeout=30) as resp:
        body = json.load(resp)
    if body.get("code") != 0:
        raise RuntimeError(f"Falha em token/{endpoint}: {body.get('code')} {body.get('message')} (request_id={body.get('request_id')})")
    return body["data"]


def exchange_code(code, app_key, app_secret):
    return _token_call("get", {"app_key": app_key, "app_secret": app_secret, "auth_code": code, "grant_type": "authorized_code"})


def refresh_tokens(refresh_token, app_key, app_secret):
    return _token_call("refresh", {"app_key": app_key, "app_secret": app_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"})


def save_tokens(data, path=TOKENS_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({**data, "obtido_em": int(time.time())}, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)  # no Windows só tira o read-only; a proteção real é a pasta do usuário
    os.replace(tmp, path)


def load_tokens(path=TOKENS_PATH):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else input("Cole o code: ").strip()
    try:
        app_key, app_secret = os.environ["TIKTOK_APP_KEY"], os.environ["TIKTOK_APP_SECRET"]
    except KeyError as e:
        sys.exit(f"Variável de ambiente ausente: {e}")
    data = exchange_code(code, app_key, app_secret)
    save_tokens(data)
    fmt = lambda ts: datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")
    print(f"Tokens salvos em {TOKENS_PATH}")
    print(f"Loja: {data.get('seller_name')} ({data.get('seller_base_region')})")
    print(f"Access token expira em: {fmt(data['access_token_expire_in'])}")
    print(f"Refresh token expira em: {fmt(data['refresh_token_expire_in'])}")
    print(f"Scopes: {', '.join(data.get('granted_scopes', []))}")


if __name__ == "__main__":
    main()
