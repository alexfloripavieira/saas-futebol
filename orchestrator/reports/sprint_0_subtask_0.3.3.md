# Subtask 0.3.3 — Descrever relacionamento entre entidades

**Sprint:** Fundação, escopo e contratos
**Task:** Mapear entidades
**Status:** completed
**Época:** 2026-06-28
**Modelo:** opencode-go/glm-5.2

---

## Output do OpenCode (GLM 5.2)

Documento técnico descrevendo os relacionamentos entre as 25 entidades (E-01 a E-25) definidas nas subtasks 0.3.1 e 0.3.2, organizadas em 7 grupos (A Organização/acesso, B Pessoas, C Estrutura esportiva, D Competições/partidas, E Mercado/vínculos, F Fluxos operacionais, G Governança/observabilidade).

---

# Relacionamentos entre entidades — SaaS de Futebol

## 1. Sumário executivo

Este documento descreve como as 25 entidades do modelo de dados do SaaS de futebol se relacionam, classificando cada vínculo em **1:1**, **1:N** ou **N:N** e especificando as **regras de dependência** que governam criação, edição, exclusão e propagação de estado. O modelo é **multi-tenant**: toda entidade de negócio carrega `tenant_id` e o isolamento lógico é garantido por Row-Level Security (RLS). Entidades transversais (grupos A e G) são **globais ou por tenant**, enquanto as demais são **sempre por tenant**.

Convenções adotadas:
- **Cardinalidade** usa notação `Pai → Filho`. O lado "1" é sempre o pai (FK ponteiro simples); o lado "N" é o filho que armazena a chave estrangeira.
- **N:N** sempre é materializada por uma **tabela de junção** nomeada `rel_<a>_<b>` (entidade de primeira classe, com `id`, `tenant_id`, timestamps e metadados).
- **Regras de dependência** são expressas em cinco categorias:
  - **Criação (C):** quando a entidade pode ser criada e quais pré-requisitos exige.
  - **Obrigatoriedade (O):** se o vínculo é obrigatório (`NOT NULL`) ou opcional.
  - **Orphan safety (OS):** o que acontece com o filho se o pai for excluído (`CASCADE`, `SET NULL`, `RESTRICT`).
  - **Integridade referencial cruzada (IRC):** invariantes que transcendem uma única FK (ex.: "participação em partida exige vínculo ativo").
  - **Propagação de estado (PE):** mudanças no pai que afetam filhos (ex.: desativação de clube invalida escalações).

---

## 2. Mapa rápido de cardinalidades

| # | Relacionamento | Cardinalidade | Tabela de junção |
|---|----------------|---------------|-------------------|
| R01 | Organização (tenant) ↔ Usuário | 1:N | — |
| R02 | Organização ↔ Plano/Assinatura | 1:1 | — |
| R03 | Usuário ↔ Papel (RBAC) | N:N | rel_usuario_papel |
| R04 | Clube ↔ Pessoa (membro de staff) | 1:N | — (via Contrato) |
| R05 | Pessoa ↔ Contrato (vínculo) | 1:N | — |
| R06 | Clube ↔ Contrato | 1:N | — |
| R07 | Contrato ↔ Clube (origem/destino) | N:N por cláusula | rel_contrato_clube |
| R08 | Clube ↔ Categoria/Equipe | 1:N | — |
| R09 | Equipe ↔ Atleta (convocação) | N:N | rel_equipe_atleta |
| R10 | Competição ↔ Edição (temporada) | 1:N | — |
| R11 | Edição ↔ Fase/Rodada | 1:N | — |
| R12 | Competição ↔ Clube participante | N:N | rel_edicao_clube |
| R13 | Partida ↔ Equipe mandante | N:1 | — |
| R14 | Partida ↔ Equipe visitante | N:1 | — |
| R15 | Partida ↔ Evento de partida | 1:N | — |
| R16 | Evento ↔ Atleta | N:1 | — |
| R17 | Partida ↔ Escalação (linha) | 1:N | — |
| R18 | Negociação/Transferência ↔ Contrato origem | 1:1 | — |
| R19 | Negociação ↔ Proposta | 1:N | — |
| R20 | Proposta ↔ Anexo/Evidência | 1:N | — |
| R21 | Fluxo de aprovação ↔ Solicitação | 1:N | — |
| R22 | Solicitação ↔ Aprovação | 1:N | — |
| R23 | Solicitação ↔ Entidade de negócio (polimórfica) | N:1 | `solicitacao.tipo_ref` + `id_ref` |
| R24 | Notificação ↔ Destinatário (Usuário) | N:N | rel_notificacao_usuario |
| R25 | Auditoria/Log ↔ Ator (Usuário) | N:1 | — |
| R26 | Auditoria ↔ Entidade alterada (polimórfica) | N:1 | `audit.entidade_tipo` + `entidade_id` |
| R27 | Log de integração ↔ Sistema externo | N:1 | — |

---

## 3. Detalhamento por grupo

### Grupo A — Organização e acesso

#### R01 — Organização → Usuário (1:N)
- **C:** O usuário só existe após a organização (tenant) existir. `tenant_id` é obrigatório.
- **O:** `tenant_id` NOT NULL em `usuario`.
- **OS:** `RESTRICT` — não é possível excluir organização com usuários ativos; exige soft-delete ou migração prévia.
- **IRC:** Todo usuário pertence a exatamente um tenant; não há usuário "órfão".
- **PE:** Suspensão do tenant (`status = suspenso`) invalida novas sessões, mas preserva registros para auditoria.

#### R02 — Organização ↔ Plano/Assinatura (1:1)
- **C:** A assinatura é criada junto à organização; urna única por tenant.
- **O:** `tenant_id` UNIQUE NOT NULL em `assinatura`. Há **exatamente uma** assinatura ativa por tenant em qualquer instante (constraint parcial `UNIQUE WHERE status = 'ativa'`).
- **OS:** `RESTRICT` — não excluir assinatura; mover para histórico (`status = 'expirada'`).
- **IRC:** Downgrade de plano deve respeitar limites de entidades (ex.: nº de clubes), validado transacionalmente.
- **PE:** Mudança de plano recalcula cotas e emite notificação.

#### R03 — Usuário ↔ Papel (N:N, `rel_usuario_papel`)
- **C:** A junção exige usuário e papel no mesmo tenant (RLS); `papel` pode ser global (sistema) ou por tenant.
- **O:** Obrigatório — usuário sem papel não pode operar; entretanto, papel pode ser concedido no primeiro login (onboarding).
- **OS:** `CASCADE` em `rel_usuario_papel` — excluir usuário remove ligações; excluir papel bloqueia se houver usuários ativos (`RESTRICT` configurável).
- **IRC:** Papéis de sistema (`admin_plataforma`) só podem ser atribuídos por outro admin; a regra é validada na camada de serviço, não como constraint.
- **PE:** Suspensão de usuário inativa todas as ligações de papel (`valido_ate = now()`).

---

### Grupo B — Pessoas

#### R04 / R05 / R06 — Clube ↔ Pessoa, via Contrato (1:N)
Implementado como **relacionamento indireto**: a Pessoa e o Clube não se tocam diretamente; o **Contrato** (E-11) é a única fonte verdade do vínculo, carregando ambas as FKs.

- **C:** Contrato exige `pessoa_id` e `clube_id` preexistentes; `data_inicio` ≤ hoje; `data_fim` ≥ `data_inicio` (se aplicável).
- **O:** Ambas as FKs NOT NULL.
- **OS:** `RESTRICT` — excluir Clube ou Pessoa com contrato ativo é proibido; exige rescisão formal antes.
- **IRC:** Em qualquer instante, uma Pessoa tem **no máximo um** Contrato ativo por Clube (constraint parcial `UNIQUE (pessoa_id, clube_id) WHERE status = 'ativo'`).
- **PE:** Rescisão (`status = 'rescindido'`) libera a Pessoa para novos vínculos e dispara notificação ao setor jurídico.

#### R07 — Contrato ↔ Clube (origem/destino em empréstimos) (N:N, `rel_contrato_clube`)
- **C:** Usada em cláusulas de empréstimo/troca; exige cláusula `tipo = 'movimentacao'`.
- **O:** Opcional — só presente em contratos com cláusula de movimentação.
- **OS:** `CASCADE` em junção; `RESTRICT` em contrato pai.
- **IRC:** O clube de destino não pode ser o mesmo de origem (check `clube_origem_id <> clube_destino_id`).
- **PE:** Encerrar empréstimo reverte cláusula para `encerrada` e restaura vínculo ativo com o clube de origem.

#### R08 — Clube → Categoria/Equipe (1:N)
- **C:** Equipe exige clube; `categoria` (ex.: Sub-20, Profissional) referenciada por enum supervisionado.
- **O:** `clube_id` NOT NULL.
- **OS:** `CASCADE` controlado — excluir Clube remove Equipes **após** confirmação de não haver partidas associadas; otherwise `RESTRICT`.
- **IRC:** Dentro de um Clube, o par `(categoria, genero)` é UNIQUE.
- **PE:** Arquivar Clube (`status = 'arquivado'`) torna Equipes indisponíveis para novas competições.

#### R09 — Equipe ↔ Atleta (N:N, `rel_equipe_atleta`)
- **C:** Exige Contrato ativo entre o Atleta (Pessoa com `tipo = 'atleta'`) e o Clube dono da Equipe.
- **O:** Vínculo opcional em Equipes de base, obrigatório para escalação em partida profissional.
- **OS:** `CASCADE` em junção (remover Equipe limpa ligações).
- **IRC:** Um Atleta pode estar em **no máximo uma** Equipe do mesmo Clube por categoria no mesmo período (`UNIQUE (atleta_id, equipe_id) WHERE dt_fim IS NULL`).
- **PE:** Rescisão de Contrato encerra automaticamente todos os vínculos `rel_equipe_atleta` ativos.

---

### Grupo C — Estrutura esportiva

(Entidades de estádio, centro de treinamento e instalações foram declaradas **não-objetivo** no MVP — N-12 a N-15. Os relacionamentos que as envolveriam estão marcados para Sprint 2+ como *futuro desejado* F-08 a F-11 e não constam do modelo atual.)

---

### Grupo D — Competições e partidas

#### R10 — Competição → Edição (1:N)
- **C:** A Edição (temporada) exige Competição mãe; `ano_temporada` validado.
- **O:** `competicao_id` NOT NULL.
- **OS:** `RESTRICT` — excluir Competição com Edições é proibido; deve-se arquivar (`status = 'encerrada'`).
- **IRC:** Dentro de uma Competição, a Edição é UNIQUE por `(competicao_id, ano_temporada, periodo)`.
- **PE:** Encerrar Edição (`status = 'encerrada'`) bloqueia novas partidas e dispara consolidação de classificação.

#### R11 — Edição → Fase/Rodada (1:N)
- **C:** Exige Edição; `ordem` é sequencial dentro da Edição.
- **O:** `edicao_id` NOT NULL.
- **OS:** `CASCADE` — excluir Edição remove Fases (apenas se não houver partidas disputadas).
- **IRC:** `ordem` UNIQUE dentro da Edição; transição de Fase segue máquina de estados (`rascunho → publicada → em_andamento → concluida`).
- **PE:** Concluir a última partida de uma Fase avança o estado automaticamente.

#### R12 — Edição ↔ Clube participante (N:N, `rel_edicao_clube`)
- **C:** Exige Edição em estado `publicada` ou anterior; exige Clube `ativo`.
- **O:** Obrigatório para montagem de tabela.
- **OS:** `RESTRICT` — excluir Clube em Edição em andamento é bloqueado.
- **IRC:** Número de participantes respeita `Competicao.limite_participantes`; inscrição além do limite é rejeitada.
- **PE:** Desistência de Clube (`dt_saida` preenchida) recalcula tabela e marca partidas futuras como `WO`.

#### R13 / R14 — Partida ↔ Equipe mandante/visitante (N:1 cada)
- **C:** Partida exige Edição + Fase + duas Equipes diferentes.
- **O:** Ambas as FKs NOT NULL.
- **OS:** `RESTRICT` — excluir Equipe com Partidas associadas (mesmo futuras) é bloqueado.
- **IRC:** `mandante_id <> visitante_id`; ambas as Equipes devem pertencer a Clubes inscritos na Edição (`rel_edicao_clube`).
- **PE:** Mudança de mandante exige reabertura da Partida (`status = 'rascunho'`).

#### R15 / R16 — Partida → Evento, Evento → Atleta (1:N, N:1)
- **C:**Evento exige Partida em estado `em_andamento` ou `concluida`; Atleta exigido apenas se `evento_tipo` requisitar jogador (gol, cartão, substituição). Eventos técnicos (início/fim, intervalo) prescindem de Atleta.
- **O:** `partida_id` NOT NULL; `atleta_id` NULL condicional.
- **OS:** `CASCADE` em eventos se Partida for reaberta (eventos são descartados e regravados).
- **IRC:** Atleta deve estar na Escalação da Partida para o time correspondente (`rel_partida_atleta`);"cris-cross"validado por trigger.
- **PE:** Gol / cartão recalculam placar e estatísticas; cartão vermelho bloqueia novos eventos do atleta.

#### R17 — Partida → Escalação (1:N)
- **C:** Escalação exige Partida `nao_iniciada` e Equipe inscrita.
- **O:** Obrigatório para iniciar a Partida.
- **OS:** `CASCADE` ao reabrir.
- **IRC:** 11 titulares + até N reservas (configurável por Regra de Competição); numeração de camisa UNIQUE por Partida/Equipe.
- **PE:** Escalação fechada (`status = 'confirmada'`) ao iniciar Partida; depois imutável.

---

### Grupo E — Mercado e vínculos

#### R18 — Negociação ↔ Contrato de origem (1:1)
- **C:** Negociação exige Contrato ativo pertencente ao Clube vendedor.
- **O:** `contrato_origem_id` UNIQUE NOT NULL.
- **OS:** `SET NULL` se Contrato for rescindido externamente; Negociação move-se para `cancelada`.
- **IRC:** O Clube vendedor deve ser parte ativa do Contrato de origem.

#### R19 — Negociação → Proposta (1:N)
- **C:** Exige Negociação aberta.
- **O:** Obrigatória (≥1 proposta para a Negociação fazer sentido, mas tecnicamente a tabela admite zero).
- **OS:** `CASCADE` em propostas rejeitadas; `RESTRICT` na proposta aceita (vide R20).
- **IRC:** Apenas uma proposta pode estar `aceita` por Negociação (`UNIQUE (negociacao_id) WHERE status = 'aceita'`).
- **PE:** Proposta aceita dispara geração de Contrato de destino e_workflow de aprovação.

#### R20 — Proposta → Anexo/Evidência (1:N)
- **C:** Anexável a Proposta em qualquer estado anterior a `aceita`.
- **O:** Opcional, mas Proposta `aceita` exige ≥1 evidência documental (check em trigger).
- **OS:** `CASCADE`.
- **IRC:** Mime-type e tamanho validados; assinatura digital é persistida como hash.

---

### Grupo F — Fluxos operacionais

#### R21 / R22 — Fluxo de aprovação → Solicitação → Aprovação (1:N → 1:N)
- **C:** Solicitação exige Fluxo ativo no tenant; Aprovação exige Solicitação `em_analise` e aprovação pendente para o papel do usuário.
- **O:** Todas NOT NULL.
- **OS:** `RESTRICT` na Solicitação enquanto houver Aprovação registrada; arquivamento em vez de exclusão.
- **IRC:** A ordem de aprovação respeita `etapa` dentro do Fluxo; não é possível aprovar etapa `N+1` enquanto `N` estiver pendente.
- **PE:** Última Aprovação `deferida` move Solicitação para `deferida` e publica efeito colateral (ex.: ativação de Contrato).

#### R23 — Solicitação ↔ Entidade de negócio (N:1, polimórfica)
- **C:**Exige `tipo_ref` (enum supervisionado) e `id_ref` válido dentro do mesmo `tenant_id`.
- **O:** NOT NULL; validação ocorre em trigger com lookup dinâmico por `tipo_ref`.
- **OS:** A exclusão da entidade referenciada move Solicitação para `anulada`.
- **IRC:** `tipo_ref` deve estar em lista permitida (Contrato, Negociação, Partida, Escalação, Inscrição em Edição).
- **PE:** Entidade muta de estado apenas quando Solicitação correspondente é `deferida`.

#### R24 — Notificação ↔ Destinatário (N:N, `rel_notificacao_usuario`)
- **C:** Notificação criada por trigger de negócio; destinatários resolvidos por regra de papel + escopo.
- **O:** Obrigatória (não há notificação sem destinatário).
- **OS:** `CASCADE` na junção; `RESTRICT` na Notificação pai (preservar trilha).
- **IRC:** `rel_notificacao_usuario` contém `lida_em`, `arquivada` — estado por usuário, não na Notificação.
- **PE:** Reenvio/resend controlado por `validade_ate`; expiradas são podadas por job.

---

### Grupo G — Governança e observabilidade

#### R25 — Auditoria/Log → Ator (Usuário) (N:1)
- **C:** Toda mutação mutável em entidade de negócio grava um registro de auditoria com `ator_id`.
- **O:** `ator_id` NULL permitido apenas para eventos de sistema (jobs, integrações); caso contrário NOT NULL.
- **OS:** `SET NULL` ao excluir Usuário — preserva trilha, sem órfão de integridade.
- **IRC:** Auditoria é **append-only**; Updates/deletes na tabela são proibidos por RBAC.
- **PE:** Nenhuma propagação — log é histórico passivo.

#### R26 — Auditoria ↔ Entidade alterada (N:1, polimórfica)
- **C:** `entidade_tipo` + `entidade_id` sempre presentes; serialização do `diff` em JSONB.
- **O:** NOT NULL.
- **OS:** Sobrevive à exclusão da entidade (log é o túmulo do dado).
- **IRC:** Não há FK física (polimórfica); validação defensiva na leitura.
- **PE:** Nenhuma.

#### R27 — Log de integração → Sistema externo (N:1)
- **C:** Toda chamada a sistema externo (Sprint 5) grava log.
- **O:** `sistema_externo_id` NOT NULL.
- **OS:** `RESTRICT` — sistemas externos são catálogos; exclusão exige `status = 'descontinuado'` e sem logs nos últimos 90 dias.
- **IRC:** Log contém requisição/resposta redigida, `http_status`, `latencia_ms`, `correlation_id`.
- **PE:** Erro persistente (3 retries) escalada para a fila de exceções.

---

## 4. Regras de dependência transversais

Estas regras cruzam múltiplas tabelas e **não podem ser expressas como constraints simples**. Devem ser implementadas via triggers transacionais + validação em serviço.

1. **Inscrição ativa exige Clube ativo:** `rel_edicao_clube` valida que o Clube está `status = 'ativo'` e o Contrato do representante técnico está vigente.
2. **Escalação exige vínculo vigente:** Toda linha de `escalacao` valida que o Atleta tem `rel_equipe_atleta` ativa e Contrato ativo com o Clube da Equipe.
3. **Gol exige atleta em campo:** Evento `tipo = 'gol'` valida que `atleta_id` está em `escalacao` com `situacao = 'titular'` ou que foi substituído para dentro (registrar minuto de entrada).
4. **Approval mirror:** Aprovação `deferida` para `tipo_ref = 'contrato'` deve refletir em `contrato.status = 'ativo'` atomicamente (mesma transação).
5. **Tenant boundary:** Todas as FKs entre entidades de negócio devem verificar `tenant_id` igual entre pai e filho (RLS garante em SELECT, mas triggers garantem em INSERT/UPDATE cross-tenant malicioso).
6. **Soft-delete cascade:** Exclusão lógica de Clube propaga para Equipes e suspende Contratos (`status = 'suspenso_clube'`), mas **nunca** exclui Partidas históricas.
7. **Idempotência de integrações:** Logs com mesmo `correlation_id` + `sistema_externo_id` são rejeitados (constraint UNIQUE) para evitar duplicação em retries.
8. **Imutabilidade pós-fato:** Partidas `concluida` há mais de 24h só podem ser alteradas com `aprovação de fluxo específico` (R21/R23 com `tipo_ref = 'partida_reabertura'`).

---

## 5. Invariantes do modelo (resumo para Sprint 1)

| ID | Invariante | Verificação |
|----|-----------|-------------|
| I-01 | Um Usuário pertence a exatamente uma Organização | `usuario.tenant_id` NOT NULL + RLS |
| I-02 | Uma Assinatura ativa por Organização | Constraint parcial UNIQUE |
| I-03 | Uma Pessoa tem no máximo um Contrato ativo por Clube | Constraint parcial UNIQUE |
| I-04 | Um Atleta tem no máximo um vínculo ativo por Equipe por período | Constraint parcial UNIQUE |
| I-05 | Mandante ≠ Visitante | CHECK na Partida |
| I-06 | 11 titulares por Escalação | Trigger no INSERT |
| I-07 | Ordem de Fases é sequencial e UNIQUE | UNIQUE (edicao_id, ordem) |
| I-08 | Apenas uma Proposta aceita por Negociação | Constraint parcial UNIQUE |
| I-09 | Auditoria é append-only | RBAC + trigger BEFORE DELETE/UPDATE |
| I-10 | tenant_id é propagated em cascata | Triggers em todas FKs de negócio |

---

## 6. Alinhamento com não-objetivos

As regras acima **omitiram** deliberadamente (alinhado às N-01 a N-26):

- **N-12 a N-15:** Estrutura física (estádio/CT) — sem relacionamentos correspondentes.
- **N-18 a N-20:** Financeiro e bilhetria — `Negociação.proposta` trata apenas valores esportivos, não contábeis.
- **N-24 a N-26:** Streaming e mídia ao vivo — `Partida` mantém apenas estado esportivo, sem link a mídia.

As lacunas foram registradas no backlog de **futuro desejado** (F-08 a F-11, F-20) e serão reavaliadas no handoff da Sprint 0 (subtask 0.6.3).