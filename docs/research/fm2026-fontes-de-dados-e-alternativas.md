# FM26: fontes de dados, licenciamento e alternativas para o SaaS

Pesquisa concluída em **12 de julho de 2026**, usando somente páginas, termos e
documentação publicados pela Sports Interactive (SI), SEGA e pelos fornecedores
citados. O objetivo é responder duas perguntas: de onde vêm os dados do Football
Manager 2026 e quais dados semelhantes podem ser usados legalmente por este SaaS.

## Resposta curta

O FM26 não é alimentado por uma única API pública. Sua base combina:

1. uma rede humana de aproximadamente **1.300 pesquisadores em 50 países**;
2. pesquisa própria e validação interna da SI;
3. observação de partidas e treinos, fontes públicas e relações com clubes, ligas
   e associações;
4. licenças de nomes, marcas, imagens, clubes e competições;
5. desde julho de 2026, dados de eventos, tracking e métricas físicas fornecidos
   exclusivamente pela **Hudl**, com intercâmbio de dados com o Wyscout.

A base resultante é propriedade da SI. O jogo e seus editores não concedem direito
de copiá-la para uso comercial. Existe, porém, uma oferta oficial: **FMDB Pro**.
Ela pode ser licenciada por clubes profissionais para scouting e análise interna,
mediante contrato e pagamento. Os termos públicos atuais não permitem que uma
empresa de SaaS redistribua esses dados entre seus tenants. Para isso seria
necessário negociar diretamente com a SI um contrato diferente e explícito.

## Situação atual do FM26

O FM26 foi lançado em 4 de novembro de 2025. Em julho de 2026 ele é a edição atual
e recebeu a expansão de seleções, inclusive com a licença da seleção masculina da
Alemanha. A [lista oficial de licenças do FM26](https://www.footballmanager.com/news/football-manager-26-licences)
inclui FIFA, UEFA, Premier League, EFL e diversas ligas e clubes. Licenciar uma
competição para aparecer no jogo, contudo, não significa que seus dados possam ser
repassados a terceiros.

## Como a Sports Interactive constrói a base

A [política oficial para profissionais do futebol](https://www.sports-interactive.com/privacy-policy-professionals)
é a fonte mais direta sobre o processo:

- a rede tem aproximadamente 1.300 pessoas em 50 países;
- os pesquisadores assistem a partidas e treinos, consultam informações públicas
  e recebem informações por relações com clubes, ligas e associações;
- a equipe interna da SI revisa e cruza dados e fontes;
- os profissionais recebem avaliações subjetivas em mais de 30 categorias
  técnicas, mentais e físicas, construídas durante semanas, meses e anos;
- a SI não garante que essas avaliações sejam exatas.

Portanto, atributos como decisão, antecipação, liderança ou potencial não são um
feed factual pronto: são uma **avaliação editorial proprietária**, produzida e
validada pela rede do FM.

### Licenças de competições

A [lista de licenças](https://www.footballmanager.com/news/football-manager-26-licences)
explica a autenticidade de nomes, marcas, uniformes, imagens e competições. A
parceria da EFL, por exemplo, torna 72 clubes e cinco competições licenciados no
FM26 ([anúncio oficial](https://www.footballmanager.com/news/efl-and-football-manager-extend-winning-partnership)).
Esses acordos são direitos concedidos ao produto Football Manager, não uma licença
aberta para usuários do jogo ou para nosso SaaS.

### Eventos, tracking e métricas físicas

Em 1º de julho de 2026, a SI anunciou a Hudl como seu fornecedor exclusivo de
dados de eventos e métricas físicas e seu único fornecedor de dados de eventos e
tracking. O acordo prevê compartilhamento bidirecional, reforçando a base Hudl
Wyscout e futuras edições do FM. O Wyscout também passou a estar integrado ao
FMDB Pro ([anúncio oficial da SI](https://www.sports-interactive.com/sv/node/463069)).

Isso indica que, para dados de partida detalhados, a origem contratável relevante
não é o arquivo do FM26: é a própria oferta comercial da Hudl Wyscout.

### Transferências

O FM26 também reproduz fluxos inspirados no **TransferRoom**, mas o anúncio diz
que a colaboração inspira as ferramentas de recrutamento do jogo; não declara que
o TransferRoom fornece toda a base de atletas ou transfere uma licença de dados
aos jogadores ([explicação oficial](https://www.footballmanager.com/fm26/features/powered-transferroom-fm26s-recruitment-revamp)).

## O que existe oficialmente para reutilização

### FMDB Pro

O FMDB Pro é a plataforma profissional da SI para a etapa inicial de identificação
de atletas e membros de comissão. Clubes como Vancouver Whitecaps e Dinamo Zagreb
receberam acesso em parcerias oficiais
([Whitecaps](https://www.footballmanager.com/index.php/news/football-manager-sign-vancouver-whitecaps-official-club-partner),
[Dinamo Zagreb](https://www.footballmanager.com/news/dinamo-zagreb-signed-official-football-manager-partner)).

Os [termos oficiais de fornecimento da FM Database](https://cdn.sports-interactive.com/site/2024-11/SI%20-%20FMDB%20Portal%20-%20Data%20Supply%20License%20Terms%20-%2015%20November%202024%20-%20JC%20%28FINAL%29.pdf)
revelam os limites concretos:

- a base contém aproximadamente 600 mil profissionais;
- o cliente recebe apenas o subconjunto definido no pedido comercial;
- a entrega pode ocorrer pela plataforma da SI ou por SFTP/transferência segura;
- há preço, prazo, usuários autorizados e requisitos de segurança;
- o propósito permitido é análise técnica, scouting e avaliação nas operações
  internas de um **clube profissional**;
- a licença é não transferível e não sublicenciável;
- os dados não podem ser divulgados a terceiros ou afiliadas, nem integrados
  permanentemente a outro dataset;
- scraping, engenharia reversa, redistribuição e criação de derivados fora do
  propósito limitado são proibidos;
- o clube se torna controlador independente dos dados pessoais e não pode tomar
  decisões significativas exclusivamente com base na base do FM.

**Conclusão para este projeto:** FMDB Pro pode ser uma opção se o cliente contratante
for o próprio clube e a arquitetura garantir acesso interno isolado. Os termos
publicados não cobrem nosso uso normal como SaaS multi-tenant. A SI precisaria
autorizar expressamente o operador SaaS, subprocessamento, exibição aos tenants,
persistência, derivados, uso por IA e encerramento/deleção.

### Jogo, editor e arquivos exportados

O editor existe para criar modificações que são carregadas no jogo. Isso não o
transforma em ferramenta de exportação comercial. O
[EULA oficial publicado pela SEGA](https://privacy.sega.com/en/fm24-eula-end-user-license-agreement)
concede uso pessoal e não comercial, reserva a propriedade à SEGA/licenciadores,
proíbe exploração comercial, redistribuição, engenharia reversa e obras derivadas
fora das permissões expressas. Embora a página disponível esteja identificada como
FM24, ela é evidência oficial do regime da série; antes de qualquer operação com
FM26 deve-se obter e revisar o EULA específico instalado com essa edição.

Arquivos de editor, saves, skins, views exportadas e APIs comunitárias não são uma
API oficial da FM Database e não concedem licença sobre os dados subjacentes.

## Matriz de decisão

| Opção | Elencos/perfis | Atributos qualitativos | Mercado/contratos | Eventos/espacial | Uso no SaaS |
|---|---:|---:|---:|---:|---|
| Banco extraído do FM26 | Sim | Sim | Sim | Parcial | **Não usar**: EULA, direitos de base e licenças de terceiros |
| FMDB Pro, termos padrão | Sim | Sim | Sim | Hudl integrado | **Não atende SaaS multi-tenant**; elegível para uso interno de clube |
| FMDB Pro, contrato customizado | Sim | Sim | Sim | Conforme pedido | **Avaliar comercialmente** com autorização expressa da SI |
| Hudl Wyscout Data API | Sim | Métricas de performance | Conforme pacote | Sim, inclusive pacote físico | **Candidato forte**, sujeito a proposta/licença |
| Stats Perform/Opta | Sim | Métricas derivadas | Conforme pacote | Eventos e tracking | **Candidato forte**, sujeito a proposta/licença |
| football-data.org | Básico | Não | Campos podem ser nulos | Resultados/escalações, sem tracking | **Bom MVP**, após confirmar plano e termos comerciais |
| StatsBomb Open Data | Amostra | Não | Não | Eventos e 360 selecionado | **P&D/benchmark**, não base operacional completa |
| Dados do próprio clube | Sim | Avaliação própria | Sim | GPS, RPE, vídeo e eventos próprios | **Fonte principal recomendada**, com governança/LGPD |

## Alternativas legalmente contratáveis

### 1. Dados internos do clube

É a alternativa mais próxima do método do FM: cadastro oficial, contratos,
avaliação humana estruturada, observação recorrente e histórico. O SaaS pode criar
sua própria escala de atributos, registrar autor, evidência, data e confiança e
aprender com resultados, sem copiar notas ou taxonomia proprietária do FM.

Recomendação: combinar fatos objetivos com pareceres da comissão técnica; nunca
apresentar atributos subjetivos como fatos. Dados médicos e físicos exigem base
legal, minimização e controle de acesso reforçado.

### 2. Hudl Wyscout

A [oferta oficial Data API](https://www.wyscout-apps.hudl.com/products/wyscout/data-api)
prevê integração via APIs, dashboards, análise de partidas e pacote de métricas
físicas. É a alternativa mais alinhada ao stack atual do próprio FM26. Deve-se
solicitar proposta específica para SaaS B2B multi-tenant, incluindo direitos de
armazenar, derivar, mostrar ao cliente e enviar dados aos providers de IA.

### 3. Stats Perform / Opta

A Opta oferece dados padronizados de eventos para análise de atletas e equipes; o
[Opta Vision](https://www.statsperform.com/products/opta-vision/) combina eventos
e tracking e disponibiliza feeds para movimentos sem bola, intensidade e pressão.
É apropriado para mapas, redes, pitch control e modelos táticos, mediante contrato
com cobertura e direitos adequados.

### 4. football-data.org

A [API oficial](https://www.football-data.org/) oferece placares, agenda, tabelas,
elencos, escalações e substituições; competições principais têm plano gratuito e
há planos pagos. A [documentação v4](https://www.football-data.org/documentation/quickstart)
mostra equipes, atletas, contratos e valor de mercado, mas muitos campos podem ser
nulos. É uma boa fonte de baixo custo para o primeiro conector, não substitui a
profundidade qualitativa do FM nem eventos espaciais.

Antes do lançamento comercial, confirmar por escrito que o plano escolhido permite
cache, exposição dentro de produto pago, retenção histórica e processamento por IA.

### 5. StatsBomb Open Data

O [repositório oficial](https://github.com/statsbomb/open-data) contém competições,
partidas, escalações, eventos e dados 360 selecionados. É excelente para desenvolver
e validar o modelo espacial com dados reais, atribuição e limites do acordo. Não
oferece cobertura operacional completa nem deve ser promovido automaticamente a
feed comercial sem clearance específico.

## Recomendação para o SaaS

Não extrair dados do FM26. Adotar uma arquitetura de fontes combinadas:

1. **Dados internos autorizados** como verdade sobre elenco, contratos,
   disponibilidade, carga e avaliação humana.
2. **football-data.org** como primeiro conector de agenda, resultados, tabelas e
   elencos, após confirmação comercial.
3. **StatsBomb Open Data** somente para P&D dos componentes espaciais.
4. Solicitar proposta de **Hudl Wyscout** e **Opta**, comparando cobertura do Brasil,
   eventos, tracking, SLA, cache, derivados, IA e sublicenciamento aos tenants.
5. Contatar a SI sobre **FMDB Pro** apenas como trilha comercial exploratória. A
   pergunta central não é “há API?”, mas “a SI licencia a um operador SaaS
   multi-tenant a exibição e o processamento dos dados para clubes clientes?”.
6. Construir uma camada própria de **avaliação qualitativa com evidências**, sem
   copiar nomes, notas ou metodologia proprietária do Football Manager.

### Perguntas obrigatórias aos fornecedores

- O licenciado pode ser um SaaS que atende vários clubes?
- Podemos mostrar dados brutos ou apenas derivados aos tenants?
- Cache, retenção histórica, treinamento/inferência de IA e exportação são
  permitidos?
- Quais competições brasileiras e femininas estão cobertas?
- Quem responde por direitos de imagem, dados pessoais e correções do titular?
- O contrato permite combinar dados sem contaminar a propriedade da base interna?
- Como os dados devem ser apagados no fim do contrato?

## Decisão proposta

**GO** para dados internos, avaliação própria e prova de conceito com fontes cuja
licença seja confirmada. **GO condicionado** para football-data.org, Hudl Wyscout,
Opta e FMDB Pro após proposta e revisão contratual. **NO-GO** para extração do jogo,
save, editor, API comunitária ou engenharia reversa da base do FM26.
