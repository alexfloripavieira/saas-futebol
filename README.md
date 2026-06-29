# SaaS do Futebol

SaaS para gestão de operações de futebol — cadastros, fluxos de aprovação, dashboards e relatórios.

## Status

Em desenvolvimento via orquestrador automático (OpenCode GLM 5.2).

## Estrutura

```
saas-futebol/
├── orchestrator/          # Orquestrador de sprints
│   ├── runner.py          # Loop de execução
│   ├── sprints.json       # Definição de sprints/tasks/subtasks
│   ├── whatsapp_notify.py # Notificações WhatsApp
│   ├── state/             # Estado de execução
│   ├── prompts/           # Prompts de sistema
│   └── reports/           # Output de cada subtask
├── docs/                  # Documentação (PRD, Tech Spec)
└── src/                   # Código-fonte
```

## Sprints

- Sprint 0: Fundação, escopo e contratos
- Sprint 1: Fundação da plataforma
- Sprint 2: Núcleo de dados do futebol
- Sprint 3: Fluxos operacionais
- Sprint 4: Interface de operação
- Sprint 5: Integrações, automações e IA
- Sprint 6: Segurança, qualidade e governança

## Tech Stack

- Modelo: GLM 5.2 (OpenCode Go)
- Orquestrador: Python 3
- Notificações: Evolution API (WhatsApp)
