"""Normalize review headings without discarding article sections."""

import re


def _heading_text(match):
    return re.sub(r'^\s*#+\s*', '', match.group(0)).strip()


def _is_section_heading(text):
    return bool(re.match(
        r'^(?:\d+(?:\.\d+)*\s*[.)、:：-]?|摘要|引言|研究现状|方法|结果|讨论|结论|参考文献)\s*',
        text,
        re.IGNORECASE,
    ))


def normalize_review_title(content: str, title: str = None) -> str:
    if not content or not content.strip():
        return content
    text = content.strip()
    headings = list(re.finditer(r'(?<!#)#(?!#)[ \t]+\S[^\n]*', text))
    first = headings[0] if headings else None
    expected = ' '.join((title or '').split()).lstrip('#').strip()

    if first and not _is_section_heading(_heading_text(first)):
        return text[first.start():].strip()

    body = text[first.start():].strip() if first else text
    fallback = expected or '医学综述'
    return f'# {fallback}\n\n{body}'
