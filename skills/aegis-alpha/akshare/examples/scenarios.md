# akshare Scenarios

## a-stock-daily
- Trigger: "查 000001 日线"
- Invocation: `python scripts/dispatch.py --command a-stock-daily --payload '{"symbol":"000001"}'`

## macro-pmi
- Trigger: "查中国 PMI"
- Invocation: `python scripts/dispatch.py --command macro-pmi --payload '{}'`
