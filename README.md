# 🎬 AI Video Transcripter Assistant

**Live app:** https://avi-aivideotranscripterassistant.streamlit.app
**Repo:** https://github.com/AbhishekGorya/AIVideoTranscripterAssistant

An end-to-end pipeline that turns any YouTube video or local audio/video file into a fully searchable meeting/video intelligence report — transcript, title, summary, action items, key decisions, open questions, and a RAG-powered chatbot to ask follow-up questions about the content.

Supports both **English** (via YouTube captions, with local Whisper as a fallback) and **Hinglish / code-mixed Hindi-English** (via Sarvam AI's speech-to-text-translate API).

---

## ✨ Features

- 🔗 **Flexible input** — paste a YouTube URL or point to a local audio/video file
- ⚡ **Caption-first transcription for YouTube** — pulls YouTube's own caption track directly when available, skipping audio download and transcription entirely (faster, cheaper, and avoids YouTube's anti-bot defenses — see [How Transcription Works](#-how-transcription-works) below)
- 🔊 **Automatic audio extraction & chunking** — long recordings are split into manageable pieces when the audio path is needed
- 📝 **Transcription fallback** — Whisper (local, offline) for English; Sarvam AI (cloud) for Hinglish
- 🏷️ **Auto-generated title** for the session
- 📋 **Map-reduce summarization** — handles transcripts of any length without hitting LLM context limits
- ✅ **Structured extraction** — action items (with owner + deadline), key decisions, and open questions
- 💬 **RAG-powered chat** — ask follow-up questions grounded strictly in the transcript, powered by a local Chroma vector store
- 🖥️ **Two interfaces** — a Streamlit web UI (`app.py`) and a CLI (`main.py`)

---

## 🏗️ Architecture / Pipeline

```
                       ┌─────────────────────┐
                       │   Input (URL/File)  │
                       └──────────┬──────────┘
                                  ▼
                  ┌───────────────────────────────┐
                  │  Is it a YouTube URL AND       │
                  │  language == "english"?        │
                  └───────┬───────────────┬─────────┘
                     yes  │               │  no
                          ▼               ▼
          ┌─────────────────────────┐   ┌─────────────────────────────┐
          │ utils/youtube_captions  │   │  utils/audio_processor       │
          │ → fetch caption track   │   │  → yt-dlp download (YouTube) │
          │   directly (no download)│   │    or pydub convert (local)  │
          └──────────┬───────────────┘   │  → chunk into fixed-length   │
                      │                   │    WAV segments               │
             captions found?              └──────────────┬───────────────┘
                 │        │                               ▼
              yes│        │no                  ┌─────────────────────────┐
                 │        └────────────────────▶│   core/transcriber      │
                 │                              │  → Whisper (English) or │
                 │                              │    Sarvam AI (Hinglish) │
                 │                              └──────────────┬───────────┘
                 │                                              │
                 └──────────────────────┬───────────────────────┘
                                         ▼
                              Full meeting transcript
                                         │
              ┌───────────────────────────┼───────────────────────────┐
              ▼                           ▼                           ▼
  ┌──────────────────────┐   ┌─────────────────────┐   ┌──────────────────────────┐
  │ core/summarizer        │   │ core/extractor       │   │ core/vector_store          │
  │ → title + summary       │   │ → action items,      │   │ → embed + store             │
  │   (map-reduce)           │   │   decisions,          │   │   transcript chunks         │
  │                           │   │   questions           │   │   in Chroma                  │
  └──────────────────────┘   └─────────────────────┘   └──────────────┬───────────┘
                                                                        ▼
                                                            ┌──────────────────────────┐
                                                            │  core/rag_engine            │
                                                            │  → retrieval-augmented      │
                                                            │    chat over transcript      │
                                                            └──────────────────────────┘
```

All LLM calls (title, summary, extraction, RAG answers) go through **Mistral AI** (`mistral-small-latest`) via LangChain's LCEL (LangChain Expression Language) pipelines.

---

## ⚡ How Transcription Works

This is the part that took the most iteration, so it's worth explaining properly.

**The naive approach** — download the video's audio with `yt-dlp`, then run it through Whisper — sounds simple but runs straight into YouTube's anti-bot defenses when hosted on a cloud platform like Streamlit Community Cloud:

1. **IP-based blocking (`HTTP 403`)** — YouTube aggressively blocks requests from known datacenter IP ranges (AWS, GCP, Streamlit Cloud, etc.), regardless of which download library is used.
2. **SABR streaming + PO Tokens** — even after working around the IP block (by having `yt-dlp` impersonate different internal clients — Android, iOS, web — via `extractor_args`), YouTube has rolled out **Server-side Adaptive Bitrate (SABR)** streaming that strips downloadable format URLs unless a valid, per-video **Proof-of-Origin (PO) Token** is presented. Generating PO Tokens reliably requires running a separate Node.js token-generation service alongside the app — not something a simple cloud deployment can host, and success is inconsistent even then.

**The fix: don't download the video at all when possible.** For any YouTube URL in English, the app first tries `utils/youtube_captions.py`, which calls YouTube's own caption/timedtext endpoint via `youtube-transcript-api`. This endpoint:

- Returns the manual or auto-generated caption track directly as text
- Involves no video/audio download, no `yt-dlp`, no SABR, no PO Token
- Is faster and avoids Whisper compute entirely

If a video has no caption track available (or the caption fetch fails for any reason), the app **falls back** to the original audio-download pipeline:

- `utils/audio_processor.py` downloads audio via `yt-dlp`, using a fallback chain of internal player clients (`android` → `ios` → `web`) and realistic HTTP headers to reduce the chance of an IP block
- Optional cookie support (`YTDLP_COOKIES_FILE` env var) for cases where only a real, logged-in browser session gets through
- The resulting audio is chunked and sent to Whisper (English) or Sarvam AI (Hinglish, which also handles translation)

Hinglish audio always uses the audio-download + Sarvam path, since captions alone don't provide the Hindi→English translation Sarvam performs.

---

## 📁 Project Structure

```
AIVideoTranscripterAssistant/
├── core/
│   ├── __init__.py
│   ├── extractor.py         # Action items / decisions / questions extraction
│   ├── rag_engine.py        # RAG chain: retrieval + Q&A over the transcript
│   ├── summarizer.py        # Map-reduce summary + title generation
│   ├── transcriber.py       # Whisper (English) / Sarvam (Hinglish) transcription
│   └── vector_store.py      # Chroma vector store build/load/retrieve
├── utils/
│   ├── __init__.py
│   ├── audio_processor.py   # YouTube download (yt-dlp, fallback path) / format conversion / chunking
│   └── youtube_captions.py  # YouTube caption fetch — primary path for English YouTube URLs
├── app.py                   # Streamlit web UI
├── main.py                  # CLI entry point
├── test.py                  # Quick smoke-test script (hardcoded sample URL)
├── requirements.txt
├── runtime.txt
├── .env                     # Your local secrets (never committed)
├── .gitignore
└── README.md
```

---

## ⚙️ Prerequisites

- **Python 3.11** (see `runtime.txt`)
- **FFmpeg** installed and available on your system `PATH` (required by both `yt-dlp` and `pydub`, only used on the audio-download fallback path)
  * Windows: [download from ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH, or `choco install ffmpeg`
  * macOS: `brew install ffmpeg`
  * Linux: `sudo apt install ffmpeg`
- A **Mistral AI API key** — [console.mistral.ai](https://console.mistral.ai)
- (Optional, only for Hinglish transcription) A **Sarvam AI API key** — [sarvam.ai](https://sarvam.ai)

---

## 🚀 Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/AbhishekGorya/AIVideoTranscripterAssistant.git
   cd AIVideoTranscripterAssistant
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # macOS / Linux
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**

   Create a `.env` file in the project root:

   ```
   MISTRAL_API_KEY=your_mistral_api_key_here
   SARVAM_API_KEY=your_sarvam_api_key_here
   WHISPER_MODEL=small
   SARVAM_STT_MODEL=saaras:v2.5
   YTDLP_COOKIES_FILE=
   ```

   | Variable              | Required                       | Description                                                                                          |
   | ---------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------ |
   | `MISTRAL_API_KEY`       | ✅ Yes                          | Powers all LLM tasks (title, summary, extraction, RAG chat)                                            |
   | `SARVAM_API_KEY`        | Only for Hinglish               | Powers Hinglish speech-to-text-translate                                                               |
   | `WHISPER_MODEL`         | No (defaults to `small`)        | Whisper model size: `tiny`, `base`, `small`, `medium`, `large`                                        |
   | `SARVAM_STT_MODEL`      | No (defaults to `saaras:v2.5`)  | Sarvam STT model version                                                                                |
   | `YTDLP_COOKIES_FILE`    | No                               | Path to a `cookies.txt` file (Netscape format) exported from a logged-in browser, used only by the audio-download fallback when YouTube blocks unauthenticated requests |

   > ⚠️ **Never commit your `.env` file or any cookies file.** Both contain credentials that should stay local.

---

## ▶️ Usage

### Option 1 — Streamlit Web UI

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`), paste a YouTube URL or local file path in the sidebar, choose a language, and click **Analyse**.

### Option 2 — CLI

```bash
python main.py
```

You'll be prompted for a URL/file path and a language, then results print to the console, followed by an interactive chat loop:

```
💬 Chat with your meeting (type 'exit' to quit)
You: What were the main decisions made?
🤖 Assistant: ...
```

### Option 3 — Quick smoke test

```bash
python test.py
```

Runs the full pipeline against a hardcoded sample YouTube URL — useful for verifying your setup works end-to-end without typing anything.

---

## 🧠 How the RAG Chat Works

1. The full transcript is split into small (~500 character) overlapping chunks.
2. Each chunk is embedded using a local HuggingFace sentence-embedding model (`all-MiniLM-L6-v2`, runs on CPU — no API cost).
3. Embeddings are stored in a local **Chroma** vector database (`vector_db/`).
4. When you ask a question, the top-k most relevant chunks are retrieved and passed as context to Mistral, which answers **strictly from the transcript** — if the answer isn't in the context, it says so explicitly rather than hallucinating.

---

## 🛠 Tech Stack

| Category               | Tools                                                     |
| ------------------------ | ----------------------------------------------------------- |
| YouTube captions          | `youtube-transcript-api` (primary path for English)          |
| Audio acquisition (fallback) | `yt-dlp`, `pydub`, `ffmpeg`                                |
| Transcription (fallback)  | `openai-whisper` (local), Sarvam AI API (Hinglish)            |
| LLM orchestration          | `langchain`, `langchain-mistralai` (LCEL pipelines), Mistral AI |
| Vector store / RAG         | `chromadb`, `langchain-chroma`, `sentence-transformers`        |
| UI                          | `streamlit`                                                    |
| PDF/export (optional)      | `reportlab`, `fpdf2`                                            |

---

## ☁️ Deployment Notes (Streamlit Community Cloud)

This app is live at **https://avi-aivideotranscripterassistant.streamlit.app**, deployed on Streamlit Community Cloud. A few things that matter if you're deploying your own fork:

- The caption-first strategy above exists *specifically* because of this hosting environment — cloud/datacenter IPs get blocked far more aggressively than home IPs when downloading video/audio directly.
- If you still see download errors on the audio-download fallback path, that almost always means YouTube is blocking the platform's IP range at that moment, not a bug in the code. See the error message raised by `download_youtube_audio()` for the current recommended workarounds (cookies file, alternate host, or updating `yt-dlp`).
- Local Whisper (`openai-whisper` + `torch`) is resource-heavy. If the app crashes or restarts unexpectedly on the audio-fallback path, check available memory on your hosting tier — this is the most likely cause.

---

## 🐞 Troubleshooting

| Issue                                                             | Fix                                                                                                                                                  |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ModuleNotFoundError: No module named 'youtube_transcript_api'`    | Run `pip install youtube-transcript-api` and make sure `youtube-transcript-api>=1.0.0` is listed in `requirements.txt`                              |
| `ModuleNotFoundError: No module named 'langchain_chroma'`         | Run `pip install langchain-chroma` (make sure it's listed in `requirements.txt`)                                                                    |
| YouTube download fails with `HTTP Error 403`                      | Almost always an IP-level block on cloud hosts. The app already retries across player clients; if it still fails, try setting `YTDLP_COOKIES_FILE`. |
| YouTube download fails with `Requested format is not available`   | YouTube's SABR streaming / PO Token requirement blocking the audio-download fallback. Rely on the caption-first path (English) where possible; for Hinglish or caption-less videos, this may require a cookies file or is currently a known limitation. |
| `FileNotFoundError` / ffmpeg errors during download or conversion | Ensure FFmpeg is installed and on your system `PATH` — test with `ffmpeg -version` in your terminal                                                 |
| Whisper model download is slow on first run                        | This is expected — Whisper downloads its model weights the first time `load_model()` is called; subsequent runs use the cached model                |
| `RuntimeError: SARVAM_API_KEY is not set`                          | Only occurs when using `language="hinglish"` — add `SARVAM_API_KEY` to your `.env`, or use `language="english"` if you don't need Hinglish support  |
| Empty / garbled Hinglish transcripts                                | Verify your Sarvam API key is valid and has quota remaining                                                                                          |
| No transcript returned for an English YouTube video                | The video may simply have no caption track and also be blocked on the audio-download fallback — this is a rare combination but can happen           |

---

## 📄 License

Add your preferred license here (e.g. MIT, Apache 2.0).

---

## 🙋 Author

**Abhishek Gorya (Avi)** · [GitHub](https://github.com/AbhishekGorya) · [LinkedIn](https://linkedin.com/in/abhishekgorya)
