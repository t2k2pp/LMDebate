"""トークン数推定ユーティリティ"""

try:
    import tiktoken
    _encoder = tiktoken.get_encoding("cl100k_base")
    _HAS_TIKTOKEN = True
except (ImportError, Exception):
    _HAS_TIKTOKEN = False
    _encoder = None


def count_tokens(text: str) -> int:
    """テキストのトークン数を推定する。

    tiktokenが利用可能な場合はcl100k_baseエンコーディングを使用。
    利用不可の場合は文字数ベースの簡易推定（日本語: 文字数×1.5、英語: 単語数×1.3）。
    """
    if not text:
        return 0

    if _HAS_TIKTOKEN and _encoder is not None:
        return len(_encoder.encode(text))

    # 簡易推定: 日本語が多い場合は文字数ベース
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    ratio = ascii_chars / len(text) if text else 0

    if ratio > 0.8:
        # 英語中心: 単語数 × 1.3
        return int(len(text.split()) * 1.3)
    else:
        # 日本語中心: 文字数 × 1.5
        return int(len(text) * 1.5)
