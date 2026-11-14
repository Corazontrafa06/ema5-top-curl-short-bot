import pandas as pd, numpy as np, itertools, pickle
from bt import SYMS, T0, SPLIT, FEE, SLIP, NOTIONAL, MARGIN, stats
T0n=T0.to_datetime64(); SPn=SPLIT.to_datetime64(); now=pd.Timestamp.now(tz='UTC')
def load(tf):
    out={}
    for s in SYMS:
        if tf=='4H': df=pd.read_csv(f'data/{s}USDT.csv',parse_dates=['ts']); h=4
        elif tf=='2H': df=pd.read_csv(f'data/{s}USDT_120.csv',parse_dates=['ts']); h=2
        else:
            df=pd.read_csv(f'data/{s}USDT_60.csv',parse_dates=['ts']); h=1
            if tf=='3H':
                df=df.set_index('ts').resample('3h',origin='epoch').agg(dict(o='first',h='max',l='min',c='last',v='sum')).dropna().reset_index(); h=3
                # drop incomplete 3h bucket
        df=df[df.ts+pd.Timedelta(hours=h)<=now].reset_index(drop=True)
        c=df.c; e=lambda n:c.ewm(span=n,adjust=False).mean().values
        out[s]=dict(o=df.o.values,h=df.h.values,l=df.l.values,c=c.values,m5=e(5),m10=e(10),m30=e(30),ts=df.ts.values.astype('datetime64[ns]'),hrs=h)
    return out
def sigs(P,rule,filt):
    m5,m10,m30=P['m5'],P['m10'],P['m30']; n=len(m5)
    top=m5>np.maximum(m10,m30); out=[]; last_top=-999; done=False
    for t in range(40,n):
        if top[t] and not top[t-1]: done=False
        if top[t]: last_top=t
        if rule=='cross_top': s=top[t] and not top[t-1]
        elif rule=='top_curl_down':
            s=top[t] and m5[t]<m5[t-1] and not done
            if s: done=True
        else: s=m5[t]<m10[t] and m5[t-1]>=m10[t-1] and t-last_top<=12
        if s and filt=='m10<m30' and not m10[t]<m30[t]: s=False
        if s: out.append(t)
    return out
def run(P,idx,side,stop,tp):
    o,h,l,c,m5,m10,ts=P['o'],P['h'],P['l'],P['c'],P['m5'],P['m10'],P['ts']
    n=len(c); MH=int(240/P['hrs']); tr=[]; busy=-1; sg=1 if side=='long' else -1
    for k in idx:
        if ts[k]<T0n or k<=busy: continue
        e=c[k]*(1+sg*SLIP); sp=e*(1-sg*stop); tpp=e*(1+sg*tp) if tp!='x510' else None
        for j in range(k+1,min(k+1+MH,n)):
            if (side=='short' and h[j]>=sp) or (side=='long' and l[j]<=sp):
                ex=(max(o[j],sp) if side=='short' else min(o[j],sp))*(1-sg*SLIP); break
            if tpp is not None and ((side=='short' and l[j]<=tpp) or (side=='long' and h[j]>=tpp)):
                ex=min(o[j],tpp) if side=='short' else max(o[j],tpp); break
            if tpp is None and m5[j]<m10[j] and m5[j-1]>=m10[j-1]: ex=c[j]*(1-sg*SLIP); break
        else: ex=c[j]*(1-sg*SLIP)
        q=NOTIONAL/e; pnl=max(sg*q*(ex-e)-FEE*NOTIONAL-FEE*q*ex,-MARGIN)
        tr.append(dict(ets=ts[k],xts=ts[j],pnl=pnl,R=pnl/(q*abs(sp-e)+2*FEE*NOTIONAL))); busy=j
    return tr
def full(tr):
    st=stats(tr); I=stats([x for x in tr if x['ets']<SPn]); O=stats([x for x in tr if x['ets']>=SPn])
    return dict(**st,IS_net=I['net'],OOS_net=O['net'],IS_wr=I['wr'],OOS_wr=O['wr'])
EXITS=[(s,t) for s in [0.03,0.05,0.08] for t in [0.02,0.03,0.05]]+[(0.05,'x510'),(0.08,'x510')]
if __name__=='__main__':
    rows=[]; ALL={}; DATA={}
    for tf in ['1H','2H','3H','4H']:
        DATA[tf]=load(tf); print(tf,{s:len(v['c']) for s,v in list(DATA[tf].items())[:1]})
        for rule,filt in itertools.product(['cross_top','top_curl_down','top_x_below10'],['none','m10<m30']):
            S={s:sigs(DATA[tf][s],rule,filt) for s in SYMS}
            for side,(stop,tp) in itertools.product(['short','long'],EXITS):
                if tp=='x510' and side=='long': pass
                tr=[]
                for s in SYMS:
                    t=run(DATA[tf][s],S[s],side,stop,tp)
                    for x in t: x['sym']=s
                    tr+=t
                name=f'{tf}|{side}|{rule}|{filt}|SL{stop}|TP{tp}'; ALL[name]=tr
                rows.append(dict(variant=name,tf=tf,side=side,rule=rule,filt=filt,stop=stop,tp=tp,**full(tr)))
    R=pd.DataFrame(rows); R.to_csv('mtf_results.csv',index=False); pickle.dump(ALL,open('mtf_trades.pkl','wb'))
    print(len(R),'variants')
