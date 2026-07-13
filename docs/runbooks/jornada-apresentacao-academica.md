# Jornada de apresentação acadêmica

## Tese do produto

O SaaS transforma dados esportivos com proveniência em uma decisão de comissão
técnica que permanece humana, explicável e versionada. A apresentação não deve
prometer que todo parecer foi produzido por IA generativa: o modo real de
execução precisa aparecer na interface e na auditoria.

## História em quatro etapas

1. **Dados** — escolher o time e a próxima partida; conferir elenco, histórico,
   fontes, validade e lacunas.
2. **Comissão** — reunir pareceres por especialidade com evidências, confiança e
   limitações.
3. **Cenários** — comparar Planos de Jogo equilibrado, ofensivo e conservador.
4. **Decisão** — revisar escalação, desenhar na prancheta e preservar versões sem
   alterar a escalação oficial.

## Modos de execução

- **Motor de regras**: é o modo operacional atual do Dossiê. Cruza contratos,
  disponibilidade, forma, eventos e registros esportivos válidos.
- **Provider de IA**: existe no catálogo e nos Agentes Especialistas, mas só pode
  ser apresentado como atuante quando um `SpecialistOpinion` registrar
  `execution_mode=provider`.
- **Laboratório**: StatsBomb Open Data e SkillCorner Open Data validam mapas,
  passes, xG e tracking. São amostras de pesquisa, separadas do contexto
  operacional.

## Base Esportiva Global

- `football-data-org` fornece partidas, classificação e elencos públicos.
- `statsbomb-open` fornece eventos para mapas de calor, finalizações, xG e redes
  de passes.
- `skillcorner-open` fornece amostras e metadados de tracking para pesquisa.
- A ingestão é única, global e administrada pela plataforma. O Tenant recebe
  acesso de leitura conforme os módulos, fontes e capacidades contratados.
- GPS, contratos, disponibilidade, informação médica, Dossiês, Planos e
  Pranchetas continuam privados e isolados por Tenant.

Sincronização manual de infraestrutura para diagnóstico:

```bash
python src/manage.py sync_platform_sports_provider \
  --provider football-data-org --competition BSA --max-teams 4
python src/manage.py sync_platform_sports_provider \
  --provider statsbomb-open --competition-id 43 --season-id 106
python src/manage.py sync_platform_sports_provider \
  --provider skillcorner-open --max-matches 2
```

Para priorizar equipes específicas no football-data.org, repita `--team-id`:

```bash
python src/manage.py sync_platform_sports_provider \
  --provider football-data-org --competition BSA \
  --team-id 4241 --team-id 1769
```

## Preparar a apresentação sem dados falsos

O comando abaixo remove somente o footprint exato do seed conhecido, escolhe
uma partida futura do catálogo global e materializa o confronto no Tenant:

```bash
python src/manage.py prepare_real_coach_journey \
  --tenant <slug> --user <usuario> --confirm-cleanup
```

O processo não cria atletas, contratos, disponibilidade nem pareceres falsos.
Ele preserva branding, memberships, provider de IA e Agentes Especialistas.

Se ainda houver cópias antigas dos providers públicos dentro do Tenant, faça
primeiro uma simulação e depois confirme a contração:

```bash
python src/manage.py retire_tenant_public_sports_copies --tenant <slug>
python src/manage.py retire_tenant_public_sports_copies --tenant <slug> --confirm
```

Lotes com artefatos são preservados. Fontes internas e licenciadas privadas não
são atingidas.

## Roteiro demonstrável

1. Abra **Treinador Inteligente** e selecione clube e confronto.
2. Confira adversário, cobertura das fontes e bloqueios operacionais.
3. Use **Ensaio com elenco público** para comparar 4-3-3, 4-2-3-1 e 5-3-2.
4. Abra o **Laboratório tático global** para mapa de calor, finalizações, xG e
   rede de passes baseada em eventos StatsBomb.
5. Explique que o ensaio não persiste escalação oficial: ele prova a inteligência
   sobre dados públicos sem fingir que o clube forneceu dados privados.
6. Com ao menos 11 contratos reais e perfis esportivos do Tenant, o mesmo fluxo
   libera Dossiê, Planos de Jogo e Prancheta operacionais e versionados.

Também é possível promover explicitamente uma partida já sincronizada:

```bash
python src/manage.py materialize_provider_match \
  --tenant <slug> \
  --provider-match-id <id>
```

O processo é idempotente e cria ou atualiza Clubes, competição, temporada, fase
e partida. O Dossiê permanece bloqueado enquanto não houver atletas com
contratos ativos e perfis esportivos privados.

## Atualização contínua

- O serviço `sports-sync` executa `scripts/watch_sports_sources.py` em ciclo.
- O intervalo padrão é de seis horas (`SPORTS_SYNC_INTERVAL_SECONDS=21600`).
- Falhas recebem três tentativas por padrão, com espera exponencial configurada
  por `SPORTS_SYNC_RETRY_ATTEMPTS` e `SPORTS_SYNC_RETRY_DELAY_SECONDS`.
- A tela **Cobertura e atualidade dos dados** mostra última checagem, validade e
  registros vencidos; usuários do Tenant não controlam a ingestão.
- Conteúdo idêntico também renova a última checagem e a validade dos registros;
  ausência de mudança no provider não é tratada como ausência de sincronização.
- Partidas `FD-*` já materializadas são atualizadas após cada sincronização do
  football-data.org.
- Em produção, a atualização é responsabilidade da plataforma: não recebe
  Tenant, usuário do clube nem depende do módulo Automações. O container
  reinicia automaticamente em caso de falha.
- Uma fonte global marcada como desabilitada interrompe imediatamente o consumo;
  a revogação de fonte ou capacidade também bloqueia laboratório e materialização.

## Estado local validado em 13/07/2026

- O seed sintético do Avaí foi removido por marcadores exatos.
- Botafogo FR × Santos FC (`FD-554921`) foi materializada a partir do catálogo
  global e possui elencos públicos para ensaio.
- As cópias públicas legadas do football-data.org e StatsBomb foram retiradas do
  Tenant; dados privados e artefatos foram preservados.
- O sincronizador automático concluiu o ciclo de football-data.org, StatsBomb
  Open e SkillCorner Open.
- A jornada pública foi validada no navegador com três formações, mapa de calor,
  finalizações, xG e rede de passes.
- O modo operacional continua, corretamente, aguardando pelo menos 11 contratos
  privados reais do clube.
