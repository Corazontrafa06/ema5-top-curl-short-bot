import pickle, pandas as pd, numpy as np
from ema_top import *
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
BEST='short|3_top_curl_down|filt=none|stop=0.05|tp=0.1'
tr=pd.DataFrame(ALL[BEST]); tr['ets']=pd.to_datetime(tr.ets)
print(full(ALL[BEST]), tr.why.value_counts().to_dict())
print('OOS excl last30d',tr[(tr.ets>=SPLIT.tz_localize(None))&(tr.ets<'2026-10-15')].pnl.sum().round(2),'last30d',tr[tr.ets>='2026-10-15'].pnl.sum().round(2))
rows=[]
for s in SYMS:
    t=tr[tr.sym==s]; rows.append(dict(sym=s,**stats(t.to_dict('records')),IS=round(t[t.ets<SPLIT.tz_localize(None)].pnl.sum(),2),OOS=round(t[t.ets>=SPLIT.tz_localize(None)].pnl.sum(),2)))
PS=pd.DataFrame(rows); print(PS.to_string(index=False)); PS.to_csv('ema_best_per_symbol.csv',index=False)
rng=np.random.default_rng(11); nets=[]
for it in range(300):
    allt=[]
    for s in SYMS:
        P=PP[s]; idx=np.where(P['ts']>=T0n)[0]; m=(tr.sym==s).sum()
        pick=np.sort(rng.choice(idx,size=m*3,replace=False)); t=run(P,pick,'short',0.05,0.10)
        if len(t)>m: t=[t[i] for i in sorted(rng.choice(len(t),m,replace=False))]
        allt+=t
    nets.append(stats(allt)['net'])
nets=np.array(nets); print('random short same exits: mean',nets.mean().round(1),'p5/50/95',np.percentile(nets,[5,50,95]).round(1),'share>=best',(nets>=stats(ALL[BEST])['net']).mean())
# current state
for s in SYMS:
    P=PP[s]; t=len(P['c'])-1; top=P['m5'][t]>max(P['m10'][t],P['m30'][t])
    print(s,'close',P['c'][t],'e5',round(P['m5'][t],5),'e10',round(P['m10'][t],5),'e30',round(P['m30'][t],5),'TOP' if top else 'not top', 'e5 down' if P['m5'][t]<P['m5'][t-1] else 'e5 up')
plt.style.use('dark_background')
fig,ax=plt.subplots(2,1,figsize=(12,7),sharex=True,gridspec_kw=dict(height_ratios=[3,1]))
t=tr.sort_values('xts'); t['xts']=pd.to_datetime(t.xts); eq=t.pnl.cumsum()
ax[0].plot(t.xts,eq,color='#ffd400',lw=1.8,label='EMA best: EMA5 on top of EMA10 & EMA30, first curl down -> short, SL +5% / TP -10%')
old=pd.DataFrame(pickle.load(open('all_trades.pkl','rb'))['SMA|slope=N|entry=a|stop=0.05|tp=0.05']).sort_values('xts')
ax[0].plot(pd.to_datetime(old.xts),old.pnl.cumsum(),color='#00e5a0',lw=1.2,alpha=.85,label='Previous best: SMA5 curl up below SMA30, SL +5% / TP -5%')
b=D['BTC'][D['BTC'].ts>=T0]; sh=sum(-(D[s][D[s].ts>=T0].c.values/D[s][D[s].ts>=T0].c.values[0]-1)*NOTIONAL for s in SYMS)
ax[0].plot(b.ts,sh,color='#7aa2ff',lw=1,ls='--',label='Baseline: short & hold all 10 (50 USD notional each)')
ax[0].axhline(nets.mean(),color='#ff6b6b',ls=':',lw=1,label=f'Random-short mean final ({nets.mean():.0f} USD)')
ax[0].axvline(SPLIT,color='w',ls=':',alpha=.6); ax[0].text(SPLIT,ax[0].get_ylim()[1]*.92,'  out-of-sample ->',color='w')
ax[0].axhline(0,color='grey',lw=.5); ax[0].set_ylabel('Cum. net PnL (USD, 10 margin x 5x)'); ax[0].legend(fontsize=8,loc='upper left')
ax[0].set_title('EMA5-on-top SHORT - 10 Bybit perps, 4H, 1 year (fees 0.055%/side + 0.05% slip)')
dd=eq.cummax().clip(lower=0)-eq; ax[1].fill_between(t.xts,-dd,color='#ff4d6d',alpha=.6); ax[1].set_ylabel('Drawdown USD')
plt.tight_layout(); plt.savefig('equity_best_ema_top.png',dpi=130); print('saved')
