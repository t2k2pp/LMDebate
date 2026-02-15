"""簡易感情分析ユーティリティ

キーワードベースで発言の感情傾向を判定し、対応する絵文字を返す。
"""

from __future__ import annotations

# 感情 -> 絵文字のマッピング
SENTIMENT_EMOJIS: dict[str, str] = {
    "aggressive": "\U0001f624",    # 😤
    "happy": "\U0001f60a",         # 😊
    "thinking": "\U0001f914",      # 🤔
    "confident": "\U0001f60e",     # 😎
    "sad": "\U0001f622",           # 😢
    "neutral": "\U0001f610",       # 😐
    "surprised": "\U0001f632",     # 😲
}

# 感情ごとのキーワードリスト（日本語）
_KEYWORD_MAP: dict[str, list[str]] = {
    "aggressive": [
        "反論", "間違い", "誤り", "問題がある", "批判", "弱点", "矛盾",
        "不適切", "全くの", "到底", "認められない", "受け入れがたい",
        "見過ごせない", "看過できない",
    ],
    "happy": [
        "賛成", "同意", "素晴らしい", "良い点", "優れた", "メリット",
        "利点", "効果的", "有望", "期待できる", "共感",
        "納得", "的確", "適切",
    ],
    "thinking": [
        "考えると", "検討", "分析", "比較", "観点", "一方で",
        "しかし", "ただし", "なお", "では", "もし",
        "仮に", "可能性", "視点",
    ],
    "confident": [
        "明らか", "確実", "間違いなく", "断言", "証明", "データが示す",
        "事実として", "疑いなく", "確信", "裏付け", "根拠",
        "実績が", "結果が示す",
    ],
    "sad": [
        "残念", "懸念", "心配", "困難", "難しい", "厳しい",
        "不安", "リスク", "危険", "課題", "問題点",
    ],
    "surprised": [
        "驚き", "予想外", "意外", "興味深い", "想定外", "注目すべき",
        "画期的", "新たな",
    ],
}


def analyze_sentiment(text: str) -> str:
    """テキストから感情を簡易分析し、対応する絵文字を返す。

    Args:
        text: 分析対象のテキスト

    Returns:
        感情に対応する絵文字文字列
    """
    if not text:
        return SENTIMENT_EMOJIS["neutral"]

    scores: dict[str, int] = {k: 0 for k in _KEYWORD_MAP}

    for sentiment, keywords in _KEYWORD_MAP.items():
        for kw in keywords:
            if kw in text:
                scores[sentiment] += 1

    max_score = max(scores.values())
    if max_score == 0:
        return SENTIMENT_EMOJIS["neutral"]

    top_sentiment = max(scores, key=lambda k: scores[k])
    return SENTIMENT_EMOJIS[top_sentiment]
