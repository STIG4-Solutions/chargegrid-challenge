<!-- GERADO por scripts/exportar_conhecimento.py a partir de docs/challenge/mentoring-01.md. Nao edite: rode o script. -->
<!-- titulo: Mentoria GoodWe do EV Challenge (13/05/2026) -->

EV CHALLENGE 2026 Sessão 1 de Mentoria — ChargeGrid Intelligence 

Orquestrando o futuro da mobilidade elétrica 

com Dados, IoT e Inteligência Artificial.

FIAP GOODWE 

13/05/2026   
**O D E S A F I O** 

De Hardware Isolado 

para Hub de Inteligência 

*A missão deixou de ser apenas carregar o veículo. O desafio é transformar cada sessão de recarga em dados  estruturados e inteligência acionável.* 

**1º Ano Presencial** 

ChargeGrid Intelligence 

Foco: Setor Comercial e Varejo. 

Otimização de tempo real, controle de demanda, tarifação dinâmica.   
**1º Ano Online** 

EV ChargeOps 

Foco: Condomínios e Setor Corporativo. 

Gestão compartilhada, rateio inteligente, síndico virtual com NLP  e UX.  
**O S 4 P I L A R E S D O C H A R G E G R I D** 

*Gestão Comercial, Controle de Demanda e Operação em Tempo Real* 

*![][image1]***Controle de Demanda** 

Ação: Gerenciamento da potência entregue aos eletropostos com base  no medidor. 

*Impacto: Redução de custos de infraestrutura e otimização da rede elétrica.* 

*![][image2]***Tarifação e Pagamento** 

Ação: Cobrança dinâmica acionada por APIs de pagamento (a definir  pela equipe). 

*Impacto: Viabilização de modelos de negócio sustentáveis para recarga  comercial.*   
*![][image3]***Protocolos Abertos** 

Ação: Integração via OCPP (futuro) e MODBUS (atual, sob solicitação). 

*Impacto: Interoperabilidade entre hardwares de diferentes fabricantes e  sistemas de gestão.* 

*![][image4]***IA Aplicada** 

Ação: Previsão de picos de consumo, análise de sessões e precificação  dinâmica. 

*Impacto: Maximização da eficiência operacional e alocação inteligente de  potência.*  
**A P I G O O D W E / S E M S \+** 

API GoodWe / SEMS+ 

Suporte API EV Chargers 

No momento não há suporte de API para os  EV Chargers. Será implementado ao final do  mês. Por questões burocráticas, não será  disponibilizado. 

![][image5]Modelo de consulta (Pull)   
Dados disponíveis 

Como a API ainda não foi implantada, os  

dados disponíveis não estão definidos — 

poderão ser avaliados e implementados  

conforme a necessidade dos clientes. 

Acesso ao SEMS+   
VPP Interface Document 

Quando a API é liberada, o cliente receberá o  VPP Interface Document com as orientações  necessárias. Mais informações no site de  desenvolvedor da API. 

![][image6]  
Os dados NÃO chegam em tempo real de forma automática (push). Só é  possível obter dados via consultas manuais/programadas à API.   
A API não será disponibilizada, mas será liberado o acesso à planta de  monitoramento no SEMS+.  
**H A R D W A R E E E Q U I P A M E N T O D E R E F E R Ê N C I A** 

Hardware e Equipamento de Referência GW7K-HCA-20 — Linha HCA G2

![]()![]()*Interação e configuração via APP de comissionamento SolarGo · APP de monitoramento SEMS+* 

*O EV Charger possui luzes indicativas para sinalização de status.*   
**P R O T O C O L O S T É C N I C O S** 

Protocolos Técnicos — OCPP, Modbus, RFID 

OCPP 

A linha HCA ainda não possui suporte OCPP.  Dessa forma, hoje ainda não é possível  realizar a cobrança direta.   
Modbus 

O EV Charger, assim como demais dispositivos  da planta (inversor, smart meter e bateria),  comunica através do protocolo Modbus.    
RFID 

A linha HCA G2 possui 2 cartões RFID inclusos  e suporta até 10 cartões. São cadastrados e  identificados via plataforma de  

monitoramento. O cartão permite a  autorização de carga local.  
**C O N T R O L E D E D E M A N D A E I A** 

Controle de Demanda e IA 

**Controle Dinâmico de Carga** 

Depois de ativar o controle dinâmico de carga, o carregador ajustará a velocidade de carregamento (ou até pausará o carregamento)  com base nos dados do medidor e na corrente de conexão à rede definida, para evitar o disparo do fusível principal. 

Quando a corrente real consumida se aproxima da corrente de conexão à rede definida, o carregador reduzirá a potência de  carregamento até pausar, para evitar o disparo. 

O carregador reiniciará automaticamente quando a diferença entre a corrente de conexão à rede e a corrente consumida da rede  atender às condições de reinício do carregador. 

Isso pode ser configurado via SolarGo ou SEMS+. 

**Configurável via SolarGo · SEMS+**  
**P A G A M E N T O E M O D E L O C O M E R C I A L** 

Pagamento e Modelo Comercial 

**O Problema Central:** 

A GoodWe não possui um modelo padrão de cobrança para a linha HCA G2, devido à ausência de suporte a plataformas terceiras de billing/pagamento. 

![]()Modelo de cobrança ![]()Responsáveis pelos custos de energia ![]()Gateway de pagamento Formato de autenticação/liberação Divisão de receita Modelo de implantação 

Fazem parte do desafio\! O objetivo é que os participantes desenvolvam soluções técnicas, operacionais e comerciais para aplicações em áreas  comerciais e condomínios.  
**E S C O P O E E N T R E G Á V E L** 

Escopo e Entregável 

O direcionamento da solução (commercial e condominial) e o formato do entregável ficam livres para cada grupo. Não há limitações de  criatividade, aplicação prática ou nível de desenvolvimento. Desde que atendidos: 

![]()1 **Arquitetura funcional (Data Flow) ![]()**2 **Papel da IA na solução** 3 **Aderência ao contexto** 4 **Visão de produto real** 

**O foco da avaliação não será apenas o código, mas principalmente:** 

**Raciocínio arquitetônico Gestão e estrutura de dados Viabilidade operacional/comercial Lógica da solução proposta**  
EV CHALLENGE 2026 

Transformem dados em inteligência, energia em estratégia e  ideias em soluções reais.  

Boa sorte a todos\!

FIAP GOODWE 

13/05/2026
