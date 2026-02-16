"""SearXNG Web検索サービス"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]


_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


@dataclass
class SearchResult:
    """検索結果の1件を表すデータクラス。"""
    title: str
    url: str
    content: str


class SearchService:
    """SearXNG APIを利用したWeb検索サービス。

    ディベート参加者が自分の主張の裏付けのためにWeb検索を行う際に使用する。
    JSON API (format=json) を試行し、403の場合はHTMLレスポンスからパースする。
    """

    def __init__(self, base_url: str = "") -> None:
        self._base_url = base_url.rstrip("/") if base_url else ""

    @property
    def is_configured(self) -> bool:
        """SearXNGのベースURLが設定されているかどうか。"""
        return bool(self._base_url)

    def update_base_url(self, base_url: str) -> None:
        """ベースURLを更新する。"""
        self._base_url = base_url.rstrip("/") if base_url else ""

    def search(self, query: str, max_results: int = 3) -> list[SearchResult]:
        """SearXNG APIでWeb検索を実行する。

        JSON API → 403ならHTMLフォールバック の順に試行する。
        """
        if not self.is_configured:
            logger.warning("SearXNG ベースURLが未設定です。検索をスキップします。")
            return []

        if httpx is None:
            logger.warning("httpx パッケージがインストールされていません。検索をスキップします。")
            return []

        # 1) JSON API を試行
        results = self._search_json(query, max_results)
        if results is not None:
            return results

        # 2) HTMLフォールバック
        results = self._search_html(query, max_results)
        if results is not None:
            return results

        return []

    def _search_json(self, query: str, max_results: int) -> list[SearchResult] | None:
        """JSON API (format=json) で検索を試行する。成功時はリスト、非対応時はNone。"""
        try:
            with httpx.Client(timeout=10.0, headers=_BROWSER_HEADERS) as client:
                response = client.get(
                    f"{self._base_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "categories": "general",
                    },
                )
                if response.status_code == 403:
                    logger.info("SearXNG JSON APIが無効（403）。HTMLフォールバックに切り替えます。")
                    return None
                response.raise_for_status()
                data = response.json()

            results: list[SearchResult] = []
            for item in data.get("results", [])[:max_results]:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                    )
                )
            logger.info("検索完了(JSON): query=%r, 結果=%d件", query, len(results))
            return results

        except Exception as e:
            logger.warning("SearXNG JSON検索に失敗: %s", e)
            return None

    def _search_html(self, query: str, max_results: int) -> list[SearchResult] | None:
        """HTML形式で検索結果を取得し、パースする。"""
        try:
            with httpx.Client(timeout=10.0, headers=_BROWSER_HEADERS) as client:
                response = client.get(
                    f"{self._base_url}/search",
                    params={
                        "q": query,
                        "categories": "general",
                    },
                )
                response.raise_for_status()
                html = response.text

            results = _parse_searxng_html(html, max_results)
            logger.info("検索完了(HTML): query=%r, 結果=%d件", query, len(results))
            return results

        except Exception as e:
            logger.warning("SearXNG HTML検索に失敗: %s", e)
            return None

    def test_connection(self, url: str) -> tuple[bool, str]:
        """接続テスト。(成功フラグ, メッセージ) を返す。"""
        if httpx is None:
            return False, "httpx パッケージが未インストール"

        base = url.rstrip("/")
        try:
            with httpx.Client(timeout=10.0, headers=_BROWSER_HEADERS) as client:
                # まず JSON API を試行
                resp_json = client.get(
                    f"{base}/search",
                    params={"q": "test", "format": "json", "categories": "general"},
                )
                if resp_json.status_code == 200:
                    data = resp_json.json()
                    if "results" in data:
                        return True, "接続OK (JSON API 利用可能)"

                # JSON が 403 ならHTMLを試行
                resp_html = client.get(
                    f"{base}/search",
                    params={"q": "test", "categories": "general"},
                )
                resp_html.raise_for_status()
                if "<html" in resp_html.text.lower():
                    return True, "接続OK (HTMLモード — JSON APIは無効)"

                return False, "予期しないレスポンス形式"

        except Exception as e:
            return False, str(e)


def _parse_searxng_html(html: str, max_results: int) -> list[SearchResult]:
    """SearXNGのHTMLレスポンスから検索結果をパースする。

    SearXNGのHTML構造:
      <article class="result">
        <h3><a href="URL">TITLE</a></h3>
        <p class="content">CONTENT</p>
      </article>
    """
    results: list[SearchResult] = []

    # <article> ... </article> ブロックを抽出
    articles = re.findall(
        r'<article[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</article>',
        html, re.DOTALL,
    )

    for article_html in articles[:max_results * 3]:  # 余裕を持って取得
        title = ""
        url = ""
        content = ""

        # URL と タイトル: <a href="URL" ...>TITLE</a> (h3内)
        h3_match = re.search(r'<h3[^>]*>(.*?)</h3>', article_html, re.DOTALL)
        if h3_match:
            a_match = re.search(r'<a\s[^>]*href="([^"]*)"[^>]*>(.*?)</a>', h3_match.group(1), re.DOTALL)
            if a_match:
                url = a_match.group(1)
                title = _strip_html_tags(a_match.group(2)).strip()

        # コンテンツ: <p class="content">...</p>
        content_match = re.search(r'<p[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</p>', article_html, re.DOTALL)
        if content_match:
            content = _strip_html_tags(content_match.group(1)).strip()

        # URL が無い結果はスキップ（広告等）
        if not url or not title:
            continue

        # 内部リンク（/search?q=...等）はスキップ
        if url.startswith("/"):
            continue

        results.append(SearchResult(title=title, url=url, content=content))

        if len(results) >= max_results:
            break

    return results


def _strip_html_tags(text: str) -> str:
    """HTMLタグを除去してプレーンテキストにする。"""
    text = re.sub(r'<[^>]+>', '', text)
    # HTMLエンティティのデコード
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")
    # 連続空白を整理
    text = re.sub(r'\s+', ' ', text)
    return text
