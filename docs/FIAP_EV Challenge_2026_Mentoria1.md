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

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAnCAYAAABJ0cukAAABnklEQVR4Xu3S3ytDYRjA8ZVciNz4C1y5c6PEIg07O6ytudjaOpudpCVkWFopF8ivpGZqarRIc0G59CP/ghul/CguRAfNHJzZj7M8zpOUXrfkXb2f+l49z3vx1KvTMQzDMMwfeowah+/WbfUYOaPedbixNh03K/l9t4CRc2qBXVeEPUSbD9RNC8ChV8DIPWoV/AHnkw0u7HXDqObjVsjvegWM3KOSFKguTUYMl1gmbgJ1zQrZLa+AkbtUkmabxrOrHGC5GAfqihXSMbELg4W6kiNfTTH5hioFfcDViL4qNd/6pIa1r4MtaUXaIRey3GJqyHySmXPswaJQjpHv/93jWMt2bpqHH818lp0ygzIhBsl31Dgd1AsXgYahZNCwjKVHech8KxV0HUsBdyn5jhoFf8AXuY8zYim/Cd78PCgDtndMHvRx5C6VZFE7QOu12wRKdxvIPnEHI/eolXByRuzFycOL6JQle38lRu5RK2HRDtB6dlgh6ekZI+fUK/wDOrQDtOROz9m9vbeMnFMvIfDl2I3NU0HOGIZhGIZhmN/zAXU2JSrgWcAGAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAnCAYAAABJ0cukAAAB9UlEQVR4Xu3Sz0vTcRzH8W9Qt/6Ajl126RDC92CwtW+6TRkz536p00pByENdIroYVEQH8cf8nmR9WzNSl81GNufWdyKb1BbDkiL7oFOXZWiQUnix27t939bB76kJX2TwfsKD7+3z5gVfjqMoiqIoiqKosorn+WOKxmvivUsPJ9mFQBS1BiZYSyDCvNIz1CyFWaP0lHmkEHLfH2Uu/zBz+h8hh3+IOQaDC56h2AmF+o5mlf0A4ZTnuMJT1VHwWjqhydyB3KY2cJhawV7VhOrOucAq2KFWsCGzsRaqDdUg6AV0Vq8HwWgE5427OoX6jmaV/QCeK/5CRdabI7kGMQFucQq5xFhRFJwDE6hh4DnYfRGo942j874w2PrHwNL3BJn7QmAtfr3BtE6hvqNZZT/gX8bwitz5ahOyCyt7Pub/Wt4nxwpobnEN5vJfoOvtNqqZ2YL61C9oT//WKdTva55hdFm+mt6A3OsMSk7FIRmPw3Q8sc+n9x/Q19UCrH9eg575bWRK/ABb8ufhDTjzeEmuiW5CV2od3Zr9H9+gWx5D6ewVuD6bO7wBlcElWT/+HUoViN1BO+8M0JuJ0oADxz/IS5UjG1CqutA8uhx5Cc4Xq9CW2j2pUL+vfbdTRyv6sy2nezMXD6pCfGPhODiyh6IoiqIoiiqlP2bEjhjCIaOaAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAnCAYAAABJ0cukAAACsklEQVR4Xu3WzWvTYBzAcd8GgsPdRVBQwYMX2T+gHmXiwYsiDhERvHvw5lXYSRyr2YRJZjdJt7Zrs6Rp2jxJmqRJ87pmc5ubb+DQoeBF5yYuj/nNizx4lL5AvvC55Eke8oQnaffsSUpKSkrqlhiG2Y8Y1OtQTg8gxzu2QA8HgKc3kaeFH3wtNIEuevcxxnvJ8zsqt9a85evhL2DLAa6L7qZXW4jASvAmqld8GiF0AJDXti14qqAhuXcsyd0Ss+omyNHCzakUfzw3Lp4DtZKztmivRhpnXwTkPG2r6xfg1YJBYCH/J59Rfkyl2MuAPG+WFu++dFaxIbhDgBxvS77mnw/0hc0/FrGjNt81UHAPkF+ePC0ONutLWC87T8DfY23J15rX4cYdZR4DQ3S245d151X8soL4GA2LYCixD4jZmuZpi1gpWLcBOV/L69oF1JF7FcR7/rtcNCKeQRjEL22KGRUuyAXzLVj2XkfVgn6DnZTSQBNsLBcbK9wEdxiQ87YkRw0GzKq7BWS2vp0fF4bqooeBXmqsy0X51ItUcRAg1sTsVGVD5UwMqjnj/fNh9hg5Z8tC4+igpza/GBVnG5RnlN1tIM9aGeAqYaRy1ld+WjZBeUaNb9zClZy2BLLPqifIOVta1y9AmJYvxf9tYKsIAD/A++A4M4x6gZDR09qc803jXQzUuQYuT6sqM1Y6Ccj5Wl78BK/52gLWhUYKkOMURfXE3/p0OatiwKal9YlHbXpZ/9XMKHdUL7lR/IP1CaCifgaOC7RwaFdGGVF5ayfeLhsgTZVOk3O0vQItTYTmSgRcNfys8Bajl+xlEH+ZIqlgfMw85c4C8tqOqOsXQD1k+mbpCg1U1t6x0Ty2qsEuKW+sMWNCP3lNxzb5OH8kPTJ3JTcm9QNyPCkpKSkpKSkp6f/2G/0HvKX1eBhhAAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAnCAYAAABJ0cukAAADgklEQVR4Xu3VW0yTdxzG8c7Eq+3ORA3JZmos0pZCyjKGsoyZaAJmI+gA2WzQOMV22bjYQrYps3MrWgWcIQ6pccBwgwwzsM1ay2ESjsVy6hBYoUgLPc0qczUm0JH4jP+PuMF7YeJFS0jeb/K5eZv3SX/pRQUCPj4+Pr7VCgLdegjy1nOfP0/+TcUvcp9FrIdbj55dSFJdgUDwAsOeQS1YF7i+PZ953CYu/Oe2uHDesiT4myR9+fu+zR+IQ3LVFGIyNjDLP4tIni155/6OOVr59AC1Wr1utPxAmqtCCiZQJ8Wjm1LMdcSSYM/OgLdf+8rT951RSvlsdN6sf9O+jczy7YjkE+YrArvOvdddbcpkrA29w0M37X6bvhnMqMmAyXYjnBYTmbYNhDyOWY9n4sEtxjf+QPxnwikTdzdirfkD3MJcxWjOV7rOSv0c09fYC5t5HCMdHjJu9cM1eh9exyzxOx/C72L+It67992e6CNG7m7EcglTFRblqVDJxxowb8SkIXbHEcSJ00l8VPIKMuFuyFJUyEw7TjqbrZgWvr16B3ilytPtGV88Sd6+F4xMlo34ahdiz3SShC27VxDtK8KrN4KIyzlP3k9TYS5V9xg5N6IY7n7YW/MHeCTHzfq38rFTmk3ikvIgr5lB/MUhskOSTZIkWWTbwTIkGh5B/uE1kiJXIHRYD7x+WcRw98OeM/pQU1/WCRxI/ZQkJR6D9IQZicprJCVRRd58TUnkez6H7IwFye9oiOZkFUJZPwDir0UMdz/sOYTZTf1Zn8F46WdSerIaxYV1uHC6gVzUNKJMq8d3JYYlpXqUXzCg5korcdj8mN9/efGAAhHD3Q97a/6AsZfTzdZ3P0FnlZ70NVowZLZj+JabjHR5YV/8L5gcvEem7gTIXds9MtHnx9xeLea3HhYx3P2wN7J5T2a3osDHPcDwfTupKPoJOm0trhbXEYt5DH/c9mGsx0vuLP7ZBfdrrMGojA0Mdz8iNX+r+/G/AxqWDvjooJokbEtdoUJbT196uM1Nfl/8lQZbpg9xNyNaS1lVQUel/glj/cWCQZMdTbUDpFRdh5Iva1H2zXXSa5yErXXmfy0zCwMmdxx3M6Kt+QPaLtW/1Fre2sS0X+1HV40dXbXOZ+qudS4wPfVTau7eqvZr0dAu49mxXON5xzOM55qKJyQM930+Pj4+Pj4+Pr7n61/J2IHElbC8IQAAAABJRU5ErkJggg==>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAc8AAACsCAYAAAAdbydrAAADq0lEQVR4Xu3by07bYBRG0fR+pbR9/4dtjvCvuqgSbGCCvZb0TVDIdOs4yeUCAAAAAAAAcHxvdntrZmZ2sO07N3uWFct3u703MzM72PadWzF9MvE0M7Mz7EXiuc7WFcsP2+6ftWZmZkfbk61nwBPOT9d92QYAZ5GCOi9ap+tcmxPNm20AcBbiCQDRk+M5j2y/XXe7DQDOYv9Tlgetzzpnny93F+fPbQBwFvtv3z7of/H8vQ0AzmL/85UHiScAPDOePy5/4/moD00B4ADEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwAi8QSASDwBIBJPAIjEEwCiZ8Xz5iKeAJyPeAJA9Ox4/toGAGeR4jnX5Xrxp+u+X3e7DQDOYrVwjsoH7eP58bqvl7vrc/Zl2/zNzMzsCJuuzZPWORhnHy7/Xp3iaWZmdm8vFs954WzeYN7w27YJ6Px0ZT3GNTMze+2brk3fVusmpnM8rng++suy88J1gU5AV40npC5PMzM70tZT1f3lOV+aXYdktn+EO5s3mzedIpuZmR1h07UVzNl6VLsOyUw8zczs6HvxeI71z/vPQvdBNTMze+1bfVvRBAAAAAAAADisP79EqdHb4TESAAAAAElFTkSuQmCC>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAcoAAACsCAYAAAD7RuwvAAADn0lEQVR4Xu3bS27bQBQFUTn/v5Psf7HRQ9gAkUEpsjyw6HOAOzFoTQvdok4nAAAAAAAAgJfnYbc3ZmZmd7x902Y3WWF8u9s7MzOzO96+aSucTyaUZmZ2tD1LKNdxdIXx/bZ/j6tmZmb3vCdb97gTyY/nfd4GAEd0VTznoXUknVPkBPL7NgA4ov2LPhcJJQCvzdWhXF94zrXr1/MetwHAEe1f7rloHlov76zT5M9tAHBEN4fy9zYAOKL9T0YuEkoAXpubQvnjJJQAHJtQAkAQSgAIQgkAQSgBIAglAAShBIAglAAQhBIAglACQBBKAAhCCQBBKAEgCCUABKEEgCCUABCEEgCCUAJAEEoACEIJAEEoASAIJQAEoQSAIJQAEIQSAIJQAkAQSgAIQgkAQSgBIAglAAShBIAglAAQhBIAglACQBBKAAhCCQBBKAEgCCUABKEEgCCUABCEEgCCUAJAEEoACEIJAEEoASAIJQAEoQSAIJQAEIQSAIJQAkAQSgAIQgkAQSgBIAglAAShBIAglAAQhBIAglACQBBKAAhCCQBBKAEgCCUABKEEgCCUABCEEgCCUAJAEEoACEIJAEEoASAIJQAEoQSAIJQAEIQSAIJQAkAQSgAIQgkAQSgBIAglAAShBIAglAAQhBIAglACQBBKAAhCCQBBKAEgCCUABKEEgCCUABCEEgCCUAJAEEoACEIJAEEoASAIJQAEoQSAIJQAEIQSAIJQAkAQSgAIQgkAQSgBIAglAAShBIAglAAQhBIAglACQBBKAAhCCQBBKAEgCCUABKEEgCCUABCEEgCCUAJAEEoACEIJAEEoASAIJQAEoQSAIJQAEIQSAIJQAkAQSgAIQgkAQSgBIAglAAShBIAglAAQhBIAglACQBBKAAhCCQBBKAEgCCUABKEEgCCUABCEEgCCUAJAEEoACEIJAEEoASAIJQCEm0L5/SSUABybUAJAuDmUv7YBwBFdFcqH895t+3Tet/MetwHAEa1IzmHxognl+ocP5305/T1VzuaEOZu/mZmZ3dumYXMI/Lhtbk/3p0mhNDOzV71nC+U8uL6rnA/8um1iOT8XWVexZmZm97Rp2LRsdW3COYfCFcpp4H+ZB9fJcmK5yjvRdKI0M7N73boZ3Z8o552cdUC82v4adjYfNh869TUzM7u3rV91rJdW13XrOiBeTSjNzOxIe/ZQjvXP++8u9/E0MzO7p62WrUACAAAAAAAAvBh/AJJLqaUqwhDJAAAAAElFTkSuQmCC>