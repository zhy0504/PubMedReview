"""Article generation and export, independent of CLI and web presentation."""

from pathlib import Path
from review_content import normalize_review_title
import re


def cited_articles(content, articles):
    body = re.split(r'(?m)^##\s*参考文献\s*$', content, maxsplit=1)[0]
    pmids = dict.fromkeys(re.findall(r'\]\(https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/?\)', body))
    by_pmid = {str(article.get('pmid', '')): article for article in articles}
    return [by_pmid[pmid] for pmid in pmids if pmid in by_pmid]


def publish_review(generator, outline_file, literature_file, title, output_filename,
                   user_input, export_format, cached_content=None):
    if export_format not in {'md', 'docx', 'both'}:
        raise ValueError(f"不支持的综述输出格式: {export_format}")
    export_docx = export_format in {'docx', 'both'}
    export_md = export_format in {'md', 'both'}
    if cached_content:
        cached_content = normalize_review_title(cached_content, title)
        paths = generator.save_article(cached_content, output_filename, user_input, export_docx, export_md)
    else:
        paths = generator.generate_from_files(
            outline_file=outline_file, literature_file=literature_file, title=title,
            output_filename=output_filename, user_input=user_input,
            export_docx=export_docx, export_md=export_md,
        )
        if not any(paths):
            content = generator.generate_complete_review_article(outline_file, literature_file, title)
            if not content:
                raise RuntimeError('综述文章生成失败')
            paths = generator.save_article(content, output_filename, user_input, export_docx, export_md)
    md_path, docx_path = (str(path) if path and Path(path).is_file() else None for path in paths)
    if not (md_path or docx_path):
        raise RuntimeError('综述导出失败：未找到实际生成的文件')
    if export_md and not md_path or export_docx and not docx_path:
        print('[WARN] 部分输出格式未生成，请查看已有文件和导出日志')
    return md_path, docx_path
