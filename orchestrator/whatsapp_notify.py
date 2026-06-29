#!/usr/bin/env python3
"""Notificações WhatsApp via Evolution API para o orquestrador da SaaS do Futebol."""

import json
import os
import urllib.request

API_URL = os.environ.get("EVOLUTION_API_BASE_URL", "http://192.168.1.152:8080")
API_KEY = os.environ.get("AUTHENTICATION_API_KEY", "")
INSTANCE = "Alex"

def _get_owner_number():
    """Busca o ownerJid da instância para garantir o número correto."""
    req = urllib.request.Request(
        f"{API_URL}/instance/fetchInstances",
        headers={"apikey": API_KEY},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    if isinstance(data, list):
        for inst in data:
            if inst.get("name") == INSTANCE:
                jid = inst.get("ownerJid", "")
                if jid:
                    return jid.replace("@s.whatsapp.net", "")
    return None

def send_whatsapp(text):
    """Envia mensagem de texto para o WhatsApp pessoal do Alex."""
    number = _get_owner_number()
    if not number:
        print(f"[WhatsApp] Não foi possível resolver o número da instância {INSTANCE}")
        return False
    payload = json.dumps({"number": number, "text": text})
    req = urllib.request.Request(
        f"{API_URL}/message/sendText/{INSTANCE}",
        data=payload.encode(),
        headers={"Content-Type": "application/json", "apikey": API_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            key = result.get("key", {})
            print(f"[WhatsApp] Mensagem enviada — ID: {key.get('id', 'unknown')}")
            return True
    except Exception as e:
        print(f"[WhatsApp] Erro: {e}")
        return False

def notify_subtask_done(subtask_id, subtask_name, sprint_name, report_path):
    msg = f"""✅ *Subtask concluída*

*Sprint:* {sprint_name}
*Subtask:* {subtask_id} — {subtask_name}
*Relatório:* {report_path}

O orquestrador continua executando..."""
    return send_whatsapp(msg)

def notify_review_needed(subtask_id, subtask_name, sprint_name, report_path):
    msg = f"""⚠️ *REVISÃO NECESSÁRIA — Orquestrador pausado*

*Sprint:* {sprint_name}
*Subtask:* {subtask_id} — {subtask_name}
*Relatório:* {report_path}

Para aprovar, responda no Slack com:
`python3 orchestrator/runner.py --approve {subtask_id}`

Ou diga "aprovar {subtask_id}" que eu executo aqui."""
    return send_whatsapp(msg)

def notify_sprint_done(sprint_name, summary):
    msg = f"""🏁 *Sprint concluída*

*Sprint:* {sprint_name}

{summary}

Próxima sprint iniciando..."""
    return send_whatsapp(msg)

def notify_all_done(report_path):
    msg = f"""🎉 *Implementação concluída!*

Todas as 7 sprints foram executadas.
Relatório técnico consolidado: {report_path}"""
    return send_whatsapp(msg)

if __name__ == "__main__":
    send_whatsapp("🧪 Teste: orquestrador SaaS do Futebol conectado ao WhatsApp!")