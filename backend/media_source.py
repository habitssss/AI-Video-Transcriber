from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse


@dataclass(frozen=True)
class MediaSource:
    """媒体源描述信息。"""

    url: str
    provider: str
    content_type: Literal["video", "podcast"]
    display_name: str


def resolve_media_source(url: str) -> MediaSource:
    """
    根据URL解析媒体来源类型。

    Args:
        url (str): 用户提交的原始链接。

    Returns:
        MediaSource: 解析后的媒体来源描述。

    Raises:
        ValueError: 当URL为空或无法解析时抛出。
    """
    if not url:
        raise ValueError("URL不能为空")

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()

    if "xiaoyuzhoufm.com" in hostname and "/episode/" in path:
        return MediaSource(
            url=url,
            provider="xiaoyuzhou",
            content_type="podcast",
            display_name="小宇宙播客",
        )

    if hostname.endswith("youtube.com") or hostname == "youtu.be":
        return MediaSource(
            url=url,
            provider="youtube",
            content_type="video",
            display_name="YouTube",
        )

    if "bilibili.com" in hostname:
        return MediaSource(
            url=url,
            provider="bilibili",
            content_type="video",
            display_name="Bilibili",
        )

    return MediaSource(
        url=url,
        provider=hostname or "generic",
        content_type="video",
        display_name="视频",
    )
