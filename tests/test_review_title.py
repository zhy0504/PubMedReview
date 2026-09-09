from pathlib import Path

import pytest

from medical_review_generator import MedicalReviewGenerator
from review_content import normalize_review_title


@pytest.mark.parametrize('prefix', ['', '生成说明。\n\n', '生成说明。'])
def test_heading_after_intro(prefix):
    article = '# 结核病患者关怀\n\n## 1. 引言\n\n正文。'
    assert MedicalReviewGenerator._clean_ai_intro(None, prefix + article) == article


@pytest.mark.parametrize('body', ['## 1. 引言\n正文', '摘要内容\n\n## 引言\n正文', '正文'])
def test_missing_title_preserves_all_content(body):
    result = normalize_review_title(body, '研究主题')
    assert result == '# 研究主题\n\n' + body
    assert normalize_review_title(result, '研究主题') == result


def test_empty_response_remains_empty():
    assert normalize_review_title('', '研究主题') == ''


def test_real_raw_output_title():
    root = Path(__file__).resolve().parents[1]
    raw = root / 'output/综述AI返回原始数据/原始输出-结核病患者关怀系统性文献综述-20260909_151403.md'
    if not raw.exists():
        pytest.skip('Local historical output is not distributed')
    content = raw.read_text(encoding='utf-8').split('\n---\n', 1)[1].strip()
    result = normalize_review_title(content)
    expected = '# 结核病患者关怀：从诊疗可及性到治疗后康复的全病程证据综述'
    assert result.startswith(expected + '\n')
    assert result == content[content.index(expected):].strip()
