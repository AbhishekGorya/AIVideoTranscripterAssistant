import os

import yt_dlp
from pydub import AudioSegment

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def download_youtube_audio(url: str) -> str:
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
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
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = (
            ydl.prepare_filename(info)  # [1]
            .replace(".webm", ".wav")
            .replace(".m4a", ".wav")
        )

    return filename


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