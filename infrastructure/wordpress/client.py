from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from domain.models import ArticleDraft
from usecases.ports import MarkdownRendererPort, SiteAdapterPort
from .markdown_renderer import DefaultMarkdownRenderer


@dataclass
class WordPressPostResult:
    success: bool
    post_id: Optional[int] = None
    url: Optional[str] = None
    error_message: Optional[str] = None
    status_code: Optional[int] = None


class WordPressClient:
    """WordPress Application Password 経由で下書きを作成するクライアント。"""

    def __init__(
        self,
        base_url: str,
        username: str,
        app_password: str,
        site_adapter: SiteAdapterPort,
        *,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        client: Optional[httpx.Client] = None,
        markdown_renderer: Optional[MarkdownRendererPort] = None,
        convert_markdown: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_header = self._build_auth_header(username, app_password)
        self.site_adapter = site_adapter
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.client = client or httpx.Client(timeout=self.timeout)
        self._owns_client = client is None
        self.markdown_renderer = markdown_renderer or DefaultMarkdownRenderer()
        self.convert_markdown = convert_markdown

    @staticmethod
    def _build_auth_header(username: str, app_password: str) -> dict:
        token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    def _build_payload(self, draft: ArticleDraft) -> dict:
        content = draft.markdown
        if self.convert_markdown and self.markdown_renderer:
            content = self.markdown_renderer.to_html(draft.markdown)

        payload = {
            "title": draft.title,
            "content": content,
            "excerpt": draft.meta_description,
            "slug": draft.slug,
            "status": "draft",
        }
        # サイト固有のカテゴリ/タグ/カスタムフィールドは Adapter に委譲
        payload = self.site_adapter.extend_wp_payload(draft, payload)
        return payload

    def create_draft(self, draft: ArticleDraft) -> WordPressPostResult:
        url = f"{self.base_url}/wp-json/wp/v2/posts"
        payload = self._build_payload(draft)
        last_error: Optional[str] = None
        last_status: Optional[int] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.post(url, json=payload, headers=self.auth_header)
                last_status = response.status_code
                if 200 <= response.status_code < 300:
                    data = response.json()
                    return WordPressPostResult(
                        success=True,
                        post_id=data.get("id"),
                        url=data.get("link"),
                        status_code=response.status_code,
                    )
                last_error = self._format_error(response)
            except httpx.RequestError as exc:
                last_error = str(exc)
            if attempt < self.max_retries:
                sleep_seconds = self.backoff_base * (2 ** (attempt - 1))
                time.sleep(sleep_seconds)

        return WordPressPostResult(
            success=False,
            error_message=last_error,
            status_code=last_status,
        )

    def _format_error(self, response: httpx.Response) -> str:
        try:
            data = response.json()
            msg = data.get("message") or response.text
            code = data.get("code")
            if code:
                return f"HTTP {response.status_code} {code}: {msg}"
            return f"HTTP {response.status_code}: {msg}"
        except Exception:
            return f"HTTP {response.status_code}: {response.text}"

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "WordPressClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
