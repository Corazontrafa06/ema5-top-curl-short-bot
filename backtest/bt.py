import pandas as pd, numpy as np, itertools, json, time
SYMS=['BTC','ETH','SOL','XRP','BNB','DOGE','ADA','AVAX','LINK','SUI']
FEE=0.00055; SLIP=0.0005; NOTIONAL=50.0; MARGIN=10.0; MAXHOLD=60; NWIN=6
now=pd.Timestamp.now(tz='UTC')
D={}
for s in SYMS:
    df=pd.read_csv(f'data/{s}USDT.csv',parse_dates=['ts'])
    df=df[df.ts+pd.Timedelta(hours=4)<=now].reset_index(drop=True)  # closed bars only
    D[s]=df
T0=D['BTC'].ts.iloc[-1]-pd.Timedelta(days=365)
SPLIT=T0+pd.Timedelta(days=243)  # ~8 months
def ma(x,n,kind): return x.rolling(n).mean() if kind=='SMA' else x.ewm(span=n,adjust=False).mean()

def prep(df,kind):
    c=df.c
    m5,m10,m30=ma(c,5,kind),ma(c,10,kind),ma(c,30,kind)
    return dict(o=df.o.values,h=df.h.values,l=df.l.values,c=c.values,m5=m5.values,m10=m10.values,m30=m30.values,ts=df.ts.values)

def signals(P,slope,entry):
    """returns list of (entry_idx, entry_price, is_limit). entry_idx = bar on which we are filled (at close for market, intrabar for limit)."""
    c,m5,m10,m30,h,o=P['c'],P['m5'],P['m10'],P['m30'],P['h'],P['o']
    n=len(c); out=[]
    for t in range(35,n):
        down=c[t]<m30[t] and m5[t]<m30[t]
        if slope: down=down and m30[t]<m30[t-3]
        curl=m5[t]>m5[t-1] and m5[t-1]<=m5[t-2]
        if not(down and curl): continue
        if entry=='a': out.append((t,c[t],t))
        elif entry=='b':
            for k in range(t+1,min(t+1+NWIN,n)):
                if m5[k]<m5[k-1]:
                    if c[k]<m30[k]: out.append((k,c[k],t))
                    break
        elif entry=='c':
            for k in range(t+1,min(t+1+NWIN,n)):
                lvl=m10[k-1]
                if h[k]>=lvl:
                    if lvl<m30[k-1]: out.append((k,max(o[k],lvl),t))
                    break
    return out

def run(P,sigs,stop,tp,start_ts):
    o,h,l,c,m5,m10,ts=P['o'],P['h'],P['l'],P['c'],P['m5'],P['m10'],P['ts']
    n=len(c); trades=[]; busy=-1
    for (k,px,t0) in sigs:
        if ts[k]<start_ts or k<=busy: continue
        entry=px*(1-SLIP)
        if stop=='swing': sp=max(h[max(0,k-5):k+1].max(),entry)*1.001
        else: sp=entry*(1+stop)
        sp=min(sp,entry*1.19)  # liquidation-ish cap at 5x
        tpp=entry*(1-tp) if isinstance(tp,float) else None
        ex=None; j=k
        for j in range(k+1,min(k+1+MAXHOLD,n)):
            if h[j]>=sp: ex=max(o[j],sp)*(1+SLIP); why='SL'; break
            if tpp and l[j]<=tpp: ex=min(o[j],tpp); why='TP'; break  # limit TP, no slip
            if tp=='ma5up' and m5[j]>m5[j-1]: ex=c[j]*(1+SLIP); why='SIG'; break
            if tp=='m10' and c[j]>m10[j]: ex=c[j]*(1+SLIP); why='SIG'; break
        else:
            if j==n-1 and j<k+MAXHOLD: 
                ex=c[j]*(1+SLIP); why='OPEN'
            else: ex=c[j]*(1+SLIP); why='TIME'
        if ex is None: continue
        q=NOTIONAL/entry
        pnl=q*(entry-ex)-FEE*NOTIONAL-FEE*q*ex
        pnl=max(pnl,-MARGIN)
        risk=q*(sp-entry)+2*FEE*NOTIONAL
        trades.append(dict(ets=ts[k],xts=ts[j],entry=entry,exit=ex,pnl=pnl,R=pnl/risk,why=why))
        busy=j
    return trades

def stats(tr):
    if not tr: return dict(n=0,wr=0,avgR=0,pf=0,net=0,mdd=0)
    df=pd.DataFrame(tr).sort_values('xts'); p=df.pnl.values
    eq=np.cumsum(p); dd=(np.maximum.accumulate(np.concatenate([[0],eq]))[1:]-eq).max()
    g=p[p>0].sum(); b=-p[p<0].sum()
    return dict(n=len(p),wr=round((p>0).mean()*100,1),avgR=round(df.R.mean(),3),pf=round(g/b,2) if b else 99,net=round(p.sum(),2),mdd=round(dd,2))

if __name__=='__main__':
    PP={(s,k):prep(D[s],k) for s in SYMS for k in ['SMA','EMA']}
    rows=[]; ALL={}
    for kind,slope,entry,stop,tp in itertools.product(['SMA','EMA'],[True,False],['a','b','c'],['swing',0.03,0.05],[0.05,0.10,'ma5up','m10']):
        tr=[]
        for s in SYMS:
            P=PP[(s,kind)]; t=run(P,signals(P,slope,entry),stop,tp,T0.to_datetime64())
            for x in t: x['sym']=s
            tr+=t
        name=f"{kind}|slope={'Y' if slope else 'N'}|entry={entry}|stop={stop}|tp={tp}"
        ALL[name]=tr
        st=stats(tr); IS=stats([x for x in tr if x['ets']<SPLIT.to_datetime64()]); OOS=stats([x for x in tr if x['ets']>=SPLIT.to_datetime64()])
        rows.append(dict(variant=name,**st,IS_net=IS['net'],IS_pf=IS['pf'],IS_n=IS['n'],OOS_net=OOS['net'],OOS_pf=OOS['pf'],OOS_n=OOS['n']))
    R=pd.DataFrame(rows).sort_values('net',ascending=False)
    R.to_csv('results_all_variants.csv',index=False)
    pd.set_option('display.width',250); pd.set_option('display.max_columns',20)
    print('window',T0,'->',D['BTC'].ts.iloc[-1],'split',SPLIT)
    print('positive variants:',(R.net>0).sum(),'of',len(R),' both IS&OOS positive:',((R.IS_net>0)&(R.OOS_net>0)).sum())
    print(R.head(15).to_string(index=False)); print(R.tail(5).to_string(index=False))
    # grouped averages
    for col in ['entry','stop','tp','kind','slope']:
        pass
    import pickle; pickle.dump(ALL,open('all_trades.pkl','wb'))
