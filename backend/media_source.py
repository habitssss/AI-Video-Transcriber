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


AUDIO_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wav",
    ".flac",
    ".m4b",
}

PODCAST_HOSTS = {
    "podcasts.apple.com": "Apple Podcasts",
    "open.spotify.com": "Spotify",
    "anchor.fm": "Anchor",
    "castbox.fm": "Castbox",
    "podbean.com": "Podbean",
}


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
    suffix = path.rsplit(".", 1)[-1] if "." in path else ""
    suffix = f".{suffix}" if suffix else ""

    if suffix in AUDIO_EXTENSIONS:
        return MediaSource(
            url=url,
            provider=hostname or "audio",
            content_type="podcast",
            display_name="播客音频",
        )

    if suffix in {".rss", ".xml"} or "rss" in path or "feed" in path:
        return MediaSource(
            url=url,
            provider=hostname or "rss",
            content_type="podcast",
            display_name="播客RSS",
        )

    if "xiaoyuzhoufm.com" in hostname and "/episode/" in path:
        return MediaSource(
            url=url,
            provider="xiaoyuzhou",
            content_type="podcast",
            display_name="小宇宙播客",
        )

    for podcast_host, display_name in PODCAST_HOSTS.items():
        if hostname == podcast_host or hostname.endswith(f".{podcast_host}"):
            return MediaSource(
                url=url,
                provider=podcast_host,
                content_type="podcast",
                display_name=display_name,
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
