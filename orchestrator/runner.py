#!/usr/bin/env python3
"""
Orquestrador da SaaS do Futebol — Loop de execução de sprints via OpenCode CLI (GLM 5.2).

Usage:
    python3 orchestrator/runner.py                # executa próximo subtask pendente
    python3 orchestrator/runner.py --loop          # executa em loop até bloquear
    python3 orchestrator/runner.py --status        # mostra status atual
    python3 orchestrator/runner.py --review        # lista subtasks aguardando revisão
    python3 orchestrator/runner.py --approve <id>   # aprova subtask aguardando revisão
    python3 orchestrator/runner.py --report        # gera relatório técnico consolidado
"""

import json
import os
import shutil
import subprocess
import sys
import argparse
from datetime import datetime
from pathlib import Path

# WhatsApp integration
sys.path.insert(0, str(Path(__file__).resolve().parent))
from whatsapp_notify import notify_subtask_done, notify_review_needed, notify_sprint_done, notify_all_done, send_whatsapp

ROOT = Path(__file__).resolve().parent.parent
ORCH = ROOT / "orchestrator"
SPRINTS_FILE = ORCH / "sprints.json"
STATE_FILE = ORCH / "state" / "execution_state.json"
REPORTS_DIR = ORCH / "reports"
PROMPTS_DIR = ORCH / "prompts"
MODEL = "opencode-go/deepseek-v4-flash"

# ─── State helpers ─────────────────────────────────────────────────────────

def load_sprints():
    with open(SPRINTS_FILE) as f:
        return json.load(f)

def load_state():
    with open(STATE_FILE) as f:
        return json.load(f)

def save_state(state):
    state["last_updated"] = datetime.now().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def now():
    return datetime.now().isoformat()

# ─── Subtask discovery ─────────────────────────────────────────────────────

def find_next_pending(sprints, state):
    """Encontra a próxima subtask pendente respeitando a ordem."""
    for sprint in sprints["sprints"]:
        for task in sprint["tasks"]:
            for sub in task["subtasks"]:
                if sub["status"] == "pending":
                    return {
                        "sprint_idx": sprints["sprints"].index(sprint),
                        "sprint_id": sprint["id"],
                        "sprint_name": sprint["name"],
                        "task_id": task["id"],
                        "task_name": task["name"],
                        "subtask_id": sub["id"],
                        "subtask_name": sub["name"],
                        "needs_review": sub.get("needs_review", False),
                    }
    return None

def get_sprint_context(sprints, sprint_idx):
    """Retorna contexto acumulado da sprint atual."""
    sprint = sprints["sprints"][sprint_idx]
    completed = []
    for task in sprint["tasks"]:
        for sub in task["subtasks"]:
            if sub["status"] == "completed":
                completed.append(f"  ✓ {sub['id']} — {sub['name']}")
    if completed:
        return "Subtasks já concluídas nesta sprint:\n" + "\n".join(completed)
    return "Primeira subtask da sprint."

# ─── Prompt builder ────────────────────────────────────────────────────────

def build_prompt(sprints, info, state):
    sprint_ctx = get_sprint_context(sprints, info["sprint_idx"])
    prompt = f"""Contexto: Sprint {info['sprint_name']} — Task {info['task_name']}
Subtask: {info['subtask_id']} — {info['subtask_name']}

{sprint_ctx}

Objetivo:
Gere o conteúdo técnico necessário para esta subtask da SaaS de futebol.

Domínio: SaaS de futebol — gestão de operações, cadastros, fluxos de aprovação, dashboards e relatórios.

Instruções:
1. Gere documentação técnica ou código em PT-BR.
2. Seja específico e objetivo — não use placeholder.
3. Mantenha consistência com o que já foi produzido nesta sprint.
4. Salve o resultado em orchestrator/reports/{info['sprint_id']}_subtask_{info['subtask_id']}.md
5. Não invente funcionalidades fora do escopo da subtask.
"""
    return prompt

# ─── OpenCode execution ────────────────────────────────────────────────────

def _find_opencode_binary():
    candidates = [
        shutil.which("opencode"),
        shutil.which("opencode-go"),
        str(Path.home() / ".opencode" / "bin" / "opencode"),
        "/root/.opencode/bin/opencode",
        "/Users/alexvieira/.opencode/bin/opencode",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("OpenCode CLI não encontrado no PATH nem nos caminhos padrão.")


def run_opencode(prompt, timeout=900):
    """Executa uma subtask via opencode CLI em modo one-shot."""
    binary = _find_opencode_binary()
    cmd = [
        binary, "run", prompt,
        "--model", MODEL,
        "-f", str(SPRINTS_FILE),
    ]
    print(f"  → Executando: {binary} run --model {MODEL} ...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ROOT),
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout após {}s".format(timeout), -1

# ─── Mark subtask ──────────────────────────────────────────────────────────

def update_subtask_status(sprints, sprint_idx, task_id, subtask_id, status):
    for task in sprints["sprints"][sprint_idx]["tasks"]:
        if task["id"] == task_id:
            for sub in task["subtasks"]:
                if sub["id"] == subtask_id:
                    sub["status"] = status
                    return True
    return False

def update_task_status(sprints, sprint_idx, task_id):
    sprint = sprints["sprints"][sprint_idx]
    for task in sprint["tasks"]:
        if task["id"] == task_id:
            all_done = all(s["status"] == "completed" for s in task["subtasks"])
            any_failed = any(s["status"] == "failed" for s in task["subtasks"])
            if all_done:
                task["status"] = "completed"
            elif any_failed:
                task["status"] = "blocked"
            else:
                task["status"] = "in_progress"

def update_sprint_status(sprints, sprint_idx):
    sprint = sprints["sprints"][sprint_idx]
    all_tasks_done = all(t["status"] == "completed" for t in sprint["tasks"])
    if all_tasks_done:
        sprint["status"] = "completed"

def save_sprints(sprints):
    with open(SPRINTS_FILE, "w") as f:
        json.dump(sprints, f, indent=2, ensure_ascii=False)

# ─── Execution ─────────────────────────────────────────────────────────────

def execute_one(sprints, state):
    info = find_next_pending(sprints, state)
    if not info:
        print("✅ Todas as subtasks foram concluídas!")
        return "done"

    print(f"\n{'='*60}")
    print(f"Sprint: {info['sprint_name']}")
    print(f"Task:   {info['task_name']}")
    print(f"Subtask: {info['subtask_id']} — {info['subtask_name']}")
    print(f"Needs review: {'SIM ⚠️' if info['needs_review'] else 'não'}")
    print(f"{'='*60}\n")

    # Atualizar estado
    state["current_sprint"] = info["sprint_idx"]
    state["current_task"] = info["task_id"]
    state["current_subtask"] = info["subtask_id"]
    state["status"] = "running"
    if not state["started_at"]:
        state["started_at"] = now()
    save_state(state)

    # Marcar subtask como in_progress
    update_subtask_status(sprints, info["sprint_idx"], info["task_id"], info["subtask_id"], "in_progress")
    update_task_status(sprints, info["sprint_idx"], info["task_id"])
    save_sprints(sprints)

    # Construir prompt e executar
    prompt = build_prompt(sprints, info, state)
    stdout, stderr, rc = run_opencode(prompt)

    # Salvar output
    report_path = REPORTS_DIR / f"{info['sprint_id']}_subtask_{info['subtask_id']}.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write(f"# Subtask {info['subtask_id']} — {info['subtask_name']}\n\n")
        f.write(f"**Sprint:** {info['sprint_name']}\n")
        f.write(f"**Task:** {info['task_name']}\n")
        f.write(f"**Status:** completed\n")
        f.write(f"**Timestamp:** {now()}\n\n")
        f.write("---\n\n")
        f.write("## Output do OpenCode (GLM 5.2)\n\n")
        f.write(stdout if stdout else "(sem output)")
        if stderr:
            f.write(f"\n\n## Stderr\n\n```\n{stderr}\n```")

    # Verificar sucesso
    if rc == 0:
        update_subtask_status(sprints, info["sprint_idx"], info["task_id"], info["subtask_id"], "completed")
        state["history"].append({
            "subtask_id": info["subtask_id"],
            "subtask_name": info["subtask_name"],
            "sprint": info["sprint_name"],
            "timestamp": now(),
            "report": str(report_path),
        })

        # Se precisa revisão
        if info["needs_review"]:
            state["review_queue"].append(info["subtask_id"])
            state["status"] = "blocked"
            save_state(state)
            update_task_status(sprints, info["sprint_idx"], info["task_id"])
            save_sprints(sprints)
            print(f"\n⚠️  SUBTASK {info['subtask_id']} AGUARDA SUA REVISÃO!")
            print(f"   Relatório: {report_path}")
            print(f"   Para aprovar: python3 orchestrator/runner.py --approve {info['subtask_id']}")
            notify_review_needed(info["subtask_id"], info["subtask_name"], info["sprint_name"], str(report_path))
            return "blocked"
        else:
            save_state(state)
            update_task_status(sprints, info["sprint_idx"], info["task_id"])
            update_sprint_status(sprints, info["sprint_idx"])
            save_sprints(sprints)
            print(f"\n✅ Subtask {info['subtask_id']} concluída!")
            notify_subtask_done(info["subtask_id"], info["subtask_name"], info["sprint_name"], str(report_path))
            if sprints["sprints"][info["sprint_idx"]]["status"] == "completed":
                sprint_name = sprints["sprints"][info["sprint_idx"]]["name"]
                summary = f"Sprint finalizada. Total acumulado: {len(state['history'])} subtasks."
                notify_sprint_done(sprint_name, summary)
            return "completed"
    else:
        update_subtask_status(sprints, info["sprint_idx"], info["task_id"], info["subtask_id"], "failed")
        state["failures"][info["subtask_id"]] = state["failures"].get(info["subtask_id"], 0) + 1
        save_state(state)
        update_task_status(sprints, info["sprint_idx"], info["task_id"])
        save_sprints(sprints)
        print(f"\n❌ Subtask {info['subtask_id']} FALHOU (rc={rc})")
        print(f"   Stderr: {stderr[:200]}")
        return "failed"

def approve_subtask(sprints, state, subtask_id):
    """Aprova uma subtask que estava aguardando revisão."""
    if subtask_id in state["review_queue"]:
        state["review_queue"].remove(subtask_id)
        state["status"] = "pending"
        save_state(state)
        print(f"✅ Subtask {subtask_id} aprovada! Continuando execução...")
    else:
        print(f"❌ Subtask {subtask_id} não está na fila de revisão.")

def show_status(sprints, state):
    print(f"\n{'='*60}")
    print(f"STATUS DA EXECUÇÃO — SaaS do Futebol")
    print(f"{'='*60}")
    print(f"Status:     {state['status']}")
    print(f"Sprint:     {state['current_sprint']}")
    print(f"Task:       {state['current_task']}")
    print(f"Subtask:    {state['current_subtask']}")
    print(f"Iniciado:   {state['started_at']}")
    print(f"Atualizado: {state['last_updated']}")
    print(f"{'='*60}")

    if state["review_queue"]:
        print(f"\n⚠️  AGUARDANDO REVISÃO ({len(state['review_queue'])}):")
        for sid in state["review_queue"]:
            print(f"   - {sid}")

    if state["failures"]:
        print(f"\n❌ FALHAS:")
        for sid, count in state["failures"].items():
            print(f"   - {sid}: {count}x")

    print(f"\nProgresso:")
    for i, sprint in enumerate(sprints["sprints"]):
        total_sub = sum(len(t["subtasks"]) for t in sprint["tasks"])
        done_sub = sum(
            1 for t in sprint["tasks"] for s in t["subtasks"]
            if s["status"] == "completed"
        )
        pct = (done_sub / total_sub * 100) if total_sub else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "blocked": "🚫"}.get(sprint["status"], "❓")
        print(f"  {status_icon} {sprint['name'][:40]:<40} [{bar}] {done_sub}/{total_sub}")

def generate_report(sprints, state):
    report_path = ORCH / "reports" / "relatorio_tecnico_consolidado.md"
    with open(report_path, "w") as f:
        f.write("# Relatório Técnico Consolidado — SaaS do Futebol\n\n")
        f.write(f"**Gerado em:** {now()}\n")
        f.write(f"**Modelo:** {MODEL}\n\n")
        f.write("---\n\n")

        f.write("## Resumo Executivo\n\n")
        total_sub = sum(len(t["subtasks"]) for s in sprints["sprints"] for t in s["tasks"])
        done_sub = sum(1 for s in sprints["sprints"] for t in s["tasks"] for sub in t["subtasks"] if sub["status"] == "completed")
        f.write(f"- Total de subtasks: {total_sub}\n")
        f.write(f"- Concluídas: {done_sub}\n")
        f.write(f"- Pendentes: {total_sub - done_sub}\n")
        f.write(f"- Fila de revisão: {len(state['review_queue'])}\n\n")

        f.write("## Status por Sprint\n\n")
        for sprint in sprints["sprints"]:
            f.write(f"### {sprint['name']}\n\n")
            f.write(f"**Status:** {sprint['status']}\n\n")
            for task in sprint["tasks"]:
                f.write(f"#### Task {task['id']} — {task['name']}\n\n")
                f.write("| Subtask | Status | Review? |\n")
                f.write("|---------|--------|--------|\n")
                for sub in task["subtasks"]:
                    review = "⚠️" if sub.get("needs_review") else ""
                    f.write(f"| {sub['id']} — {sub['name']} | {sub['status']} | {review} |\n")
                f.write("\n")

        f.write("---\n\n")
        f.write("## Histórico de Execução\n\n")
        for h in state["history"]:
            f.write(f"- **{h['subtask_id']}** — {h['subtask_name']} ({h['sprint']}) — {h['timestamp']}\n")
            f.write(f"  Relatório: `{h['report']}`\n")

    print(f"✅ Relatório salvo em: {report_path}")
    return str(report_path)

# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Orquestrador SaaS Futebol")
    parser.add_argument("--loop", action="store_true", help="Executa em loop até bloquear")
    parser.add_argument("--status", action="store_true", help="Mostra status atual")
    parser.add_argument("--review", action="store_true", help="Lista subtasks aguardando revisão")
    parser.add_argument("--approve", type=str, help="Aprova subtask (ID ex: 0.1.3)")
    parser.add_argument("--report", action="store_true", help="Gera relatório técnico consolidado")
    args = parser.parse_args()

    sprints = load_sprints()
    state = load_state()

    if args.status:
        show_status(sprints, state)
        return
    if args.review:
        if state["review_queue"]:
            print("Subtasks aguardando revisão:")
            for sid in state["review_queue"]:
                print(f"  - {sid}")
        else:
            print("Nenhuma subtask aguardando revisão.")
        return
    if args.approve:
        approve_subtask(sprints, state, args.approve)
        return
    if args.report:
        generate_report(sprints, state)
        return

    if args.loop:
        while True:
            result = execute_one(sprints, state)
            sprints = load_sprints()
            state = load_state()
            if result in ("blocked", "failed", "done"):
                break
        if result == "done":
            report = generate_report(sprints, state)
            notify_all_done(report)
        show_status(sprints, state)
    else:
        execute_one(sprints, state)
        show_status(sprints, state)

if __name__ == "__main__":
    main()