# PRD — Fontes Reais e Providers de IA

## Problem Statement

O Treinador Inteligente já possui Fonte de Dados Esportivos, importação local,
proveniência e fallback determinístico, mas ainda não dispõe de uma plataforma
operacional para conectar fontes reais e providers de IA com segurança.

Cada fornecedor pode usar autenticação, limites, licenças, schemas, validade,
custos e disponibilidade diferentes. Implementar integrações diretamente no
fluxo do Dossiê criaria acoplamento, risco de vazamento entre Tenants, dados
incomparáveis e dependência de um único vendor.

## Solution

Criar uma camada configurável de conexões para Fontes de Dados Esportivos e
providers de IA. Ela deverá receber os fornecedores que serão informados pelo
responsável do produto, validar credenciais, declarar capacidades, normalizar
respostas, preservar payload bruto e proveniência, controlar cache, limites e
custos e oferecer contratos estáveis ao Treinador Inteligente.

A PRD define a fundação independente de vendor. Cada fonte ou provider real será
registrado posteriormente com nome, documentação oficial, finalidade, credencial,
licença, limites, ambiente e capacidades habilitadas.

## User Stories

1. Como administrador da plataforma, quero cadastrar uma conexão, para integrar um fornecedor sem alterar o fluxo do Dossiê.
2. Como administrador da plataforma, quero classificar a conexão como Fonte de Dados Esportivos ou provider de IA, para aplicar políticas adequadas.
3. Como administrador da plataforma, quero registrar documentação oficial e contato do fornecedor, para manter governança operacional.
4. Como administrador da plataforma, quero declarar ambiente de sandbox ou produção, para testar antes de liberar dados reais.
5. Como administrador da plataforma, quero armazenar credenciais fora do banco de domínio, para reduzir exposição de segredos.
6. Como administrador da plataforma, quero testar uma credencial sem persistir sua representação em logs, para validar a configuração com segurança.
7. Como administrador do Tenant, quero habilitar somente conexões permitidas para meu clube, para respeitar contrato e licença.
8. Como administrador do Tenant, quero selecionar quais capacidades consumir, para controlar escopo e custo.
9. Como gestor, quero visualizar saúde, última sincronização e próxima tentativa, para acompanhar disponibilidade.
10. Como gestor, quero limites de requisições, tokens e orçamento, para impedir consumo inesperado.
11. Como gestor, quero receber alerta antes de atingir o orçamento, para ajustar o uso.
12. Como gestor, quero desativar imediatamente uma conexão, para responder a incidentes ou mudanças contratuais.
13. Como engenheiro de dados, quero um adaptador por fornecedor, para isolar autenticação e schema externo.
14. Como engenheiro de dados, quero um modelo canônico de partidas, eventos, classificação, tracking e disponibilidade, para comparar fontes.
15. Como engenheiro de dados, quero preservar o payload bruto e o normalizado, para auditoria e reprocessamento.
16. Como engenheiro de dados, quero registrar versão do adaptador e schema, para reproduzir transformações.
17. Como engenheiro de dados, quero importar de forma incremental por cursor ou janela, para evitar recargas completas.
18. Como engenheiro de dados, quero idempotência por fonte e registro, para evitar duplicação.
19. Como engenheiro de dados, quero quarentena para registros inválidos, para não bloquear todo o lote.
20. Como auditor, quero visualizar licença, atribuição, qualidade e validade, para verificar uso permitido.
21. Como auditor, quero saber qual registro externo sustentou uma Recomendação Tática, para reconstruir a decisão.
22. Como auditor, quero histórico imutável de sincronizações, para investigar alterações do fornecedor.
23. Como analista, quero reconciliar entidades externas com clubes, atletas e competições do Tenant, para evitar associações por nome frágeis.
24. Como analista, quero revisar associações ambíguas, para impedir mistura de entidades.
25. Como analista, quero uma prioridade entre fontes equivalentes, para resolver divergências de maneira explícita.
26. Como analista, quero ver conflitos entre fontes, para não receber uma falsa versão única dos dados.
27. Como usuário, quero que dados vencidos sejam identificados e não usados silenciosamente, para confiar na análise.
28. Como usuário, quero saber quando um valor é sintético, interno, comunitário ou licenciado, para interpretar sua qualidade.
29. Como Coordenador Técnico, quero solicitar capacidades sem conhecer o vendor, para manter a Comissão Técnica Digital desacoplada.
30. Como Agente Especialista, quero receber um pacote de evidências normalizado, para produzir parecer rastreável.
31. Como administrador da plataforma, quero cadastrar providers de IA com modelos permitidos, para controlar a execução.
32. Como administrador da plataforma, quero configurar timeout, tentativas e fallback por provider, para preservar disponibilidade.
33. Como administrador da plataforma, quero bloquear modelos não aprovados, para cumprir política e orçamento.
34. Como gestor, quero definir provider e modelo padrão por capacidade, para adequar qualidade e custo.
35. Como gestor, quero fallback para outro modelo ou modo determinístico, para concluir o Dossiê quando houver falha.
36. Como auditor, quero registrar prompt versionado, parâmetros, modelo, tokens, duração e custo, para auditar uma execução.
37. Como auditor, quero impedir que segredos e dados sensíveis sejam enviados ao provider, para preservar privacidade.
38. Como responsável por segurança, quero lista de campos permitidos por provider, para aplicar minimização de dados.
39. Como responsável por segurança, quero rotação e revogação de credenciais, para responder a incidentes.
40. Como responsável por segurança, quero trilha de quem criou, testou, ativou ou alterou uma conexão, para assegurar responsabilização.
41. Como operador, quero retry com backoff e circuit breaker, para evitar sobrecarregar serviços indisponíveis.
42. Como operador, quero cache com validade por capacidade, para respeitar limites e reduzir custo.
43. Como operador, quero métricas de latência, erro, rate limit e custo por Tenant, para operar a integração.
44. Como operador, quero reprocessar um lote após corrigir o adaptador, para recuperar dados sem perder histórico.
45. Como desenvolvedor, quero fixtures contratuais sanitizadas, para testar adaptadores sem rede e sem segredos.
46. Como desenvolvedor, quero validação de schema na fronteira, para rejeitar respostas incompatíveis cedo.
47. Como responsável do produto, quero adicionar as fontes e providers escolhidos a um catálogo, para priorizar o rollout.
48. Como responsável do produto, quero um checklist de prontidão por conexão, para liberar somente integrações verificadas.

## Implementation Decisions

- Não será criado um novo Módulo Contratado chamado Fontes, Data Hub ou Providers. A solução aprofundará **Integrações**, **IA**, **Automações**, **Auditoria** e **Relatórios/BI**.
- O módulo **Integrações** será proprietário de Sistemas Externos, Fontes de Dados Esportivos, sincronizações, lotes, quarentena, cache e reprocessamento.
- O módulo **IA** continuará proprietário do catálogo de providers, modelos, Agentes Especialistas, prompts, roteamento e fallback determinístico.
- O módulo **Automações** será proprietário de agendas, gatilhos, retries automáticos e alertas. Sincronização manual continuará disponível em Integrações sem exigir esse módulo.
- O módulo **Auditoria** será proprietário da trilha de credenciais configuradas, ativações, execuções, custos e alterações, sem armazenar o segredo.
- O módulo **Relatórios/BI** consumirá métricas agregadas de qualidade, cobertura, latência e custo; não será responsável por operar conectores.
- Operação, Transferências e o Treinador Inteligente consumirão somente registros normalizados; nenhum deles conhecerá autenticação, paginação ou schema específico do fornecedor.
- O gating seguirá o contrato comercial: fontes esportivas reais exigem Integrações; execução de Agentes Especialistas exige IA; rotinas programadas exigem Automações; consultas históricas avançadas exigem Relatórios.
- A implementação evoluirá as estruturas já existentes: Sistema Externo representará a conexão operacional; Fonte de Dados Esportivos continuará representando proveniência e licença; provider de IA continuará representando catálogo e execução de modelos. Não será criado um cadastro paralelo com o mesmo significado.
- Registros de Integração continuarão sendo a trilha técnica de recebimento e processamento; Lotes e Registros Esportivos continuarão sendo o histórico imutável dos dados normalizados.
- Segredos serão referenciados por identificador de secret manager ou variável de ambiente; valores não serão persistidos em payloads, auditoria ou mensagens de erro.
- Cada adaptador declarará capacidades, versão de contrato, autenticação, paginação, rate limit, política de cache e licença exigida.
- O catálogo inicial de capacidades esportivas incluirá agenda/resultados, classificação/forma, escalações, eventos, estatísticas agregadas, dados espaciais, tracking, disponibilidade física e ambiente.
- O contrato de normalização produzirá registro canônico, payload bruto, hash, origem, observação, expiração, licença, qualidade e versão do adaptador.
- Entidades externas usarão mapeamento persistido para entidades do Tenant; correspondência automática por nome será apenas sugestão revisável.
- Lotes serão atômicos por unidade de publicação, idempotentes e reprocessáveis; registros inválidos irão para quarentena com motivo estruturado.
- Dados vencidos permanecerão no histórico, serão marcados como vencidos e não alimentarão recomendações sem política explícita.
- Quando duas fontes divergirem, o sistema manterá ambas e aplicará prioridade configurada, sem sobrescrever silenciosamente a evidência.
- Providers de IA implementarão um contrato único de execução estruturada com mensagens, schema de saída, timeout, cancelamento, uso e custo.
- O catálogo atual de providers e Agentes Especialistas será estendido, preservando configuração por Tenant e os tipos já suportados: OpenAI, Anthropic, OpenRouter, Ollama, OpenCode, Gemini e provider customizado.
- A saída de IA será validada por schema antes de persistir uma contribuição da Comissão Técnica Digital.
- A política de roteamento escolherá provider/modelo por capacidade, Tenant, sensibilidade, disponibilidade, limite e orçamento.
- O fallback será explícito e auditável: mesmo provider, provider alternativo ou modo determinístico.
- Prompts serão templates versionados; alterações exigirão nova versão e não modificarão execuções históricas.
- O pacote enviado ao provider será montado por allowlist de campos e classificação de sensibilidade.
- A execução assíncrona usará chaves idempotentes, retry com backoff, circuit breaker e fila de falhas.
- Cache será separado por Tenant, conexão, capacidade e parâmetros; a validade virá da fonte ou de política mais restritiva.
- Telemetria armazenará identificadores técnicos e métricas, nunca credenciais ou conteúdo sensível completo.
- A ativação seguirá estados `draft`, `testing`, `active`, `degraded`, `disabled` e `revoked`.
- Uma conexão somente poderá ficar `active` após teste de credencial, validação contratual, confirmação de licença, fixture contratual e aprovação administrativa.
- O cadastro futuro de cada vendor deverá fornecer: nome, tipo, URL oficial, documentação, autenticação, segredo de referência, ambiente, licença, atribuição, capacidades, limites, custo, residência de dados, retenção e contato de suporte.
- O rollout será feito primeiro em sandbox, depois em um Tenant piloto e por fim disponibilizado a outros Tenants habilitados.
- A ordem inicial já planejada será: dados internos do clube; football-data.org para agenda, tabela e resultados; laboratório isolado com StatsBomb e SkillCorner; somente depois feeds espaciais licenciados para recomendações do adversário.
- Recomendações espaciais sobre o adversário exigirão, por padrão, ao menos cinco partidas recentes com eventos coordenados ou tracking e qualidade mensurada; abaixo disso, a saída continuará identificada como hipótese.

## Testing Decisions

- O seam principal será o contrato do adaptador: uma fixture externa entra e registros canônicos, proveniência e validade saem, sem rede real.
- Um segundo seam testará a execução estruturada do provider: pacote permitido entra e contribuição validada, uso e custo saem.
- Testes não verificarão detalhes internos de bibliotecas HTTP; verificarão autenticação sanitizada, paginação, normalização, erros e comportamento observável.
- Cada adaptador real exigirá fixtures sanitizadas de sucesso, resposta vazia, schema alterado, rate limit, timeout e erro de autenticação.
- Testes de contrato impedirão que campos secretos ou sensíveis apareçam em logs, auditoria, exceções e snapshots.
- Idempotência será testada repetindo lote e job com a mesma chave.
- Concorrência será testada com duas sincronizações da mesma fonte e janela.
- Mapeamento de entidades terá testes para associação confirmada, ambiguidade, rejeição e isolamento por Tenant.
- Validade terá testes para datas ausentes permitidas, datas inválidas, vencimento, reprocessamento e conflito entre fontes.
- Roteamento de IA terá testes de provider principal, timeout, rate limit, orçamento esgotado, fallback alternativo e fallback determinístico.
- Saídas fora do schema serão rejeitadas e não criarão parecer pronto.
- Testes de integração HTTP usarão servidor falso local ou transporte mockado; a suíte não acessará vendors reais.
- Smoke tests reais serão executados separadamente, somente em ambiente autorizado, com orçamento mínimo e credenciais de teste.
- O gate de ativação verificará migrations, segurança, licença, atribuição, limites, telemetria, rollback e revogação.
- Testes de composição verificarão que Integrações funciona sem Automações para sincronização manual, IA funciona sem fonte real por fallback e cada tela respeita o Módulo Contratado correspondente.
- Os testes cruzarão os seams existentes de Sistema Externo, Registro de Integração, Fonte de Dados Esportivos, provider de IA e Agente Especialista, evitando uma segunda infraestrutura de testes para os mesmos conceitos.

## Out of Scope

- Escolher ou contratar fornecedores em nome do responsável do produto.
- Armazenar credenciais diretamente no banco de domínio.
- Scraping de páginas sem API ou autorização explícita.
- Contornar rate limits, paywalls ou termos de uso.
- Redistribuir datasets quando a licença não permitir.
- Treinar modelos próprios nesta fase.
- Enviar dados clínicos ou documentos pessoais a providers sem base, finalidade e autorização específicas.
- Tornar qualquer vendor obrigatório para o funcionamento básico do Treinador Inteligente.
- Criar módulos contratáveis separados para cada fonte, provider, modalidade de dado ou Agente Especialista.

## Further Notes

- Baseline técnico: Fonte de Dados Esportivos, Lote de Importação, Registro Esportivo, provider de IA, Agente Especialista, Sistema Externo e Registro de Integração já existem e devem ser aprofundados, não substituídos.
- Esta PRD materializa as pendências 14.2.3 (provider assíncrono) e 14.3.3 (adaptadores live licenciados e cache), mantendo 14.4.3 dependente de cobertura espacial real.
- A pesquisa já registrada recomenda `club_internal + football-data.org` para o MVP brasileiro e restringe StatsBomb, SkillCorner e Metrica a P&D ou uso compatível com licença.
- O piloto permanece em NO-GO operacional temporário até restauração ensaiada, observabilidade externa e assinatura formal; nenhuma conexão real altera esse gate.
- Esta PRD será atualizada quando o responsável do produto fornecer as fontes e providers reais.
- Para cada item recebido será criada uma ficha de conexão com riscos, licença, custo, limites, capacidades e ordem de rollout.
- A pesquisa existente de fontes gratuitas é referência de descoberta, não autorização automática de uso.
- A primeira conexão deve ser escolhida pelo melhor equilíbrio entre licença clara, fixture estável, utilidade para o Dossiê e baixo risco operacional.
- Dependência relacionada: “PRD — Evolução do Treinador Inteligente”.

### Fontes públicas recebidas em 12 de julho de 2026

A imagem fornecida foi validada contra páginas, termos e repositórios oficiais. A
classificação abaixo é um gate de produto: consulta humana gratuita não equivale
a API pública, licença aberta ou direito de uso comercial no SaaS.

| Fonte | Classificação inicial | Uso autorizado nesta fase |
|---|---|---|
| FotMob | Condicionada a contrato/permissão | Referência humana; sem scraping ou endpoints internos |
| Sofascore | Condicionada a contrato | Referência humana ou widget autorizado; sem ingestão da base |
| oGol / zerozero | Condicionada a permissão escrita | Links e checagem humana |
| WhoScored | Condicionada a licença | Nenhuma ingestão ou engenharia reversa |
| FBref | Incompatível com o fluxo atual de IA sem licença específica | Não usar como evidência, prompt ou entrada de previsão |
| Understat | Condicionada a permissão escrita | Pesquisa humana; downloads não entram em produção |
| Transfermarkt | Condicionada a acordo comercial | Nenhum bot, scraping, treinamento ou uso por IA |
| “TF”, provavelmente TransferFeed | Identidade pendente e produto comercial | Confirmar a marca e solicitar proposta de integração |
| CIES Football Observatory | Referência metodológica | Relatórios e métodos citados; sem ingestão da base subjacente |
| StatsBomb Open Data | P&D/open data com atribuição | Fixtures, protótipos e algoritmos em ambiente `research_sample`; produção após clearance |

A ordem segura permanece: dados internos autorizados; football-data.org para
agenda/tabela/resultados; StatsBomb Open Data em laboratório; depois negociação
de feeds comerciais. A análise detalhada e as fontes oficiais estão no relatório
“Validação das fontes públicas mostradas na imagem”.
