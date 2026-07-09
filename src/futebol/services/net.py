"""Utilidades de rede com proteção contra SSRF.

Usado sempre que o servidor faz requisições HTTP para URLs influenciadas por
usuários (importação de fontes por URL, chamadas a providers de IA). Bloqueia
acesso a endereços internos (loopback, privados, link-local, metadata de nuvem)
e revalida a cada redirect.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse
import urllib.request


class UnsafeURLError(ValueError):
    """URL recusada por apontar para host inválido ou endereço interno."""


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def ensure_public_http_url(url: str) -> urllib.parse.ParseResult:
    """Valida esquema/host e recusa URLs que resolvam para endereços internos.

    Resolve TODOS os endereços do host (IPv4 e IPv6); se qualquer um cair em
    faixa interna, a URL é recusada (evita rebinding parcial). Levanta
    ``UnsafeURLError`` quando insegura.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        raise UnsafeURLError('Somente URLs http ou https são permitidas.')
    host = parsed.hostname
    if not host:
        raise UnsafeURLError('URL sem host válido.')

    # Host literal em IP: valida direto.
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        if _is_blocked_ip(literal_ip):
            raise UnsafeURLError(f'Acesso a endereço interno não é permitido: {host}')
        return parsed

    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f'Não foi possível resolver o host: {host}') from exc

    for info in infos:
        address = info[4][0]
        ip = ipaddress.ip_address(address)
        if _is_blocked_ip(ip):
            raise UnsafeURLError(f'O host {host} resolve para um endereço interno ({address}).')
    return parsed


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Revalida o destino de cada redirect com ``ensure_public_http_url``."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        ensure_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(SafeRedirectHandler)


def safe_urlopen(request: urllib.request.Request | str, *, timeout: float = 45):
    """Abre a requisição só depois de validar a URL (e cada redirect).

    Aceita um ``Request`` ou string de URL. Levanta ``UnsafeURLError`` se a URL
    (ou qualquer redirect) apontar para endereço interno.
    """
    url = request.full_url if isinstance(request, urllib.request.Request) else request
    ensure_public_http_url(url)
    return _opener.open(request, timeout=timeout)
