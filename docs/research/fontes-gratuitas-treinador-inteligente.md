# Fontes gratuitas para o Treinador Inteligente

> Complemento: a lista de FotMob, Sofascore, oGol, WhoScored, FBref, Understat,
> Transfermarkt, possível TransferFeed, CIES e StatsBomb enviada posteriormente
> foi verificada em
> [Validação das fontes públicas mostradas na imagem](fontes-publicas-imagem-validacao.md).
> Sites públicos não foram classificados automaticamente como dados abertos.

Pesquisa realizada em 12 de julho de 2026, usando apenas documentação, repositórios e termos publicados pelos próprios provedores.

## Conclusão executiva

Não existe hoje uma fonte gratuita única que entregue, com segurança jurídica e cobertura do futebol brasileiro, todos os dados necessários para um treinador inteligente comercial. O MVP deve combinar:

1. **Dados do próprio clube** como fonte principal de disponibilidade, carga, saúde, treino, modelo de jogo e desempenho dos atletas.
2. **football-data.org no plano gratuito** para calendário, resultados, classificação e contexto básico do Brasileirão Série A. É a opção gratuita mais útil para o contexto brasileiro, mas não fornece eventos espaciais, tracking ou xG no plano grátis.
3. **StatsBomb Open Data, SkillCorner Open Data e Metrica Sports Sample Data** somente para pesquisa, prototipagem, validação de modelos e demonstrações controladas. São amostras históricas, não um feed operacional do próximo adversário brasileiro.
4. **API-Football** apenas como experimento de cobertura/granularidade. O plano grátis é limitado a 100 chamadas por dia e o próprio provedor declara que não concede licença para publicação ou direitos comerciais sobre as competições.
5. **Sportmonks Free Plan** apenas como sandbox técnico: cobre duas ligas europeias; xG, tracking e vários recursos avançados exigem plano/add-on.

Recomendação: construir uma camada de provedores substituível, começar com `club_internal + football_data_org`, manter datasets de pesquisa em ambiente separado e não prometer análise tática espacial real enquanto o clube não fornecer vídeo/eventos/tracking próprios ou contratar um feed licenciado.

## Matriz comparativa

| Fonte | Categoria | Cobertura gratuita relevante | Jogos/escalações/eventos | Coordenadas/tracking/xG | Autenticação e limite | Licença e uso comercial | Uso recomendado no MVP |
|---|---|---|---|---|---|---|---|
| StatsBomb Open Data | Open data com acordo próprio | Seleção histórica de competições e temporadas; não é feed completo nem focado no Brasil | Jogos, escalações e eventos detalhados | Localização de eventos, `shot_statsbomb_xg`; 360 em partidas selecionadas | Arquivos JSON no GitHub, sem chave; sujeito aos limites/antiabuso do GitHub | README limita o propósito a pesquisa/interesse genuíno e exige atribuição/logo; o `LICENSE.pdf` deve ser validado juridicamente antes de qualquer uso comercial | Pesquisa de xG, mapas de passe, pressão e explicabilidade; não usar como base comercial sem autorização |
| SkillCorner Open Data | Open data de amostra | 10 jogos da A-League 2024/25 + agregados da temporada | Escalações, tracking, eventos dinâmicos e fases de jogo | Jogadores/bola a 10 fps, coordenadas métricas; métricas físicas, corridas sem bola e passe; sem xG declarado | Download no GitHub, sem chave | Repositório marcado MIT e pede crédito; confirmar por escrito se a licença cobre todos os arquivos de dados antes de produção | Excelente para prototipar compactação, largura, profundidade, transições e carga física |
| Metrica Sports Sample Data | Amostra gratuita de fornecedor | 3 jogos anonimizados | Eventos e tracking sincronizados | Jogadores/bola, coordenadas e formato FIFA EPTS; xG não fornecido | Download no GitHub, sem chave | README pede uso responsável e atribuição, mas não exibe licença padronizada no repositório | Laboratório local de pitch control/EPV; não incluir no produto comercial sem permissão escrita |
| football-data.org Free | Free tier, não open data | 12 competições, incluindo Campeonato Brasileiro Série A | Fixtures, resultados atrasados e tabelas; escalações/substituições e artilheiros ficam em pacote pago | Sem coordenadas, tracking ou xG no grátis | `X-Auth-Token`; 10 chamadas/minuto | Termos exigem atribuição, chave por aplicação e impedem manter/exibir dados após cancelamento; logos exigem direitos próprios | Contexto operacional do Brasileirão: agenda, tabela, forma simples e adversário |
| API-Football Free | Free tier, não open data | Todas as competições/endpoints, mas temporadas disponíveis são limitadas | Fixtures, eventos, escalações, estatísticas de times/jogadores, lesões, suspensões e transferências, quando cobertos | Grid de posição da escalação; documentação não promete tracking/eventos com coordenadas nem xG bruto | Header `x-apisports-key`; 100 chamadas/dia | O provedor diz expressamente que não concede licença de publicação nem direitos comerciais sobre as competições; usuário deve obter autorizações | Prova técnica temporária; não publicar dados derivados sem clearance jurídico/comercial |
| Sportmonks Free | Free tier, não open data | Scottish Premiership e Danish Superliga | Fixtures, times, jogadores, escalações, eventos e estatísticas conforme cobertura/plano | A plataforma possui ball coordinates e xG, mas xG exige pacote e recursos podem ser premium/delayed | `api_token`; limite gratuito não está claramente publicado na tabela oficial consultada; planos pagos limitam por entidade/hora | Produção é suportada, mas assinatura e direitos de imagens/logos seguem termos; não presumir que “free” transfere direitos de redistribuição | Sandbox de integração e validação de adaptador; não resolve adversários brasileiros |
| OpenLigaDB | Open database comunitária | Ligas criadas/mantidas pela comunidade, forte viés alemão | Jogos, placares, rodadas, tabelas e gols básicos | Sem escalações táticas, coordenadas, tracking ou xG | API JSON sem autenticação; nenhum rate limit formal publicado | Dados sob ODbL: permite uso com atribuição e obrigações de share-alike para banco derivado aplicável | Fallback para placares/fixtures e teste do pipeline, não para inteligência tática |
| OpenFootball / football.json | Open data comunitário | Grandes ligas e históricos variados; atualização por comunidade | Calendários, rodadas e placares | Sem escalações, eventos espaciais, tracking ou xG | Arquivos JSON via GitHub, sem chave | Dados/esquema em domínio público/CC0 segundo o projeto | Bootstrap de histórico e testes; não tratar como fonte oficial nem em tempo real |
| CBF (site e súmulas) | Fonte oficial pública, **não open data** | Competições brasileiras, páginas de jogos e súmulas em PDF | Resultados, atletas e documentos, dependendo da competição | Sem API pública documentada, coordenadas ou xG | Navegação web; nenhuma API pública/licença aberta localizada | Termos vedam cópia, reprodução, distribuição e utilização não autorizada, comercial ou não | Apenas links e importação manual autorizada; **não raspar** o site |

## Avaliação por fonte

### 1. StatsBomb Open Data

O [repositório oficial](https://github.com/statsbomb/open-data) publica JSON de competições/temporadas, jogos, escalações, eventos e dados 360 em partidas selecionadas. Isso oferece a melhor granularidade gratuita para desenvolver mapas de passe, redes, zonas de criação, pressão, finalizações e modelos de xG. A cobertura é uma seleção histórica variável, não uma API ao vivo nem garantia de que o próximo adversário estará presente.

Não confundir “Open Data” no nome com licença comercial irrestrita. O próprio README diz que os dados são disponibilizados para projetos de pesquisa e interesse genuíno em analytics e exige crédito à StatsBomb e uso do logo ao publicar análises. O repositório inclui um [acordo de usuário em PDF](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf). Para um SaaS comercial, tratar a fonte como **não liberada para produção** até revisão jurídica ou autorização da StatsBomb.

**Decisão:** usar em dataset isolado de P&D e em testes de algoritmos; armazenar `provider`, versão/commit, competição, temporada e os requisitos de atribuição em cada importação.

### 2. SkillCorner Open Data

O [repositório oficial da SkillCorner](https://github.com/SkillCorner/opendata) contém 10 partidas da A-League 2024/25. Por jogo há escalação, tracking extrapolado de jogadores e bola a 10 fps, eventos dinâmicos e fases de jogo; também existem agregados físicos, corridas sem bola e passes da temporada. As coordenadas são expressas em metros e os dados permitem protótipos reais de compactação, linhas defensivas, ocupação de corredores, velocidade, aceleração e transições.

O GitHub identifica o repositório como MIT e o README solicita crédito. Como a licença padrão foi aplicada ao repositório inteiro, a confiança é maior que na amostra da Metrica; ainda assim, para exploração comercial com dados esportivos, é prudente pedir confirmação do provedor de que os arquivos de dados também estão sob MIT. A amostra não cobre Brasil e não atualiza o próximo adversário.

**Decisão:** primeira escolha para laboratório espacial e para criar fixtures determinísticos de testes.

### 3. Metrica Sports Sample Data

O [repositório oficial da Metrica Sports](https://github.com/metrica-sports/sample-data) oferece três jogos anonimizados, com tracking de jogadores/bola e eventos sincronizados; o terceiro usa FIFA EPTS para tracking/metadados. É excelente para pitch control, EPV e visualização tática.

O texto legal publicado apenas pede uso responsável e atribuição; não há licença padronizada exibida. Disponibilidade pública não equivale a licença de exploração comercial.

**Decisão:** laboratório local e demonstração interna; não redistribuir nem treinar ativo comercial persistente sem autorização escrita.

### 4. football-data.org

O [plano gratuito oficial](https://www.football-data.org/pricing) fornece 12 competições, fixtures, agenda/placares atrasados e tabelas, com 10 chamadas por minuto. A [cobertura oficial](https://www.football-data.org/coverage) inclui o Campeonato Brasileiro Série A. O acesso usa chave `X-Auth-Token`, conforme o [quickstart oficial](https://www.football-data.org/documentation/quickstart).

O plano gratuito não entrega a granularidade necessária para “por onde jogar”: escalações/substituições e artilheiros aparecem em pacotes pagos; não há tracking, coordenadas de eventos ou xG no free. Os [termos](https://www.football-data.org/about) exigem atribuição visível, restringem a chave a uma aplicação, proíbem guardá-la em repositório público, exigem direitos separados para logos e impedem continuar exibindo os dados após o cancelamento.

**Decisão:** melhor fonte gratuita para agenda, tabela e forma básica do adversário brasileiro. Implementar cache curto com expiração e remoção dos dados ao encerrar a assinatura.

### 5. API-Football

O [plano gratuito oficial](https://www.api-football.com/pricing) oferece 100 chamadas/dia, todos os endpoints e competições, mas limita temporadas. A [documentação](https://www.api-football.com/documentation-beta) usa o header `x-apisports-key` e expõe fixtures, eventos, escalações, grids posicionais, estatísticas, jogadores, lesões, suspensões e transferências. Eventos básicos são gol, cartão, substituição e VAR; isso é útil, mas não equivale a um event stream espacial ou tracking.

O risco jurídico é alto: nos [termos oficiais](https://www.api-football.com/terms), o provedor afirma que não concede licença de uso/publicação e nenhum direito comercial sobre competições; cabe ao cliente obter autorizações dos titulares. O plano pode mudar sem aviso.

**Decisão:** integrar somente atrás de feature flag para avaliar cobertura. Não exibir nem usar seus dados em recomendações comerciais até clearance documentado.

### 6. Sportmonks

O [Free Plan oficial](https://www.sportmonks.com/football-api/free-plan/) é gratuito sem expiração, mas cobre apenas Scottish Premiership e Danish Superliga. A plataforma expõe fixtures, eventos, escalações, estatísticas e dados avançados; a [documentação de lineups](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/includes/lineups) traz titulares, banco, formação e posição. Existem [xG por atleta](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/expected-xg/get-expected-by-player) e [ball coordinates](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/includes), mas esses recursos variam por pacote e podem exigir add-on; a própria documentação de erros exemplifica que xG não está no plano básico.

A autenticação é por `api_token`. Os [limites oficiais](https://docs.sportmonks.com/v3/api/rate-limit) são por entidade/hora; a tabela consultada publica números dos planos pagos, não um número inequívoco para o Free Plan. Os [termos](https://www.sportmonks.com/terms-of-service/) exigem que o cliente cuide dos direitos de logos e fotos.

**Decisão:** útil para testar um adaptador rico, mas inadequado ao MVP brasileiro e insuficiente para xG/tracking gratuito em produção.

### 7. OpenLigaDB e OpenFootball

A [OpenLigaDB oficial](https://openligadb.de/) é comunitária, não exige autenticação e publica dados sob ODbL. A [API documentada](https://api.openligadb.de/index.html) oferece ligas, jogos, rodadas e consultas por time. Não há rate limit formal publicado; portanto, usar cache, `If-Modified-Since` quando possível e baixa frequência. A ODbL requer atenção a atribuição e compartilhamento do banco derivado aplicável.

O [OpenFootball/football.json](https://github.com/openfootball/football.json) publica fixtures e placares em JSON por GitHub e declara dados/esquema em domínio público. É simples e permissivo, mas comunitário, sem SLA e sem dados táticos.

**Decisão:** bons para histórico básico, fixtures de teste e fallback; nunca elevar sua confiança ao nível de um feed oficial de clube/competição.

### 8. CBF e federações

A CBF publica páginas de partidas e [súmulas](https://www.cbf.com.br/futebol-brasileiro/noticias/detalhes/competicoes-campeonato-brasileiro-serie-a/cbf-divulga-sumulas-de-partidas-do-campeonato-brasileiro-serie-a-b-e-c), mas não foi localizada API pública documentada nem licença aberta. Os [Termos de Uso da CBF](https://www.cbf.com.br/termos-de-uso) vedam cópia/reprodução e utilização comercial ou não comercial sem autorização específica.

**Decisão:** não criar scraper. Admitir somente URL de referência, upload manual de documento que o clube tenha direito de usar, ou integração formal autorizada por CBF/federação.

## Kaggle e scraping

Nenhum dataset do Kaggle foi aprovado nesta pesquisa. Estar no Kaggle ou possuir botão de download não prova que quem publicou é titular dos dados nem que a licença permite uso comercial. Aceitar futuramente apenas datasets publicados pela conta oficial do provedor/federação, com licença do dataset e cadeia de origem verificáveis.

Também ficam fora do MVP scrapers de CBF, sites de resultados, notícias, FBref, SofaScore, Transfermarkt, Understat ou páginas de clubes. Ausência de bloqueio técnico não é permissão. Scraping cria risco de termos de uso, direitos sobre bases de dados, marca/imagem, instabilidade de HTML e banimento de IP.

## Arquitetura de ingestão recomendada

Criar uma interface por capacidade, não por fornecedor:

```text
ProviderAdapter
├── fixtures_and_results()
├── standings_and_form()
├── squads_and_availability()
├── lineups_and_formations()
├── match_events()
├── spatial_events()
├── tracking_frames()
└── expected_metrics()
```

Cada registro importado deve carregar:

- `tenant`, `provider`, `provider_record_id` e versão do schema;
- competição, temporada, partida e timestamp de coleta;
- licença/termo aceito, URL da fonte e obrigação de atribuição;
- nível de cobertura e qualidade (`official`, `licensed_provider`, `club_internal`, `community`, `research_sample`);
- validade/expiração e política de exclusão;
- campos de confiança e ausência explícita; `null` não pode virar zero.

Separar fisicamente:

- **produção:** dados internos do clube e feeds com direitos confirmados;
- **P&D:** StatsBomb, SkillCorner e Metrica, sem mistura com recomendações comerciais;
- **demonstração:** dados sintéticos ou amostras claramente rotuladas.

## Sequência prática para o MVP

1. Importar dados próprios do clube: RPE, minutos, GPS (quando houver), testes físicos, lesões/restrições, posição/função, treinos, escalações e eventos manuais.
2. Integrar football-data.org para Série A, agenda, tabela e resultados, respeitando atribuição e 10 chamadas/minuto.
3. Criar laboratório com StatsBomb para eventos/xG e SkillCorner para tracking/fases; usar isso para desenvolver os algoritmos, não para afirmar que conhece o próximo adversário.
4. Permitir upload CSV/JSON e vídeo/anotações do analista, com proveniência e autorização explícitas.
5. Só habilitar recomendações espaciais do adversário quando houver no mínimo 5 partidas recentes com eventos coordenados ou tracking e qualidade mensurada.
6. Antes do piloto comercial, negociar um feed brasileiro licenciado ou parceria direta com clubes/competição.

## Veredito

O MVP gratuito pode ser inteligente em **seleção de atletas, disponibilidade, forma, comparação de cenários e explicação**, porque esses dados podem vir do próprio clube. Ele pode conhecer calendário/tabela do adversário via football-data.org. Porém, afirmar com rigor “ataque o corredor esquerdo” ou “pressione a saída pelo zagueiro X” exige eventos espaciais, tracking ou vídeo anotado recente — dado que as fontes gratuitas pesquisadas não fornecem de modo contínuo, comercialmente seguro e com cobertura brasileira.

Portanto, a promessa correta é: **primeiro um treinador inteligente alimentado pelos dados do clube, com laboratório tático open-data; depois inteligência de adversário em produção quando houver fonte licenciada ou captura própria autorizada.**

## Fontes complementares por especialidade

Além dos provedores puramente esportivos, o produto pode enriquecer o Dossiê da
Partida com fontes abertas de clima, logística e ciência. Elas não substituem os
dados do clube nem autorizam diagnóstico médico.

| Especialidade | Fonte primária | Dados aproveitáveis | Limites e licença | Decisão |
|---|---|---|---|---|
| Clima de jogo | [Open-Meteo](https://open-meteo.com/en/pricing) | Temperatura, chuva, vento, umidade e radiação por coordenada | Dados CC BY 4.0; endpoint gratuito é para avaliação/não comercial, até 10 mil chamadas/dia e sem SLA; produção comercial usa endpoint contratado | MVP em modo de demonstração; conector substituível para produção |
| Clima histórico | [NASA POWER](https://power.larc.nasa.gov/docs/services/api/) | Séries meteorológicas globais e contexto climático | Serviço gratuito; resolução espacial é ampla e dados consolidados podem substituir os quase reais depois de 2–3 meses | P&D e histórico; não usar como previsão fina de estádio |
| Estádios e viagem | [OpenStreetMap](https://www.openstreetmap.org/copyright/en) + [política Nominatim](https://operations.osmfoundation.org/policies/nominatim/) | Coordenadas, altitude disponível, endereço e distância aproximada | Dados ODbL; Nominatim público limita a 1 requisição/s, exige identificação/atribuição, cache e proíbe uso sistemático/bulk | Geocodificar estádio uma vez e armazenar proveniência; não usar autocomplete nem consultas em massa |
| Ciência esportiva | [OpenAlex](https://help.openalex.org/hc/en-us/articles/24397762024087-Pricing) | Metadados e descoberta de estudos sobre carga, recuperação, prevenção e tática | CC0; plano gratuito com até 100 mil chamadas/dia e 10/s; metadados não significam que o texto integral seja reutilizável | Índice do agente científico, sempre apontando ao estudo original |
| Texto científico reutilizável | [PubMed Central OAI-PMH](https://pmc.ncbi.nlm.nih.gov/tools/oai/) | Metadados e texto integral de artigos cujo direito permite reutilização | 3 requisições/s; somente o conjunto `pmc-open` garante recuperação e cada licença continua registrada no artigo | Base documental curada; nunca converter evidência populacional em diagnóstico individual |
| Vídeo e reconhecimento de ações | [SoccerNet](https://www.soccer-net.org/faq) | Vídeos/annotations para action spotting, replay e compreensão audiovisual | O próprio projeto limita o dataset a pesquisa e declara que não se destina a uso comercial; vídeo exige NDA | P&D apenas; produção deve usar vídeo próprio/autorizado do clube |
| Eventos espaço-temporais históricos | [Wyscout/Figshare](https://figshare.com/collections/Soccer_match_event_dataset/4415000/2) | Passes, chutes, faltas e outros eventos de temporadas completas de sete competições | Coleção acadêmica histórica; validar a licença de cada artefato e não confundir com acesso à API comercial Wyscout | Treino e validação de algoritmos, não feed operacional |

### Matriz agente × fontes

| Agente especialista | Fontes de produção no MVP | Fontes de laboratório/P&D | Saída responsável |
|---|---|---|---|
| Coordenador Técnico | Dados internos, calendário e tabela via football-data.org | Todos os datasets já normalizados | Consolida conflitos e gera três planos comparáveis |
| Analista Tático | Escalações/eventos próprios e vídeo anotado autorizado | StatsBomb, SkillCorner, Metrica e Wyscout/Figshare | Formação, zonas, padrões, pressão e transições com evidências |
| Especialista Ofensivo | Finalizações, passes, cruzamentos e bolas paradas do clube | StatsBomb/Wyscout históricos | Onde progredir, criar superioridade e finalizar |
| Especialista Defensivo | Eventos sofridos, duelos, bolas paradas e escalações próprias | StatsBomb/SkillCorner | Bloco, encaixes, cobertura e gatilhos de pressão |
| Preparador Físico | GPS/RPE, minutos, testes e restrições fornecidos pelo clube | SkillCorner/Metrica e literatura curada | Disponibilidade, limite de minutos e risco de carga; sem diagnóstico |
| Olheiro | Observações e avaliações próprias, elenco/agenda licenciados | Dados históricos open-data | Perfil, encaixe no modelo e lacunas de observação |
| Especialista em Ambiente | Estádio, viagem, fuso, clima e altitude com proveniência | NASA POWER e amostras históricas | Ajustes de hidratação, aquecimento e logística, como apoio |
| Agente Científico | Protocolos internos aprovados e literatura licenciada/aberta | OpenAlex e PMC Open Access | Resume evidência e grau de certeza; não prescreve tratamento |

### Dados que ainda precisam ser inseridos pelo clube

Nenhuma fonte gratuita pesquisada substitui estes dados operacionais:

- disponibilidade diária, lesões/restrições autorizadas e retorno progressivo;
- RPE, GPS, distância, aceleração, velocidade máxima e carga aguda/crônica;
- modelo de jogo, funções por posição e princípios do treinador;
- vídeos próprios, tags do analista e contexto de cada evento;
- pé dominante, posições/funções, entrosamento e limite individual de minutos;
- avaliação qualitativa do olheiro e aderência comportamental;
- gramado, viagem real, sono, fuso e logística do clube.

Esses dados devem ter consentimento, finalidade, retenção e acesso por papel. Dados
de saúde e biometria nunca devem ser enviados indiscriminadamente a um provider de
IA externo.
