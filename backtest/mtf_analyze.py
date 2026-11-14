import pandas as pd, numpy as np, pickle
from mtf import *
R=pd.read_csv('mtf_results.csv'); ALL=pickle.load(open('mtf_trades.pkl','rb'))
DATA={tf:load(tf) for tf in ['1H','2H','3H','4H']}
rng=np.random.default_rng(5)
def base(v,iters=100):
    tf,side,rule,filt,sl,tp=v.split('|'); sl=float(sl[2:]); tp=tp[2:]; tp=tp if tp=='x510' else float(tp)
    tr=pd.DataFrame(ALL[v]); W=[];N=[]
    for it in range(iters):
        allt=[]
        for s in SYMS:
            P=DATA[tf][s]; idx=np.where(P['ts']>=T0n)[0]; m=(tr.sym==s).sum()
            if m==0: continue
            t=run(P,np.sort(rng.choice(idx,size=min(len(idx),m*4),replace=False)),side,sl,tp)
            if len(t)>m: t=[t[i] for i in sorted(rng.choice(len(t),m,replace=False))]
            allt+=t
        st=stats(allt); W.append(st['wr']); N.append(st['net'])
    return round(np.mean(W),1),round(np.mean(N),1),round(np.percentile(N,95),1)
cols=['variant','n','wr','pf','net','mdd','IS_net','OOS_net','IS_wr','OOS_wr']
Q=R[R.n>=100]
top=Q.sort_values(['wr','net'],ascending=False).head(8).copy()
b=[base(v) for v in top.variant]; top['rand_wr']=[x[0] for x in b]; top['rand_net']=[x[1] for x in b]; top['rand_net_p95']=[x[2] for x in b]
pd.set_option('display.width',260); pd.set_option('display.max_columns',30)
print('TOP 8 BY WR (n>=100)'); print(top[cols+['rand_wr','rand_net','rand_net_p95']].to_string(index=False))
q60=Q[Q.wr>=60].sort_values('net',ascending=False).head(8).copy()
b=[base(v) for v in q60.variant]; q60['rand_wr']=[x[0] for x in b]; q60['rand_net']=[x[1] for x in b]; q60['rand_net_p95']=[x[2] for x in b]
print('\nBEST NET WITH WR>=60'); print(q60[cols+['rand_wr','rand_net','rand_net_p95']].to_string(index=False))
# edge over random WR for all wr>=60 tops
print('\nby tf/side mean net:'); print(Q.groupby(['tf','side'])[['wr','net','pf']].mean().round(1).to_string())
print('\nby rule/side:'); print(Q.groupby(['rule','side'])[['wr','net']].mean().round(1).to_string())
print('count positive both IS/OOS & wr>=60:',((Q.wr>=60)&(Q.IS_net>0)&(Q.OOS_net>0)).sum(),'of',(Q.wr>=60).sum())
pd.concat([top,q60]).to_csv('mtf_top_with_baseline.csv',index=False)
best=q60.variant.iloc[0]; t=pd.DataFrame(ALL[best])
print('\nper coin',best); print(t.groupby('sym').pnl.agg(['count','sum',lambda x:(x>0).mean()*100]).round(1).to_string())
