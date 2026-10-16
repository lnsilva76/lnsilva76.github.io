import json
import time

import tiktok_tools as t

AGORA = int(time.time())


def msg(tipo, conteudo, role="BUYER", atraso=0):
    return {"type": tipo, "content": json.dumps(conteudo), "sender": {"role": role}, "create_time": AGORA - atraso}


class FakeClient:
    def __init__(self, rotas):
        self.rotas, self.chamadas = rotas, []

    def request(self, method, path, params=None, body=None):
        self.chamadas.append((method, path, params, body))
        return self.rotas[path]


def test_buscar_reclamacoes():
    c = FakeClient({
        "/customer_service/202309/conversations": {"conversations": [
            {"id": "c1", "latest_message": {"create_time": AGORA}, "participants": [{"role": "BUYER", "nickname": "Ana"}]},
            {"id": "c2", "latest_message": {"create_time": AGORA - 30 * 86400}},  # fora da janela
        ]},
        "/customer_service/202309/conversations/c1/messages": {"messages": [
            msg("TEXT", {"content": "Faltou uma PEÇA no meu pedido"}),
            msg("TEXT", {"content": "veio 10 unidades, ok"}),
            msg("TEXT", {"content": "Não veio a tampa"}, role="SHOP"),
            msg("ORDER_CARD", {"order_id": "576000000000000001"}),
        ]},
    })
    r = t.buscar_reclamacoes_falta_item(c, 7)
    assert len(r) == 1, r
    assert r[0]["comprador"] == "Ana" and r[0]["pedidos"] == ["576000000000000001"] and "PEÇA" in r[0]["trecho"]
    assert all("c2" not in ch[1] for ch in c.chamadas)


def test_sem_pedido_identificado():
    c = FakeClient({
        "/customer_service/202309/conversations": {"conversations": [{"id": "c1", "latest_message": {"create_time": AGORA}}]},
        "/customer_service/202309/conversations/c1/messages": {"messages": [msg("TEXT", {"content": "só veio um"})]},
    })
    assert t.buscar_reclamacoes_falta_item(c, 7)[0]["pedidos"] == "sem pedido identificado"


def test_detalhe_pedido_agrupa_itens():
    li = {"sku_id": "s1", "product_name": "Kit", "sku_name": "Azul", "seller_sku": "K-AZ"}
    c = FakeClient({"/order/202309/orders": {"orders": [{"id": "1", "status": "DELIVERED", "line_items": [li, li]}]}})
    d = t.detalhe_pedido(c, "1")
    assert d["itens"] == [{"produto": "Kit", "variacao": "Azul", "sku": "K-AZ", "quantidade": 2}]


def test_devolucoes_filtra_motivo():
    c = FakeClient({"/return_refund/202309/returns/search": {"return_orders": [
        {"return_id": "r1", "order_id": "1", "return_reason": "ecom_order_delivered_refund_reason_missing_item"},
        {"return_id": "r2", "order_id": "2", "return_reason_text": "Não gostei"},
    ]}})
    r = t.devolucoes_por_falta_item(c, 30)
    assert [d["devolucao_id"] for d in r["devolucoes"]] == ["r1"] and r["total_analisadas"] == 2
    assert c.chamadas[0][0] == "POST" and "create_time_ge" in c.chamadas[0][3]


def test_mensagens_conversa_cronologica():
    c = FakeClient({"/customer_service/202309/conversations/c1/messages": {"messages": [
        msg("TEXT", {"content": "segunda"}), msg("TEXT", {"content": "primeira"}, atraso=60)]}})
    assert [m["texto"] for m in t.mensagens_conversa(c, "c1")] == ["primeira", "segunda"]


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
    print("ok")
