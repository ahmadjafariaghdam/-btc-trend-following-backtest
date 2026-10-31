"""
Backtest on REAL BTC/USD daily data (Bitstamp, built from 1-minute candles).

Usage: python3 -I real_data_backtest.py <data_dir> <out_dir>

1) Fixed moving-average crossover MA(10,50) vs buy & hold, after costs.
2) Walk-forward: every year, optimize (fast, slow) on the previous 3 years,
   then trade the next unseen year with those parameters.
"""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR, OUT_DIR = sys.argv[1], sys.argv[2]
COST = 0.001            # 0.1% per position change
START = "2014-01-01"    # skip the illiquid early years
TRAIN_DAYS = 3 * 365
GRID = [(f, s) for f in (5, 10, 20, 30) for s in (50, 100, 150, 200) if f < s]


def load_daily():
    parts = []
    for name in ("hist.csv.gz", "latest.csv"):
        d = pd.read_csv(f"{DATA_DIR}/{name}", usecols=["timestamp", "close"])
        parts.append(d)
    d = pd.concat(parts).drop_duplicates("timestamp").sort_values("timestamp")
    d.index = pd.to_datetime(d["timestamp"], unit="s", utc=True)
    daily = d["close"].resample("1D").last().ffill()
    return daily[daily.index >= START]


def strat_returns(close, f, s):
    ma_f = close.rolling(f).mean()
    ma_s = close.rolling(s).mean()
    pos = (ma_f > ma_s).astype(float).where(ma_s.notna(), 0.0)
    pos = pos.shift(1).fillna(0.0)              # trade next day: no look-ahead
    ret = close.pct_change().fillna(0.0)
    trades = pos.diff().abs().fillna(0.0)
    return pos * ret - trades * COST


def stats(r):
    r = r.dropna()
    eq = (1 + r).cumprod()
    years = len(r) / 365.0
    cagr = eq.iloc[-1] ** (1 / years) - 1
    mdd = (eq / eq.cummax() - 1).min()
    sharpe = r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else np.nan
    return dict(total=eq.iloc[-1] - 1, cagr=cagr, mdd=mdd, sharpe=sharpe)


def show(name, r):
    s = stats(r)
    print(f"{name:<34} total {s['total']:>10.0%}  CAGR {s['cagr']:>6.1%}  "
          f"maxDD {s['mdd']:>6.1%}  Sharpe {s['sharpe']:.2f}")


close = load_daily()
close.to_csv(f"{OUT_DIR}/btc_daily_bitstamp.csv", header=["close"])
print(f"Daily candles: {len(close)}  from {close.index[0].date()} to {close.index[-1].date()}")
print(f"Price: {close.iloc[0]:.0f} -> {close.iloc[-1]:.0f} USD\n")

bh = close.pct_change().fillna(0.0)
ma = strat_returns(close, 10, 50)

print("=== Experiment 1: whole period (fixed MA(10,50), costs included) ===")
show("Buy & hold", bh)
show("MA(10,50) crossover", ma)

# Walk-forward
oos_parts = []
rows = []
years = sorted(set(close.index.year))
for y in years:
    test_idx = close.index[close.index.year == y]
    if test_idx[0] < close.index[0] + pd.Timedelta(days=TRAIN_DAYS):
        continue
    train_end = test_idx[0]
    train = close[close.index < train_end].iloc[-TRAIN_DAYS:]
    best, best_score = None, -np.inf
    for f, s in GRID:
        sc = (1 + strat_returns(train, f, s)).prod() - 1
        if sc > best_score:
            best, best_score = (f, s), sc
    # signals use only past data, so compute on data up to end of the test year
    upto = close[close.index <= test_idx[-1]]
    r_wf = strat_returns(upto, *best).loc[test_idx]
    oos_parts.append(r_wf)
    rows.append((y, best, best_score,
                 (1 + r_wf).prod() - 1,
                 (1 + ma.loc[test_idx]).prod() - 1,
                 (1 + bh.loc[test_idx]).prod() - 1))

wf = pd.concat(oos_parts)
bh_oos = bh.loc[wf.index]
ma_oos = ma.loc[wf.index]

print(f"\n=== Experiment 2: walk-forward, unseen years {wf.index[0].year}-{wf.index[-1].year} ===")
show("Buy & hold (same period)", bh_oos)
show("MA(10,50) fixed", ma_oos)
show("MA optimized on past 3y, then traded", wf)

print("\nYear | chosen (fast,slow) | in-sample ret | OOS optimized | MA(10,50) | Buy&hold")
for y, b, sc, rw, rm, rb in rows:
    print(f"{y} | {str(b):<11} | {sc:>10.0%} | {rw:>12.0%} | {rm:>9.0%} | {rb:>8.0%}")
beat = sum(1 for r in rows if r[3] > r[5])
print(f"\nOptimized strategy beat buy&hold in {beat} of {len(rows)} unseen years.")

# Plot
fig, ax = plt.subplots(1, 2, figsize=(15, 5))
ax[0].plot((1 + bh).cumprod(), label="Buy & hold")
ax[0].plot((1 + ma).cumprod(), label="MA(10,50)")
ax[0].set_yscale("log")
ax[0].set_title("BTC/USD (Bitstamp), growth of $1, log scale, 2014-2026")
ax[0].legend()
ax[1].plot((1 + bh_oos).cumprod(), label="Buy & hold")
ax[1].plot((1 + wf).cumprod(), label="Walk-forward optimized MA")
ax[1].set_yscale("log")
ax[1].set_title("Unseen years only (parameters chosen on the past)")
ax[1].legend()
plt.tight_layout()
plt.savefig(f"{OUT_DIR}/real_data_results.png", dpi=130)
print("\nSaved real_data_results.png and btc_daily_bitstamp.csv")
