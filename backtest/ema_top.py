import pandas as pd, numpy as np, itertools, pickle
from bt import D, SYMS, T0, SPLIT, FEE, SLIP, NOTIONAL, MARGIN, MAXHOLD, prep, stats
T0n=T0.to_datetime64(); SPn=SPLIT.to_datetime64()
PP={s:prep(D[s],'EMA') for s in SYMS}

def sigs(P,rule,filt):
    c,m5,m10,m30=P['c'],P['m5'],P['m10'],P['m30']; n=len(c); out=[]
    top=m5>np.maximum(m10,m30)
    last_top=-999; ep_down_done=False
    for t in range(35,n):
        if top[t] and not top[t-1]: ep_down_done=False
        if top[t]: last_top=t
        if rule=='1_cross_top': s=top[t] and not top[t-1]
        elif rule=='3_top_curl_down':
            s=top[t] and m5[t]<m5[t-1] and not ep_down_done
            if s: ep_down_done=True
        elif rule=='4_top_then_x_below10':
            s=m5[t]<m10[t] and m5[t-1]>=m10[t-1] and t-last_top<=12
        elif rule=='5_curl_up_below30':
            s=c[t]<m30[t] and m5[t]<m30[t] and m5[t]>m5[t-1] and m5[t-1]<=m5[t-2]
        if not s: continue
        if filt in('m30dn','both') and not m30[t]<m30[t-3]: continue
        if filt in('m10<m30','both') and not m10[t]<m30[t]: continue
        out.append(t)
    return out

def run(P,idx,side,stop,tp):
    o,h,l,c,m5,m30,ts=P['o'],P['h'],P['l'],P['c'],P['m5'],P['m30'],P['ts']
    n=len(c); tr=[]; busy=-1; sg=1 if side=='long' else -1
    for k in idx:
        if ts[k]<T0n or k<=busy: continue
        e=c[k]*(1+sg*SLIP)
        if stop=='swing':
            sp=(h[k-5:k+1].max()*1.001 if side=='short' else l[k-5:k+1].min()*0.999)
            sp=min(sp,e*1.19) if side=='short' else max(sp,e*0.81)
        else: sp=e*(1-sg*stop)
        tpp=e*(1+sg*tp) if isinstance(tp,float) else None
        for j in range(k+1,min(k+1+MAXHOLD,n)):
            if side=='short' and h[j]>=sp: ex=max(o[j],sp)*(1+SLIP); w='SL'; break
            if side=='long' and l[j]<=sp: ex=min(o[j],sp)*(1-SLIP); w='SL'; break
            if tpp is not None and ((side=='short' and l[j]<=tpp) or (side=='long' and h[j]>=tpp)):
                ex=min(o[j],tpp) if side=='short' else max(o[j],tpp); w='TP'; break
            if tp=='x530' and m5[j]<m30[j] and m5[j-1]>=m30[j-1]: ex=c[j]*(1-sg*SLIP); w='SIG'; break
        else: ex=c[j]*(1-sg*SLIP); w='TIME'
        q=NOTIONAL/e; pnl=max(sg*q*(ex-e)-FEE*NOTIONAL-FEE*q*ex,-MARGIN)
        risk=q*abs(sp-e)+2*FEE*NOTIONAL
        tr.append(dict(ets=ts[k],xts=ts[j],pnl=pnl,R=pnl/risk,why=w)); busy=j
    return tr

def full(tr):
    st=stats(tr); I=stats([x for x in tr if x['ets']<SPn]); O=stats([x for x in tr if x['ets']>=SPn])
    return dict(**st,IS_net=I['net'],IS_pf=I['pf'],OOS_net=O['net'],OOS_pf=O['pf'],OOS_n=O['n'])

RULES=['1_cross_top','3_top_curl_down','4_top_then_x_below10','5_curl_up_below30']
FILTS=['none','m30dn','m10<m30','both']
EX_S=[(0.05,0.05),(0.05,0.10),('swing',0.05),('swing','x530'),(0.05,'x530')]
EX_L=[(0.05,0.05),(0.05,0.10),(0.05,'x530')]
rows=[]; ALL={}
for rule,filt in itertools.product(RULES,FILTS):
    S={s:sigs(PP[s],rule,filt) for s in SYMS}
    for side,EX in [('short',EX_S),('long',EX_L)]:
        if side=='long' and rule=='5_curl_up_below30': continue
        for stop,tp in EX:
            tr=[]
            for s in SYMS:
                t=run(PP[s],S[s],side,stop,tp)
                for x in t: x['sym']=s
                tr+=t
            name=f"{side}|{rule}|filt={filt}|stop={stop}|tp={tp}"; ALL[name]=tr
            rows.append(dict(variant=name,side=side,rule=rule,filt=filt,exit=f'{stop}/{tp}',**full(tr)))
R=pd.DataFrame(rows).sort_values('net',ascending=False); R.to_csv('ema_top_results.csv',index=False)
pickle.dump(ALL,open('ema_top_trades.pkl','wb'))
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
cols=['variant','n','wr','avgR','pf','net','mdd','IS_net','IS_pf','OOS_net','OOS_pf','OOS_n']
for side in ['short','long']:
    X=R[R.side==side]; print(f'\n== {side}: {len(X)} variants, positive {(X.net>0).sum()}, IS&OOS positive {((X.IS_net>0)&(X.OOS_net>0)).sum()}')
    print(X[cols].head(12).to_string(index=False))
    print(X.groupby('rule')[['net','pf','OOS_net']].agg(['mean','max']).round(1).to_string())
    print(X.groupby('filt')[['net','pf']].mean().round(1).to_string()); print(X.groupby('exit')[['net','pf']].mean().round(1).to_string())
print('\nbest per short rule:')
print(R[R.side=='short'].sort_values('net',ascending=False).groupby('rule').head(1)[cols].to_string(index=False))
