"""
YouTube transcript acquisition.

Production priority:
1. Supadata API
2. youtube-transcript-api
3. yt-dlp/audio fallback handled by the caller

The important design decision is that the production application
should not depend on downloading YouTube audio from a cloud IP.
"""

import os
import re
import requests

from youtube_transcript_api import YouTubeTranscriptApi


_VIDEO_ID_PATTERNS = [
    r"(?:youtube\.com/watch\?v=|youtube\.com/embed/|youtube\.com/shorts/|youtube\.com/live/)([A-Za-z0-9_-]{11})",
    r"youtu\.be/([A-Za-z0-9_-]{11})",
]


def extract_video_id(url: str) -> str | None:
    """Extract the 11-character YouTube video ID."""

    if not url:
        return None

    for pattern in _VIDEO_ID_PATTERNS:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None


def fetch_supadata_transcript(
    url: str,
    language: str = "en",
) -> str | None:
    """
    Fetch a YouTube transcript through Supadata.

    mode='auto':
        Try the native transcript first and use generated
        transcription if necessary.
    """

    api_key = os.getenv("SUPADATA_API_KEY")

    if not api_key:
        print("[Supadata] SUPADATA_API_KEY not configured.")
        return None

    endpoint = "https://api.supadata.ai/v1/transcript"

    headers = {
        "x-api-key": api_key,
        "Accept": "application/json",
    }

    params = {
        "url": url,
        "lang": language,
        "text": "true",
        "mode": "auto",
    }

    try:
        response = requests.get(
            endpoint,
            headers=headers,
            params=params,
            timeout=60,
        )

        if response.status_code != 200:
            print(
                f"[Supadata] Request failed "
                f"with HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )
            return None

        data = response.json()

        # Normal synchronous response
        content = data.get("content")

        if isinstance(content, str):
            return content.strip() or None

        # Some responses may return transcript chunks
        if isinstance(content, list):
            parts = []

            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")

                    if text:
                        parts.append(str(text))

            transcript = " ".join(parts).strip()

            if transcript:
                return transcript

        print("[Supadata] Response contained no transcript text.")

        return None

    except requests.RequestException as exc:
        print(f"[Supadata] Network error: {exc}")
        return None

    except Exception as exc:
        print(f"[Supadata] Unexpected error: {exc}")
        return None


def fetch_local_youtube_transcript(
    url: str,
    languages: list[str] | None = None,
) -> str | None:
    """
    Local/dev fallback using youtube-transcript-api.

    This should NOT be considered the primary production
    mechanism on Streamlit Cloud because YouTube can block
    cloud-provider IPs.
    """

    video_id = extract_video_id(url)

    if not video_id:
        return None

    languages = languages or [
        "en",
        "en-US",
        "en-GB",
    ]

    try:
        api = YouTubeTranscriptApi()

        fetched = api.fetch(
            video_id,
            languages=languages,
        )

        text = " ".join(
            snippet.text
            for snippet in fetched
        ).strip()

        return text or None

    except Exception as exc:
        print(
            f"[youtube-transcript-api] "
            f"Could not retrieve transcript: {exc}"
        )

        return None


def fetch_youtube_transcript(
    url: str,
    languages: list[str] | None = None,
) -> str | None:
    """
    Production transcript strategy.

    1. Supadata
    2. youtube-transcript-api

    Audio/yt-dlp fallback is intentionally NOT performed here.
    The caller decides whether audio fallback is appropriate.
    """

    language = "en"

    if languages:
        language = languages[0]

    # ---------------------------------------------------------
    # Production provider
    # ---------------------------------------------------------

    transcript = fetch_supadata_transcript(
        url,
        language=language,
    )

    if transcript:
        print(
            "[YouTube] Transcript obtained through Supadata."
        )

        return transcript

    # ---------------------------------------------------------
    # Local fallback
    # ---------------------------------------------------------

    transcript = fetch_local_youtube_transcript(
        url,
        languages=languages,
    )

    if transcript:
        print(
            "[YouTube] Transcript obtained through "
            "youtube-transcript-api."
        )

        return transcript

    print(
        "[YouTube] No transcript provider could retrieve "
        "the transcript."
    )

    return None
