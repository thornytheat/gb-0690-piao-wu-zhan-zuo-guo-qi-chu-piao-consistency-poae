import json
import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.config import SAMPLES
from app.normalize import instant
from app.modules.m3_leases.rules import replay
from app.modules.m6_reconcile.rules import reconcile,adjudicate

RACE=(SAMPLES/'race.csv').read_bytes()
END=instant('2026-11-18T00:00:00+08:00')

def hold(id_,seat,channel,order,t,exp):
    return dict(id=id_,time=instant(f'2026-11-17T{t}:00+08:00'),type='hold',seat=seat,
                order=order,expires=instant(f'2026-11-17T{exp}:00+08:00'),channel=channel,_line=int(id_[-1])+1)

def test_same_second_cross_channel_is_race_not_overlap():
    rows=[hold('H1','A-01','官方','O1','10:00','10:15'),hold('H2','A-01','票社','O2','10:00','10:15')]
    retained,bad,leases,races=replay(rows,END)
    assert bad==[] and len(leases)==2 and len(races)==1
    assert all(l['contested'] and l['race_id']=='R001' for l in leases)

def test_different_time_overlap_still_rejected():
    rows=[hold('H1','A-01','官方','O1','10:00','10:15'),hold('H2','A-01','票社','O2','10:05','10:20')]
    retained,bad,leases,races=replay(rows,END)
    assert len(leases)==1 and races==[] and bad[0]['code']=='OVERLAP'

def test_same_second_same_channel_order_is_not_race():
    rows=[hold('H1','A-01','官方','O1','10:00','10:15'),hold('H2','A-01','官方','O1','10:00','10:15')]
    retained,bad,leases,races=replay(rows,END)
    assert races==[] and bad[0]['code']=='OVERLAP'

def test_real_race_sample_three_groups():
    r=run(RACE,stop=6,persist=False)
    assert len(r['races'])==3
    assert {x['seat'] for x in r['races']}=={'A-01','A-02','A-03'}

def test_single_complete_evidence_wins_and_money_follows_channel():
    r=run(RACE,stop=6,persist=False)
    a01=next(d for d in r['disputes'] if d['seat']=='A-01')
    assert a01['state']=='已认票' and a01['winner_channel']=='官方'
    official=next(b for b in r['channel_balances'] if b['channel']=='官方')
    # 官方成交：A-01 的100 + A-04 的150；A-02 的200 被搁置，不计入成交
    assert D(official['paid'])==D('250') and D(official['held'])==D('200')
    agency=next(b for b in r['channel_balances'] if b['channel']=='票社')
    # 票社败方付款100 不计成交，只显示搁置
    assert D(agency['paid'])==D('0') and D(agency['held'])==D('100')

def test_pending_race_excludes_all_claim_money():
    r=run(RACE,stop=6,persist=False)
    a02=next(d for d in r['disputes'] if d['seat']=='A-02')
    assert a02['state']=='待裁决' and a02['held_amount']=='400'
    assert set(r['held_leases'])=={'RH2','RH3','RH4','RH5','RH6'}
    # 搁置票款整体：100(败方)+400(双方各200)+0(无付款)
    assert r['stages'][-1]['metrics']['搁置票款']=='500'

def test_undisputed_seat_not_blocked():
    r=run(RACE,stop=6,persist=False)
    assert len(r['tickets'])==2
    assert {t['seat'] for t in r['tickets']}=={'A-01','A-04'}

def test_reconcile_skips_held_leases():
    payments=[{'channel':'官方','amount':D('100'),'lease':'L1'},{'channel':'官方','amount':D('200'),'lease':'L2'}]
    tickets=[{'channel':'官方','amount':D('100'),'lease':'L1'}]
    out=reconcile(payments,tickets,held_leases={'L2'})
    assert out[0]['paid']==D('100') and out[0]['ticketed']==D('100') and out[0]['state']=='通过'

def test_adjudicate_both_complete_forces_pending():
    # 人工构造双方证据都齐（绕过 M5 唯一座席限制的语义测试）
    leases=[{'lease':'L1','seat':'A-01','channel':'官方','order':'O1','race_id':'R001','race_status':'待裁决'},
            {'lease':'L2','seat':'A-01','channel':'票社','order':'O2','race_id':'R001','race_status':'待裁决'}]
    payments=[{'id':'P1','lease':'L1','channel':'官方','amount':D('100')},{'id':'P2','lease':'L2','channel':'票社','amount':D('100')}]
    tickets=[{'id':'T1','ticket':'TA','lease':'L1','channel':'官方','amount':D('100')},
             {'id':'T2','ticket':'TB','lease':'L2','channel':'票社','amount':D('100')}]
    races=[{'race_id':'R001','seat':'A-01','claims':[{'lease':'L1','channel':'官方','order':'O1','source_line':2},
                                                     {'lease':'L2','channel':'票社','order':'O2','source_line':3}]}]
    disputes,held=adjudicate(leases,payments,tickets,races)
    assert disputes[0]['state']=='待裁决' and held=={'L1','L2'}
    assert disputes[0]['held_amount']=='200'

def test_replay_is_idempotent_no_double_entry(raw,isolate):
    a=run(raw);b=run(raw)
    assert a['manifest']['run_id']==b['manifest']['run_id']
    assert a['disputes']==b['disputes'] and a['channel_balances']==b['channel_balances']

def test_race_replay_idempotent(isolate):
    a=run(RACE);b=run(RACE)
    assert a['manifest']['run_id']==b['manifest']['run_id']
    assert a['disputes']==b['disputes']

def test_dirty_sample_has_no_race_by_default(raw):
    r=run(raw,stop=6,persist=False)
    assert r['races']==[] and r['disputes']==[] and r['held_leases']==[]

def test_m6_page_marks_pending_seats(client):
    reply=client.post('/api/runs',json={'text':RACE.decode('utf-8')})
    run_id=reply.json['manifest']['run_id']
    page=client.get(f'/m/6?run={run_id}')
    assert page.status_code==200 and '待裁决座席'.encode() in page.data and 'A-02'.encode() in page.data
    seat_page=client.get(f'/m/3?run={run_id}')
    assert '待裁决'.encode() in seat_page.data

def test_evidence_csv_carries_race_rows(client):
    reply=client.post('/api/runs',json={'text':RACE.decode('utf-8')})
    run_id=reply.json['manifest']['run_id']
    text=client.get(f'/api/evidence.csv?run={run_id}').text
    assert 'RACE_WIN' in text and 'RACE_LOSS' in text and 'RACE_WAIT' in text

def test_race_sample_row_conservation():
    r=run(RACE,persist=False)
    assert r['audit']['input']==r['audit']['retained']+r['audit']['isolated']
