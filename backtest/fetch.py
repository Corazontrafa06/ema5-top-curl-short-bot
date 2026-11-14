import requests, pandas as pd, time, os
os.makedirs('data', exist_ok=True)
SYMS=['BTC','ETH','SOL','XRP','BNB','DOGE','ADA','AVAX','LINK','SUI']
end=int(time.time()*1000); start=end-(365+40)*86400*1000  # extra 40d warmup
for s in SYMS:
    sym=s+'USDT'; rows=[]; e=end
    while True:
        r=requests.get('https://api.bybit.com/v5/market/kline',params=dict(category='linear',symbol=sym,interval='240',end=e,limit=1000),timeout=20).json()
        l=r['result']['list']
        if not l: break
        rows+=l; oldest=int(l[-1][0])
        if oldest<=start: break
        e=oldest-1; time.sleep(0.2)
    df=pd.DataFrame(rows,columns=['ts','o','h','l','c','v','to']).astype(float).drop_duplicates('ts').sort_values('ts')
    df=df[df.ts>=start]; df['ts']=pd.to_datetime(df.ts,unit='ms',utc=True)
    df.to_csv(f'data/{sym}.csv',index=False); print(sym,len(df),df.ts.iloc[0],df.ts.iloc[-1])
