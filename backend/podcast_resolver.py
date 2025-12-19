from dataclasses import dataclass
import logging
import re
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

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
DEFAULT_MAX_BYTES = 2_000_000
DEFAULT_TIMEOUT = 15


@dataclass(frozen=True)
class PodcastEpisode:
    """播客单集解析结果。"""

    audio_url: str
    title: str
    episode_url: Optional[str]
    feed_url: Optional[str]
    mime_type: Optional[str]


def resolve_podcast_episode(
    url: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout: int = DEFAULT_TIMEOUT,
    max_depth: int = 1,
) -> PodcastEpisode:
    """
    解析播客链接，提取可下载的音频地址与标题。

    Args:
        url (str): 播客链接（可为RSS/Atom、音频直链或播客页面）。
        max_bytes (int): 拉取内容的最大字节数，避免过大响应。
        timeout (int): 请求超时时间（秒）。
        max_depth (int): HTML页面中解析RSS链接的最大递归深度。

    Returns:
        PodcastEpisode: 解析到的播客单集信息。

    Raises:
        ValueError: 当链接无效或无法解析出音频地址时抛出。
    """
    if not url:
        raise ValueError("播客链接不能为空")
    return _resolve_podcast_episode(
        url,
        max_bytes=max_bytes,
        timeout=timeout,
        max_depth=max_depth,
        feed_url=None,
    )


def _resolve_podcast_episode(
    url: str,
    *,
    max_bytes: int,
    timeout: int,
    max_depth: int,
    feed_url: Optional[str],
) -> PodcastEpisode:
    """
    解析播客链接的内部实现。

    Args:
        url (str): 待解析链接。
        max_bytes (int): 最大读取字节数。
        timeout (int): 超时时间（秒）。
        max_depth (int): HTML递归解析深度。
        feed_url (Optional[str]): RSS来源地址（若已知）。

    Returns:
        PodcastEpisode: 解析到的播客单集信息。

    Raises:
        ValueError: 当解析失败或无法找到音频链接时抛出。
    """
    if _looks_like_audio_url(url):
        return PodcastEpisode(
            audio_url=url,
            title=_guess_title_from_url(url),
            episode_url=None,
            feed_url=feed_url,
            mime_type=None,
        )

    content_type, payload, final_url = _fetch_url_payload(
        url, max_bytes=max_bytes, timeout=timeout
    )

    if _is_audio_content_type(content_type):
        return PodcastEpisode(
            audio_url=final_url,
            title=_guess_title_from_url(final_url),
            episode_url=None,
            feed_url=feed_url,
            mime_type=content_type,
        )

    text = payload.decode("utf-8", errors="ignore")
    if _looks_like_xml(text, content_type):
        return _parse_feed(text, final_url)

    if max_depth > 0 and _looks_like_html(text, content_type):
        rss_url = _extract_rss_link(text, final_url)
        if rss_url:
            return _resolve_podcast_episode(
                rss_url,
                max_bytes=max_bytes,
                timeout=timeout,
                max_depth=max_depth - 1,
                feed_url=rss_url,
            )

    raise ValueError("无法从该链接解析播客音频")


def _fetch_url_payload(url: str, *, max_bytes: int, timeout: int) -> Tuple[str, bytes, str]:
    """
    拉取URL内容的前若干字节，用于判断类型或解析RSS。

    Args:
        url (str): 需要请求的URL。
        max_bytes (int): 最大读取字节数。
        timeout (int): 超时时间（秒）。

    Returns:
        Tuple[str, bytes, str]: (Content-Type, 内容字节, 最终URL)。

    Raises:
        ValueError: 当网络请求失败或响应为空时抛出。
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (AI-Video-Transcriber)",
        "Accept": "*/*",
    }
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            payload = response.read(max_bytes)
            final_url = response.geturl() or url
            return content_type, payload, final_url
    except (HTTPError, URLError) as exc:
        logger.error(f"获取播客链接失败: {exc}")
        raise ValueError(f"获取播客链接失败: {exc}") from exc


def _parse_feed(xml_text: str, feed_url: str) -> PodcastEpisode:
    """
    解析RSS/Atom内容，提取第一条音频信息。

    Args:
        xml_text (str): RSS/Atom文本内容。
        feed_url (str): RSS/Atom地址。

    Returns:
        PodcastEpisode: 解析到的播客单集信息。

    Raises:
        ValueError: 当RSS/Atom结构异常或未找到音频链接时抛出。
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error(f"解析播客RSS失败: {exc}")
        raise ValueError("播客RSS格式无法解析") from exc

    items = [
        element
        for element in root.iter()
        if _strip_namespace(element.tag) in {"item", "entry"}
    ]

    for item in items:
        audio_url, mime_type = _extract_enclosure(item)
        if not audio_url:
            continue
        title = _get_child_text(item, "title") or _guess_title_from_url(audio_url)
        episode_url = _get_episode_link(item)
        return PodcastEpisode(
            audio_url=audio_url,
            title=title,
            episode_url=episode_url,
            feed_url=feed_url,
            mime_type=mime_type,
        )

    raise ValueError("RSS中未找到可用的音频链接")


def _extract_enclosure(item: ET.Element) -> Tuple[Optional[str], Optional[str]]:
    """
    从RSS/Atom条目中提取enclosure或media内容。

    Args:
        item (ET.Element): RSS/Atom条目节点。

    Returns:
        Tuple[Optional[str], Optional[str]]: (音频URL, MIME类型)。

    Raises:
        None.
    """
    for element in item.iter():
        tag = _strip_namespace(element.tag)
        if tag == "enclosure":
            url = element.attrib.get("url")
            mime_type = element.attrib.get("type")
            if url:
                return url, mime_type
        if tag == "content":
            url = element.attrib.get("url")
            mime_type = element.attrib.get("type")
            if url and (_looks_like_audio_url(url) or _is_audio_content_type(mime_type or "")):
                return url, mime_type
        if tag == "link" and element.attrib.get("rel") == "enclosure":
            url = element.attrib.get("href")
            mime_type = element.attrib.get("type")
            if url:
                return url, mime_type
    return None, None


def _get_episode_link(item: ET.Element) -> Optional[str]:
    """
    获取播客条目的页面链接。

    Args:
        item (ET.Element): RSS/Atom条目节点。

    Returns:
        Optional[str]: 条目链接，未找到则为None。

    Raises:
        None.
    """
    link_text = _get_child_text(item, "link")
    if link_text:
        return link_text
    for element in item.iter():
        if _strip_namespace(element.tag) == "link":
            href = element.attrib.get("href")
            if href:
                return href
    return None


def _get_child_text(element: ET.Element, name: str) -> Optional[str]:
    """
    获取指定子节点的文本内容（忽略命名空间）。

    Args:
        element (ET.Element): 父节点。
        name (str): 子节点名称。

    Returns:
        Optional[str]: 子节点文本，未找到则为None。

    Raises:
        None.
    """
    for child in element:
        if _strip_namespace(child.tag) == name and child.text:
            return child.text.strip()
    return None


def _extract_rss_link(html_text: str, base_url: str) -> Optional[str]:
    """
    从HTML中提取RSS/Atom链接。

    Args:
        html_text (str): HTML文本内容。
        base_url (str): 当前页面URL，用于拼接相对地址。

    Returns:
        Optional[str]: RSS链接，未找到则为None。

    Raises:
        None.
    """
    link_pattern = re.compile(r"<link[^>]+>", re.IGNORECASE)
    type_pattern = re.compile(r'type=["\']([^"\']+)["\']', re.IGNORECASE)
    href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)

    for tag in link_pattern.findall(html_text):
        type_match = type_pattern.search(tag)
        href_match = href_pattern.search(tag)
        if not type_match or not href_match:
            continue
        link_type = type_match.group(1).lower()
        if "rss" in link_type or "atom" in link_type:
            return urljoin(base_url, href_match.group(1).strip())
    return None


def _looks_like_xml(text: str, content_type: str) -> bool:
    """
    判断内容是否为XML/RSS。

    Args:
        text (str): 文本内容。
        content_type (str): Content-Type头信息。

    Returns:
        bool: 是否为XML内容。

    Raises:
        None.
    """
    if "xml" in (content_type or "").lower():
        return True
    sample = text.lstrip()[:200].lower()
    return sample.startswith("<?xml") or "<rss" in sample or "<feed" in sample


def _looks_like_html(text: str, content_type: str) -> bool:
    """
    判断内容是否为HTML。

    Args:
        text (str): 文本内容。
        content_type (str): Content-Type头信息。

    Returns:
        bool: 是否为HTML内容。

    Raises:
        None.
    """
    if "html" in (content_type or "").lower():
        return True
    sample = text.lstrip()[:200].lower()
    return sample.startswith("<!doctype html") or "<html" in sample


def _is_audio_content_type(content_type: str) -> bool:
    """
    判断Content-Type是否为音频类型。

    Args:
        content_type (str): Content-Type头信息。

    Returns:
        bool: 是否为音频类型。

    Raises:
        None.
    """
    return (content_type or "").lower().startswith("audio/")


def _looks_like_audio_url(url: str) -> bool:
    """
    判断URL是否为音频文件直链。

    Args:
        url (str): 待判断的URL。

    Returns:
        bool: 是否为音频直链。

    Raises:
        None.
    """
    suffix = (urlparse(url).path or "").lower()
    for ext in AUDIO_EXTENSIONS:
        if suffix.endswith(ext):
            return True
    return False


def _guess_title_from_url(url: str) -> str:
    """
    从URL猜测可读标题。

    Args:
        url (str): 音频URL。

    Returns:
        str: 推测得到的标题。

    Raises:
        None.
    """
    parsed = urlparse(url)
    filename = (parsed.path or "").rstrip("/").split("/")[-1]
    title = re.sub(r"\.[a-z0-9]+$", "", filename, flags=re.IGNORECASE)
    return title or "untitled"


def _strip_namespace(tag: str) -> str:
    """
    去除XML命名空间前缀。

    Args:
        tag (str): 带命名空间的标签名。

    Returns:
        str: 去除命名空间后的标签名。

    Raises:
        None.
    """
    return tag.split("}", 1)[-1] if "}" in tag else tag
