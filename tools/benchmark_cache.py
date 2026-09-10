"""Offline benchmark against the exact upstream MemoryCache implementation."""

import argparse
import json
import platform
import random
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', default='99c3fec10e23ab3ede55888a03ae2faa40f40cf9')
    parser.add_argument('--size', type=int, default=5000)
    parser.add_argument('--accesses', type=int, default=20000)
    parser.add_argument('--pairs', type=int, default=7)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'src'))
    from cache import MemoryCache
    source = subprocess.check_output(['git', 'show', args.baseline + ':src/cache.py'], cwd=root).decode('utf-8')
    baseline = types.ModuleType('benchmark_baseline_cache')
    sys.modules[baseline.__name__] = baseline
    exec(compile(source, args.baseline + ':src/cache.py', 'exec'), baseline.__dict__)
    rng = random.Random(20260908)
    keys = [str(rng.randrange(args.size)) for _ in range(args.accesses)]

    def measure(cache_type):
        cache = cache_type(maxsize=args.size)
        for index in range(args.size):
            cache.set(str(index), index)
        start = time.perf_counter()
        checksum = sum(cache.get(key) for key in keys)
        return time.perf_counter() - start, checksum

    observations = {'baseline': [], 'refactored': []}
    for pair in range(args.pairs):
        order = [('baseline', baseline.MemoryCache), ('refactored', MemoryCache)]
        if pair % 2:
            order.reverse()
        checksums = []
        for name, cache_type in order:
            elapsed, checksum = measure(cache_type)
            observations[name].append(elapsed)
            checksums.append(checksum)
        assert len(set(checksums)) == 1
    medians = {name: statistics.median(values) for name, values in observations.items()}
    print(json.dumps({'python': platform.python_version(), 'baseline_commit': args.baseline,
        'size': args.size, 'accesses': args.accesses, 'pairs': args.pairs,
        'seed': 20260908, 'seconds': observations, 'median_seconds': medians,
        'speedup': medians['baseline'] / medians['refactored'],
        'scope': 'MemoryCache hot reads only; excludes network, AI, startup and exports'}, indent=2))


if __name__ == '__main__':
    main()
