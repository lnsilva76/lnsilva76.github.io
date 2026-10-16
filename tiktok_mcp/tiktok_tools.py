"""Lógica das ferramentas MCP (somente leitura). Fica separada do server.py para ser testável sem o pacote mcp."""
import json
import re
import time
import unicodedata
from datetime import datetime

TERMOS_FALTA = ["faltou", "veio faltando", "so veio", "nao veio", "incompleto", "falta peca", "veio 1"]
RE_FALTA = re.compile(r"\b(" + "|".join(map(re.escape, TERMOS_FALTA)) + r")\b")
RE_MOTIVO_FALTA = re.compile(r"missing|falt|incomplet")  # ponytail: códigos de motivo do Brasil não confirmados; ver "motivos_vistos"
RE_PEDIDO = re.compile(r"\b\d{15,20}\b")
MAX_PAGINAS = 50  # ponytail: teto de paginação por varredura; aumentar se a loja tiver muito volume


def normalizar(texto):
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def segundos(ts):
    return ts / 1000 if ts > 10**12 else ts


def data_br(ts):
    return datetime.fromtimestamp(segundos(ts)).strftime("%d/%m/%Y %H:%M") if ts else None


def conteudo(msg):
    try:
        c = json.loads(msg.get("content") or "{}")
    except ValueError:
        return {"content": msg.get("content")}
    return c if isinstance(c, dict) else {"content": str(c)}


def texto_msg(msg):
    c = conteudo(msg)
    if msg.get("type") == "TEXT":
        return c.get("content", "")
    if msg.get("type") == "ORDER_CARD":
        return f"[cartão do pedido {c.get('order_id')}]"
    return f"[{msg.get('type')}] {json.dumps(c, ensure_ascii=False)}"


def paginar(client, path, chave, params=None, method="GET", body=None):
    token = ""
    for _ in range(MAX_PAGINAS):
        data = client.request(method, path, {**(params or {}), **({"page_token": token} if token else {})}, body)
        yield from data.get(chave) or []
        token = data.get("next_page_token")
        if not token:
            return


def mensagens(client, conversa_id, desde=0):
    """Mensagens da mais nova para a mais antiga, parando ao passar de `desde`."""
    # sort_order/sort_field: confirmar na primeira chamada real que a API respeita DESC
    params = {"page_size": 10, "sort_order": "DESC", "sort_field": "create_time"}
    for m in paginar(client, f"/customer_service/202309/conversations/{conversa_id}/messages", "messages", params):
        if segundos(m.get("create_time", 0)) < desde:
            return
        yield m


def pedidos_citados(msgs):
    pedidos = set()
    for m in msgs:
        if m.get("type") == "ORDER_CARD" and conteudo(m).get("order_id"):
            pedidos.add(str(conteudo(m)["order_id"]))
        elif m.get("type") == "TEXT":
            pedidos.update(RE_PEDIDO.findall(texto_msg(m)))
    return sorted(pedidos)


def comprador(conv):
    for p in conv.get("participants") or []:
        if p.get("role") == "BUYER":
            return p.get("nickname")
    return None


def buscar_reclamacoes_falta_item(client, dias=7):
    corte = time.time() - max(1, int(dias)) * 86400
    resultados = []
    for conv in paginar(client, "/customer_service/202309/conversations", "conversations", {"page_size": 20}):
        if segundos((conv.get("latest_message") or {}).get("create_time", 0)) < corte:
            break  # conversas vêm da mais recente para a mais antiga
        msgs = list(mensagens(client, conv["id"], corte))
        pedidos = pedidos_citados(msgs) or "sem pedido identificado"
        for m in msgs:
            texto = texto_msg(m) if m.get("type") == "TEXT" else ""
            if (m.get("sender") or {}).get("role", "BUYER") == "BUYER" and RE_FALTA.search(normalizar(texto)):
                resultados.append({"conversa_id": conv["id"], "comprador": comprador(conv), "data": data_br(m.get("create_time")),
                                   "trecho": texto[:300], "pedidos": pedidos})
    return resultados


def detalhe_pedido(client, order_id):
    pedidos = client.request("GET", "/order/202309/orders", {"ids": str(order_id)}).get("orders") or []
    if not pedidos:
        return {"erro": f"Pedido {order_id} não encontrado"}
    o = pedidos[0]
    itens = {}
    for li in o.get("line_items") or []:
        i = itens.setdefault(li.get("sku_id"), {"produto": li.get("product_name"), "variacao": li.get("sku_name"),
                                                "sku": li.get("seller_sku"), "quantidade": 0})
        i["quantidade"] += li.get("quantity", 1)  # na 202309 cada line_item costuma ser 1 unidade
    return {"pedido_id": o.get("id"), "status": o.get("status"), "criado_em": data_br(o.get("create_time")),
            "pronto_para_envio_em": data_br(o.get("rts_time")), "coletado_em": data_br(o.get("collection_time")),
            "entregue_em": data_br(o.get("delivery_time")), "transportadora": o.get("shipping_provider"),
            "rastreio": o.get("tracking_number"), "itens": list(itens.values())}


def mensagens_conversa(client, conversa_id):
    msgs = sorted(mensagens(client, conversa_id), key=lambda m: m.get("create_time", 0))
    return [{"data": data_br(m.get("create_time")), "remetente": (m.get("sender") or {}).get("role"),
             "tipo": m.get("type"), "texto": texto_msg(m)} for m in msgs]


def devolucoes_por_falta_item(client, dias=30):
    agora = int(time.time())
    body = {"create_time_ge": agora - max(1, int(dias)) * 86400, "create_time_lt": agora}
    devolucoes, motivos, total = [], set(), 0
    for r in paginar(client, "/return_refund/202309/returns/search", "return_orders", {"page_size": 50}, "POST", body):
        total += 1
        motivo = f"{r.get('return_reason') or ''} {r.get('return_reason_text') or ''}".strip()
        motivos.add(motivo)
        if RE_MOTIVO_FALTA.search(normalizar(motivo)):
            devolucoes.append({"devolucao_id": r.get("return_id"), "pedido_id": r.get("order_id"), "tipo": r.get("return_type"),
                               "status": r.get("return_status"), "motivo": motivo, "data": data_br(r.get("create_time")),
                               "itens": [f"{li.get('product_name')} ({li.get('sku_name')})" for li in r.get("return_line_items") or []]})
    return {"devolucoes": devolucoes, "total_analisadas": total, "motivos_vistos": sorted(motivos)}
