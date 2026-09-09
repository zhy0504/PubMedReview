"""Normalize review headings without discarding article sections."""

import re


def normalize_review_title(content: str, title: str = None) -> str:
    if not content or not content.strip():
        return content
    heading = re.search(r'(?m)^\s*#(?!#)[ \t]+\S[^\n]*', content)
    first_section = re.search(r'(?m)^\s*#{2,6}[ \t]+', content)
    if heading and (not first_section or heading.start() < first_section.start()):
        return content[heading.start():].strip()
    prefix_end = first_section.start() if first_section else len(content)
    inline_heading = re.search(r'(?<!#)#(?!#)[ \t]+\S[^\n]*', content[:prefix_end])
    if inline_heading:
        return content[inline_heading.start():].strip()
    fallback = ' '.join((title or '医学综述').split()).lstrip('#').strip() or '医学综述'
    return f'# {fallback}\n\n{content.strip()}'
