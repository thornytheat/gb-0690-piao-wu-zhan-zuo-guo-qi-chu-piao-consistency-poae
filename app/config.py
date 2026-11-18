from pathlib import Path
TITLE = '票务占座过期与出票一致性'
SHORT = 'seat-expiry'
STAGES = ['receive', 'seats', 'leases', 'payments', 'tickets', 'reconcile', 'replay']
MODULES = ['渠道接收', '座席映射', '租约回放', '支付归属', '出票核验', '渠道对账', '补传复核']
COLUMNS = {'id': '事件号', 'channel': '渠道', 'seat': '座席', 'order': '订单', 'time': '时刻 UTC', 'type': '事件', 'expires': '到期 UTC', 'version': '版本', 'state': '状态', 'payment': '支付状态', 'ticket': '票号', 'reason': '原因', 'code': '原因码', 'line': '行号', 'count': '数量', 'lease': '租约号', 'amount': '金额 CNY', 'key': '业务键', 'detail': '依据', 'late_minutes': '迟到 min'}
DEFAULTS = {'observation_end': '2026-11-18T00:00:00+08:00', 'late_minutes': '10'}
RULE_VERSION = "2026.11.18-v2"
SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"
MAX_BYTES = 4 * 1024 * 1024

COLUMNS.update({'start':'占座起 UTC','end':'租约止 UTC','paid':'支付 CNY','ticketed':'出票 CNY','delta':'悬单 CNY','payments':'支付笔','tickets':'出票笔'})
COLUMNS.update({'race_id':'竞座号','race_status':'裁决状态','held':'搁置 CNY','held_count':'搁置笔','winner_channel':'认票渠道','held_amount':'搁置票款 CNY','evidence':'证据链','verdict':'裁决意见','payment':'支付事件','source_line':'来源行'})
