"""Rank HTTPS package indexes using bounded, concurrent availability probes."""

import concurrent.futures
import time
import urllib.request


INDEXES = (
    'https://pypi.org/simple',
    'https://pypi.tuna.tsinghua.edu.cn/simple',
    'https://mirrors.aliyun.com/pypi/simple',
    'https://mirrors.cloud.tencent.com/pypi/simple',
)


def measure(index):
    started = time.monotonic()
    try:
        request = urllib.request.Request(index + '/pandas/', headers={'Accept': 'text/html'})
        with urllib.request.urlopen(request, timeout=5) as response:
            content = response.read(262144)
            if response.status != 200 or b'pandas-' not in content:
                return None
        return time.monotonic() - started, index
    except Exception:
        return None


def ranked_indexes():
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(INDEXES)) as executor:
        results = [result for result in executor.map(measure, INDEXES) if result]
    indexes = [index for _, index in sorted(results)]
    if INDEXES[0] not in indexes:
        indexes.append(INDEXES[0])
    return indexes


if __name__ == '__main__':
    print('\n'.join(ranked_indexes()))
