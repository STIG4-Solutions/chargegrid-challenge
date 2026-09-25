<!-- GERADO por scripts/exportar_conhecimento.py a partir de docs/references/goodwe/hca-g2-user-manual-pt-br.md. Nao edite: rode o script. -->
<!-- titulo: Manual do usuário GoodWe HCA G2 -->

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
