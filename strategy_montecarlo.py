"""
Monte Carlo strategy tester on simulated price paths (Geometric Brownian Motion).

Question: if prices follow a random walk with a small positive drift,
does a moving-average crossover strategy beat buy & hold after costs?
And what happens when we optimize parameters on past data (overfitting)?
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

rng = np.random.default_rng(42)

N_PATHS = 2000          # number of simulated markets
N_DAYS = 1000           # ~4 trading years
MU, SIGMA = 0.0003, 0.01  # daily drift and volatility
COST = 0.001            # 0.1% cost per position change


def simulate_prices(n_paths, n_days):
    r = rng.normal(MU - 0.5 * SIGMA**2, SIGMA, size=(n_paths, n_days))
    return 100 * np.exp(np.cumsum(r, axis=1)), r


def moving_average(x, w):
    c = np.cumsum(np.insert(x, 0, 0.0, axis=1), axis=1)
    ma = (c[:, w:] - c[:, :-w]) / w
    pad = np.full((x.shape[0], w - 1), np.nan)
    return np.concatenate([pad, ma], axis=1)


def strategy_returns(prices, fast, slow):
    """Long when fast MA > slow MA (signal shifted by 1 day: no look-ahead)."""
    mf, ms = moving_average(prices, fast), moving_average(prices, slow)
    pos = (mf > ms).astype(float)
    pos = np.nan_to_num(pos)
    pos = np.concatenate([np.zeros((prices.shape[0], 1)), pos[:, :-1]], axis=1)
    ret = np.diff(prices, axis=1) / prices[:, :-1]
    ret = np.concatenate([np.zeros((prices.shape[0], 1)), ret], axis=1)
    trades = np.abs(np.diff(pos, axis=1, prepend=0.0))
    return pos * ret - trades * COST


def total_return(daily):
    return np.prod(1 + daily, axis=1) - 1


prices, _ = simulate_prices(N_PATHS, N_DAYS)
bh = np.diff(prices, axis=1) / prices[:, :-1]
bh = np.concatenate([np.zeros((N_PATHS, 1)), bh], axis=1)
bh_tr = total_return(bh)

ma_tr = total_return(strategy_returns(prices, 10, 50))

beat = np.mean(ma_tr > bh_tr)
print("=== Experiment 1: fixed MA(10,50) vs buy&hold ===")
print(f"Buy&hold   mean total return: {bh_tr.mean():8.2%}  median: {np.median(bh_tr):8.2%}")
print(f"MA(10,50)  mean total return: {ma_tr.mean():8.2%}  median: {np.median(ma_tr):8.2%}")
print(f"Share of markets where strategy beats buy&hold: {beat:.1%}")
print(f"Share of markets where strategy loses money:    {np.mean(ma_tr < 0):.1%}")

# Experiment 2: overfitting. Optimize (fast, slow) on first half, test on second half.
half = N_DAYS // 2
grid = [(f, s) for f in (5, 10, 15, 20) for s in (30, 50, 80, 120) if f < s]
n_sub = 500
is_best, oos = [], []
for i in range(n_sub):
    p = prices[i:i + 1]
    scores = []
    for f, s in grid:
        d = strategy_returns(p, f, s)
        scores.append(total_return(d[:, :half])[0])
    best = grid[int(np.argmax(scores))]
    d = strategy_returns(p, *best)
    is_best.append(max(scores))
    oos.append(total_return(d[:, half:])[0])
is_best, oos = np.array(is_best), np.array(oos)

# buy&hold over the same halves for reference
bh_is = total_return(bh[:n_sub, :half])
bh_oos = total_return(bh[:n_sub, half:])

print("\n=== Experiment 2: parameter optimization (overfitting) ===")
print(f"In-sample  best-params mean return : {is_best.mean():8.2%}  (buy&hold: {bh_is.mean():.2%})")
print(f"Out-of-sample same params mean ret.: {oos.mean():8.2%}  (buy&hold: {bh_oos.mean():.2%})")
print(f"Share of markets where optimized strategy beats B&H out-of-sample: {np.mean(oos > bh_oos):.1%}")

# Plots
fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
ax[0].plot(prices[:5].T, lw=0.8)
ax[0].set_title("5 simulated price paths (GBM)")
ax[0].set_xlabel("day")

ax[1].hist(bh_tr, bins=50, alpha=0.6, label="Buy & hold")
ax[1].hist(ma_tr, bins=50, alpha=0.6, label="MA(10,50) after costs")
ax[1].set_title("Total return distribution, 2000 markets")
ax[1].legend()

ax[2].hist(is_best, bins=40, alpha=0.6, label="in-sample (optimized)")
ax[2].hist(oos, bins=40, alpha=0.6, label="out-of-sample")
ax[2].set_title("Overfitting: optimized vs. unseen data")
ax[2].legend()

plt.tight_layout()
plt.savefig("montecarlo_results.png", dpi=130)
print("\nSaved montecarlo_results.png")
