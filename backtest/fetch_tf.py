import os
import requests, pandas as pd, time
SYMS=['BTC','ETH','SOL','XRP','BNB','DOGE','ADA','AVAX','LINK','SUI']
os.makedirs("data", exist_ok=True)
end=int(time.time()*1000); start=end-(365+25)*86400*1000
for iv in ['60','120']:
  for s in SYMS:
    sym=s+'USDT'; rows=[]; e=end
    while True:
        l=requests.get('https://api.bybit.com/v5/market/kline',params=dict(category='linear',symbol=sym,interval=iv,end=e,limit=1000),timeout=20).json()['result']['list']
        if not l: break
        rows+=l; o=int(l[-1][0])
        if o<=start: break
        e=o-1; time.sleep(0.15)
    df=pd.DataFrame(rows,columns=['ts','o','h','l','c','v','to']).astype(float).drop_duplicates('ts').sort_values('ts')
    df=df[df.ts>=start]; df['ts']=pd.to_datetime(df.ts,unit='ms',utc=True); df.to_csv(f'data/{sym}_{iv}.csv',index=False); print(iv,sym,len(df))
