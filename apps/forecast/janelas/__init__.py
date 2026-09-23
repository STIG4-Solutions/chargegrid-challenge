"""Previsao em cinco janelas: hora, dia, semana, mes, ano.

Vive AO LADO de `pipeline/`, e nao dentro, porque `pipeline/` e' copia verbatim
de `eletroposto-forecast/src/` - o `ruff.toml` a exclui do lint e o `treinar.py`
sobrepoe `PARAMS` em vez de editar o arquivo, tudo para que a copia continue
reatualizavel da origem sem conflito.

O que este pacote reusa de la': `wape`, `treinar_um`, `QUANTIS`, `PARAMS`.
"""
