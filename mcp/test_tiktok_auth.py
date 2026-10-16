import io
import json
import tempfile
from pathlib import Path
from unittest import mock

import tiktok_auth


def fake_urlopen(body):
    return mock.patch.object(tiktok_auth.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(body).encode()))


def test_troca_e_salva():
    data = {"access_token": "A", "refresh_token": "R", "access_token_expire_in": 1, "refresh_token_expire_in": 2}
    with fake_urlopen({"code": 0, "data": data}) as m:
        assert tiktok_auth.exchange_code("c0de", "k", "s") == data
    assert "auth_code=c0de" in m.call_args[0][0] and "grant_type=authorized_code" in m.call_args[0][0]

    path = Path(tempfile.mkdtemp()) / "sub" / "tokens.json"
    tiktok_auth.save_tokens(data, path)
    salvo = tiktok_auth.load_tokens(path)
    assert salvo["access_token"] == "A" and "obtido_em" in salvo


def test_erro_da_api():
    with fake_urlopen({"code": 36004004, "message": "invalid auth code"}):
        try:
            tiktok_auth.exchange_code("x", "k", "s")
        except RuntimeError as e:
            assert "36004004" in str(e)
        else:
            raise AssertionError("deveria falhar")


if __name__ == "__main__":
    test_troca_e_salva()
    test_erro_da_api()
    print("ok")
