"""
Fetch a YouTube video's existing caption track (manual or auto-generated)
directly via YouTube's timedtext endpoint — no video/audio download, no
yt-dlp, no SABR streaming, no PO Token.

This is the preferred path for YouTube URLs when captions exist: it's
faster, cheaper (no Whisper), and sidesteps the yt-dlp/YouTube anti-bot
arms race entirely (see audio_processor.py's docstring for that saga).
It can still fail (captions disabled, or YouTube blocking this endpoint
too) — callers should fall back to the audio-download path when it does.
"""

import re

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

_VIDEO_ID_PATTERNS = [
    r"(?:youtube\.com/watch\?v=|youtube\.com/embed/|youtube\.com/shorts/|youtube\.com/live/)([A-Za-z0-9_-]{11})",
    r"youtu\.be/([A-Za-z0-9_-]{11})",
]


def extract_video_id(url: str) -> str | None:
    """Pull the 11-character video ID out of any common YouTube URL shape."""
    for pattern in _VIDEO_ID_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_youtube_transcript(url: str, languages: list[str] | None = None) -> str | None:
    """
    Try to fetch an existing caption track for a YouTube URL.

    Returns the joined transcript text, or None if no caption track could
    be retrieved for any reason (disabled, not found, blocked, etc.) — the
    caller should treat None as "fall back to audio download + Whisper".
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None

    languages = languages or ["en", "en-US", "en-GB"]

    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=languages)
        text = " ".join(snippet.text for snippet in fetched).strip()
        return text or None
    except (
        TranscriptsDisabled,
        NoTranscriptFound,
        VideoUnavailable,
        CouldNotRetrieveTranscript,
    ) as e:
        print(f"[fetch_youtube_transcript] No usable captions for {video_id}: {e}")
        return None
    except Exception as e:
        # Covers IpBlocked / RequestBlocked / PoTokenRequired and anything
        # else the library might raise — same "fall back" contract applies.
        print(f"[fetch_youtube_transcript] Could not fetch captions for {video_id}: {e}")
        return None
