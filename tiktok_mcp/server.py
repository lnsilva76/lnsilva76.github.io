"""Servidor MCP (stdio, somente leitura) da loja TikTok Shop da ELD Imports."""
from mcp.server.fastmcp import FastMCP

import tiktok_tools as t
from tiktok_client import TikTokClient

mcp = FastMCP("tiktok-shop-eld")
_cliente = None


def cliente():
    global _cliente
    if _cliente is None:
        _cliente = TikTokClient()
    return _cliente


@mcp.tool()
def buscar_reclamacoes_falta_item(dias: int = 7) -> list[dict]:
    """Varre as conversas dos últimos `dias` atrás de reclamações de item faltando
    ("faltou", "veio faltando", "só veio", "não veio", "incompleto", "falta peça", "veio 1").
    Retorna conversa, comprador, data, trecho e nº do pedido citado na conversa (ou "sem pedido identificado")."""
    return t.buscar_reclamacoes_falta_item(cliente(), dias)


@mcp.tool()
def detalhe_pedido(order_id: str) -> dict:
    """Detalhe de um pedido: status, datas de envio/entrega, rastreio e itens com SKU e quantidade."""
    return t.detalhe_pedido(cliente(), order_id)


@mcp.tool()
def mensagens_conversa(conversa_id: str) -> list[dict]:
    """Histórico completo de uma conversa do chat, em ordem cronológica. Não marca como lida."""
    return t.mensagens_conversa(cliente(), conversa_id)


@mcp.tool()
def devolucoes_por_falta_item(dias: int = 30) -> dict:
    """Devoluções/reembolsos dos últimos `dias` cujo motivo indica item faltante.
    Também lista todos os motivos vistos, para conferir os códigos usados no Brasil."""
    return t.devolucoes_por_falta_item(cliente(), dias)


if __name__ == "__main__":
    mcp.run()
