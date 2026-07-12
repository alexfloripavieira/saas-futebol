# PRD — Evolução do Treinador Inteligente

## Problem Statement

A primeira versão do Treinador Inteligente já produz um Dossiê da Partida,
pareceres da Comissão Técnica Digital, três Planos de Jogo e um rascunho de
escalação sujeito à decisão humana. Entretanto, a comissão ainda não consegue
trabalhar sobre dados espaciais reais, editar visualmente o Plano de Jogo,
comparar a recomendação com o que ocorreu em campo nem acompanhar a atualização
assíncrona do Dossiê.

Sem essas capacidades, a plataforma organiza e explica decisões, mas ainda não
fecha o ciclo completo de preparação, decisão, execução e aprendizado pós-jogo.

## Solution

Evoluir o Treinador Inteligente para um ambiente contínuo de preparação da
partida. O produto deve combinar dados internos e Fontes de Dados Esportivos,
orquestrar a Comissão Técnica Digital, oferecer uma prancheta interativa,
apresentar análises espaciais somente quando houver cobertura suficiente e criar
uma avaliação pós-jogo que compare Plano de Jogo, decisão humana e eventos reais.

A revisão humana continuará sendo a autoridade final. Toda Recomendação Tática
deverá mostrar evidências, confiança, limitações, validade e origem. A conexão
com fontes reais e providers de IA será regida pela PRD complementar “Fontes
Reais e Providers de IA”.

## User Stories

1. Como treinador, quero visualizar nosso time e o adversário no mesmo campo, para comparar estruturas com rapidez.
2. Como treinador, quero alternar entre os Planos equilibrado, ofensivo e conservador, para avaliar os cenários sem perder o contexto.
3. Como treinador, quero arrastar atletas no campo, para ajustar a formação sugerida.
4. Como treinador, quero desenhar setas, linhas e zonas, para registrar movimentos e responsabilidades.
5. Como treinador, quero salvar versões da prancheta, para comparar alternativas discutidas pela comissão.
6. Como treinador, quero distinguir movimento observado de movimento hipotético, para não tratar inferência como fato.
7. Como analista tático, quero ver mapas de calor por atleta e equipe, para entender ocupação espacial.
8. Como analista tático, quero ver redes de passe, para identificar conexões e dependências na circulação.
9. Como analista tático, quero ver progressões, recuperações e finalizações no campo, para relacionar comportamento e resultado.
10. Como analista tático, quero filtrar a análise por período e estado do placar, para evitar médias que escondam mudanças do jogo.
11. Como analista tático, quero comparar nosso padrão com o padrão do adversário, para encontrar vantagens e riscos.
12. Como membro da comissão, quero saber a cobertura espacial da amostra, para julgar se um gráfico é confiável.
13. Como membro da comissão, quero que gráficos espaciais sejam ocultados quando não houver dado suficiente, para evitar falsa precisão.
14. Como Coordenador Técnico, quero consolidar conflitos entre Agentes Especialistas, para apresentar escolhas claras ao treinador.
15. Como Coordenador Técnico, quero registrar qual evidência sustenta cada conflito, para tornar a síntese auditável.
16. Como Preparador Físico, quero importar disponibilidade, carga e RPE autorizados, para informar limites de participação.
17. Como Preparador Físico, quero restringir a visualização de dados sensíveis, para preservar privacidade e finalidade esportiva.
18. Como Preparador Físico, quero registrar limite de minutos sem emitir diagnóstico, para apoiar a decisão técnica dentro do escopo permitido.
19. Como analista de ambiente, quero receber clima, viagem, altitude e condição do gramado, para antecipar impactos logísticos.
20. Como olheiro, quero acompanhar a idade e abrangência das observações do adversário, para identificar lacunas de scouting.
21. Como treinador, quero receber uma notificação quando o Dossiê estiver pronto, para não precisar aguardar na tela.
22. Como treinador, quero ver o progresso da geração dos pareceres, para saber quais Agentes Especialistas concluíram ou falharam.
23. Como treinador, quero regenerar apenas uma contribuição desatualizada, para evitar custo e demora desnecessários.
24. Como gestor, quero configurar uma janela de atualização automática, para manter o Dossiê atual sem gerar análises em excesso.
25. Como gestor, quero limites de custo e uso por Tenant, para controlar providers e processamento.
26. Como auditor, quero rastrear dados, regras, providers e versões usados em cada recomendação, para reconstruir a decisão.
27. Como auditor, quero diferenciar fallback determinístico de execução por provider, para saber como cada parecer foi produzido.
28. Como treinador, quero revisar e aprovar o rascunho sem alterar a escalação oficial, para preservar o fluxo operacional existente.
29. Como treinador, quero comparar o rascunho revisado com o Plano original, para entender as alterações humanas.
30. Como treinador, quero registrar o motivo de uma alteração humana, para alimentar a avaliação pós-jogo.
31. Como analista, quero comparar o Plano de Jogo com escalação e eventos realizados, para avaliar aderência.
32. Como analista, quero registrar quais hipóteses foram confirmadas ou refutadas, para melhorar análises futuras.
33. Como Coordenador Técnico, quero produzir uma avaliação pós-jogo, para transformar resultado em aprendizado institucional.
34. Como gestor, quero métricas de adoção, tempo de geração, falhas e custo, para decidir sobre expansão do módulo.
35. Como administrador do Tenant, quero ativar capacidades gradualmente, para conduzir um piloto controlado.
36. Como administrador da plataforma, quero desativar uma capacidade ou provider sem indisponibilizar o restante do módulo, para reduzir risco operacional.
37. Como equipe do piloto, quero executar ensaio de rollback e checklist de aceite, para tomar decisão formal de go/no-go.
38. Como usuário, quero explicações em português claro, para compreender recomendações sem conhecer detalhes técnicos dos modelos.

## Implementation Decisions

- Não será criado um novo Módulo Contratado para scouting, preparação física, campo tático, dados espaciais ou avaliação pós-jogo. Essas capacidades aprofundarão os módulos originais.
- O módulo **IA** será proprietário do Treinador Inteligente, Dossiê da Partida, Comissão Técnica Digital, Planos de Jogo, prancheta e revisão do rascunho.
- O módulo **Operação** continuará proprietário dos dados oficiais de clubes, pessoas, competições, partidas, escalações e eventos; o Treinador Inteligente apenas os consumirá.
- O módulo **Transferências** continuará proprietário de contratos e vínculos usados na elegibilidade dos atletas; não haverá um segundo cadastro esportivo dentro da IA.
- O módulo **Integrações** será proprietário da entrada, normalização, qualidade e reprocessamento de Fontes de Dados Esportivos reais.
- O módulo **Relatórios/BI** será proprietário de histórico, comparação Plano de Jogo × execução e avaliação pós-jogo. O Dossiê poderá apontar para essas análises sem duplicá-las.
- O módulo **Previsões** será proprietário de tendências entre partidas e riscos futuros. A recomendação para uma partida específica continuará pertencendo ao Treinador Inteligente.
- O módulo **Automações** será proprietário da programação recorrente, gatilhos, notificações e reprocessamento automático. A geração manual do Dossiê continuará funcionando apenas com o módulo IA.
- O módulo **Aprovações** poderá formalizar a escalação quando contratado e configurado pelo Tenant; a revisão humana simples continuará disponível sem obrigar um Fluxo de Aprovação.
- O módulo **Auditoria** continuará proprietário da trilha de dados, execuções, decisões humanas, alterações e custos.
- O Centro de Scouting existente será aprofundado como visão especializada do Dossiê e do Olheiro, e não como um décimo módulo.
- Capacidades cruzadas terão uma interface pequena: cada módulo proprietário expõe dados ou ações estáveis, sem compartilhar regras internas nem criar dependência circular.
- O gating seguirá o contrato comercial: IA habilita o Treinador; Integrações habilita fontes reais; Relatórios habilita avaliação histórica; Automações habilita execução programada; Aprovações habilita o gate formal opcional.
- O Dossiê da Partida continuará sendo o snapshot versionado compartilhado pela Comissão Técnica Digital.
- A evolução estenderá os modelos existentes de Dossiê, parecer, Plano de Jogo e rascunho; não criará um segundo fluxo de inteligência esportiva em paralelo.
- A geração assíncrona será modelada como uma execução rastreável, com estados `queued`, `running`, `partial`, `completed`, `failed` e `cancelled`.
- Cada contribuição registrará modo de execução, versão de prompt, provider, modelo, evidências, confiança, limitações, duração e custo estimado.
- O Coordenador Técnico consumirá contribuições concluídas, explicitará conflitos e produzirá cenários comparáveis; não terá autoridade para confirmar escalação oficial.
- O fallback determinístico continuará disponível quando providers estiverem indisponíveis, desativados ou fora do orçamento.
- A prancheta salvará versões imutáveis de posições, linhas, setas, zonas e anotações, mantendo uma versão ativa editável.
- Elementos da prancheta terão classificação explícita: observado, calculado, recomendado ou hipótese.
- Mapas de calor, redes de passe e pitch control somente serão gerados quando a Fonte de Dados Esportivos declarar capacidade e cobertura suficientes.
- Métricas espaciais deverão carregar período, amostra, direção de ataque, sistema de coordenadas e transformação aplicada.
- Dados de saúde e carga terão permissão específica, minimização, auditoria de acesso e retenção configurável; o sistema não fará diagnóstico médico.
- A avaliação pós-jogo relacionará Dossiê, Plano de Jogo, rascunho revisado, escalação oficial, eventos e justificativas humanas.
- Pesos e confiança não serão recalibrados automaticamente sem conjunto de avaliação, aprovação humana e versionamento.
- Jobs assíncronos deverão ser idempotentes por Tenant, partida, versão do Dossiê e capacidade solicitada.
- Notificações reutilizarão o subsistema existente e nunca incluirão dados sensíveis no texto da mensagem.
- Telemetria reutilizará as Métricas Operacionais, auditoria append-only e correlação por Request ID já existentes.
- A interface continuará server-rendered em Django Templates; a prancheta poderá usar SVG e JavaScript progressivo, sem introduzir uma SPA nesta fase.
- O módulo manterá isolamento por Tenant em modelos, jobs, cache, arquivos e telemetria.
- A entrega será incremental: prancheta editável; jobs assíncronos; análises espaciais; avaliação pós-jogo; piloto controlado.

## Testing Decisions

- Os testes verificarão comportamento observável e invariantes de domínio, sem depender do texto exato de prompts ou da implementação interna dos cálculos.
- O seam principal será a jornada HTTP: gerar Dossiê, acompanhar execução, revisar Plano de Jogo, editar rascunho e registrar avaliação pós-jogo.
- O seam de domínio continuará sendo o serviço de geração e revisão do Dossiê, reutilizando os testes atuais do Treinador Inteligente.
- A prancheta será testada por contrato de persistência: versões, elementos, classificação da evidência e isolamento por Tenant.
- Cálculos espaciais usarão fixtures pequenas e determinísticas com resultados conhecidos; nenhum teste acessará a internet.
- Jobs serão testados com filas e providers falsos, incluindo sucesso, resposta parcial, timeout, repetição, cancelamento e fallback.
- Permissões terão testes de matriz para treinador, gestor, Preparador Físico, auditor e usuário sem acesso.
- Dados sensíveis terão testes de não exposição em logs, notificações, auditoria serializada e respostas HTTP.
- A avaliação pós-jogo terá testes de vínculo entre recomendação, decisão humana e evento realizado.
- O gate final executará suíte completa, verificação de migrations, check de produção, jornada piloto e ensaio de rollback.
- A composição modular terá testes externos: IA isolada mantém geração manual e fallback; Integrações adiciona fontes reais; Automações adiciona recorrência; Relatórios adiciona pós-jogo; Aprovações adiciona o gate formal.
- Menus, rotas e ações continuarão cobertos por testes de Módulo Contratado e papel, evitando que uma capacidade profunda exponha módulos não adquiridos.

## Out of Scope

- Diagnóstico, prescrição ou decisão médica automatizada.
- Confirmação automática de escalação oficial.
- Aprendizado online que altere recomendações sem avaliação e aprovação.
- Scraping não autorizado ou redistribuição de dados sem licença.
- Promessa de tracking em tempo real quando a fonte não oferecer essa capacidade.
- Produção automática de vídeo ou visão computacional nesta fase.
- Detalhes de autenticação e contratos de vendors específicos, tratados na PRD complementar.
- Novos Módulos Contratados chamados Scouting, Campo Tático, Performance Física ou Pós-jogo nesta fase.

## Further Notes

- Baseline funcional: Sprint 14 entregue no commit `b6ff4d2`, com Dossiê, oito integrantes da Comissão Técnica Digital, três Planos de Jogo, campo espelhado, proveniência e rascunho revisável.
- Primeiro incremento de análises espaciais implementado em julho de 2026: o Lab Tático consome amostras normalizadas da StatsBomb Open Data, permite selecionar partida e equipe e apresenta densidade de ações, rede de passes, finalizações e xG com cobertura e proveniência visíveis.
- A densidade de ações deste incremento não será chamada de mapa de ocupação ou tracking. Ela representa apenas coordenadas de eventos. Mapas de calor de ocupação, trajetórias, velocidade, linhas de pressão e movimentos contínuos dependem da ingestão de frames posicionais de uma fonte que autorize esse uso.
- O próximo incremento espacial deverá armazenar tracking como artefato versionado e processável por streaming, evitando converter milhões de frames em registros genéricos. A interface deve manter estado indisponível explícito até existir cobertura suficiente.
- Os dados abertos são dados reais de partidas disponibilizados para pesquisa e desenvolvimento; no produto, também funcionam como base de treinamento, homologação dos cálculos e testes dos Agentes Especialistas. Não devem ser apresentados como dados operacionais do clube do Tenant.
- Esta PRD consolida as pendências já registradas como 14.2.3 (execução assíncrona por provider), 14.4.3 (mapas, redes e interação com dados reais) e a evolução de GPS/RPE e avaliação pós-jogo descrita no plano da Sprint 14.
- A ativação comercial não substitui a pendência 13.6.3: restauração em ambiente descartável, observabilidade externa e assinatura formal de go/no-go continuam bloqueadores do piloto.
- A plataforma deve preferir ausência explícita de dado a estimativas sem evidência.
- A primeira implantação deverá manter as capacidades avançadas desligadas por padrão e ativadas por Tenant.
- Os critérios de go/no-go devem incluir utilidade percebida pela comissão, segurança, tempo de resposta, custo, disponibilidade e capacidade de rollback.
- Dependência: “PRD — Fontes Reais e Providers de IA”.
