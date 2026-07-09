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

- Modelo: DeepSeek V4 Flash (OpenCode Go)
- Orquestrador: Python 3
- Notificações: Evolution API (WhatsApp)

## Fontes de IA / atualização automática

O projeto mantém as fontes de conhecimento do agente como registros persistidos em `KnowledgeSource`, com URLs rastreáveis e vínculo ao agente principal.

### Como sincronizar manualmente

```bash
make sync-ai-sources
```

### Como deixar automático

```bash
make watch-ai-sources
```

Esse watcher:
- monta o Segundo Cérebro em `/vault` dentro do container;
- monitora mudanças em:
  - `Areas/CBF Academy`
  - `📚 Relatórios`
  - `🚀 Projetos`
  - `docs/`
  - `orchestrator/reports/`
- reexecuta a importação quando encontra alterações.

### O que o sync faz

- cria fontes novas;
- atualiza fontes existentes;
- religa o agente às fontes;
- mantém os dados alinhados com o Segundo Cérebro e as fontes de referência do sistema.

### Dependência do vault local

Por padrão, o serviço `ai-sync` monta:

```bash
/Users/alexvieira/segundo-cerebro:/vault:ro
```

Se o vault estiver em outro caminho, ajuste a variável:

```bash
SECOND_CEREBRO_ROOT=/caminho/para/segundo-cerebro
```
