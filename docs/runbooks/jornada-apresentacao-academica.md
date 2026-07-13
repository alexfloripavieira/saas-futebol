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

## Dados reais e dados sintéticos

- `football-data-org` é a fonte operacional básica de partidas e classificação.
- `statsbomb-open` e `skillcorner-open` são fontes públicas de pesquisa.
- `demo-treinador-sintetico-v1` pode ser removida com segurança por:

  ```bash
  python src/manage.py purge_demo_data --tenant <slug>
  python src/manage.py purge_demo_data --tenant <slug> --confirm
  ```

  O comando remove somente a fonte sintética e Dossiês derivados, inclusive os
  Dossiês dos dois confrontos conhecidos do seed. Não remove cadastros do tenant, dados
  reais, providers ou Agentes Especialistas.

## Promover uma partida real ao Treinador

Depois de sincronizar o football-data.org:

```bash
python src/manage.py materialize_provider_match \
  --tenant <slug> \
  --provider-match-id <id>
```

O processo é idempotente e cria ou atualiza Clubes, competição, temporada, fase
e partida. O Dossiê continua bloqueado enquanto não houver atletas com contratos
ativos e perfis esportivos; o produto não inventa elenco para completar a demo.

## Atualização contínua

- O serviço `sports-sync` executa `scripts/watch_sports_sources.py` em ciclo.
- O intervalo padrão é de seis horas (`SPORTS_SYNC_INTERVAL_SECONDS=21600`).
- A tela **Fontes Esportivas** mostra última checagem, próxima sincronização,
  validade, registros vencidos e oferece **Atualizar agora**.
- Conteúdo idêntico também renova a última checagem e a validade dos registros;
  ausência de mudança no provider não é tratada como ausência de sincronização.
- Partidas `FD-*` já materializadas são atualizadas após cada sincronização do
  football-data.org.
- Em produção, `SPORTS_SYNC_TENANT` e `SPORTS_SYNC_USER` são obrigatórios e o
  container reinicia automaticamente em caso de falha.

## Estado local em 13/07/2026

- A fonte sintética e os Dossiês que a consumiam foram removidos após backup.
- Coritiba FBC × SE Palmeiras (`FD-554924`) foi materializada a partir do
  football-data.org.
- O sincronizador automático foi ativado e concluiu o ciclo das três fontes.
- A partida real ainda exige importação de elenco para gerar escalação e Plano de
  Jogo de forma responsável.
