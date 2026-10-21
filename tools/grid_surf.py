import sys
sys.path.insert(0,'/home/user1/src/rvt-sheets-dev')
from rvtsheets.decode import Decoder
from rvtsheets.reader import ob
d=Decoder(sys.argv[1]); d.doc(); f=d.f
for eid in map(int,sys.argv[2:]):
    fl=f.rec(eid)['fields']; s=ob(fl['m_pSurface'])
    print(eid, fl.get('m_text'), {k:(v if not isinstance(v,float) else round(v,3)) for k,v in s.items() if k in('m_origin','m_xVec','m_yVec','m_Envelope','m_orig','m_flip','m_normal')}, 'free',fl.get('m_freeEnd'),'bub',fl.get('m_bubbleEnd'))
