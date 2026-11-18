from decimal import Decimal as D
from .rules import reconcile,adjudicate
def execute(ctx):
    disputes,held_leases=adjudicate(ctx['leases'],ctx['payments'],ctx['tickets'],ctx.get('races',[]))
    balances=reconcile(ctx['payments'],ctx['tickets'],held_leases)
    held_by_channel={}
    for dispute in disputes:
        for claim in dispute['claims']:
            if claim['lease'] in held_leases:
                held_by_channel[claim['channel']]=held_by_channel.get(claim['channel'],D(0))+D(claim['amount'])
    known={row['channel'] for row in balances}
    for name in sorted(held_by_channel):
        if name not in known:balances.append({'channel':name,'paid':D(0),'ticketed':D(0),'payments':0,'tickets':0,'delta':D(0),'state':'通过'})
    for row in balances:
        held=held_by_channel.get(row['channel'],D(0))
        row['held']=held;row['held_count']=sum(1 for dispute in disputes for claim in dispute['claims'] if claim['lease'] in held_leases and claim['channel']==row['channel'])
        if held>0 and row['state']=='通过':row['state']='待裁决'
    balances.sort(key=lambda r:r['channel'])
    ctx['disputes']=disputes;ctx['held_leases']=sorted(held_leases);ctx['channel_balances']=balances
    pending=sum(1 for d in disputes if d['state']=='待裁决')
    ctx['stages'].append({'title':'渠道对账','rows':balances,'metrics':{'渠道':len(balances),'有效支付':len(ctx['payments']),'悬单':len(ctx['payments'])-len(ctx['tickets']),'待裁决组':pending,'搁置票款':str(sum((D(d['held_amount']) for d in disputes),D(0)))}});return ctx
