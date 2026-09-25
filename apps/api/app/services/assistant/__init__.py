"""Assistente do operador: Azure OpenAI com ferramentas de leitura sobre a praca.

client.py        o modelo, atras de uma interface que o teste substitui
tools.py         o que o modelo pode consultar (rotas GET das abas)
guardrails.py    guardas que valem mesmo se o modelo desobedecer
prompts.py       como responder
orchestrator.py  o laco modelo -> ferramentas -> modelo, e o que se grava
"""
