#!/usr/bin/env python3
"""EMA5 Top-Curl SHORT 1H — ALERT-ONLY bot for Bybit USDT perpetuals.

Rule (backtest/mtf.py, rule=top_curl_down, filt=none, timeframe 1H):
  On every newly CLOSED 1H candle t:
    EMA5[t] > max(EMA10[t], EMA30[t])      (yellow EMA5 is "on top" of green EMA10 & purple EMA30)
    and EMA5[t] < EMA5[t-1]                (yellow curls down)
    and it is the FIRST curl-down since EMA5 last went on top
  -> SHORT alert at current price. SL +8%, TP1 -3%, TP2 -5%, max leverage 5x.

This bot ONLY prints/sends alerts. It has no order code and needs no API keys
(Bybit public market data only). Not financial advice / bukan saran finansial.
"""
import json, os, sys, time, datetime as dt, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor


def _load_dotenv(path):
    """Minimal .env loader (KEY=VALUE lines). Existing env vars win."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


BASE = os.path.dirname(os.path.abspath(__file__))
_load_dotenv(os.path.join(BASE, ".env"))

E = os.environ.get
BYBIT_HOSTS = [h.strip() for h in E("BYBIT_HOSTS", "https://api.bybit.com,https://api.bytick.com").split(",") if h.strip()]
MIN_TURN = float(E("MIN_TURNOVER_USD", "5e6"))      # 24h turnover >= $5M
MIN_AGE_D = float(E("MIN_AGE_DAYS", "30"))          # listed >= 30 days
MAX_ALERTS = int(E("MAX_ALERTS_PER_HOUR", "0"))     # 0 = unlimited (send all)
LATE_PCT = float(E("LATE_PCT", "3"))                # skip if price moved >3% since candle close
DELAY_SEC = int(E("DELAY_SEC", "60"))               # check 60s after candle close
FRESH_SEC = int(E("FRESH_SEC", "1200"))             # don't alert on candles older than 20 min
THREADS = int(E("THREADS", "4"))
SL_PCT, TP1_PCT, TP2_PCT = float(E("SL_PCT", "0.08")), float(E("TP1_PCT", "0.03")), float(E("TP2_PCT", "0.05"))
MAX_LEV = int(E("MAX_LEVERAGE", "5"))
TG_TOKEN, TG_CHAT = E("TELEGRAM_BOT_TOKEN", ""), E("TELEGRAM_CHAT_ID", "")
WEBHOOK_URL = E("WEBHOOK_URL", "")
STATE_PATH = E("STATE_FILE", os.path.join(BASE, "state.json"))
TZ = dt.timezone(dt.timedelta(hours=float(E("TZ_OFFSET_HOURS", "7"))))   # default WIB
TZ_NAME = E("TZ_NAME", "WIB")
NON_CRYPTO = {"stock", "ETF", "commodity", "forex"}
H1, H4 = 3600, 4 * 3600
SIGNAL = "EMA5_TOP_CURL_SHORT_1H"


# ---------------- HTTP ----------------
def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "ema5-top-curl-short-bot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def bybit(path):
    err = None
    for h in BYBIT_HOSTS:
        for i in range(3):
            try:
                d = _get(h + path)
                if d.get("retCode") == 0:
                    return d["result"]
                err = d.get("retMsg")
                if "Too many" in str(err) or "rate" in str(err).lower():
                    time.sleep(1.5 * (i + 1)); continue
                break
            except Exception as e:
                err = e; time.sleep(0.5)
    raise RuntimeError(f"bybit error: {err}")


# ---------------- indicators ----------------
def ema(x, n):
    k = 2 / (n + 1); out = []; e = None
    for v in x:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def top_curl_signal(closes):
    """True if the LAST closed bar is a first curl-down while EMA5 is on top (identical to backtest)."""
    m5, m10, m30 = ema(closes, 5), ema(closes, 10), ema(closes, 30)
    n = len(closes); done = False; hit = False
    top = [m5[i] > max(m10[i], m30[i]) for i in range(n)]
    for t in range(40, n):
        if top[t] and not top[t - 1]:
            done = False
        s = top[t] and m5[t] < m5[t - 1] and not done
        if s:
            done = True
        if t == n - 1:
            hit = s
    t = n - 1
    return hit, {"ema5": m5[t], "ema10": m10[t], "ema30": m30[t], "close": closes[t]}


def fmt(x):
    return float(f"{x:.6g}")


# ---------------- market data ----------------
def instruments():
    l, cursor = [], ""
    for _ in range(5):
        q = "/v5/market/instruments-info?category=linear&limit=1000"
        if cursor:
            q += "&cursor=" + urllib.parse.quote(cursor)
        r = bybit(q)
        l.extend(r.get("list") or [])
        cursor = (r.get("nextPageCursor") or "").strip()
        if not cursor:
            break
    out = {}
    for x in l:
        sym = x.get("symbol") or ""
        if x.get("quoteCoin") != "USDT" or not sym.endswith("USDT"):
            continue
        if x.get("contractType") and x["contractType"] != "LinearPerpetual":
            continue
        if x.get("symbolType") in NON_CRYPTO or x.get("status") != "Trading":
            continue
        out[sym] = x
    return out


def universe(now):
    inst = instruments()
    tick = bybit("/v5/market/tickers?category=linear")["list"]
    pool = []
    for t in tick:
        x = inst.get(t["symbol"])
        if not x:
            continue
        age_d = (now - int(x.get("launchTime") or 0) / 1000) / 86400
        if age_d >= MIN_AGE_D and float(t.get("turnover24h") or 0) >= MIN_TURN:
            pool.append(t)
    return pool


def closes(sym, interval, limit, bar_sec, bar_open=None):
    rows = bybit(f"/v5/market/kline?category=linear&symbol={sym}&interval={interval}&limit={limit}")["list"]
    rows = sorted(rows, key=lambda r: int(r[0]))
    if bar_open is not None:
        rows = [r for r in rows if int(r[0]) // 1000 <= bar_open]
        if not rows or int(rows[-1][0]) // 1000 != bar_open:
            return None
    else:
        rows = [r for r in rows if int(r[0]) // 1000 + bar_sec <= time.time()]
    return [float(r[4]) for r in rows]


# ---------------- evaluation ----------------
def evaluate(bar_open, now):
    pool = universe(now)

    def one(t):
        try:
            cl = closes(t["symbol"], 60, 300, H1, bar_open)
            time.sleep(0.05)
            if not cl or len(cl) < 120:
                return None
            hit, r = top_curl_signal(cl)
            if not hit:
                return None
            c4 = closes(t["symbol"], 240, 200, H4) or []
            e4 = ema(c4, 30)[-1] if len(c4) >= 30 else None
            return t, r, e4
        except Exception as e:
            print(f"[warn] {t['symbol']}: {e}", file=sys.stderr)
            return None

    with ThreadPoolExecutor(THREADS) as ex:
        res = [x for x in ex.map(one, pool) if x]
    close_local = dt.datetime.fromtimestamp(bar_open + H1, TZ).strftime("%H:%M")
    sigs = []
    for t, r, e4 in res:
        sym = t["symbol"]; px = float(t["lastPrice"]); close = r["close"]
        fund = float(t.get("fundingRate") or 0) * 100; turn = float(t["turnover24h"])
        move = (px / close - 1) * 100
        checks = {
            "ema5_on_top": True,
            "ema5_curl_down_first": True,
            "ema10_below_ema30": r["ema10"] < r["ema30"],
            "funding_positive": fund > 0,
            "turnover_ge_20m": turn >= 20e6,
            "price_below_4h_ema30": bool(e4 and px < e4),
        }
        sigs.append({
            "signal": SIGNAL, "side": "short", "symbol": sym, "timeframe": "1H",
            "score": sum(bool(v) for v in checks.values()), "score_max": len(checks), "checks": checks,
            "entry": fmt(px), "stop": fmt(px * (1 + SL_PCT)), "tp1": fmt(px * (1 - TP1_PCT)), "tp2": fmt(px * (1 - TP2_PCT)),
            "max_leverage": MAX_LEV, "bar_close": close_local + " " + TZ_NAME, "bar_close_price": fmt(close),
            "move_since_close_pct": round(move, 2), "late": abs(move) > LATE_PCT,
            "ema5": fmt(r["ema5"]), "ema10": fmt(r["ema10"]), "ema30": fmt(r["ema30"]),
            "ema30_4h": fmt(e4) if e4 else None, "funding_pct": round(fund, 4), "turnover24h": round(turn),
            "chg24h_pct": round(float(t.get("price24hPcnt") or 0) * 100, 1),
        })
    sigs.sort(key=lambda s: (-s["score"], -s["turnover24h"]))
    return len(pool), sigs


def message(s):
    return (f"🔻 {s['symbol']} SHORT — EMA5 top-curl 1H | score {s['score']}/{s['score_max']}\n"
            f"Entry {s['entry']} | SL {s['stop']} (+{SL_PCT*100:g}%) | TP1 {s['tp1']} (−{TP1_PCT*100:g}%) | "
            f"TP2 {s['tp2']} (−{TP2_PCT*100:g}%)\n"
            f"Candle 1H tutup {s['bar_close']}: EMA5 {s['ema5']} > EMA10 {s['ema10']} & EMA30 {s['ema30']}, baru nukik turun. "
            f"Funding {s['funding_pct']:+.4f}%, turnover 24j ${s['turnover24h']/1e6:.1f}M, 24j {s['chg24h_pct']:+.1f}%.\n"
            f"Maks {MAX_LEV}x, pasang SL langsung (di 5x kena SL ≈ −{SL_PCT*MAX_LEV*100:.0f}% margin). "
            f"Alert saja, bukan saran finansial.")


# ---------------- outputs ----------------
def send_telegram(text):
    if not (TG_TOKEN and TG_CHAT):
        return
    try:
        data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": "true"}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=15).read()
    except Exception as e:
        print(f"[warn] telegram: {e}", file=sys.stderr)


def send_webhook(payload):
    if not WEBHOOK_URL:
        return
    try:
        req = urllib.request.Request(WEBHOOK_URL, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print(f"[warn] webhook: {e}", file=sys.stderr)


def emit(s):
    text = message(s)
    print(text + "\n", flush=True)
    send_telegram(text)
    send_webhook({**s, "message": text})


# ---------------- state ----------------
def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {"last_bar": None, "seen": {}}


def save_state(st):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
    os.replace(tmp, STATE_PATH)


# ---------------- main loop ----------------
def run_bar(bar_open, st, dry=False):
    now = time.time()
    n, sigs = evaluate(bar_open, now)
    seen = st.setdefault("seen", {})
    fresh = [s for s in sigs if not s["late"] and seen.get(s["symbol"]) != bar_open]
    send = fresh[:MAX_ALERTS] if MAX_ALERTS > 0 else fresh
    label = dt.datetime.fromtimestamp(bar_open + H1, TZ).strftime("%Y-%m-%d %H:%M")
    print(f"[{label} {TZ_NAME}] universe {n}, lolos {len(sigs)}, fresh {len(fresh)}, kirim {len(send)}", flush=True)
    if dry:
        for s in sigs:
            print(("[late] " if s["late"] else "") + message(s) + "\n")
        return
    for s in send:
        emit(s)
        seen[s["symbol"]] = bar_open
    # prune dedupe memory (> 3 days)
    st["seen"] = {k: v for k, v in seen.items() if v >= bar_open - 72 * H1}
    st["last_bar"] = bar_open
    save_state(st)


def main():
    if "--once" in sys.argv:   # evaluate the last closed 1H candle now and print, no state, no sending
        run_bar(int(time.time() // H1) * H1 - H1, {}, dry=True)
        return
    print(f"EMA5 top-curl SHORT 1H alert bot jalan (alert saja, tanpa order). Min turnover ${MIN_TURN/1e6:g}M, "
          f"umur >= {MIN_AGE_D:g} hari, SL +{SL_PCT*100:g}% TP1 −{TP1_PCT*100:g}% TP2 −{TP2_PCT*100:g}%, maks {MAX_LEV}x. "
          f"Telegram: {'on' if TG_TOKEN and TG_CHAT else 'off'}, webhook: {'on' if WEBHOOK_URL else 'off'}", flush=True)
    st = load_state()
    while True:
        now = time.time()
        bar_open = int(now // H1) * H1 - H1
        close_unix = bar_open + H1
        if st.get("last_bar") != bar_open and now >= close_unix + DELAY_SEC:
            if now - close_unix > FRESH_SEC:
                st["last_bar"] = bar_open; save_state(st)
                print(f"[skip] candle {dt.datetime.fromtimestamp(close_unix, TZ):%H:%M} {TZ_NAME} sudah lewat (start/restart)", flush=True)
            else:
                try:
                    run_bar(bar_open, st)
                except Exception as e:
                    print(f"[error] {e}", file=sys.stderr, flush=True)
        time.sleep(20)


if __name__ == "__main__":
    main()
