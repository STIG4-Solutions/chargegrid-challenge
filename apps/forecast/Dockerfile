# Imagem do job de previsao, separada da API de proposito.
#
# `lightgbm` traz binario nativo e nao pode entrar na imagem que roda o
# rebalanceamento de potencia: um import quebrado ali derrubaria o que impede o
# disjuntor de abrir. Aqui, no maximo, deixa de haver previsao.
FROM python:3.12-slim

WORKDIR /forecast

# libgomp e' o runtime de OpenMP que o LightGBM exige em tempo de execucao.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Sem CMD: este container nao fica de pe'. E' chamado sob demanda com
# `treinar.py` ou `exportar.py`, doze vezes por ano.
