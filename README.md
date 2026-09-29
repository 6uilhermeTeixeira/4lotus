# 4lotus

Fonte oficial da estratégia unificada Lotus: gatilhos, filtros de contexto,
filtros temporais e roteadores. O serviço de inspeção usa `127.0.0.1:7774` e
nunca participa do caminho crítico de decisão da VPS.

```bash
uv sync
uv run uvicorn lotus_app.main:app --host 127.0.0.1 --port 7774
uv run python scripts/build_bundle.py --output dist/4lotus-strategies.zip
```

Bundles em `bundles/` são imutáveis para uma versão publicada. O `2lotus`
valida o SHA-256 interno antes de carregar uma estratégia.

