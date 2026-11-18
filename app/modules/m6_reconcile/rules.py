from decimal import Decimal as D
from collections import defaultdict
def _claim_key(lease,payments,tickets):
    # Evidence chain required to prove a sale: a payment that falls inside the lease
    # and the matching ticket accepted by M5, both on the same channel/order/seat.
    pay=next((p for p in payments if p['lease']==lease['lease']),None)
    ticket=next((t for t in tickets if t['lease']==lease['lease']),None)
    return pay,ticket
def adjudicate(leases,payments,tickets,races):
    disputes=[];held_leases=set();by_id={l['lease']:l for l in leases}
    for race in races:
        claims=[]
        for claim in race['claims']:
            lease=by_id[claim['lease']]
            pay,ticket=_claim_key(lease,payments,tickets)
            complete=pay is not None and ticket is not None
            claims.append({**claim,'payment':pay['id'] if pay else None,'ticket':ticket['ticket'] if ticket else None,
                           'amount':str(pay['amount']) if pay else '0',
                           'evidence':'付款+票据' if complete else ('仅付款' if pay else '无有效付款'),
                           'complete':complete})
        winners=[c for c in claims if c['complete']]
        if len(winners)==1:
            winner=winners[0]
            for c in claims:
                c['verdict']='认票成交' if c is winner else '败方搁置'
                if c is winner:by_id[c['lease']]['race_status']='认票成交'
                else:
                    held_leases.add(c['lease']);by_id[c['lease']]['race_status']='败方搁置'
            verdict=f"认票渠道 {winner['channel']}：唯一租约内付款且票据齐全"
            state='已认票'
        else:
            state='待裁决'
            for c in claims:
                c['verdict']='待裁决';held_leases.add(c['lease'])
                by_id[c['lease']]['race_status']='待裁决'
            verdict='双方证据均齐，禁止抢先确认，整组人工裁决' if len(winners)>1 else '无一方同时具备租约内付款与对应票据，待裁决'
        held_amount=sum((D(c['amount']) for c in claims if c['lease'] in held_leases),D(0))
        disputes.append({'race_id':race['race_id'],'seat':race['seat'],'state':state,'verdict':verdict,
                         'winner_channel':winners[0]['channel'] if len(winners)==1 else '',
                         'held_amount':str(held_amount),'claims':claims})
    return disputes,held_leases
def reconcile(payments,tickets,held_leases=None):
    held_leases=held_leases or set()
    settled_pay=[p for p in payments if p.get('lease') not in held_leases]
    settled_tix=[t for t in tickets if t.get('lease') not in held_leases]
    channels=defaultdict(lambda:{'paid':D(0),'ticketed':D(0),'payments':0,'tickets':0})
    for p in settled_pay:channels[p['channel']]['paid']+=p['amount'];channels[p['channel']]['payments']+=1
    for t in settled_tix:channels[t['channel']]['ticketed']+=t['amount'];channels[t['channel']]['tickets']+=1
    result=[]
    for name,row in sorted(channels.items()):result.append({'channel':name,**row,'delta':row['paid']-row['ticketed'],'state':'通过' if row['paid']==row['ticketed'] and row['payments']==row['tickets'] else '待出票'})
    return result
