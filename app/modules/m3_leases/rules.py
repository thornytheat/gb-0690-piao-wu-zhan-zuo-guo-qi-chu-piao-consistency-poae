from app.reasons import rejected
# Lease replay owns only holds/releases; payment and issue events are judged by later modules.
# Same-instant holds from different channels both grab the seat: they form a race that M6
# adjudicates from in-lease payment + ticket evidence instead of being rejected outright.
def replay(rows,end):
    active={};leases=[];bad=[];retained=[];race_seq=0
    priority={'release':0,'hold':1,'pay':2,'issue':3}
    for row in sorted(rows,key=lambda x:(x['time'],priority[x['type']],x['id'])):
        seat=row['seat'];current_list=active.get(seat,[])
        # Expired leases (end <= event time) drop out of the active set; the seat is reusable.
        alive=[l for l in current_list if l['end']>row['time']]
        if len(alive)!=len(current_list):
            current_list=alive
            if current_list:active[seat]=current_list
            else:active.pop(seat,None)
        if row['type']=='hold':
            same_instant=[l for l in current_list if l['start']==row['time']]
            if same_instant and any(l['channel']!=row['channel'] or l['order']!=row['order'] for l in same_instant):
                race_seq+=1;race_id=f'R{race_seq:03d}'
                lease={'lease':row['id'],'seat':seat,'order':row['order'],'channel':row['channel'],'start':row['time'],'end':row['expires'],'expires':row['expires'],'released':False,'source_line':row['_line'],'contested':True,'race_id':race_id,'race_status':'待裁决'}
                leases.append(lease);current_list.append(lease);active[seat]=current_list
                for l in same_instant:
                    l['contested']=True;l['race_id']=race_id;l['race_status']='待裁决'
                retained.append(row);continue
            if current_list:
                bad.append(rejected(row,'OVERLAP','座席仍被其他租约占用'));continue
            lease={'lease':row['id'],'seat':seat,'order':row['order'],'channel':row['channel'],'start':row['time'],'end':row['expires'],'expires':row['expires'],'released':False,'source_line':row['_line'],'contested':False,'race_id':None,'race_status':''}
            leases.append(lease);active[seat]=[lease]
        elif row['type']=='release':
            target=next((l for l in current_list if l['order']==row['order']),None)
            if target is None:bad.append(rejected(row,'STATE','释放事件没有对应占座'));continue
            target['end']=row['time'];target['released']=True
            remaining=[l for l in current_list if l is not target]
            if remaining:active[seat]=remaining
            else:active.pop(seat,None)
        retained.append(row)
    for lease in leases:
        lease['state']='已释放' if lease['released'] else '已过期' if lease['end']<=end else '占用中'
    races=[]
    seen=set()
    for lease in leases:
        rid=lease.get('race_id')
        if rid and rid not in seen:
            seen.add(rid)
            group=[l for l in leases if l.get('race_id')==rid]
            races.append({'race_id':rid,'seat':group[0]['seat'],'time':min(l['start'] for l in group),'claims':sorted(({'lease':l['lease'],'channel':l['channel'],'order':l['order'],'source_line':l['source_line']} for l in group),key=lambda c:c['source_line'])})
    races.sort(key=lambda r:r['race_id'])
    return retained,bad,leases,races
