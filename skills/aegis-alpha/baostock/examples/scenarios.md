# baostock Scenarios

## index-daily
- Trigger: "查上证指数日线"
- Invocation: `python scripts/dispatch.py --command index-daily --payload '{"symbol":"sh.000001"}'`

## stock-basic
- Trigger: "查股票基础信息"
- Invocation: `python scripts/dispatch.py --command stock-basic --payload '{}'`
