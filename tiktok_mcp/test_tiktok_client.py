import hashlib
import hmac
import io
import json
import tempfile
import time
from pathlib import Path
from unittest import mock

import tiktok_auth
import tiktok_client


def test_sign():
    params = {"timestamp": 100, "app_key": "K", "shop_cipher": "C", "sign": "x", "access_token": "y"}
    esperado = hmac.new(b"S", b"S/a/b" + b"app_keyKshop_cipherCtimestamp100" + b'{"q":1}' + b"S", hashlib.sha256).hexdigest()
    assert tiktok_client.sign("/a/b", params, '{"q":1}', "S") == esperado


def cliente_com_tokens(expira_em):
    path = Path(tempfile.mkdtemp()) / "tokens.json"
    tiktok_auth.save_tokens({"access_token": "VELHO", "refresh_token": "R",
                             "access_token_expire_in": expira_em, "refresh_token_expire_in": time.time() + 10**6}, path)
    return tiktok_client.TikTokClient("K", "S", path), path


def test_refresh_quando_perto_de_expirar():
    c, path = cliente_com_tokens(time.time() + 60)
    novos = {"access_token": "NOVO", "refresh_token": "R2", "access_token_expire_in": time.time() + 10**5, "refresh_token_expire_in": time.time() + 10**6}
    with mock.patch.object(tiktok_auth, "refresh_tokens", return_value=novos) as m:
        assert c.access_token() == "NOVO"
        assert c.access_token() == "NOVO"
    m.assert_called_once_with("R", "K", "S")
    assert tiktok_auth.load_tokens(path)["refresh_token"] == "R2"


def test_sem_refresh_quando_valido():
    c, _ = cliente_com_tokens(time.time() + 10**5)
    with mock.patch.object(tiktok_auth, "refresh_tokens") as m:
        assert c.access_token() == "VELHO"
    m.assert_not_called()


def test_request_monta_url_e_header():
    c, _ = cliente_com_tokens(time.time() + 10**5)
    c._shop_cipher = "CIF"
    resp = io.BytesIO(json.dumps({"code": 0, "data": {"ok": 1}}).encode())
    with mock.patch.object(tiktok_client.urllib.request, "urlopen", return_value=resp) as m:
        assert c.request("GET", "/order/202309/orders", {"ids": "1"}) == {"ok": 1}
    req = m.call_args[0][0]
    assert req.full_url.startswith("https://open-api.tiktokglobalshop.com/order/202309/orders?")
    assert "shop_cipher=CIF" in req.full_url and "sign=" in req.full_url and "app_key=K" in req.full_url
    assert req.get_header("X-tts-access-token") == "VELHO" and req.data is None


if __name__ == "__main__":
    test_sign()
    test_refresh_quando_perto_de_expirar()
    test_sem_refresh_quando_valido()
    test_request_monta_url_e_header()
    print("ok")
