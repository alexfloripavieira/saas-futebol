#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

DEFAULT_INTERVAL_SECONDS = 300
WATCHED_RELATIVE_ROOTS = (
    'docs',
    'orchestrator/reports',
)
WATCHED_VAULT_ROOTS = (
    'Areas/CBF Academy',
    '📚 Relatórios',
    '🚀 Projetos',
)
WATCHED_EXTENSIONS = {'.md', '.txt', '.csv', '.json', '.yaml', '.yml'}


def iter_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        if path.name.startswith('.'):
            continue
        if path.suffix and path.suffix.lower() not in WATCHED_EXTENSIONS:
            continue
        yield path


def signature(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        digest.update(path.as_posix().encode('utf-8'))
        digest.update(str(stat.st_mtime_ns).encode('utf-8'))
        digest.update(str(stat.st_size).encode('utf-8'))
    return digest.hexdigest()


def watched_paths(project_root: Path, vault_root: Path | None) -> list[Path]:
    paths: list[Path] = []
    for relative in WATCHED_RELATIVE_ROOTS:
        candidate = project_root / relative
        if candidate.exists():
            paths.append(candidate)
    if vault_root is not None and vault_root.exists():
        for relative in WATCHED_VAULT_ROOTS:
            candidate = vault_root / relative
            if candidate.exists():
                paths.append(candidate)
    return paths


def run_sync(project_root: Path, tenant: str, vault_root: Path | None, seed_agent: bool) -> int:
    cmd = [
        sys.executable,
        'src/manage.py',
        'import_ai_sources',
        '--tenant',
        tenant,
        '--root',
        str(project_root),
    ]
    if vault_root is not None and vault_root.exists():
        cmd.extend(['--vault-root', str(vault_root)])
    if seed_agent:
        cmd.append('--seed-agent')

    print(f'[ai-sync] executando: {" ".join(cmd)}', flush=True)
    completed = subprocess.run(cmd, cwd=project_root)
    if completed.returncode != 0:
        print(f'[ai-sync] falha ao sincronizar (exit={completed.returncode})', flush=True)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description='Sincroniza fontes de IA quando o vault ou docs mudarem.')
    parser.add_argument('--tenant', default=os.getenv('AI_SYNC_TENANT', 'demo-local'))
    parser.add_argument('--project-root', default=os.getenv('AI_SYNC_PROJECT_ROOT', '/app'))
    parser.add_argument('--vault-root', default=os.getenv('AI_SYNC_VAULT_ROOT', '/vault'))
    parser.add_argument('--interval', type=int, default=int(os.getenv('AI_SYNC_INTERVAL_SECONDS', str(DEFAULT_INTERVAL_SECONDS))))
    parser.add_argument('--seed-agent', action='store_true', default=os.getenv('AI_SYNC_SEED_AGENT', '1') not in {'0', 'false', 'False'})
    parser.add_argument('--once', action='store_true', help='Executa uma sincronização e encerra.')
    args = parser.parse_args()

    project_root = Path(args.project_root)
    vault_root = Path(args.vault_root) if args.vault_root else None

    if not project_root.exists():
        print(f'[ai-sync] project root inexistente: {project_root}', flush=True)
        return 2
    if vault_root is not None and not vault_root.exists():
        print(f'[ai-sync] vault root indisponível: {vault_root} (continuando apenas com o projeto)', flush=True)
        vault_root = None

    last_signature = None
    while True:
        paths = watched_paths(project_root, vault_root)
        current_signature = signature(file for path in paths for file in iter_files(path))
        if current_signature != last_signature:
            status = run_sync(project_root, args.tenant, vault_root, args.seed_agent)
            if status == 0:
                last_signature = current_signature
        if args.once:
            return 0 if last_signature is not None else 1
        time.sleep(max(15, args.interval))


if __name__ == '__main__':
    raise SystemExit(main())
