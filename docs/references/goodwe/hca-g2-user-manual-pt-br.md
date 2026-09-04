![][image1]  
**Manual do usuário** 

 **Carregador CA** 

Série HCA 

 (7 a 22 kW) G2

V1.5-2025-11-11   
Declaração de direitos autorais 

**Copyright©GoodWe Technologies Co.,Ltd. 2025\. Todos os direitos reservados.** 

Nenhuma parte desse manual pode ser reproduzida ou transmitida para a plataforma pública  de nenhuma forma nem por nenhum meio sem a autorização prévia por escrito da GoodWe. 

**Marcas comerciais** 

 e outras marcas comerciais da GoodWe pertencem à GoodWe Company.  Todas as outras marcas comerciais ou marcas registradas mencionadas nesse manual são de  propriedade da empresa GoodWe. 

**AVISO** 

As informações neste manual do usuário estão sujeitas a alterações devido a atualizações do  produto ou outros motivos. Esse manual não pode substituir as instruções de segurança ou  etiquetas no equipamento, a menos que especificado de outra forma. 

I   
CONTEÚDO 

**CONTEÚDO** 

**1 Sobre esse manual 1** 1.1 Modelo aplicável 1 1.2 Público-alvo 1 1.3 Definição dos símbolos 2 

**2 Precauções de segurança 3** 2.1 Segurança Geral 3 2.2 Segurança do carregador CA 3 2.3 Requisitos de pessoal 4 2.4 Declaração de Conformidade 5 

**3 Apresentação do produto 6** 3.1 Visão geral do produto 6 3.2 Cenários de uso 7 3.3 Modo de carregamento 9 3.4 Status operacional do carregador 10 3.5 Funcionalidades 10 3.6 Aparência 12   
3.6.1 Descrição das peças 12 3.6.2 Dimensão 14 3.6.3 Descrição do indicador 16 3.6.4 Placa de identificação 16 

**4 Verificação e armazenamento 17** 4.1 Verificação antes de receber 17 4.2 Entregas 17 4.3 Armazenamento 18 

**5 Instalação 19** 5.1 Requisitos de instalação 19 5.2 Instalação 21   
5.2.1 Movimentação do carregador 21 5.2.2 Instalação do carregador (na parede) 22 5.2.3 Instalação do carregador (no suporte) 23 5.2.4 Instalação do medidor MID (opcional) 24 

**6 Conexão elétrica 25** 6.1 Precauções de segurança 25 6.2 Conexão do cabo RCBO 27 6.3 Conexão do cabo CA 28

**II**   
CONTEÚDO 

6.4 Conexão do cabo de comunicação 29 6.4.1 Conexão do cabo de comunicação RS485 29 6.4.2 Conexão do cabo de comunicação LAN 30 6.4.3 Conexão do cabo do medidor MID (opcional) 30 

**7 Comissionamento do equipamento 31** 7.1 Verificação antes de ligar 31 7.2 Ligar 31 7.3 Carregamento de veículo elétrico 32   
7.3.1 Iniciar carregamento pelo aplicativo SolarGo ou SEMS Portal 32 7.3.2 Agendar carregamento pelo aplicativo SolarGo ou SEMS Portal 33 7.3.3 Modo de início automático 34 7.3.4 Carregamento de cartão RFID 34 

**8 Comissionamento do sistema 35** 8.1 Indicador 35 8.2 Configuração e verificação de informações do carregador pelo aplicativo SolarGo  (instaladores) 35 

8.2.1 Download e instalação do aplicativo 35 8.2.2 Login no carregador 36 8.2.3 Introdução à página principal 37 8.2.4 Configuração de Wi-Fi 38 8.2.5 Configuração do modo de carregamento 39 8.2.6 Mais 41 

8.3 Configuração e verificação de informações do carregador pelo aplicativo SEMS Portal  (instaladores) 44 8.3.1 Download e instalação do aplicativo 44 8.3.2 Registrar uma conta de usuário final 44 8.3.3 Login no aplicativo 45 8.3.4 Criação da estação de energia 46 8.3.5 Configuração do modo de carregamento 47 8.3.6 Configuração 50 

**9 Manutenção 54** 9.1 Desligar o carregador 54 9.2 Desmontar o carregador 54 9.3 Descartar o carregador 54 9.4 Manutenção de rotina 54 9.5 Solução de problemas 55 

**10 Parâmetros técnicos 57**

**III** 

**1 Sobre esse manual**   
01 Sobre esse manual 

Esse manual descreve as informações do produto, a instalação, a conexão elétrica, o  comissionamento, a solução de problemas e a manutenção do carregador. Leia esse  manual antes de instalar e operar o produto. Todos os instaladores e usuários devem  

estar familiarizados com os recursos, funções e precauções de segurança do produto. Este  manual está sujeito a atualização sem aviso prévio. Para mais detalhes sobre o produto e os  documentos mais recentes, acesse https://en.goodwe.com/. 

**1.1 Modelo aplicável** 

Esse manual se aplica aos carregadores listados abaixo: (doravante referidos como HCA). 

• GW7K-HCA-20 

• GW11K-HCA-20 

• GW22K-HCA-20 

**1.2 Público-alvo** 

Esse manual se aplica apenas a profissionais técnicos treinados e experientes. O pessoal técnico  deve estar familiarizado com o produto, as normas locais e os sistemas elétricos.

1   
01 Sobre esse manual 

**1.3 Definição dos símbolos** 

Os diferentes níveis de mensagens de advertência neste manual são definidos da seguinte forma:

| PERIGO |
| ----- |
| Indica um perigo de alto nível que, se não for evitado, resultará em morte ou ferimentos  graves. |
| **ALERTA** |
| Indica um perigo de nível médio que, se não for evitado, pode resultar em morte ou  ferimentos graves. |
| **CUIDADO** |
| Indica um perigo de baixo nível que, se não for evitado, pode resultar em ferimentos leves ou  moderados. |
| **AVISO** |
| Destaca e complementa os textos. Ou habilidades e métodos para resolver problemas  relacionados ao produto para economizar tempo. |

2   
02 Precauções de segurança 

**2 Precauções de segurança** 

Siga rigorosamente estas instruções de segurança no manual do usuário durante a operação. 

| AVISO |
| ----- |
| O carregador foi projetado e testado em conformidade com as regras de segurança  relacionadas. Leia e siga todas as instruções e precauções de segurança antes de qualquer  operação. A operação inadequada pode causar ferimentos ou danos à propriedade, pois o  carregador é um equipamento elétrico. |

**2.1 Segurança Geral** 

| AVISO |
| ----- |
| • As informações neste manual do usuário estão sujeitas a alterações devido a atualizações  do produto ou outros motivos. Este guia não substitui os rótulos do produto ou as  precauções de segurança no manual do usuário, a menos que especificado o contrário.  Todas as descrições no manual são somente para orientação.  • Antes das instalações, leia o manual do usuário para aprender sobre o produto e as  precauções.  • Todas as instalações devem ser realizadas por técnicos treinados e experientes que  estejam familiarizados com as normas locais e os regulamentos de segurança. • Use ferramentas isolantes e vista equipamento de proteção individual ao operar o  carregador para garantir a segurança pessoal. Use luvas, roupas e pulseiras antiestáticas  ao tocar em dispositivos eletrônicos para proteger o carregador contra danos. • Siga rigorosamente as instruções de instalação, operação e configuração desse manual.  O fabricante não será responsável por danos ao equipamento ou ferimentos se você não  seguir as instruções. Para obter mais detalhes sobre a garantia, acesse: https://en.goodwe. com/warranty. |

**2.2 Segurança do carregador CA**

| PERIGO |
| ----- |
| • Não desmonte os módulos do carregador por conta própria. Não estenda o cabo de  carregamento. Caso contrário, pode causar redução da classificação de proteção de  entrada ou risco de choque elétrico.   • O equipamento permite apenas o carregamento de veículos elétricos (EVs). Não carregue  outros dispositivos.   • Depois de usar o conector de carregamento, cubra o plugue de carregamento  adequadamente e enrole o cabo ao redor do carregador.   • O carregador e os cabos não devem ser dobrados, espremidos ou emaranhados. Caso  contrário, pode causar danos ao equipamento.   • Desconecte o carregador e seus interruptores upstream antes da instalação, manutenção  e outras operações.  • É estritamente proibido tocar no conector de carregamento quando o carregador está  ligado. |
| **ALERTA** |
| Verifique regularmente se a tampa e a aparência do carregador estão normais. |

3   
02 Precauções de segurança 

| PERIGO |
| ----- |
| • Todos os rótulos e marcações de advertência devem estar visíveis após a instalação. Não  cubra, rabisque ou danifique nenhum rótulo no equipamento.  • Os rótulos de advertência no carregador são os seguintes: |

|  | RISCO DE ALTA TENSÃO   Existe alta tensão durante  a operação do carregador.  Desconecte toda a energia de  entrada e desligue o produto  antes de trabalhar nele. |  | Atrase a descarga. Aguarde  5 minutos depois de desligar  até que os componentes   estejam completamente   descarregados. |
| :---- | :---- | :---- | :---- |
|  | Leia o manual do usuário  antes de qualquer operação. |  | Existem riscos potenciais.  Use EPI adequado antes de  qualquer operação. |
|  | Risco de alta temperatura.  Não toque no produto   em operação para evitar  queimaduras. |  | Não descarte o carregador  como lixo doméstico. Descarte  o produto de acordo com as leis  e regulamentações locais ou  envie-o de volta ao fabricante. |
|  | Marcação CE.  |  | Marcação RCM. |
|  | Marca ANATEL do Brasil. |  |  |

**2.3 Requisitos de pessoal**

| AVISO |
| ----- |
| • O pessoal que instala ou realiza a manutenção do equipamento deve ser rigorosamente  treinado, e aprender sobre as precauções de segurança e as operações corretas. • Apenas profissionais qualificados ou pessoal treinado estão autorizados a instalar, operar,  realizar manutenção e substituir o equipamento ou peças. |

4   
02 Precauções de segurança 

**2.4 Declaração de Conformidade** 

**União Europeia** 

O produto com função de comunicação sem fio vendido no mercado europeu atende aos  requisitos das seguintes diretivas: 

• Diretiva de Equipamentos de Rádio 2014/53/EU (RED) 

• Diretiva de Restrições de Substâncias Perigosas 2011/65/EU e (UE) 2015/863 (RoHS) 

**Reino Unido** 

O produto com função de comunicação sem fio vendido no mercado britânico atende aos  requisitos das seguintes diretivas: 

• Regulamentos de equipamentos de rádio de 2017 

• As restrições ao uso de determinadas substâncias perigosas em regulamentos de  equipamentos elétricos e eletrônicos de 2012 (S.I. 2012/3032) 

**Brasil**

O produto com função de comunicação sem fio vendido no mercado brasileiro atende aos  requisitos das seguintes diretivas: 

• Incorpora produto homologado pela Anatel sob número 06795-24-02673. • Este equipamento não tem direito à proteção contra interferência prejudicial e não pode  causar interferência em sistemas devidamente autorizados. Para obter mais informações,  consulte o site da ANATEL www.gov.br/anatel/pt-br. 

| AVISO |
| ----- |
| • Wi-Fi de 2,4 G, frequência de operação: 2.412 a 2.472 MHz, potência máxima e.i.r.p:  18,99 dBm  • BLE 1M&2M, frequência de operação: 2.402 a 2.480 MHz, potência máxima e.i.r.p: 2,99 dBm • RFID 13,56 MHz, potência máxima e.r.p: \-47,50 dBm |

5   
03 Apresentação do produto 

**3 Apresentação do produto** 

**3.1 Visão geral do produto** 

O produto da série HCA é um carregador residencial CA, projetado principalmente para carregar  veículos elétricos. Ele se comunica com um inversor para utilizar a energia fotovoltaica no  carregamento do veículo, além de obter dados do medidor inteligente por meio do inversor  para o gerenciamento dinâmico da carga. Também pode se conectar a um medidor MID  (medidor inteligente certificado MID) para gerar faturas reembolsáveis. O carregador pode  ser iniciado por cartão RFID, via aplicativo ou automaticamente ao conectar o plugue de  carregamento. Além disso, oferece proteção durante o carregamento, monitoramento de rede e  outras funcionalidades. 

**Modelo** 

Esse manual se aplica aos carregadores listados abaixo: 

• GW7K-HCA-20  

• GW11K-HCA-20 

• GW22K-HCA-20 

**Descrição do modelo** 

**GW11K-HCA-20**

| Nº  | Referência  | Explicação |
| ----- | :---- | :---- |
| 1  | Código da marca  | GW: GoodWe |
| 2  | Potência nominal  | • 7.000: a potência nominal de saída é de 7 kW. • 11.000: a potência nominal de saída é de 11 kW. • 22.000: a potência nominal de saída é de 22 kW. |
| 3  | Série  | HCA: Série HCA |
| 4  | Geração  | 20: a segunda geração. |

6   
03 Apresentação do produto 

**3.2 Cenários de uso** 

**Com PV e bateria**  

Servidor do SEMS    
Portal 

Roteador 

m 

Aplicativo  SEMS Portal 

\< 100 m   
\< 15   
m 

Aplicativo SolarGo   
\< 100   
\< 15 m 

\< 10m 

**4** 

Arranjo    
fotovoltaico  

**5**   
**1** 

**3**   
Inversor 

Carregador

Medidor MID 

RCBO   
CT 

EV (Veículo  elétrico) 

Medidor  inteligente   
**6** 

Rede    
Medidor de  

**2** 

elétrica 

Bateria   
energia 

**Sem PV ou bateria**  Aplicativo SolarGo   
Bluetooth LAN WiFi RS485 

Roteador Servidor do SEMS Portal 

Aplicativo SEMS Portal 

\< 10 m   
m \< 100 

**4** 

m   
\< 15 

**5** 

**3** 

RCBO   
Medidor de energia Rede elétrica   
Veículo elétrico  

Carregador 

Medidor MID   
Bluetooth LAN WiFi RS485 

7   
03 Apresentação do produto 

| Nº  | Peças  | Descrição |
| :---: | ----- | ----- |
| 1  | Inversor  | Inversores fotovoltaicos Grid-Tie e híbridos da GoodWe. |
| 2  | Bateria  | Baterias compatíveis com os inversores híbridos da GoodWe. |
| 3  | RCBO  | Oferece proteção contra corrente residual e sobrecorrente para o  carregador. Entre em contato com o fabricante do carregador para  comprar.  |
| 4  | Carregador  | Carregador da série HCA da GoodWe. |
| 5  | Medidor   MID | Coleta os dados de consumo de energia do carregador de veículo  elétrico, que podem ser utilizados para reembolso de faturas. |
| 6  | Medidor   inteligente | Entregue com o inversor ou adquirido do fabricante do inversor. |

**Diagrama de circuito** 

Confira abaixo o diagrama de circuito para o carregador HCA: 

Parada de    
emergência 

RS485, portas LAN 

Interruptor    
de proteção    
contra  

Exibição de status de LED 

Unidade de    
controle inteligente 

Unidade de medição  de energia elétrica 

Rede ou    
fonte de    
alimentação  CA   
vazamento Entrada 

Relé de saída   
Saída 

• A porta RS485 é utilizada para comunicação com inversores fotovoltaicos ou medidores  MID.  

• A porta LAN é utilizada para comunicação com o roteador. 

• Para carregador CA monofásico e trifásico, a porta de entrada é usada para conectar  com cabo de alimentação monofásico de três fios da rede elétrica e cabo de alimentação  trifásico de cinco fios da rede, respectivamente. 

• A porta de saída é usada para conectar com o plugue de carregamento. • Parada de emergência se refere ao botão de parada de emergência.

8   
03 Apresentação do produto 

**Tipos de redes** 

Cenário monofásico: 

Carregador Carregador Carregador Carregador Cenário trifásico: 

Carregador Carregador Carregador Carregador 

**3.3 Modo de carregamento** 

| AVISO |
| ----- |
| Para modos de prioridade de energia fotovoltaica e energia fotovoltaica \+ bateria, a potência  de carregamento do carregador de veículo elétrico é limitada pela potência máxima de saída  do inversor. |

**Rápido** 

O carregador utiliza eletricidade da rede elétrica, dos painéis solares ou das baterias para  carregar veículos elétricos. A potência de saída do carregador é configurada como a potência  nominal por padrão, e os usuários podem ajustar a potência, desde que não exceda a nominal. 

**Prioridade de energia fotovoltaica** 

Somente a energia fotovoltaica é usada para carregar o veículo elétrico. As cargas, que  podem ser da rede elétrica ou de sistemas de backup, têm prioridade no consumo da energia  fotovoltaica, e o excedente é utilizado para carregar o veículo. 

**Energia fotovoltaica \+ bateria**

A energia fotovoltaica e a bateria são utilizadas para carregar o veículo elétrico. As cargas, que  podem ser da rede elétrica ou de sistemas de backup, têm prioridade no consumo de energia,  e o excedente é utilizado para carregar o veículo. 

9   
03 Apresentação do produto 

**3.4 Status operacional do carregador** Em    
Ocioso Carregando preparação Em espera 

Carregamento    
completo ou    
Alarme 

**3.5 Funcionalidades** 

| AVISO |
| ----- |
| • A potência máxima de carregamento do carregador é limitada pela potência máxima de  carregamento do carregador interno (OBC) dos veículos.  • A corrente mínima de partida por fase do carregador é de 6 A. Para carregamento  monofásico, a potência mínima é de 1,4 kW, e para carregamento trifásico, é de 4,2 kW. • Os carregadores trifásicos aceitam carregamento monofásico, bifásico e trifásico, mas a  potência real de carregamento é influenciada pelo OBC. Quando um carregador trifásico  carrega um veículo que só aceita carregamento monofásico, sua potência máxima de  carregamento é 1/3 da potência nominal do carregador. Quando um carregador trifásico  carrega um veículo que só aceita carregamento bifásico, sua potência máxima de  carregamento é 2/3 da potência nominal do carregador. |

**Controle dinâmico de carga** 

Depois de ativar o controle dinâmico de carga, o carregador ajustará a velocidade de  carregamento (ou até pausará o carregamento) com base nos dados do medidor e na  corrente de conexão à rede definida, para evitar o disparo do fusível principal. Quando a  corrente real consumida se aproxima da corrente de conexão à rede definida, o carregador  reduzirá a potência de carregamento até pausar, para evitar o disparo. O carregador reiniciará  automaticamente quando a diferença entre a corrente de conexão à rede e a corrente  consumida da rede atender às condições de reinício do carregador. 

**Garantir potência mínima de carregamento** 

Quando a energia fotovoltaica ou a combinação de energia fotovoltaica \+ bateria for insuficiente,  o carregador pode obter suporte da rede elétrica ou da bateria para manter a potência de saída  desejada, caso a função Garantir potência mínima de carregamento esteja ativada. Essa função  está disponível apenas nos modos Prioridade de energia fotovoltaica ou Energia fotovoltaica \+  bateria. Os usuários podem ativar essa função pelo aplicativo SolarGo ou SEMS. 

10   
03 Apresentação do produto 

| Status  | Explicação |
| :---: | ----- |
| LIGADO  | Continue carregando com o suporte da rede elétrica e da bateria para garantir  a potência mínima necessária para o carregamento (1,4 kW para carregadores  de 7 kW e 4,2 kW para carregadores de 11/22 kW). |
| DESLIGADO  | Interrompa o carregamento se o excedente de energia fotovoltaica não estiver  mais disponível. |

**Alternância de fase** 

| AVISO |
| ----- |
| A função de alternância de fase está disponível apenas para carregadores trifásicos. |

| Status  | Explicação |
| :---: | ----- |
| LIGADO  | Quando a potência total de entrada for inferior a 4,2 kW, o carregador alterna  automaticamente para o modo de carregamento monofásico para evitar  o consumo de energia da rede ou o desligamento. A potência mínima de  carregamento no modo monofásico é de 1,4 kW. (O tempo de alternância de  fase é de aproximadamente 3 minutos) |
| DESLIGADO  | O carregador permanece no modo de carregamento trifásico. |

**Seguro e confiável** 

• A classificação de proteção de entrada do carregador é IP66 e a do plugue de carregamento  é IP55. Com uma classificação alta, o carregador conta com excelentes recursos antipoeira e  à prova d’água e pode ser operado e mantido em áreas externas. 

• Para proteger o produto e garantir um status de funcionamento seguro, o produto é  integrado com proteção contra sobretensão e subtensão, proteção contra sobrecarga,  proteção contra curto-circuito, proteção contra vazamento, aterramento, proteção contra  excesso de temperatura, proteção EMS e proteção contra iluminação.

11   
03 Apresentação do produto 

**3.6 Aparência** 

**3.6.1 Descrição das peças Carregador** 

**Tipo um**

12   
03 Apresentação do produto 

**Tipo dois** 

HCA20DSC0004

| Nº  | Peças  | Descrição |
| :---: | ----- | ----- |
| 1  | Indicador  | Indica o status operacional do carregador. |
| 2  | Área do cartão RFID  | Para encostar o cartão e ativar o carregamento. |
| 3  | Porta de entrada para cabo CA  | Conecta-se com cabo de entrada CA monofásico ou  trifásico. |
| 4  | Porta de comunicação RS485  | Conecta o cabo de comunicação RS485 de um  inversor ou medidor.  |
| 5  | Porta de comunicação LAN  | Conecta o cabo de comunicação de um roteador. |
| 6  | Cabo de carregamento  | \- |
| 7  | Plugue de carregamento  | Conectado à porta de carregamento de EV. |
| 8  | Placa de montagem  | Fixa o carregador no material de suporte. |
| 9  | Botão de parada de emergência  | Usado para proteção de emergência. |

13   
03 Apresentação do produto 

**(Opcional) Quadro de distribuição** 

**GW7K-HCA-20 GW11K-HCA-20 e GW22K-HCA-20** 

1\. Furos para fixação 2\. Porta de entrada para cabo CA 3 Porta de saída para cabo CA 

**(Opcional) Suporte** 

**GW7K-HCA-20 GW11K-HCA-20 e GW22K-HCA-20** 

Vista frontal Vista traseira Vista frontal Vista traseira1\. Posição de montagem    
do carregador 2\. Porta do cabo CA entre    
o RCBO e o carregador 3\. Porta do cabo de    
comunicação 

4\. Posição de instalação    
do soquete falso 5\. Posição do furo para    
fixação da base 6\. Posição de instalação    
do RCBO 

7 Cabo de entrada CA    
do RCBO 8 Porta do cabo CA entre    
o RCBO e o carregador 9 Placa de operação 

10 Porta PE 

14   
03 Apresentação do produto 

**3.6.2 Dimensão** 

**Carregador** 

170 mm 

149mm 130mm   
208 mm 

450 mm 

**(Opcional) Quadro de distribuição do RCBO** 

**GW7K-HCA-20** 

107 mm 88 mm 

202 mm   
202 mm   
107 mm 

**GW11K-HCA-20 e GW22K-HCA-20** 

219 mm 

200 mm   
100 mm 150 mm 150 mm

15   
03 Apresentação do produto **(Opcional) Suporte** 

**GW7K-HCA-20** 

120 mm 60 mm 

1.300 mm 

250 mm 

4 \* Φ 15 mm 

185 mm 

115 mm 250 mm 

55 mm   
185 mm 

**GW11K-HCA-20 e GW22K-HCA-20** 180 mm 60 mm   
Vista inferior do suporte 185 mm 

1.300 mm 

250 mm 

4 \* Φ 15 mm 

55 mm 

115 mm 

250 mm 

Vista inferior do suporte  
185 mm 

16 

**(Opcional) Medidor MID**   
03 Apresentação do produto 

90mm 

50mm 

65mm 

90mm   
50mm 

65mm   
72mm 

**3.6.3 Descrição do indicador** 

36mm 

| Indicador  | Cor  | Explicação |
| ----- | :---- | :---- |
|  | Verde LIGADO  | O carregador está em modo de espera. |
|  | Pisca em verde  | O sistema do carregador está sendo atualizado. |
|  | Azul LIGADO  | O carregador está carregando. |
|  | Vermelho LIGADO  | Ocorreu uma falha. |
|  | Status da luz indicadora quando a ativação do carregamento por cartão RFID está  anormal |  |
|  | Luz vermelha acesa  por 2 segundos | Encoste o cartão antes de conectar o plugue de  carregamento ao veículo elétrico. |
|  | Luz vermelha pisca  duas vezes  | O carregador e o cartão não correspondem. |

**3.6.4 Placa de identificação** 

A placa de identificação é apenas para referência. 

**\*\*~~\*~~\*\*\***  
Marca comercial GOODWE, tipo de produto  e modelo do produto 

Parâmetros técnicos 

Símbolos de segurança e marcações de  certificação 

Informações de contato e número de série 

17   
04 Verificação e armazenamento 

**4 Verificação e armazenamento** 

**4.1 Verificação antes de receber** 

Verifique os seguintes itens antes de receber o produto. 

1\. Verifique se há danos na embalagem externa, como furos, rachaduras, deformações e  outros sinais de danos ao equipamento. Não retire a embalagem e entre em contato com o  fornecedor o mais rápido possível se encontrar algum dano. 

2\. Verifique o modelo do carregador. Se o modelo do carregador não for o que você solicitou,  não desembale o produto e entre em contato com o fornecedor. 

3\. Verifique as entregas quanto ao modelo correto, conteúdo completo e aparência intacta.  Entre em contato com o fornecedor o mais rápido possível se encontrar algum dano. 

**4.2 Entregas** 

| ALERTA |
| ----- |
| Conecte os cabos aos terminais fornecidos. O fabricante não será responsável por danos se  outros terminais forem usados. |

|  |
| :---- |
|  |

|  |
| :---- |
|  |

|  |
| :---- |
|  |
|  |

1 carregador 1 conector CA 4 parafusos    
1 soquete  falso   
4 parafusos  de fixação do  soquete falso 

de    
expansão   
1 conector de  comunicação  RS485   
1 conector de  comunicação LAN 

1 chave  de fenda   
1 chave  de fenda   
5 terminais  de pino para  cabo CA   
4 terminais  de pino para  cabo RS485   
2 cartões  RFID   
1 terminal  RJ45   
2 tampões de  borracha à  prova d’água  
1    
documentação 

18 

**(Opcional) GW7K-HCA-20**   
04 Verificação e armazenamento 

4 parafusos de expansão M12\*100 

8   
parafusos M5\*12   
2 parafusos M4\*10 

4 parafusos M4\*10 

1 quadro de    
distribuição do RCBO 

1 RCBO 

1 medidor MID 

4 terminais de pino para  cabo CA 

1 suporte   
4 parafusos de expansão 

2 terminais de pino para  cabo RS485 

**(Opcional) GW11K-HCA-20 e GW22K-HCA-20** 

1 placa    
adaptadora 

12 parafusos  M5\*12   
2 parafusos  M4\*10 

4 parafusos  M4\*10 

1 quadro de    
distribuição do RCBO 

1 RCBO 

1 medidor MID 

8 terminais de pino para  

1 suporte   
4 parafusos de expansão  M12\*100 

4 parafusos de expansão  
cabo CA 

2 terminais de pino para  cabo RS485 

**4.3 Armazenamento** 

Se o carregador não for instalado ou usado imediatamente, certifique-se de que o ambiente de  armazenamento atenda aos seguintes requisitos: 

1\. Não retire a embalagem externa nem jogue o dessecante fora. 

2\. Guarde o carregador em um local limpo. Certifique-se de que a temperatura e a umidade  sejam adequadas e sem condensação. 

3\. A altura e direção dos carregadores empilhados devem seguir as instruções na caixa de  embalagem. 

4\. Os carregadores devem ser empilhados com cuidado para evitar que caiam. 5\. Se o carregador tiver sido armazenado por um longo período, ele deve ser verificado por  profissionais antes de ser colocado em uso. 

19   
05 Instalação 

**5 Instalação** 

**5.1 Requisitos de instalação** 

**Requisitos do ambiente de instalação** 

1\. Não instale o equipamento próximo a materiais inflamáveis, explosivos ou corrosivos. 2\. Não instale o equipamento em um lugar fácil de tocar. O equipamento fica a altas  temperaturas durante o funcionamento. Não toque na superfície para evitar queimaduras. 3\. Evite os canos de água e cabos dentro da parede ao fazer furos. 

4\. Instale o equipamento em um local coberto. 

5\. O local de instalação do equipamento deve ser bem ventilado para irradiação de calor e  suficientemente amplo para as operações. 

6\. O equipamento com alta classificação de proteção de entrada pode ser instalado em  ambientes internos e externos. A temperatura e a umidade no local de instalação devem  estar dentro da faixa apropriada. 

7\. Instale o equipamento a uma altura conveniente para operação e manutenção, conexões  elétricas e conferência de indicadores e rótulos. 

8\. A altitude para instalar o carregador deve ser inferior à altitude máxima de funcionamento  de 2.000 m. 

9\. Instale o equipamento longe de interferências eletromagnéticas. 

|  |
| :---- |

300mm 300mm   
300mm 

1 \- 1.3m 

Children No Touch 

|  |  |  |
| :---- | :---- | :---- |
|  |  |  |
|  |  |  |

|  |  |  |
| :---- | :---- | :---- |
|  |  |  |
|  |  |  |
|  |  |  |

|  |  |
| :---- | :---- |
|  |  |

ALT: 2000m **IP66** 

**IP55**

5%\~95%RH 

20   
05 Instalação 

**Requisitos do suporte de montagem** 

• O suporte de montagem deve ser não inflamável e à prova de fogo. 

• Instale o carregador em uma superfície firme o suficiente para suportar seu peso. **Requisitos do ângulo de instalação**   
• É recomendável instalar o carregador verticalmente. 

• Não instale o carregador de cabeça para baixo, inclinado para frente, inclinado para trás ou  horizontalmente.

21   
05 Instalação 

**Requisitos das ferramentas de instalação** 

As ferramentas a seguir são recomendadas ao instalar o equipamento. Use outras ferramentas  auxiliares no local, se necessário. 

Óculos de  segurança 

Alicates    
Calçados de  segurança 

Desencapador    
Luvas de  segurança   
Máscara    
contra poeira Caneta    
Martelo de  borracha 

diagonais   
de fio Martelete Presilhas    
marcadora Nível Aspirador    
Multímetro de cabo 

**5.2 Instalação** 

**5.2.1 Movimentação do carregador**  
de pó Torquês 

| CUIDADO |
| ----- |
| Mova o carregador para o local antes da instalação. Siga as instruções abaixo para evitar  ferimentos ou danos ao equipamento.  1\. Considere o peso do equipamento antes de movê-lo. Designe pessoal suficiente para  mover o equipamento, para evitar ferimentos.  2\. Use luvas de segurança para evitar ferimentos.  3\. Mantenha o equipamento em equilíbrio durante a movimentação para evitar que ele caia. |

22   
05 Instalação 

**5.2.2 Instalação do carregador (na parede)** 

| AVISO |
| ----- |
| • Evite os canos de água e cabos dentro da parede ao fazer furos.  • Use óculos de proteção e uma máscara contra poeira para evitar que a poeira seja inalada  ou entre em contato com os olhos ao fazer furos.  • Certifique-se de que o carregador esteja firmemente instalado em caso de queda. |

**Etapa 1** Pegue a placa de montagem do carregador. 

**Etapa 2** Coloque a placa de montagem, o quadro de distribuição do RCBO e o soquete falso na parede  horizontalmente e marque as posições para perfurar os furos. 

**Etapa 3** Faça os furos usando o martelete. 

**Etapa 4** Use os parafusos de expansão para fixar a placa de montagem, o quadro de distribuição do  RCBO e o soquete falso na parede. 

**Etapa 5** Instale o carregador na placa de montagem e fixe a placa de montagem. 1 3   
2 

GW11K-HCA-20、   
GW22K-HCA-20 

**2** 

**1** 

**1** 

GW7K-HCA-20 

Depth:45mm 

GW11K-HCA-20、 GW22K-HCA-20   
Depth: 35mm 

GW7K-HCA-20   
Depth:50mm Depth:: 60mm 

4 5 M6 **2** 2N·m M6 **3** 2N·m   
**1** 

M4 **1** 0.8N·m 

GW11K-HCA-20、   
GW22K-HCA-20 GW7K-HCA-20 **2 1**

**2** 

**3** 

**2** 

**2** 

M5 2N·m 

HPA10INT0003 

23   
05 Instalação 

**5.2.3 Instalação do carregador (no suporte)** 

| AVISO |
| ----- |
| Entre em contato com o fabricante para adquirir um suporte se precisar instalar o carregador  em um suporte. |

**Etapa 1** Retire a placa de operação do suporte. 

**Etapa 2** Posicione o suporte no chão verticalmente e marque as posições para fazer os furos. Um conduíte com um diâmetro de 60 mm deve ser embutido no subsolo. **Etapa 3** Faça furos com 75 mm de profundidade, usando o martelete com broca de 15 mm de  diâmetro. 

**Etapa 4** Passe o cabo embutido através do suporte, use os parafusos de expansão para fixar o  carregador no chão e tampe os furos de fixação extras com parafusos. 

**Etapa 5** Instale o quadro de distribuição do RCBO e a placa adaptadora no suporte. **Etapa 6** Instale o soquete falso no suporte. 

**Etapa 7** Retire a placa de montagem do carregador. 

**Etapa 8** Instale a placa de montagem no suporte. 

**Etapa 9** Instale o carregador na placa de montagem. 

1   
2 3 

4   
GW7K-HCA-20   
GW11K-HCA-20、 GW22K-HCA-20 **3** 

|  |
| :---- |

**3 3**   
M4 1.2N·m 

5   
GW11K-HCA-20、GW22K-HCA-20   
**3**   
**3** 

| 2 |
| :---: |

**3**   
15mm   
Depth: 75mm 

GW7K-HCA-20 

**1 1** 

**2** 

|  |
| :---- |

|  |
| :---- |

AC cable inCom cable **1** 

**1**   
**1** 

|  |  |  |  |
| :---- | :---- | :---- | :---- |

**1** 

|  |
| :---- |

AC cable out 

**1 1 1 1** 

**3 3** 

|  |
| :---- |
|  |

**3 3** 

|  |
| :---- |

|  |
| :---- |

|  |
| :---- |

|  |
| :---- |

|  |
| :---- |

|  |  |
| :---- | :---- |
|  |  |

AC cable out 

Length of AC cable out: ≥755mm **2 2 2** 

M4 1.2N·m M5 2N·m M4 1.2N·m 

|  |
| :---- |

|  |
| :---- |

24 

|  |
| :---- |

![][image2]

6 

**1** 

**1**   
M5 2N·m 

|  |
| :---- |

7 

|  |  |
| :---- | :---- |
|  |  |

|  |
| :---- |

**2** 

|  |
| :---- |
|  |

|  |
| :---- |

|  |  |
| :---- | :---- |
|  |  |

RCBO RCD 

|  |
| :---- |

05 Instalação 

|  |
| :---- |
|  |

|  |
| :---- |

|  |
| :---- |

8 9 

|  |  |
| :---- | :---- |
|  |  |

|  |
| :---- |
|  |

**2** 

|  |  |  |  |  |
| :---- | :---- | :---- | :---- | :---- |

**~~1~~** 

|  |
| :---- |

|  |
| :---- |

|  |
| :---- |

**2** 

M5 2N·m M5 

|  |  |  |  |  |  |  |
| :---- | :---- | :---- | :---- | ----- | :---- | :---- |
|  |  |  |  | 2N·m |  |  |
|  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |

|  |  |  |  |  |  |
| :---- | :---- | :---- | :---- | :---- | ----- |
|  |  |  |  |  | HPA10INT0004 **5.2.4 Instalação do medidor MID (opcional)**  |
|  |  |  |  |  | **AVISO** |
|  |  |  |  |  | Entre em contato com o fabricante para adquirir o medidor MID, se precisar. |

GW7K-HCA-20 GW11K-HCA-20 and GW22K-HCA-20 

**2**   
**2** 

**1 1**   
**3**   
**3** 

25   
06 Conexão elétrica 

**6 Conexão elétrica** 

**6.1 Precauções de segurança**

| PERIGO |
| ----- |
| • Todas as especificações de operações, cabos e peças durante a conexão elétrica devem  estar em conformidade com as leis e regulamentos locais.  • Desconecte o interruptor upstream antes da conexão elétrica. Não trabalhe com ele ligado.  Caso contrário, pode ocorrer choque elétrico.  • Amarre cabos do mesmo tipo e coloque-os separados de cabos de tipos diferentes. Não  coloque os cabos emaranhados ou cruzados.  • Se o cabo suportar muita tensão, a conexão pode ser ruim. Reserve um certo comprimento  do cabo antes de conectá-lo à porta do cabo do carregador.  • Ao crimpar os terminais, certifique-se de que a parte condutora do cabo esteja em contato  total com os terminais. Não crimpe o revestimento do cabo com o terminal. Caso contrário,  o carregador pode não operar ou seu bloco de terminais pode ser danificado devido ao  aquecimento e outros fenômenos devido à conexão não confiável após a operação. |

| ALERTA |
| ----- |
| • Conecte os cabos de entrada CA aos terminais correspondentes, como as portas “L1”, “L2”,  “L3”, “N” e “PE”, corretamente. Caso contrário, causará danos ao carregador. • Certifique-se de que todos os núcleos do cabo estejam inseridos nos orifícios dos  terminais. Nenhuma parte do núcleo do cabo pode ser exposta.  • Certifique-se de que os cabos estejam conectados firmemente. Caso contrário, causará  danos ao carregador devido ao superaquecimento durante sua operação. |

| AVISO |
| ----- |
| • Use equipamento de proteção pessoal como sapatos de segurança, luvas de segurança e  luvas isolantes durante as conexões elétricas.  • Todas as conexões elétricas devem ser realizadas por profissionais qualificados. • As cores dos cabos nesse documento são apenas para referência. As especificações de  cabos devem atender às leis e regulamentos locais.  • Para facilitar a fiação, não se recomendam fios de alumínio e fios de cobre sólido. |

26   
06 Conexão elétrica 

**Especificações de fiação** 

| Modelo  | Cabo  | Especificação |
| ----- | ----- | ----- |
| GW7K-HCA-20 | Cabo AC externo  de três núcleos   com múltiplos fios | • Cobre, 105 ℃, 1.000 V  • Diâmetro externo: 13 a 14 mm  • Área da seção transversal do condutor: 6 mm2 |
| GW11K-HCA-20 | Cabo AC externo  de cinco núcleos  com múltiplos fios | • Cobre, 105 ℃, 1.000 V  • Diâmetro externo: 12,6 a 17,3 mm  • Área da seção transversal do condutor: 4 a  6 mm2  |
| GW22K-HCA-20 |  | • Cobre, 105 ℃, 1.000 V  • Diâmetro externo: 16,3 a 17,3 mm  • Área da seção transversal do condutor: 6 mm2 |

**Especificações do RCBO**

| Modelo do   carregador  | Tipo do  RCBO | Característica  de disparo   instantâneo do  RCBO | Corrente de   disparo    do RCBO | Corrente   nominal  do RCBO | Tensão   nominal  do RCBO |
| ----- | :---: | ----- | ----- | ----- | ----- |
| GW7K  HCA-20 | TIPO A  | C  | 30 mA | 40 A | CA 230 V   (2P) |
| GW11K  HCA-20 |  |  |  | 25 A | CA 400 V   (4P) |
| GW22K  HCA-20 |  |  |  | 40 A | CA 400 V   (4P) |

27   
06 Conexão elétrica 

**6.2 Conexão do cabo RCBO** 

| AVISO |
| ----- |
| • As instruções de instalação abaixo se aplicam a dispositivos adquiridos do fabricante do  carregador. Se o dispositivo for de outro fornecedor, você deve consultar o manual do  usuário.  • O cabo CA 1 é conectado à rede elétrica ou à saída CA do inversor e o cabo CA 2 é  conectado à entrada CA do carregador. |

**Etapa 1** Prepare o cabo CA. 

**Etapa 2** Passe o cabo CA e o terminal através do quadro de distribuição, e parafuse o terminal  CA no RCBO. 

**Etapa 3** Instale a tampa superior do quadro de distribuição do RCBO para evitar a entrada de  água ou outros materiais estranhos. 

GW7K-HCA-20   
1 2 3 

1 

2   
260mm   
12mm 12mm 

L   
N   
PE 

L   
N 

1 2   
M5 2N·m 

**1 2** 

120mm   
PE 

PE 

**1** 

12mm 230~~mm~~ 12mm 

GW11K-HCA-20, GW22K-HCA-20   
12mm 

1 2 

M5 2N·m 

1 

2   
330mm 

100mm 12mm 285mm   
L1L2L3NPE 

L1L2L3NPE 

1 2 

1 2

**2**   
**1** 

**1** 

**1** 

**1** 

HPA10ELC0002 

28   
06 Conexão elétrica 

**6.3 Conexão do cabo CA** 

| PERIGO |
| ----- |
| Conecte o cabo de entrada CA monofásico ao carregador GW7K-HCA-20; e conecte o cabo de  entrada CA trifásico aos carregadores GW11K-HCA-20 e GW22K-HCA-20.  1\. Para GW7K-HCA-20: sua tensão deve ser 230 VCA, L/N/PE; a corrente deve ser 32 A; e a  frequência deve ser 50/60 Hz.  2\. Para GW11K-HCA-20: sua tensão deve ser 400 VCA, 3L/N/PE; a corrente deve ser 16 A; e a  frequência deve ser 50/60 Hz.  3\. Para GW22K-HCA-20: sua tensão deve ser 400 VCA, 3L/N/PE; a corrente deve ser 32 A; e a  frequência deve ser 50/60 Hz. |

A figura a seguir usa o cabo CA trifásico L1, L2, L3, N, PE como exemplo. Os cabos CA  monofásicos são L, N, PE. 

**Etapa 1** Prepare o cabo CA. 

**Etapa 2** Insira o cabo de entrada CA nos terminais CA e aperte-o. 

**Etapa 3** Aperte o terminal de entrada CA no carregador. 

GW7K-HCA-20   
1 2 3   
**2**   
1.2N·m GW7K-HCA-20 :   
L1,N,PE 

17mm   
L   
N 

30.5mm 2-3N·m **5**  
GW11K-HCA-20, GW22K-HCA-20 

**4** 

: L1,L2,L3,N,PE 

**2** 0.4N·m 

25-35mm   
PE 

**1 3** 

**2** 

GW11K-HCA-20, GW22K-HCA-20 17mm 

L1L2L3NPE   
25-35mm   
**5** 

**2**   
**1** 

**2** 

**2** 

HPA10ELC0001 

29   
06 Conexão elétrica 

**6.4 Conexão do cabo de comunicação** 

| AVISO |
| ----- |
| • Ao conectar a linha de comunicação, certifique-se de que a definição da porta de fiação e  o equipamento estão totalmente compatíveis, e o caminho de alinhamento do cabo deve  evitar fontes de interferência, linhas de energia, etc., para não afetar a recepção do sinal.  • As portas não utilizadas devem ser tampadas para não comprometer o desempenho de  proteção do carregador.  • As portas RS485\_A1/B1 do carregador são para comunicação com o inversor. Para a porta  RS485 específica do inversor, consulte o manual do inversor correspondente. • Após os dispositivos serem ligados, confirme se o status da conexão do inversor está verde  sólido no SolarGo, caso contrário, a conexão do inversor falhará. ![][image3] |

**Tipo um** 

RS485\_A1 

**Tipo dois** 

Inverter 

MID meter 

EV Charger LAN 

B A 

RS485\_B1 

RS485\_B2   
RS485\_A2 

1 2 3 4 8 7 6 5 

2 1 

3 4 

1.RS485\_A1 2.RS485\_B1 

4.RS485\_B2 3.RS485\_A2 

B A   
AC Charger 

LAN 

Router 

MID meter 

Inverter 

Router 

5   
~~DI\_1~~ W4 EnWG 14a   
EnWG 14a (Optional)  
6 GND 

HCA20ELC0004 

30   
CONTEÚDO

| Tipo de inversor  | Série/Faixa de  potência  | Modelo | ARM  Software  Versão |
| ----- | ----- | ----- | ----- |
| Na rede  Omvormer | SDT G2 | GW5K-DT GW6K-DT   GW8K-DT GW10KT-DT  GW12KT-DT GW15KT-DT | 59.183 ou   acima |
|  | SDT G3 | GW4000-SDT-30 GW5000-SDT-30  GW6000-SDT-30 GW8000-SDT-30  GW10K-SDT-30 GW10K-SDT-EU30  GW12K-SDT-30 GW15K-SDT-30  GW17K-SDT-30 GW20K-SDT-30  GW12KLV-SDT-C30 GW17KLV-SDT-C30  GW23K-SDT-C30 GW25K-SDT-C30  GW27K-SDT-C30 GW20K-SDT-31  GW25K-SDT-P31 GW30K-SDT-C30 | 05.56 ou   acima |
|  |  | GW50K-SDT-C30  | 0.6 ou acima |
|  |  | GW5000-SDT-AU30 GW6000-SDT-AU30  GW8000-SDT-AU30 GW9990-SDT-AU30  GW15K-SDT-AU30 GW20K-SDT-AU30  GW25K-SDT-AU30 GW29K9-SDT-AU30   GW25K-SDT-30 GW30K-SDT-30 | 0.0 ou acima |

**31**   
CONTEÚDO

| Híbrido  Omvormer | ET G1 (5-10kW） | GW5K-ET GW6.5K-ET  GW8K-ET GW10K-ET   GW10KL-ET GW8KL-ET  GW5KN-ET GW8KN-ET  GW10KN-ET GW5KL-ET   GW6KL-ET GW6.5KN-ET | 30.290 oou   acima |
| ----- | :---- | :---- | :---- |
|  | ET G2 (6-15kW） | GW6000-ET-20 GW8000-ET-20  GW9900-ET-20 GW10K-ET-20  GW12K-ET-20 GW15K-ET-20 | 13.436 ou   acima |
|  | ET (15-30kW） | GW12KL-ET GW15K-ET   GW18KL-ET GW20K-ET   GW29.9K-ET GW30K-ET  GW25K-ET  | 13.436 ou   acima |
|  | ES G2 (3-6kW） | GW3000-ES-20 GW3600-ES-20  GW5000-ES-20 GW6000-ES-20  GW3600M-ES-20 GW5000M-ES-20  GW6000M-ES-20 GW3500L-ES-BR20  GW3600-ES-BR20 GW6000-ES-BR20 | 10.427 ou   acima |
|  | EHB | GW9.99K-EHB-AU-G11  GW5K-EHB-AU-G11  GW8.6K-EHB-AU-G11 | 31.309 ou   supérieur |
|  | EH Plus | GW3600N-EH  GW5000N-EH-BE  GW5000N-EH  GW6000N-EH |  |
| Sistema de   Armazenamento  de Energia Tudo  em-Um Residencial | ESA | GW3K-EHA-G20 GW3.6K-EHA-G20  GW5K-EHA-G20 GW6K-EHA-G20  GW8K-EHA-G20 GW10K-EHA-G20  GW9.999K-EHA-G20 | 02.100 ou   acima |

**32**   
CONTEÚDO 

**6.4.1 Conexão do cabo de comunicação RS485** 

| AVISO |
| ----- |
| • Providencie cabos trançados externos que atendam aos padrões locais. • Quando a porta RS485 não estiver em uso, tampe o conector com o plugue de borracha à  prova d’água fornecido e conecte o conector ao carregador. |

**Etapa 1** Prepare o cabo de comunicação. 

**Etapa 2** Fixe o cabo no conector. 

**Etapa 3** Conecte o conector ao carregador. 

**Tipo um** 

7-8mm 1 2 3 

**2** 

12-13mm   
0.5mm2   
0.7-0.9N·m **3** 

**2** 

**1** 

If the port  

**3** 

**Tipo dois**  
isn't used   
**1**   
**2**   
20.5mm 1.2-1.8N·m 

1 0.4-0.6N·m   
3   
7-8mm 

27-33mm   
1.5mm2   
2 

**3** 

32mm 2-3N·m **3** 

**1** 1 2 3 4 

8 7 6 5 

**2** 

HCA20ELC0007 

**33**   
06 Conexão elétrica 

**6.4.2 Conexão do cabo de comunicação LAN** 

| AVISO |
| ----- |
| • Providencie o cabo de comunicação por conta própria.  • Quando a porta LAN-2 não estiver em uso, tampe o conector com o plugue de borracha à  prova d’água fornecido e conecte o conector ao carregador. |

I   
II   
If the port isn't    
used If the port  isn't used 

**1** 

**4** 

**5** 

|  |
| :---- |

**1** 

**2**   
**3**   
**3** 

**4** 

**1**   
**2**   
**62**   
**4** 

**2** 

**7**   
**3** 

|  |
| :---- |

1 2 3 4 5 6 7 8   
1 8 

**1** 

**5** 

1 2 3 4 5 6 7 8   
1 8   
23mm 1-1.4N·m 14mm 0.5N·m **7 5** 

**6.4.3 Conexão do cabo do medidor MID (opcional)**HPA10ELC0004 

1 

GW7K-HCA-20 

12mm 

L   
N   
25-35mm 

GW11K-HCA-20, GW22K-HCA-20 12mm 

**AC**   
3   
GW7K-HCA-20 Grid side 

Charger side 

21 22   
RS485\_A RS485\_B 

L N   
**1** 

**3**   
21 22 

**1**   
L’ N’ 

COM **2** 

**4** 

**2**   
2N·m **2 4** 

0.7-0.9N·m 

L1L2L3N   
25-35mm 

GW11K-HCA-20/ GW22K-HCA-20 Grid side 

**1**   
L1 L2 L3 N 

COM 

2 

7-8mm 

**COM** 

21 22   
RS485\_A RS485\_~~B~~ 

**1**   
**3** 

**4**   
**2 2**  
2N·m **2 4** 

0.7-0.9N·m 

12-13mm   
0.5mm2 

Charger side 

HCA20ELC0005   
L1’ L2’ L3’ N’ 

34   
07 Comissionamento do equipamento 

**7 Comissionamento do equipamento** 

**7.1 Verificação antes de ligar** 

| Nº  | Item Para Verificação |
| :---: | ----- |
| 1  | O carregador está instalado firmemente em um local limpo, bem ventilado e fácil de  operar. |
| 2  | Os cabos CA de entrada e de comunicação estão conectados corretamente e com  segurança. |
| 3  | As braçadeiras de cabo estão intactas, roteadas de maneira adequada e uniforme. |
| 4  | Portas e terminais não utilizados estão vedados. |
| 5  | A tensão, frequência e outros fatores da rede são consistentes com os requisitos de  funcionamento do carregador. |

**7.2 Ligar** 

**Conectado à rede**   
**1** 

Rede elétrica Medidor de energia RCBO Carregador 

Ligue o RCBO entre o carregador e a rede. 

**Conectado ao arranjo fotovoltaico e baterias** 

Arranjo  

fotovoltaico   
Inversor 

**1** 

**~~2~~** 

Bateria   
Carregador 

**3** 

RCBO 

Medidor de energia Rede elétrica

**Etapa 1** Ligue os interruptores CA e CC no lado do inversor. **Etapa 2 (Opcional)** Ligue os interruptores no lado da bateria. **Etapa 3** Ligue o RCBO. 

35   
07 Comissionamento do equipamento 

**7.3 Carregamento de veículo elétrico** 

| PERIGO |
| ----- |
| • Não mova o veículo elétrico durante o carregamento.  • Pressione o botão de parada de emergência para desconectar a fonte de alimentação  quando ocorrer uma anormalidade durante o carregamento.  • Não carregue em dias de chuva e com trovões. Verifique se o plugue de carregamento e a  porta de carregamento do EV estejam secos se precisar carregar.  • Mantenha as crianças longe do carregador. Não é permitido que crianças usem o  carregador.  • É proibido carregar o EV quando ocorreu uma falha ou o cabo está quebrado. |

| AVISO |
| ----- |
| • Conecte o plugue de carregamento na porta de carregamento do veículo elétrico antes de  iniciar o carregamento.  • Após o término do carregamento, desconecte o plugue e recoloque sua tampa. Enrole o  cabo ao redor do soquete falso ou do próprio carregador.  • Se o EV não aceitar carregamento automático, será necessário reconectar o plugue de  carregamento do carregador para reiniciar o carregamento caso tenha sido interrompido: • No modo de início automático, reconecte o plugue e o carregamento será reiniciado; • Nos outros modos, o carregamento pode ser reiniciado ao encostar o cartão ou pelo  início via aplicativo.  |

**7.3.1 Iniciar carregamento pelo aplicativo SolarGo ou SEMS Portal** SolarGo SEMS

**AUTO Start** 

**Scheduled Charging**   
**![][image4]AUTO Start** 

36   
07 Comissionamento do equipamento 

**7.3.2 Agendar carregamento pelo aplicativo SolarGo ou SEMS Portal** SolarGo:  

**AUTO Start AUTO Start** 

**Scheduled Charging** 

SEMS: 

**AUTO Start**

**Scheduled Charging** 

37   
07 Comissionamento do equipamento 

**7.3.3 Modo de início automático** 

Quando o modo de partida AUTOMÁTICA estiver ativado, o carro começará a carregar assim  que o plugue de carregamento for conectado, sem a necessidade de passar um cartão RFID,  desde que não haja um carregamento programado definido.

SolarGo SEMS 

**AUTO Start** 

**AUTO Start** 

**Scheduled Charging** 

**7.3.4 Carregamento de cartão RFID**  

| AVISO |
| ----- |
| • O cartão RFID precisa ser vinculado ao carregador com antecedência. Consulte o capítulo  8.2.6 ou 8.3.6 para obter as etapas de vinculação.  • A sequência correta é: conecte o plugue de carregamento no veículo elétrico e, em  seguida, encoste o cartão. |

Depois de encostar o cartão, o carregador iniciará o carregamento do veículo. 

38   
08 Comissionamento do sistema 

**8 Comissionamento do sistema** 

**8.1 Indicador** 

| Indicador  | Cor  | Explicação |
| ----- | :---- | :---- |
|  | Verde LIGADO  | O carregador está em modo de espera. |
|  | Pisca em verde  | O sistema do carregador está sendo atualizado. |
|  | Azul LIGADO  | O carregador está carregando. |
|  | Vermelho LIGADO  | Ocorreu uma falha. |
|  | Status da luz indicadora quando a ativação do carregamento por cartão RFID está  anormal |  |
|  | Luz vermelha acesa  por 2 segundos | Encoste o cartão antes de conectar o plugue de  carregamento ao veículo elétrico. |
|  | Luz vermelha pisca  duas vezes  | O carregador e o cartão não correspondem. |

**8.2 Configuração e verificação de informações do carregador pelo  aplicativo SolarGo (instaladores)** 

**8.2.1 Download e instalação do aplicativo** 

**Certifique-se de que o celular atenda aos seguintes requisitos:** 

• Sistema operacional do celular: Android 4.3 ou posterior, iOS 9.0 ou posterior. • O celular pode acessar a Internet. 

• O celular é compatível com WLAN ou Bluetooth. 

Método 1: Pesquise SolarGo no Google Play (Android) ou na App Store (iOS) para baixar e  instalar o aplicativo. 

play 

**SolarGo** 

App Store 

Aplicativo    
SolarGo 

Método 2: Digitalize o código QR abaixo para baixar e instalar o aplicativo. ![][image5]![][image6]  
Aplicativo  

SolarGo

39   
08 Comissionamento do sistema 

| AVISO |
| ----- |
| Este documento é baseado no SolarGo da versão 6.5.0. O conteúdo pode variar dependendo  da versão do SolarGo. |

**8.2.2 Login no carregador** 

| AVISO |
| ----- |
| • Faça login usando a senha inicial pela primeira vez e altere a senha o quanto antes.  Para garantir a segurança da conta, recomenda-se alterar a senha periodicamente e  memorizar a nova senha.  • Se a senha for digitada incorretamente 3 vezes, a conta será bloqueada. Você pode  entrar em contato com o serviço de pós \-venda da GOODWE para obter a super senha.  Após fazer login, altere a senha de login. |

**Etapa 1** Certifique-se de que o carregador esteja ligado e funcionando corretamente. **Etapa 2** Na página inicial do app SolarGo, selecione a aba **Bluetooth**. 

**Etapa 3** Deslize para baixo ou toque em **Search Device** para atualizar a lista de dispositivos.  Encontre o dispositivo pelo número de série do carregador. Toque no nome do dispositivo para  acessar a **Home**. 

**Etapa 4** (opcional): Para a primeira conexão com o equipamento via Bluetooth, aparecerá um  aviso de pareamento. Toque em **Pair** para continuar a conexão. 

**Etapa 5** Insira a senha de login para acessar a página inicial. Senha inicial: goodwe2022. 

**Etapa 6 (opcional)**: Se a senha inicial for usada, o aplicativo solicitará que você a altere após o  login. Altere-a conforme suas necessidades.

![][image7]40   
08 Comissionamento do sistema 

**8.2.3 Introdução à página principal** 

1 

2 

**AUTO Start** 

**Scheduled Charging**

3 

4 

5 

6 

7 

8 

| Nº  | Nome/ícone  | Descrição |
| ----- | ----- | :---- |
| 1  | More  | Definir os parâmetros do carregador. Como **WiFi Configuration**,  **Ensure Minimum Charging Power etc.** |
| 2  | Device Status  | Status do carregador, como **Idle (plugged)**, **Charing** etc. |
| 3  | AUTO Start  | Iniciar o carregamento sem a necessidade de encostar o cartão após  conectar o plugue de carregamento. |
| 4  | Charging Mode  | Selecionar o modo de carregamento para veículo elétrico. |
| 5  | Start/ End   Charging | • Iniciar carregamento: Iniciar o carregamento do veículo elétrico. • Encerrar carregamento: Encerrar o carregamento do veículo elétrico. |
| 6  | Scheduled   TCharging | Definir o tempo de um único carregamento ou o tempo de ciclo de  carregamento. |
| 7  | Communication  Status | **Inverter:** indica se o carregador está se comunicando com o inversor. **Meter:** indica se o carregador está se comunicando com o medidor. **WiFi:** indica se o carregador está se comunicando com o roteador. **Cloud:** indica se o carregador está se comunicando com a nuvem. |
| 8  | Alarm Record  | Verificar os alarmes. |

41   
08 Comissionamento do sistema 

**8.2.4 Configuração de Wi-Fi** 

Configure as informações do roteador ou comutador que se comunica com o carregador  para garantir a comunicação entre o carregador e o roteador ou comutador. Caso contrário, o  carregador não conseguirá se conectar ao servidor.

**Etapa 1** Toque em **More** \> **Communication Setting** para configurar os parâmetros. **Etapa 2** Toque em **Network Name** e selecione a rede correta. Insira a **Password** da rede  selecionada. 

**Etapa 3** Habilite ou desabilite o **DHCP** conforme suas necessidades.   
**Etapa 4** Configure p **IP Address**, a **Subnet Mask**, o **Gateway Address,** e o **DNS Server** de  acordo com as informações do roteador ou comutador, se o **DHCP** estiver desabilitado. **Etapa 5** Toque em **Save** para concluir as configurações. 

![]()

| Nº  | do ambiente  | Descrição |
| ----- | ----- | ----- |
| 1  | Network Name | Selecione uma rede para estabelecer a comunicação entre o  carregador e um roteador ou comutador de rede. Em seguida,  o carregador poderá se conectar à nuvem. |
| 2  | Password  | Senha do Wi-Fi para a rede conectada real. |
| 3  | DHCP | • Habilite o DHCP quando o roteador estiver no modo IP dinâmico. • Desative o DHCP quando um interruptor for usado ou o roteador  estiver no modo IP estático. |
| 4  | IP Address | • Não configure os parâmetros quando o DHCP estiver habilitado. • Configure os parâmetros de acordo com as informações do  roteador ou interruptor quando o DHCP estiver desabilitado. |
| 5  | Subnet Mask |  |
| 6  | Gateway Address |  |
| 7  | DNS Server |  |

42   
08 Comissionamento do sistema 

**8.2.5 Configuração do modo de carregamento** 

Existem três modos de carregamento: Rápido, Prioridade de energia fotovoltaica e Energia  fotovoltaica \+ bateria. 

**Rápido** 

O carregador utiliza eletricidade da rede elétrica, dos painéis solares ou das baterias para  carregar veículos elétricos. A potência de saída do carregador é configurada como a potência  nominal por padrão, e os usuários podem ajustar a potência, desde que não exceda a nominal. 

**AUTO Start** 

**2** 

**1** 

**Scheduled Charging**

43   
08 Comissionamento do sistema 

**Prioridade de energia fotovoltaica** 

Somente a energia fotovoltaica é usada para carregar o veículo elétrico. As cargas, que  podem ser da rede elétrica ou de sistemas de backup, têm prioridade no consumo da energia  fotovoltaica, e o excedente é utilizado para carregar o veículo. 

**2 AUTO Start** 

**1** 

**Scheduled Charging** 

**Energia fotovoltaica \+ bateria** 

A energia fotovoltaica e a bateria são utilizadas para carregar o veículo elétrico. As cargas, que  podem ser da rede elétrica ou de sistemas de backup, têm prioridade no consumo de energia,  e o excedente é utilizado para carregar o veículo. 

**2 AUTO Start** 

**1** 

**Scheduled Charging**

44   
08 Comissionamento do sistema 

**8.2.6 Mais** 

**Controle dinâmico de carga**  

Depois de ativar o controle dinâmico de carga, o carregador ajustará a velocidade de  carregamento (ou até pausará o carregamento) com base nos dados do medidor e na  corrente de conexão à rede definida, para evitar o disparo do fusível principal. Quando a  corrente real consumida se aproxima da corrente de conexão à rede definida, o carregador  reduzirá a potência de carregamento até pausar, para evitar o disparo. O carregador reiniciará  automaticamente quando a diferença entre a corrente de conexão à rede e a corrente  consumida da rede atender às condições de reinício do carregador.

![]()45   
08 Comissionamento do sistema 

**Alternância de fase**

| AVISO |  |
| ----- | ----- |
| A função de alternância de fase está disponível apenas para carregadores trifásicos. |  |
|  |  |
| **Status**  | **Explicação** |
| LIGADO  | Quando a potência total de entrada for inferior a 4,2 kW, o carregador alterna  automaticamente para o modo de carregamento monofásico para evitar  o consumo de energia da rede ou o desligamento. A potência mínima de  carregamento no modo monofásico é de 1,4 kW. (O tempo de alternância de  fase é de aproximadamente 3 minutos) |
| DESLIGADO  | O carregador permanece no modo de carregamento trifásico. |

![]()

46   
08 Comissionamento do sistema 

**Configurações de energia** 

Passo: Toque em Mais \> Configurações de energia para definir os parâmetros relacionados. 8.4.5 设置功率参数 Limit Output Power 

Grid Compliance Limit 

Grid Power Limit 

Grid Compliance Limit   
Grid Compliance Limit

| Nr.  | Parâmetros  | Descrições |
| :---- | ----- | :---- |
| 1  | Limit Output  Power | Defina a potência de carregamento da estação de carregamento.  Se não configurada, a potência de carregamento padrão é a  potência nominal. |
| 2 | Ensure   Minimum   Charging   Power | „Durante intervalos limitados de regulação do sistema, o processo  de carregamento solar pode receber suporte da rede ou da bateria  para manter a potência desejada.  LIGADO: Continuar o carregamento com suporte da rede e  da bateria para garantir a potência mínima necessária para  carregamento (1,4kW para módulo de 7kW, 4,2kW para módulo de  11/22kW).  DESLIGADO: Interromper o carregamento se o excesso de energia  fotovoltaica não estiver mais disponível." |
| 3  | Grid Power   Limit | Limite de potência de pico para compra de eletricidade da rede  elétrica, a quantidade de eletricidade consumida pelo VE não  excederá a limite de potência de pico da rede. |
| 4 | Grid   Compliance   Limit | De acordo com a Lei Alemã EnWG (Lei da Indústria de Energia) 14a,  todas as SteuVEs (cargas controláveis) precisam ser submetidas  a atenuação de emergência pela rede. O operador da rede  pode reduzir temporariamente o consumo máximo de energia  comprada na rede de cargas controláveis para 4,2 kW. Se apenas  for necessário usar DI4 \- EnWG 14a, outras portas DI não precisam  ser cabeadas. |

47   
08 Comissionamento do sistema 

**Gerenciamento de cartão de veículo elétrico** 

Os cartões RFID podem ser adicionados e removidos, e cada carregador pode ser vinculado a  até 10 cartões. 

![]()**Distância por kWh**   
Você pode definir a proporção de conversão entre energia e quilometragem ou manter a  configuração padrão.

![]()  
48   
08 Comissionamento do sistema 

**Atualização de Equipamentos** 

**Passo:** Toque em Mais \> Atualização de Equipamentos para atualizar o carregador de VE. 

**Alterar Senha de Login** 

**Passo:** Toque em Mais \> Alterar Senha de Login para alterar a senha. 

**Restaurar Configurações de Fábrica** 

| AVISO |
| ----- |
| Após restaurar as configurações de fábrica, a senha voltará à senha inicial goodwe2022. |

**Passo:** Toque em Mais \> Restaurar Configurações de Fábrica.

49   
08 Comissionamento do sistema 

**8.3 Configuração e verificação de informações do carregador pelo  aplicativo SEMS Portal (instaladores)** 

**8.3.1 Download e instalação do aplicativo** 

**Requisito de telefone celular:** 

• Sistema operacional: Versões 4.3 ou posteriores para Android; versões 9.0 ou posteriores  para iOS. 

• Compatível com conexão à internet e navegação online. 

• Suporta conexão WLAN/Bluetooth. 

Método 1 Pesquise SEMS Portal no Google Play (Android) ou na App Store (iOS) para baixar e  instalar; 

Método 2 Digitalize o código QR abaixo para baixar e instalar. 

Aplicativo SEMS Portal 

**8.3.2 Registrar uma conta de usuário final** 

Toque em **Register** e preencha os campos para concluir o cadastro. 

**2**

Observação: Selecione    
**sua região** com base na    
localização da estação    
**1**   
de energia. Uma seleção    
incorreta pode causar    
falha na criação da    
estação de energia. 

50   
08 Comissionamento do sistema 

**8.3.3 Login no aplicativo** 

| AVISO |
| ----- |
| Já possui a conta e a senha. |

Digite a conta e a senha, toque em **Login** e acesse o aplicativo SEMS Portal. ![]()**1![]()**

51   
08 Comissionamento do sistema 

**8.3.4 Criação da estação de energia**  

Etapa 1 Siga as etapas abaixo e entre na página **Create Plant**. 

Etapa 2 Leia as instruções, insira os dados solicitados e toque em **Submit**. (\*refere-se aos itens  obrigatórios) 

Etapa 3 Siga as instruções para adicionar os dispositivos e concluir a criação. (Ou toque em **ADD** na página principal para incluir novos dispositivos.) 

![]()![]()Insira os dados solicitados   
Digitalize o código QR do  

dispositivo para adicionar

**2** 

Adicionar dispositivos 

**1 ![]()**  
52   
08 Comissionamento do sistema 

**8.3.5 Configuração do modo de carregamento** 

Existem três modos de carregamento: Rápido, Prioridade de energia fotovoltaica e Energia  fotovoltaica \+ bateria. 

![]()![]()**Auto Start AUTO Start**   
**Rápido** 

O carregador utiliza eletricidade da rede elétrica, dos painéis solares ou das baterias para  carregar veículos elétricos. A potência de saída do carregador é configurada como a potência  nominal por padrão, e os usuários podem personalizar a potência de saída conforme suas  necessidades (desde que não exceda a potência nominal). 

![]()![]()![]()  
**1** 

**2 AUTO Start**

53   
08 Comissionamento do sistema 

**Prioridade de energia fotovoltaica** 

Somente a energia fotovoltaica é usada para carregar o veículo elétrico. As cargas têm  prioridade no consumo da energia fotovoltaica, e o excedente é utilizado para carregar  o veículo. 

**1** 

**AUTO Start**

**2 ![]()**

54 

**Energia fotovoltaica \+ bateria**   
08 Comissionamento do sistema 

A energia fotovoltaica e a bateria são utilizadas para carregar o veículo elétrico. As cargas têm  prioridade no consumo da energia, e o excedente é utilizado para carregar o veículo. 

**1 ![]()**  
**![]()![]()**  
**2** 

**AUTO Start**

**3 ![]()**

55   
08 Comissionamento do sistema 

**8.3.6 Configuração** 

**Controle dinâmico de carga** 

**![]()![]()![]()![]()Grid Connection![]()**

56   
08 Comissionamento do sistema 

**Garantir potência mínima de carregamento**

**![]()![]()**57   
08 Comissionamento do sistema 

**Gerenciamento de cartões RFID**

**![]()![]()![]()![]()**

58   
08 Comissionamento do sistema 

**Alternância de fase** 

| AVISO |
| ----- |
| A função de alternância de fase está disponível apenas para carregadores trifásicos. |

![]()  
**Distância por kWh** 

Você pode definir a proporção de conversão entre energia e quilometragem ou manter a  configuração padrão.

![]()![]()![]()59   
09 Manutenção 

**9 Manutenção** 

**9.1 Desligar o carregador** 

| PERIGO |
| ----- |
| Desligue o carregador antes das operações e manutenção. Caso contrário, o carregador pode  ser danificado ou podem ocorrer choques elétricos. |

Desconecte o RCBO entre o carregador e a rede/o inversor. 

**9.2 Desmontar o carregador** 

| ALERTA |
| ----- |
| • Certifique-se de que o carregador esteja desligado.  • Use EPI adequado antes de qualquer operação. |

**Etapa 1** Desconecte todos os cabos, incluindo cabos CA e de comunicação. **Etapa 2** Remova o carregador da placa de montagem. 

**Etapa 3** Remova a placa de montagem. 

**Etapa 4** Guarde o carregador adequadamente. Se o carregador precisar ser usado  posteriormente, certifique-se de que as condições de armazenamento atendam aos requisitos. 

**9.3 Descartar o carregador** 

Se o carregador não funcionar mais, descarte-o de acordo com os requisitos locais de descarte  de resíduos de equipamentos elétricos. O carregador não pode ser descartado com o lixo  doméstico. 

**9.4 Manutenção de rotina**

| Item de manutenção  | Método de manutenção  | Período de manutenção |
| ----- | :---- | ----- |
| Botão de parada de  emergência | Ligue e desligue o EMS três vezes  consecutivas para se certificar de que  está funcionando corretamente. | Uma vez a cada 6 meses |
| Conexão elétrica | Verifique se os cabos estão bem  conectados. Verifique se os cabos  estão quebrados ou se há algum  núcleo de cobre exposto. | Uma vez a cada 6 a 12 meses |
| Vedação | Verifique se todos os terminais e  portas estão devidamente vedados.  Vede novamente o orifício do cabo  se não estiver vedado ou for muito  grande. | Uma vez a cada 6 a 12 meses |

60   
09 Manutenção 

**9.5 Solução de problemas** 

O carregador mostra em vermelho quando há falha. Faça login no aplicativo SEMS Portal ou no  aplicativo PV Master para obter a solução de problemas detalhada. 

Realize a solução de problemas de acordo com os seguintes métodos. Entre em contato com o  serviço pós-venda se esses métodos não funcionarem. 

Reúna as informações abaixo antes de entrar em contato com o serviço pós-venda, para que os  problemas sejam resolvidos rapidamente. 

1\. Informações do carregador como número de série, versão do software, data de instalação,  hora da falha, frequência da falha etc. 

2\. Ambiente de instalação, incluindo condições climáticas etc. É recomendável fornecer algumas  fotos e vídeos para auxiliar na análise do problema. 

3\. Situação da rede elétrica.

| Nº  | Falha  | Causa  | Soluções |
| :---- | :---- | :---- | :---- |
| 1 | Falha na conexão  da pistola | O carregador está   desconectado durante o  carregamento. | Reconecte o carregador. |
| 2 | Parada de   emergência | O botão de parada de  emergência está sendo  pressionado. | Solte o botão. |
| 3 | Erro de   aterramento | O cabo de aterramento  da entrada CA está   desconectado. | Verifique e reconecte o cabo de  aterramento. |
| 4  | Temperatura   ambiente | A temperatura do   carregador é superior a  98 graus. | O problema é removido após o  resfriamento e o carregador entra no  status de espera. |
| 5  | Sobretensão  | A entrada CA está com  sobretensão.  | O problema é removido depois que  a tensão fica normal e o carregador  entra no status de espera.  |
| 6  | Subtensão  | A entrada CA está com  subtensão. |  |
| 7  | Sobrecorrente | A conexão de saída está  em curto-circuito ou com  sobrecorrente. | O problema é removido depois que  a saída fica normal e o carregador  entra no status de espera. |

61   
09 Manutenção

| Nº  | Falha  | Causa  | Soluções |
| :---- | ----- | :---- | ----- |
| 8  | Tempo limite de  desvio | 1\. A bateria do EV está  totalmente carregada. 2\. A temperatura   ambiente é muito baixa  e a bateria não pode   ser carregada.  3\. A conexão do   carregador está   anormal. | 1\. Verifique se o carregamento da  bateria foi concluído por meio de  software.  2\. Inicie o pré-aquecimento do EV  cerca de cinco minutos antes de  carregá-lo quando o ambiente  estiver muito frio.  3\. Verifique e desconecte o conector  de carregamento e reconecte-o  cerca de 15 segundos depois. |
| 9  | Tempo limite de  preparação | A comunicação do sinal CP  não foi bem-sucedida. | 1\. Verifique se o EV está totalmente  carregado.  2\. Reconecte o conector de   carregamento após desconectá-lo  por cerca de 15 segundos. Entre  em contato com o revendedor  ou o serviço pós-venda se os   problemas não puderem ser   resolvidos. Entre em contato com  o revendedor ou o serviço pós venda, se o problema persistir. |
| 10 | Falha do contator  soldado | O componente interno  está com defeito. | Reinicie o carregador. Entre em  contato com o revendedor ou o  serviço pós-venda se os problemas  não puderem ser resolvidos. |
| 11  | Falha no medidor |  |  |
| 12 | Falha de corrente  de fuga  |  |  |
| 13  | Erro de leitura |  |  |
| 14  | Erro EEPROM |  |  |
| 15  | Erro de flash |  |  |
| 16 | Falha no detector  de vazamento |  |  |

62   
10 Parâmetros técnicos 

**10 Parâmetros técnicos** 

**Dados técnicos GW7K-HCA-20GW11K HCA-20GW22K-HCA-20** Entrada 

Tensão nominal de entrada    
(V)230\*3, L/N/PE 400\*3, 3L/N/PE 400\*3, 3L/N/PE Corrente nominal de entrada    
(A)32 16 32 Frequência nominal da rede    
CA (Hz)50/60 50/60 50/60 Saída 

Potência nominal de saída    
(W)7000 11000 22000 Tensão nominal de saída (V) 230 400 400 

Corrente nominal de saída (A) 32 16 32 Frequência nominal de saída    
(Hz)50/60 50/60 50/60 Proteção 

Proteção de corrente residual AC 30mA+ DC  6mA  

Proteção contra    
AC 30mA+ DC    
6mAAC 30mA+ DC 6mA 

sobrecorrente Integrado Integrado Integrado Proteção contra sobretensão Integrado Integrado Integrado 

Proteção contra temperatura    
excessiva Integrado Integrado Integrado Proteção contra falha de    
aterramento Integrado Integrado Integrado Proteção contra surtos de CA Type III Type III Type III 

Desligamento de emergência Integrado Integrado Integrado 

Dados gerais 

Faixa de temperatura    
operacional (℃) \-30 \~ \+50\*1 \-30 \~ \+50\*1 \-30 \~ \+50\*1

63   
10 Parâmetros técnicos

| Dados técnicos  | GW7K-HCA-20 | GW11K  HCA-20 |  | GW22K-HCA-20 |  |  |
| ----- | ----- | :---: | ----- | :---: | ----- | :---: |
| Umidade relativa  | 5% \~ 95% (Não   condensante) |  | 5% \~ 95% (Não  condensante) |  | 5% \~ 95% (Não   condensante) |  |
| Altitude operacional  máx. (m)  | 2000  |  | 2000  |  | 2000 |  |
| Método de   resfriamento  | Convecção natural  |  | Convecção   natural  |  | Convecção natural |  |
| Interface do usuário  | WLAN+APP, LED  |  | WLAN+APP, LED  |  | WLAN+APP, LED |  |
| Método de   inicialização  | APP, RFID, AUTO Start  |  | APP, RFID, AUTO  Start  |  | APP, RFID, AUTO Start |  |
| Comunicação  | Bluetooth, WiFi, RS485 （\*2), LAN |  | Bluetooth, WiFi,  RS485（\*2), LAN |  | Bluetooth, WiFi, RS485 （\*2), LAN |  |
| Modo de trabalho | Carregamento rápido Prioridade PV  PV+BATT  Carregamento   programado  Controle de carga   dinâmico |  | Carregamento  rápido  Prioridade PV  PV+BATT  Carregamento  programado  Controle de   carga dinâmico |  | Carregamento rápido Prioridade PV  PV+BATT  Carregamento   programado  Controle de carga   dinâmico |  |
| Peso (kg) | 5.2 (com cabo de  6 m)  5.6 (com cabo de  7,5 m) | 5.4 (com  cabo de  6 m)  5.6 (com  cabo de  7,5 m) |  | 6.4 (com cabo de 6 m)  7.1 (com cabo de 7,5 m) |  |  |
| Dimensão (L×A×P)  (mm) | 208\*450\*170  |  |  | PV+BATT  |  | 208\*450\*170 |

64   
10 Parâmetros técnicos 

| Emissão de ruído (dB)  | \< 20  | \< 20  | \< 20 |
| ----- | ----- | :---: | ----- |
| Potência em espera  (W) | \< 6.5  | \< 6.5  | \< 6.5 |
| Classificação de   proteção de entrada  | IP66\*2  | IP66\*2  | IP66\*2 |
| Cabo de saída e   conector | Cabo de 6 m (7,5 m  opcional)  IEC Tipo 2 | Cabo de 6 m (7,5 m  opcional)  IEC Tipo 2 | Cabo de 6 m (7,5 m  opcional)  IEC Tipo 2 |
| Acessórios  | RFID Card\*2  | RFID Card\*2  | IEC Type2 |
| Instalação  | Dentro ou fora de  casa | Dentro ou fora de  casa | Dentro ou fora de  casa |
| Protocolo de   comunicação | Modbus TCP  | Modbus TCP  | Modbus TCP |
| Proteção | É necessário um   RCD externo tipo A | É necessário um RCD  externo tipo A | É necessário um   RCD externo tipo A |
| MTBF（h）  | 100,000  | 100,000  | 100,000 |
| Classe de proteção  | I  | I  | I |
| Método de montagem  | Parede/Piso   (Suporte Opcional) | Parede/Piso (Suporte  Opcional) | Parede/Piso   (Suporte Opcional) |
| Certificações | IEC61851-1  IEC62311   IEC62955  AS/NZS 4268:2017 IEC61008-1 | IEC61851-1  IEC62311   IEC62955  AS/NZS 4268:2017 IEC61008-1 | IEC61851-1  IEC62311   IEC62955  AS/NZS 4268:2017 IEC61008-1 |
| EMC  | Classe B  | Classe B  | Classe B |
| País de fabricação  | China  | China  | China |

\*1: Faixa de temperatura operacional (℃): O carregador é de \-30\~+55℃ e o plugue de  carregamento é de 50℃ 

\*2: Classificação de proteção de entrada: O plugue de carregamento IEC tipo 2 é IP55 \*3: Para o Brasil é: 220/380/380Vac

65   
Site da GoodWe 

**GoodWe Technologies Co., Ltd.** 

No. 90 Zijin Rd., New District, Suzhou, 215011, China www.goodwe.com 

service@goodwe.com 

Contatos locais

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAASwAAAFwCAYAAAACMUb5AABwV0lEQVR4XuydB3xW1fnHASUJG8JICCS8CRmQEEIWkDDDBhVlqoCKA/dCVFTc26q1y2rtv7Wu1lmr4h5Yt62ttbbWveqoezOT3P/zPeZ5czkkyHjvfRPec/h8PyR5733vuee95/c+z3Oec06bNq644oorram0bdvW4XA4WjROsBwOR6vBCZbD4Wg1OMFyOBytBidYDoej1eAEy+FwtBqcYIVIu3btDM393txnYf/NPs5fmvrb5kpT7+v/u11H+1j77w5HkLgHLyS040NKSkqbrKysnYuKinpBXl7ekN12223ShAkTFsOSJUtOWbRo0aV77rnnVTB37twbjjnmmD9efPHF98JZZ531yCmnnPLMySef/DycdNJJLy5fvvw/J5544mvCW3DCCSe828CbDbwqvCSvvQDy89/kvCfPPPPMh+Ciiy5aOXv27JuFa0GuebnU4fw99tjjGBg/fvycMWPGVA8cODAHysrKOicnJ7dr3759G9hpp502uWeHI9Y4wQqRSCTSGS655JJbf/KTn3wlQlEHIjbesmXLoixdujT6Pxx33HHmd/73o68rxx577EaIyG3C0Ucf3SRHHXWUd8QRR3hHHnmk4fDDD/cOO+ywKIcccoh36KGHmr+DvP/6FStWvD1jxoyZ4ATLEQZOsEIk4gTL4dgunGCFiIjOUXD77bd78Mc//tFw4403er/5zW88cfcMImKeuHxRxO3zxH3bCETORlw9T1y9Zjn++OM3YXMiiEjq9U499VTv7LPP9sQdNfAz9ZSfP4JIJNLbvl+HI9Y4wQqJpKSktjfccMPDgFjdcccd3t133224//77vQceeMB76KGHDPfee68nx3k//elPDeecc453+umnb8Rpp51mRAT42f87iPWzCSp+fvwiyO+IEJx//vlGPMUaNPzoRz/yLrjgAu+8884znHvuudFjYf78+UcRn3PPkyNI3AMWElVVVf3uvPPOdXDXXXd5K1eu9O655x4DYvXwww97jz76qOGJJ57w/vrXv3p///vfDfx+2223eT/72c8MiAkWjqJWjx9E5IwzztgIFTqF4xAh+PGPfxx9f0AoL7vsMu/SSy81IFoXXXRR9HgEy39tsfAe79KlS1tcQ+ceOoLCCVZIOMFyOLYfJ1gBooUOvHTp0kNwAwHBQqjuu+8+A27gqlWrvMcee8zw1FNPGcF64YUXDP/5z3+8N99803vrrbcMzz//vPenP/3Ju/zyyw0qILiO/K8/g4oaf0PoVIA471e/+pV31VVXGfj5iiuuiL7nz3/+c+8nP/mJES0VLtxCRAt4L/91RADXDRo0KMcJliNInGCFQHJycpubbrrpDrGuPFCxwrJS6+rPf/6z9+STTxqeffZZI0r/+te/DK+++qoRqvfff9/w8ccfe19++aX32WefGf79738bIURoLrzwQgOCwv+IDiBIv/vd77xrrrnGcO2115rfCfbDr3/9a+/KK6/0fvnLXxp+8YtfGEtLz0e0NJblj2epQCKKixYtOmjnnXduA3YbOByxwAlWgGiiaGlpaScRqS9xA4Gguj/Irm7gM888Y3juuee8f/7zn97LL79seOONN7z//ve/3ocffmj49NNPvc8//9z7+uuvDd999523du1a8/Prr79uIJj/+9//3hOhNNxyyy0GRiSB16677jrv6quvNiBaWFqIlgoXoqWBf0QLt1GD8OoeIoxqbR1zzDH3IM5gt4XDEQucYAWIEyyHI7Y4wQoQFax99923BjcQoQKNWz3yyCMGjVv95S9/MeAO4ua99tprhrffftu4gh999JEBwcIl/Pbbbw2rV682grVu3TqvtrbW8OKLL5pYmbqhmvelwvWHP/zBu/7666Mu4m9/+1vv//7v/6IxLY1nEcvyx7M0BkbKgz8Ij2ideuqpn/Tv378z2G3hcMQCJ1ghIB37R/4gO9YVQkXcSmNXaln5rSsC7fDee+8Zy+qTTz4xqHWFZQVr1qwxYrV+/fqoYCF4XFOtOkSLQD2jjXDzzTcb0cLKAr9ogQbhsbL88SysLLW0iGVpzIx41llnnVU/duzYSWC3gcMRC5xghYBYVU+pGwgPPvigGRV8/PHHDU8//fRGo4IvvfSSceveeecdwwcffGAsKw2yf/HFF94333xjhMovVhs2bIgKFu/BNTV1QkVLs+xvvfVW4yqSoAqIFkF4RAuaCsJrqgOoaOmooVpZixcvPhfsNnA4YoETrBBwguVwxAYnWAEydOjQLiBu4Ld+wdI0BgLtQBoDCaLEneCVV16JuoLwv//9Lxq3AtxBYlebEyxyt7gW036A66toqXAhWhqE94uWpjtoLEvjWf40B79bqPlZiNbxxx//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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGkAAAAgCAYAAAAR1VaeAAAFVElEQVR4Xu2YC0xbVRjHN3EapqZRY6JO0kTZ2MSwzMEUItAHzEQiiVUzA7LIQIlZEQeCQyigMCJPYTyWDDoDAoMhxHWoE43yWEd5jFlKgYK0oMAQ2Sbh0TJp8ftqt1yPulk409LdX/JLy/naQ3v+555zetets1McHR35qIODw3sNDQ0PkXUWG+DZ3bv3o5mJ79aUlZX7knUWG8CuQsrLy3MLCAjwQMPCwu4k6zQJDw/3huXnrdra2vUoWafJO68FvYAaGj7uHRz8YQtZX3OoVKq70JKSEs+kpCRBRESEEM3KyhLCek7tC0Kf4r3BQYeqq6vdUbK+UmDvcUYj3hT7WvT22v6EBE15VaQLC933OvkeawkODg5AYZK9nZ+f/yRZ/19pamralJqaykfj4uKEEKKwuLjYF21ra7uffP310PSo3PSnjummpy86o2SdJn4CvghNTYjXZWZk7CHr1qJQdGxDR0ZG7h0e1rqQ9ZuFTqe7nWz7C2xIf2DTIf0dk5OTt6F1dXVu8fHxQghPgOJSKZVKPTQazR0o+T7N+W53fU3+DK2QMjMzH8E9LjAw0Btl1qB/Ebr0y4Saxp6kUameQg2nK76Efq3uT6lUOqLt7e3OhYWFz4A8NCoqipeWlsaDrcAsPOcnJCTwq6qqfNHIyMgHyb5WjUKhuBv2Ni8Ur7zY2FhhcnKy2Sqp9MWx8hxqIZWWlvpB/wlxsXH7UGZtqr9HhMLBgU5Iyu8FqP547mhLS+s2GOyHUTgAuWdnZ/PS09PNJiYmkoPOy83N5clkMg+Lm2CCO5D92wyVlVXPZWR8OBd/MD4EhS8hKCoq8pHL5feh5OtvBAT9mOGbE5V4haLM2lSfUoT+m5Cam5s54ONoTk6ODw4shG8Wn0dHR/MOiPdHo++HiCYLCgpeaWxs3IxCUBvJ/tY0bEhrAI1S6aE/WYrL3WYU22BjdKivr3dDYX3mx8TE8GFpNAvH9J2wt20g+7kKhrRQkqJVffe1EMU22Ng3wOBxy44UHUST976kkyRKQpiDDsuw+dGiL/zM2A4BPYCS/+MqELQAXV5eHqWxVNssMNt3WQ4O10K6Hl1dXbi/eYrFYh6KgyyRSHzgsOKNwqYalCLynzgQ8UY0insDbMaeMLu5FZ9UhKJD59qHOjrP7SD7thaNWi1AF1tldh5ST88uy5VE5eAwNDTs8tvlaS3McD+UWZOf/uJlVCHNGx3QDK4+JMbBgcZnt1nYkNYALa1ywfDg0Gyvun8HStatBUPSN5/UanqU/iizZpz80RXFgwOzfaX0ne8WoAsnDo+OjY3bb0hnWlr8lcePzp89q3gaJevWAiFtmTuarB040+SPMmumhTlX9Ernt1RC6uzqfh6dGh8bh8edZN1uMFya5lys/GiGbF8p5pCOHdIOKOT+KLMGpzBX1LQwSyWkPpXKC+0oL55S9/VvJet2AxvSGsA0P8vR1xZSC6lX3eeiVfeOt7V17EGZNePPP7mihs/LqIQEn90JxYMDWbMrYGZzTEtL1EIaG594tOOz6gsy2alQlFmjfXC4ZUIyGfQcQ2M1tZAQvOMAYXBRZrtp9ldXdFHxFZWQYII5ocbZy2xI1sKGRBkYNA7eFiLbV8NC6Qda2Hu4KLMdBnSrxR5m+0oxLRqcULwtRNbsCtPcDEf/aRHVkIwzl7QQBBdltsPf6y3+qX2l3DJ7kvngoJ+nGtIVRaMWfrRyUbJGk2sh1eSzIVkLGxJlLMtPFNm+Gv7p4EAbk9HoZFY/b98h3Qz+q5Bgcm20mErWWG7A0oURLcxwLkrWWGwENqQ1ACw/h8F7ULJmL/wOQXzHnfSrGMgAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,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>

[image5]: <data:image/png;base64,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>

[image6]: <data:image/png;base64,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>

[image7]: <data:image/png;base64,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>