# Validação das fontes públicas mostradas na imagem

Pesquisa realizada em 12 de julho de 2026, a partir da imagem fornecida e usando
somente páginas, termos, documentação e repositórios publicados pelas próprias
organizações. Este documento complementa
[`fontes-gratuitas-treinador-inteligente.md`](fontes-gratuitas-treinador-inteligente.md)
e a PRD
[`prd-fontes-reais-providers-ia.md`](../prd/prd-fontes-reais-providers-ia.md).

## Conclusão executiva

**Acesso público não significa open data.** Um site pode permitir consulta humana
gratuita e, ao mesmo tempo, não conceder licença para copiar sua base, automatizar
consultas ou usar os dados em um SaaS comercial. Entre as marcas visíveis, apenas
o **StatsBomb Open Data** oferece um conjunto oficial para download sem chave;
mesmo ele deve permanecer em P&D até revisão do acordo de uso para o caso comercial.

FotMob, Sofascore, oGol, WhoScored, FBref, Understat, Transfermarkt, TransferFeed e
CIES não devem ser tratados como APIs públicas abertas. Endpoints internos vistos
no navegador e bibliotecas de terceiros não são APIs oficiais nem autorização de
uso.

## Identificação dos logotipos

| Posição na imagem | Identificação | Confiança |
|---|---|---|
| Dados públicos, topo | **FotMob** | Alta: símbolo circular e identidade visual compatíveis com o site oficial, mas a resolução não permite leitura textual. |
| Dados públicos, demais | **Sofascore**, **oGol**, **WhoScored**, **FBref**, **Understat** | Alta; nomes ou marcas são legíveis. O logo parcialmente encoberto com bola/ponto de interrogação é compatível com WhoScored. |
| Mercado, topo e base | **Transfermarkt** e **CIES Football Observatory** | Alta; nomes legíveis. |
| Mercado, quadrado “TF” | **Provavelmente TransferFeed** | Média. A identidade é compatível com o serviço de rumores TransferFeed, mas não há texto suficiente na imagem para excluir outra marca “TF”. Não cadastrar esta fonte sem confirmação do autor do slide. |
| Dados de evento | **StatsBomb** | Alta; nome legível. |

## Matriz de decisão

| Fonte | API pública oficial? | Natureza do acesso | Classificação para o SaaS |
|---|---|---|---|
| FotMob | Não localizada | Site/app público; automação proibida | **Não integrar** sem contrato/permissão |
| Sofascore | Não localizada | Site/app público; base protegida e scraping proibido | **Não integrar** sem contrato |
| oGol | Não localizada | Site editorial/estatístico público; direitos reservados | **Condicionado a permissão escrita** |
| WhoScored | Não localizada | Site público; nenhuma licença aberta oficial localizada | **Não integrar** sem licença |
| FBref | Não | Reuso pontual condicionado; automação, banco substituto e uso por IA restringidos | **Não integrar ao Treinador/IA** |
| Understat | Não localizada | Site público com xG; nenhuma licença aberta oficial localizada | **Não integrar** sem permissão |
| Transfermarkt | Não localizada | Site público; reprodução exige consentimento | **Não integrar** sem acordo comercial |
| TransferFeed (provável) | Não localizada | Site/app e produto profissional de inteligência de mercado | **Condicionado a confirmação e contrato** |
| CIES Football Observatory | Não localizada | Resultados, rankings e metodologia públicos; dados de parceiros | **Referência metodológica**, não ingestão |
| StatsBomb Open Data | Arquivos JSON oficiais, não API live | Open Data de amostra com acordo e atribuição | **P&D/open data**; produção somente após clearance |

## Avaliação individual

### FotMob

O [site oficial](https://www.fotmob.com/en/download) informa cobertura de placares,
notícias e estatísticas detalhadas de mais de 500 ligas. A própria FAQ descreve
métricas como xG, xGOT, xA, ações defensivas e traços de jogadores
([FAQ oficial](https://www.fotmob.com/en-GB/faq)).

Não foi localizada documentação de API pública oficial, cadastro de desenvolvedor,
licença aberta, autenticação ou quota publicada. Os
[Termos de Uso](https://www.fotmob.com/term-of-service) proíbem serviços automáticos,
robôs, crawlers, indexação e outros usos sistemáticos ou regulares.

**Decisão:** não consumir endpoints internos nem fazer scraping. Pode ser usado por
um analista como referência visual, mas produção exige autorização/contrato que
defina dados, armazenamento, derivação, atribuição, limites e uso comercial.

### Sofascore

O [site oficial](https://www.sofascore.com/) oferece resultados, tabelas e
estatísticas de partidas e atletas. Não foi localizado portal oficial de API
pública para terceiros; o host `api.sofascore.com` usado pelo próprio produto não
constitui, por si só, uma oferta pública licenciada.

Os [Termos e Condições](https://www.sofascore.com/en-us/terms-and-conditions)
declaram que o conteúdo da base é protegido, vedam extração ou disponibilização
sem consentimento e proíbem requests automatizados, embedding, agregação, scraping
e reprodução sem autorização explícita.

**Decisão:** não integrar nem raspar. Somente produção autorizada após licença
escrita que também esclareça direitos de terceiros presentes nas estatísticas.

### oGol / zerozero

O [oGol](https://www.ogol.com.br/) publica elencos, jogos, fichas, competições,
estatísticas, fotos e notícias. A própria página identifica a ZOS, Lda. como
responsável e mostra “todos os direitos reservados”; sua
[política oficial](https://www.ogol.com.br/helpdesk.php?type=3) trata privacidade e
conta, mas não concede licença aberta sobre a base esportiva.

Não foi localizada API pública oficial, documentação de autenticação, quota ou
licença de dados. A ausência desses instrumentos não autoriza o uso dos dados.

**Decisão:** condicionado a permissão escrita. Até lá, admitir apenas link de
referência ou pesquisa humana; não criar scraper nem importar a base.

### WhoScored

O [site oficial](https://www.whoscored.com/) oferece estatísticas, ratings,
formações, mapas e análises de partidas. Não foi localizada API pública oficial
para terceiros nem uma licença aberta oficial que autorize copiar e operar essa
base no SaaS. Nesta pesquisa também não foi possível obter, a partir do domínio
oficial, uma página de termos suficientemente verificável; por isso nenhuma
restrição específica é atribuída aqui ao WhoScored sem evidência primária.

**Decisão:** não integrar. Pacotes Python e endpoints encontrados por engenharia
reversa são terceiros e não mudam os termos do titular.

### FBref / Sports Reference

O [FBref](https://fbref.com/) disponibiliza tabelas de competições, equipes,
atletas e partidas. Não há API pública oficial do FBref. Os
[Termos da Sports Reference](https://static.fbref.com/termsofuse.html) permitem
reuso pontual com crédito, mas restringem automação que afete o serviço, criação
de banco/serviço substituto e, de forma expressa, uso do conteúdo para treinar,
ajustar, instruir ou **promptar IA**, inclusive para previsão ou classificação.

**Decisão:** não usar como evidência do Treinador Inteligente nem enviar seu
conteúdo aos agentes. Uma licença negociada precisaria permitir explicitamente
ingestão automatizada, armazenamento, derivação e processamento por IA.

### Understat

O [site oficial](https://understat.com/) publica xG e estatísticas de partidas,
times e atletas de seis ligas europeias e apresenta opções de download CSV, JSON
e XLSX. Isso torna os dados acessíveis para download, mas não foi localizada API
pública, documentação de autenticação/limite, licença de dataset ou termos oficiais
que concedam reutilização comercial automatizada.

**Decisão:** não integrar. “JSON visível na página” ou bibliotecas comunitárias
não são licença. Solicitar autorização escrita antes de qualquer ingestão, ainda
que o acesso humano ao site seja gratuito.

### Transfermarkt

O [Transfermarkt](https://www.transfermarkt.com/) oferece perfis, transferências,
elencos, contratos estimados e valores de mercado. Seus
[Termos de Uso](https://www.transfermarkt.com/intern/anb) regem o conteúdo e os
serviços do site; o
[aviso legal oficial](https://www.transfermarkt.com/intern/impressum) informa que
reprodução, inclusão em serviços online ou duplicação, mesmo parcial, só é
permitida com consentimento prévio por escrito.

Não foi localizada API pública oficial. Projetos chamados “Transfermarkt API” em
repositórios de terceiros não representam autorização do Transfermarkt. Valores
de mercado são estimativas/metodologia própria, não taxas oficiais de negócio.

**Decisão:** não raspar nem integrar sem acordo comercial escrito.

### “TF” — provavelmente TransferFeed

O [site oficial do TransferFeed](https://www.transferfeed.com/about) se apresenta
como agregador de rumores em tempo real, com grafo de conhecimento, valuations,
salários e um Market Explorer voltado a clubes, agentes e profissionais. Isso é
compatível com a coluna “Mercado” do slide, mas a identidade do pequeno logo **não
está confirmada**.

Não foi localizado portal de API pública, licença aberta, autenticação ou limites
oficiais. Rumores também exigem proveniência e não devem virar fatos confirmados.

**Decisão:** primeiro confirmar a marca. Se for TransferFeed, tratar como produto
comercial e solicitar proposta/termos de integração; não extrair do site.

### CIES Football Observatory

O [CIES Football Observatory](https://football-observatory.com/) publica relatórios,
rankings e ferramentas de pesquisa. A seção oficial de
[métodos](https://football-observatory.com/-Methods-90-) descreve modelos para
nível de partidas, experiência, performance, estilo e valores de transferência.
Relatórios identificam dados fornecidos por parceiros como Wyscout, InStat,
SkillCorner ou Impect, conforme o estudo; publicação de um ranking não transfere
direitos sobre a base subjacente.

Não foi localizada API pública nem licença aberta para baixar e reutilizar a base.

**Decisão:** usar relatórios como referência metodológica citada e como benchmark
humano. Qualquer ingestão estruturada depende de autorização do CIES e, quando
aplicável, dos fornecedores subjacentes.

### StatsBomb Open Data

O [repositório oficial](https://github.com/statsbomb/open-data) fornece arquivos
JSON de competições, partidas, escalações, eventos e dados 360 para partidas
selecionadas. Não exige chave e é exportado do produto StatsBomb, mas é uma seleção
histórica, não uma API operacional ao vivo. O README limita a finalidade declarada
a pesquisa/projetos de interesse genuíno em analytics e exige atribuição e logo ao
publicar; o repositório contém um
[acordo de uso](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf).

**Decisão:** aprovada para ambiente isolado de P&D, testes e protótipos de mapas,
redes, xG e explicabilidade. Não misturar automaticamente com recomendações de
produção nem redistribuir em nosso SaaS antes de revisão jurídica/autorização.

## Ordem segura de integração

1. **Dados internos autorizados do clube**, já previstos na arquitetura, continuam
   sendo a fonte de produção para atletas, disponibilidade, carga, modelo de jogo,
   vídeo e eventos próprios.
2. **football-data.org**, já validado na pesquisa anterior, permanece o primeiro
   adaptador externo do MVP para agenda, resultados, tabela e forma básica.
3. **StatsBomb Open Data** entra somente no ambiente `research_sample`, com versão,
   licença, atribuição e expiração registradas, para desenvolver algoritmos
   espaciais sem alegar cobertura do próximo adversário.
4. **Solicitação comercial em lote** a FotMob, Sofascore, oGol, WhoScored,
   Transfermarkt e, após confirmação, TransferFeed: pedir API/feed, cobertura do
   Brasil, direitos de derivação/IA, cache, retenção, exibição, SLA e preço.
5. **CIES** permanece referência metodológica; uma parceria só avança se houver
   direitos claros sobre os dados dos parceiros usados em cada produto.
6. **FBref e Understat ficam fora do pipeline** enquanto não houver permissão
   específica. No caso do FBref, a proibição explícita de uso por IA é incompatível
   com o Treinador Inteligente atual.

Nenhuma conexão deve ser marcada `active` apenas porque o site é público. O gate
da PRD continua obrigatório: identidade confirmada, documentação oficial, teste de
credencial, licença comercial, atribuição, retenção, fixture contratual e aprovação
administrativa.
