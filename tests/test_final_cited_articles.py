from workflow_exports import cited_articles


def test_ris_selection_uses_body_links_not_all_references():
    articles = [{'pmid': '1'}, {'pmid': '2'}, {'pmid': '3'}]
    content = '# Title\nText[[2]](https://pubmed.ncbi.nlm.nih.gov/2). Again[[2]](https://pubmed.ncbi.nlm.nih.gov/2/).\n## 参考文献\n[1](https://pubmed.ncbi.nlm.nih.gov/1)\n[3](https://pubmed.ncbi.nlm.nih.gov/3)'
    assert cited_articles(content, articles) == [{'pmid': '2'}]
    assert cited_articles('# Title\nNo citations', articles) == []


def test_ris_selection_accepts_hidden_url_citation_links():
    articles = [{'pmid': '1'}, {'pmid': '2'}]
    content = '# Title\nText[\\[2\\]](https://pubmed.ncbi.nlm.nih.gov/2).\n## 参考文献\n[\\[1\\]](https://pubmed.ncbi.nlm.nih.gov/1)'
    assert cited_articles(content, articles) == [{'pmid': '2'}]
