# Runbook — Jornada de implantação e uso por perfil

Roteiro operacional e de venda da SaaS do Futebol, do go-live à operação diária.
Serve de narrativa verificável (issue épica #7) e acompanha o seed demonstrável
`seed_futebol_demo`.

> Preparar o ambiente de demonstração:
> ```
> python src/manage.py seed_futebol_demo --tenant avai --name "Avaí FC"
> ```
> O seed cria tenant com branding, módulos contratados, usuários por papel,
> clubes/pessoas/competição/partidas e a base de IA/fontes.

---

## 1. Fornecedor entrega (Administrador da plataforma)

**Quem:** operador da SaaS (`admin_plataforma` / superusuário).
**Objetivo:** preparar o tenant do clube e o primeiro acesso.

- Cria o tenant (nome, slug) — via `seed_futebol_demo` ou Django Admin.
- Define o plano: quais **Módulos Contratados** o clube adquiriu.
- Entrega as credenciais do primeiro responsável do clube.

O visitante sem acesso vê a **tela institucional** pública (`/`, view `landing`)
com proposta de valor, módulos e CTA de login. A tela de login (`/accounts/login/`)
é uma página pública, separada visualmente da área operacional.

## 2. Avaí entra (Primeiro responsável → onboarding)

**Quem:** primeiro usuário do clube (assume `admin_tenant`).
**Objetivo:** configurar o ambiente sem depender de suporte técnico.

- Ao logar sem tenant ativo, é redirecionado para o **Onboarding** (`/onboarding/`).
- Define **nome/slug**, **branding** (cores, logo, favicon, símbolo, títulos) e
  seleciona os **Módulos Contratados** — que passam a controlar o menu.
- Escolhe o **papel inicial** (papéis internos do tenant; `admin_plataforma` é
  reservado ao fornecedor).
- Ao concluir, fica vinculado ao tenant e cai no **painel** (`/painel/`).

## 3. Gestor administra (Administração do Tenant)

**Quem:** `admin_tenant` / `gestor_clube`.
**Objetivo:** manter o clube pós-onboarding sem Django Admin.

- Central única em **Administração do Tenant** (`/…`, view `tenant_admin`):
  usuários, papéis, status de vínculo, **módulos ativos/inativos** e **prévia de
  branding**.
- Cria usuários e edita perfil/vínculo/papel.
- Altera **branding** e **módulos contratados** direto na central.
- Quando o módulo **IA** está contratado, a central oferece atalhos para
  **providers, agentes e fontes**.
- Governança operacional: dashboard, **Solicitações/Fluxos de Aprovação**,
  **Auditoria**, **Relatórios/BI**, competições e partidas — respeitando o
  isolamento por tenant e o acesso por papel (aprovador, auditor, gestor…).

## 4. Analista gera inteligência (IA e fontes)

**Quem:** `analista de desempenho`.
**Objetivo:** transformar fontes e dados em análise.

- Importa **fonte pública por URL** (título/resumo/conteúdo salvos no tenant).
- **Vincula fontes a um agente** e executa perguntas com resposta rastreável.
- Relaciona a IA com dados esportivos recentes (scouting/partidas).

## 5. Comissão técnica consome decisão (Previsões e alertas)

**Quem:** comissão técnica / `gestor_competicao`.
**Objetivo:** priorizar treino, escalação e preparação.

- **Central de previsões**: próximo adversário, tendência de performance e risco
  de suspensão, com as **fontes usadas** de forma rastreável.
- **Gatilhos de automação** geram alertas operacionais a partir de eventos.

---

## Acesso por módulo contratado

O menu lateral mostra **apenas** os módulos contratados (o módulo base
**Operação** é sempre preservado). Acesso direto a uma URL de módulo não
contratado retorna a tela **"Módulo não contratado"**. Novos módulos podem ser
contratados/ativados depois na Administração do Tenant.

## Cobertura de testes

A narrativa é coberta ponta a ponta em `src/futebol/tests.py`:

| Etapa | Testes |
|---|---|
| Institucional / login / onboarding | `WhiteLabelPhase1Tests`, `PublicLoginJourneyTests` |
| Módulos contratados (menu + bloqueio) | `WhiteLabelModuleGatingTests` |
| Administração do tenant | `TenantAdminSprint2Tests` |
| IA e fontes | `AIFeatureTests`, `Sprint12ScoutingTests` |
| Governança / relatórios | `Sprint6GovernanceTests`, `Sprint8ReportingTests`, `Sprint10BiCenterTests` |
| Previsões e alertas | `RemainingPrdSprintTests` |
| Seed do piloto Avaí | `RemainingPrdSprintTests.test_avai_pilot_seed_creates_branded_tenant_and_modules` |
| Performance básica (nº de queries) | `MainPagesPerformanceTests` |
