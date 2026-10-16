"""Cliente da TikTok Shop Open API (202309): assinatura HMAC, refresh automático e shop_cipher.

Uso como teste rápido (lista as lojas autorizadas):
    python tiktok_client.py
"""
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import tiktok_auth

API_URL = "https://open-api.tiktokglobalshop.com"
REFRESH_MARGIN = 3600  # renova se faltar menos de 1h para expirar


def sign(path, params, body, app_secret):
    """secret + path + chave/valor ordenados (sem sign/access_token) + body + secret, HMAC-SHA256 com o secret."""
    pares = "".join(f"{k}{params[k]}" for k in sorted(params) if k not in ("sign", "access_token"))
    texto = f"{app_secret}{path}{pares}{body}{app_secret}"
    return hmac.new(app_secret.encode(), texto.encode(), hashlib.sha256).hexdigest()


class TikTokClient:
    def __init__(self, app_key=None, app_secret=None, tokens_path=tiktok_auth.TOKENS_PATH):
        self.app_key = app_key or os.environ["TIKTOK_APP_KEY"]
        self.app_secret = app_secret or os.environ["TIKTOK_APP_SECRET"]
        self.tokens_path = tokens_path
        self.tokens = tiktok_auth.load_tokens(tokens_path)
        self._shop_cipher = os.environ.get("TIKTOK_SHOP_CIPHER")

    def access_token(self):
        if self.tokens["access_token_expire_in"] - time.time() < REFRESH_MARGIN:
            if self.tokens["refresh_token_expire_in"] < time.time():
                raise RuntimeError("Refresh token expirado: refaça a autorização da loja e rode tiktok_auth.py.")
            novos = tiktok_auth.refresh_tokens(self.tokens["refresh_token"], self.app_key, self.app_secret)
            tiktok_auth.save_tokens(novos, self.tokens_path)
            self.tokens = tiktok_auth.load_tokens(self.tokens_path)
        return self.tokens["access_token"]

    def shop_cipher(self):
        if not self._shop_cipher:
            # ponytail: assume uma única loja autorizada (ELD); defina TIKTOK_SHOP_CIPHER se houver mais de uma
            self._shop_cipher = self.authorized_shops()[0]["cipher"]
        return self._shop_cipher

    def authorized_shops(self):
        return self.request("GET", "/authorization/202309/shops", shop=False)["shops"]

    def request(self, method, path, params=None, body=None, shop=True):
        params = {**(params or {}), "app_key": self.app_key, "timestamp": int(time.time())}
        if shop:
            params["shop_cipher"] = self.shop_cipher()
        body_text = json.dumps(body, separators=(",", ":")) if body is not None else ""
        params["sign"] = sign(path, params, body_text, self.app_secret)
        req = urllib.request.Request(
            f"{API_URL}{path}?{urllib.parse.urlencode(params)}",
            data=body_text.encode() if body is not None else None,
            method=method,
            headers={"x-tts-access-token": self.access_token(), "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resposta = json.load(resp)
        except urllib.error.HTTPError as e:
            resposta = json.loads(e.read() or b"{}")
            resposta.setdefault("message", f"HTTP {e.code}")
        if resposta.get("code") != 0:
            raise RuntimeError(f"Erro da API em {path}: {resposta.get('code')} {resposta.get('message')} (request_id={resposta.get('request_id')})")
        return resposta.get("data", {})


if __name__ == "__main__":
    for loja in TikTokClient().authorized_shops():
        print(f"{loja['name']} | região {loja['region']} | id {loja['id']} | cipher {loja['cipher']}")
