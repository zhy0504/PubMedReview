"""Complete journal-table loading and bounded source hashing."""

import hashlib
from pathlib import Path

import pandas as pd


def load_journal_table(path, clean):
    source = Path(path)
    if not source.is_file():
        print(f"期刊数据文件不存在: {source}")
        return pd.DataFrame()
    try:
        reader = pd.read_csv(source, encoding='utf-8-sig', chunksize=1000)
        chunks = [clean(chunk) for chunk in reader]
    except UnicodeDecodeError:
        reader = pd.read_csv(source, encoding='gb18030', chunksize=1000)
        chunks = [clean(chunk) for chunk in reader]
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()


def source_digest(paths):
    digest = hashlib.sha256()
    for path in paths:
        source = Path(path)
        digest.update(str(source.resolve()).encode('utf-8'))
        digest.update(b'\0')
        if source.is_file():
            with source.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
        digest.update(b'\0')
    return digest.hexdigest()
