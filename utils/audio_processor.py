import os
import time

import yt_dlp
from pydub import AudioSegment

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Optional: path to a cookies.txt file (Netscape format), exported from a
# real, logged-in browser session. Set this via an env var / Streamlit
# secret — never commit the file itself. This is the only reliable fix
# when YouTube is blocking the *IP address itself* rather than just the
# request signature (common on cloud hosts like Streamlit Community Cloud).
YTDLP_COOKIES_FILE = os.getenv("YTDLP_COOKIES_FILE")

# YouTube's "confirm you're not a bot" / 403 wall is usually tied to which
# internal "player client" yt-dlp pretends to be. The default web client is
# the one most aggressively blocked on datacenter IPs; android/ios clients
# use a different auth flow and frequently get through when web doesn't.
# We try them in order and fall back to the next on failure.
_PLAYER_CLIENT_FALLBACKS = ["android", "ios", "web"]

# ============================================================================
# ADDED: 'tv' client fallback (2026 PO-Token / SABR workaround)
# ----------------------------------------------------------------------------
# Since early 2026 YouTube has been enforcing PO Tokens / SABR streaming that
# breaks the android/ios/web clients above with "Requested format is not
# available" even when cookies are valid — this is an active YouTube-vs-yt-dlp
# fight, not a bug in this code. The 'tv' client currently still works
# without a PO Token in most cases (yt-dlp's own maintainers added it as
# their standard workaround), so we try it last as an extra safety net.
_PLAYER_CLIENT_FALLBACKS = _PLAYER_CLIENT_FALLBACKS + ["tv"]
# ============================================================================

_COMMON_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _build_ydl_opts(output_path: str, player_client: str) -> dict:
    opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "http_headers": _COMMON_HTTP_HEADERS,
        "extractor_args": {"youtube": {"player_client": [player_client]}},
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
    }
    if YTDLP_COOKIES_FILE and os.path.exists(YTDLP_COOKIES_FILE):
        opts["cookiefile"] = YTDLP_COOKIES_FILE
    return opts


def download_youtube_audio(url: str) -> str:
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    last_error = None

    for attempt, player_client in enumerate(_PLAYER_CLIENT_FALLBACKS, start=1):
        ydl_opts = _build_ydl_opts(output_path, player_client)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = (
                    ydl.prepare_filename(info)  # [1]
                    .replace(".webm", ".wav")
                    .replace(".m4a", ".wav")
                )
            return filename
        except yt_dlp.utils.DownloadError as e:
            last_error = e
            print(
                f"[download_youtube_audio] '{player_client}' client failed "
                f"(attempt {attempt}/{len(_PLAYER_CLIENT_FALLBACKS)}): {e}"
            )
            time.sleep(1.5)  # brief backoff before trying the next client
            continue

    # All player clients failed — this is almost always YouTube blocking
    # the server's IP address outright rather than a code bug.
    raise RuntimeError(
        "Could not download audio from YouTube after trying multiple "
        f"client strategies ({', '.join(_PLAYER_CLIENT_FALLBACKS)}). "
        "This usually means YouTube is blocking the server's IP address "
        "(common on Streamlit Community Cloud and other cloud hosts), not "
        "a bug in this code. Fixes, in order of reliability:\n"
        "  1. Export cookies.txt from a real logged-in browser session "
        "(e.g. with the 'Get cookies.txt LOCALLY' extension) and set the "
        "YTDLP_COOKIES_FILE env var / Streamlit secret to its path.\n"
        "  2. Run this app on a host with a residential/non-datacenter IP, "
        "or behind a proxy, instead of a shared cloud platform.\n"
        "  3. Update yt-dlp to the latest version — YouTube changes its "
        "defenses often and yt-dlp ships fixes frequently.\n"
        f"Last underlying error: {last_error}"
    )


def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to WAV format using pydub."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000)  # [2]
    audio.export(output_path, format="wav")
    return output_path


def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:
    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000  # [3]

    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        chunk = audio[start : start + chunk_ms]  # [4]
        chunk_path = f"{wav_path}_chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")

        chunks.append(chunk_path)

    return chunks


def process_input(source: str) -> list:
    if source.startswith("http://") or source.startswith("https://"):
        print("Detected YouTube URL. Downloading audio...")
        wav_path = download_youtube_audio(source)
    else:
        print("Detected local file. Converting to WAV...")
        wav_path = convert_to_wav(source)

    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    print(f"Audio ready — {len(chunks)} chunk(s) created.")
    return chunks


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
# [1] prepare_filename() returns the filename yt-dlp would use for the RAW
#     download (before the FFmpegExtractAudio postprocessor runs), so its
#     extension still reflects the original container (.webm/.m4a). Since
#     the postprocessor always converts the file to .wav, we patch the
#     extension manually to match what's actually on disk.
#
# [2] Downmixing to mono + resampling to 16kHz is the standard input format
#     expected by most speech-to-text/ASR models (e.g. Whisper). It also
#     keeps file size small before chunking.
#
# [3] pydub measures audio length in milliseconds, hence minutes * 60 * 1000.
#
# [4] Slicing an AudioSegment with [start:end] works like a list slice —
#     pydub automatically clamps the end index past the audio's length, so
#     the final chunk just comes out shorter instead of erroring.
#
# Workflow overview:
#   process_input() picks a path based on the source type:
#     - YouTube URL -> download_youtube_audio() (yt-dlp + ffmpeg -> WAV)
#     - Local file  -> convert_to_wav() (pydub -> mono/16kHz WAV)
#   Either way, the resulting WAV is passed to chunk_audio(), which splits
#   it into fixed-length pieces (default 10 min) so long recordings can be
#   fed into downstream processing (transcription, embeddings, etc.) that
#   often has file-size/duration limits.
