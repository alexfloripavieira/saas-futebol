# Sprint 14 — Treinador Inteligente e Comissão Técnica Digital

## Resultado de produto

Para uma partida futura, a comissão técnica seleciona o jogo, gera um Dossiê da
Partida e recebe três Planos de Jogo — equilibrado, ofensivo e conservador. Cada
plano apresenta escalação, formação, comportamentos por fase, riscos, evidências e
confiança. O treinador pode aplicar uma opção como rascunho; nunca como decisão
final automática.

## Princípios

- regra determinística valida disponibilidade, tenant e consistência antes da IA;
- todos os agentes trabalham sobre o mesmo Dossiê versionado;
- toda afirmação relevante aponta para dado, fonte e idade da informação;
- ausência de dado aparece como ausência, nunca como zero ou certeza inventada;
- conflito entre agentes é visível e resolvido pelo Coordenador Técnico;
- saúde e biometria têm acesso restrito e não produzem diagnóstico;
- dados sintéticos, comunitários, internos e licenciados nunca são misturados sem rótulo.

## Comissão Técnica Digital

A primeira versão provisiona oito personas: um Coordenador Técnico e sete
especialistas. O fallback atual é determinístico e rastreável; execução estruturada
por provider permanece como evolução separada.

| Agente | Responsabilidade | Saída principal |
|---|---|---|
| Coordenador Técnico | consolidar recomendações e conflitos | três Planos de Jogo comparáveis |
| Analista Tático | formações, fases, pressão e transições | leitura de padrão e estrutura sugerida |
| Preparador Físico | disponibilidade, carga e limite de minutos | restrições e risco físico não clínico |
| Especialista Defensivo | bloco, cobertura, duelos e bola parada defensiva | plano sem bola |
| Especialista Ofensivo | progressão, criação, finalização e bola parada ofensiva | plano com bola e zonas prioritárias |
| Olheiro | perfil do adversário e lacunas de observação | pontos fortes, fracos e confiança do scouting |
| Especialista em Bola Parada | escanteios, faltas e reposições | rotinas prioritárias e marcações |
| Analista de Ambiente | clima, viagem, altitude e gramado | alertas ambientais com fonte identificada |

## Fatia vertical 14.1

1. Selecionar uma partida futura do tenant ativo.
2. Gerar um Dossiê a partir dos modelos existentes e de registros externos válidos.
3. Produzir recomendações determinísticas explicáveis com três cenários.
4. Persistir Dossiê, contribuições dos agentes e Planos de Jogo.
5. Exibir uma página dedicada com comparação visual e gráficos simples.
6. Aplicar a escalação de um plano como rascunho, sem substituir escalação confirmada.
7. Auditar geração e aplicação.

## Fontes e ingestão 14.2

- primeira fonte: `demo-treinador-sintetico-v1`, criada pelo projeto e rotulada como sintética;
- capacidades iniciais: agenda/resultados e classificação/forma;
- importação JSON segura, atômica, idempotente e isolada por tenant;
- cada registro carrega provedor, versão, hash, licença, atribuição, qualidade e validade;
- adaptador football-data.org usa o mesmo contrato, fica desligado por padrão e não faz rede nos testes;
- datasets StatsBomb, SkillCorner, Metrica, Wyscout e SoccerNet permanecem em P&D conforme licença.

A pesquisa e as restrições de cada fonte estão em
[`docs/research/fontes-gratuitas-treinador-inteligente.md`](../research/fontes-gratuitas-treinador-inteligente.md).

## Interface 14.3

- rota de entrada: `/ia/treinador/`;
- detalhe: `/ia/treinador/partidas/<id>/`;
- cards de forma, disponibilidade, gols, cartões, confiança e idade dos dados;
- gráfico de forma recente e comparação nosso time × adversário;
- campo tático em CSS/SVG com titulares por posição;
- abas para equilibrado, ofensivo e conservador;
- blocos “por onde jogar”, “como defender”, “transições” e “bola parada”;
- alertas claros de dados ausentes ou demonstrativos;
- POST auditável para gerar análise e POST separado para aplicar rascunho.

## Modelo conceitual

- **Dossiê da Partida:** snapshot versionado por partida e tenant.
- **Contribuição do Agente:** recomendação especializada com evidências, confiança e alertas.
- **Plano de Jogo:** cenário consolidado com formação, escalação e instruções.
- **Rascunho de Escalação:** seleção editável derivada de um Plano de Jogo.
- **Fonte de Dados Esportivos:** configuração e política de proveniência.
- **Lote de Importação:** execução rastreável de uma carga.
- **Registro Esportivo Externo:** payload normalizado, versionado e separado dos modelos oficiais.

## Invariantes

- todos os relacionamentos esportivos pertencem ao mesmo tenant;
- um Dossiê referencia uma partida existente e acessível;
- um Plano pertence a exatamente um Dossiê;
- confiança está entre 0 e 100 e não pode existir sem evidências/alerta de ausência;
- jogador indisponível não pode ser sugerido como titular;
- rascunho não altera escalações já confirmadas;
- dados vencidos permanecem identificados como vencidos;
- fonte sintética sempre aparece como demonstrativa na UI.

## Seams de TDD confirmados

1. **Serviço de domínio:** gerar Dossiê e três Planos de Jogo conhecidos para uma partida.
2. **Interface HTTP:** usuário autorizado visualiza apenas análises do tenant ativo.
3. **Ação HTTP:** aplicar um Plano cria/atualiza apenas o rascunho da escalação e gera auditoria.
4. **Contrato de dados:** adaptador local e fixture HTTP normalizam a mesma resposta sem rede real.

## Critérios de aceite

- três cenários diferentes e explicáveis para a mesma partida;
- nenhuma sugestão de atleta indisponível;
- evidência e idade da informação visíveis;
- isolamento por tenant testado nos serviços e endpoints;
- aplicação exige POST, papel permitido e confirmação explícita;
- suíte não acessa internet;
- página funciona sem provider de LLM por meio de fallback determinístico;
- revisão humana continua sendo a autoridade final.

## Evolução posterior

- eventos espaciais, mapas de calor, redes de passe e pitch control;
- ingestão de GPS/RPE e disponibilidade diária;
- análise de vídeo próprio com tags autorizadas;
- provider brasileiro licenciado;
- avaliação pós-jogo que compara recomendação, decisão humana e resultado;
- calibração dos pesos somente após volume e validação suficientes.

## Evolução visual do campo

O campo entregue na primeira fatia é deliberadamente um rascunho funcional. Ele
prova a seleção dos atletas, mas ainda não comunica o Plano de Jogo com qualidade
de comissão técnica. A evolução será incremental:

1. **Formação real:** campo em proporção 105×68, linhas e jogadores posicionados
   por coordenadas relativas específicas para 4-3-3, 4-2-3-1 e 5-3-2.
2. **Funções e relações:** função tática, pé dominante, capitão, limite de minutos,
   distâncias entre setores e conexões prioritárias.
3. **Zonas e movimentos:** corredores, meio-espaços, zonas fortes/fracas, setas de
   progressão, coberturas e gatilhos de pressão.
4. **Dados observados:** mapas de calor, rede de passes, finalizações, recuperações,
   altura do bloco, largura e profundidade — somente quando houver eventos
   coordenados ou tracking suficiente.
5. **Comparação:** sobrepor nosso plano e padrão do adversário, alternar cenários e
   comparar visualmente equilíbrio, risco, intensidade e ocupação.
6. **Interação humana:** arrastar jogador, trocar função, simular substituição e
   recalcular riscos sem publicar a escalação oficial.

Nenhuma camada espacial pode ser simulada como fato. Sem dados adequados, a tela
deve exibir a formação planejada e marcar zonas/movimentos como hipótese.
