"""SearXNG Web検索サービス"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]


@dataclass
class SearchResult:
    """検索結果の1件を表すデータクラス。"""
    title: str
    url: str
    content: str


class SearchService:
    """SearXNG APIを利用したWeb検索サービス。

    ディベート参加者が自分の主張の裏付けのためにWeb検索を行う際に使用する。
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

        Parameters
        ----------
        query : 検索クエリ
        max_results : 最大結果件数

        Returns
        -------
        list[SearchResult]
            検索結果のリスト。エラー時は空リストを返す（ディベートを中断しない）。
        """
        if not self.is_configured:
            logger.warning("SearXNG ベースURLが未設定です。検索をスキップします。")
            return []

        if httpx is None:
            logger.warning("httpx パッケージがインストールされていません。検索をスキップします。")
            return []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LMDebate/1.0",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=10.0, headers=headers) as client:
                response = client.get(
                    f"{self._base_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "categories": "general",
                    },
                )
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
            logger.info("検索完了: query=%r, 結果=%d件", query, len(results))
            return results

        except Exception as e:
            logger.warning("SearXNG 検索に失敗しました: %s", e)
            return []
