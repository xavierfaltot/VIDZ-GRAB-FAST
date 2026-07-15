from __future__ import annotations

from urllib.parse import urlparse


def detect_platform(source_url: str) -> str:
    host = urlparse(source_url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if "instagram.com" in host:
        return "instagram"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "tiktok.com" in host:
        return "tiktok"
    if "vimeo.com" in host:
        return "vimeo"
    if host in {"x.com", "twitter.com"} or host.endswith(".x.com") or host.endswith(".twitter.com"):
        return "x"
    if "facebook.com" in host or host == "fb.watch":
        return "facebook"
    if source_url.lower().split("?", 1)[0].endswith(".mp4"):
        return "direct_mp4"
    return ""
