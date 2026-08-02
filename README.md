# 🎬 AI Video Transcripter Assistant

An end-to-end pipeline that turns any YouTube video or local audio/video file into a fully searchable meeting/video intelligence report — transcript, title, summary, action items, key decisions, open questions, and a RAG-powered chatbot to ask follow-up questions about the content.

Supports both **English** (via local Whisper) and **Hinglish / code-mixed Hindi-English** (via Sarvam AI's speech-to-text-translate API) audio.

---

## ✨ Features

- 🔗 **Flexible input** — paste a YouTube URL or point to a local audio/video file
- 🔊 **Automatic audio extraction & chunking** — long recordings are split into manageable pieces
- 📝 **Transcription** — Whisper (local, offline) for English; Sarvam AI (cloud) for Hinglish
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
                  ┌────────────────────────┐
                  │  utils/audio_processor │  → download / convert to WAV,
                  │                        │     split into fixed-length chunks
                  └───────────┬────────────┘
                               ▼
                  ┌────────────────────────┐
                  │   core/transcriber     │  → Whisper (English) or
                  │                        │     Sarvam AI (Hinglish)
                  └───────────┬────────────┘
                               ▼
                     Full meeting transcript
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
 ┌──────────────────┐ ┌─────────────────┐ ┌──────────────────────┐
 │ core/summarizer   │ │ core/extractor  │ │ core/vector_store     │
 │ → title + summary │ │ → action items, │ │ → embed + store       │
 │   (map-reduce)     │ │   decisions,    │ │   transcript chunks   │
 │                    │ │   questions     │ │   in Chroma            │
 └──────────────────┘ └─────────────────┘ └──────────┬────────────┘
                                                       ▼
                                            ┌─────────────────────┐
                                            │  core/rag_engine     │
                                            │  → retrieval-augmented│
                                            │    chat over transcript│
                                            └─────────────────────┘
```

All LLM calls (title, summary, extraction, RAG answers) go through **Mistral AI** (`mistral-small-latest`) via LangChain's LCEL (LangChain Expression Language) pipelines.

---

## 📁 Project Structure

```
AIVideoTranscripterAssistant/
├── core/
│   ├── __init__.py
│   ├── extractor.py       # Action items / decisions / questions extraction
│   ├── rag_engine.py      # RAG chain: retrieval + Q&A over the transcript
│   ├── summarizer.py      # Map-reduce summary + title generation
│   ├── transcriber.py     # Whisper (English) / Sarvam (Hinglish) transcription
│   └── vector_store.py    # Chroma vector store build/load/retrieve
├── utils/
│   ├── __init__.py
│   └── audio_processor.py # YouTube download / format conversion / chunking
├── app.py                 # Streamlit web UI
├── main.py                # CLI entry point
├── test.py                # Quick smoke-test script (hardcoded sample URL)
├── requirements.txt
├── .env                   # Your local secrets (never committed)
├── .gitignore
└── README.md
```

---

## ⚙️ Prerequisites

- **Python 3.10+**
- **FFmpeg** installed and available on your system `PATH` (required by both `yt-dlp` and `pydub`)
  - Windows: [download from ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH, or `choco install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- A **Mistral AI API key** — [console.mistral.ai](https://console.mistral.ai)
- (Optional, only for Hinglish transcription) A **Sarvam AI API key** — [sarvam.ai](https://sarvam.ai)

---

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-username>/AIVideoTranscripterAssistant.git
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
   ```env
   MISTRAL_API_KEY=your_mistral_api_key_here
   SARVAM_API_KEY=your_sarvam_api_key_here
   WHISPER_MODEL=small
   SARVAM_STT_MODEL=saaras:v2.5
   ```

   | Variable | Required | Description |
   |---|---|---|
   | `MISTRAL_API_KEY` | ✅ Yes | Powers all LLM tasks (title, summary, extraction, RAG chat) |
   | `SARVAM_API_KEY` | Only for Hinglish | Powers Hinglish speech-to-text-translate |
   | `WHISPER_MODEL` | No (defaults to `small`) | Whisper model size: `tiny`, `base`, `small`, `medium`, `large` |
   | `SARVAM_STT_MODEL` | No (defaults to `saaras:v2.5`) | Sarvam STT model version |

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

## 🛠️ Tech Stack

| Category | Tools |
|---|---|
| Audio acquisition | `yt-dlp`, `pydub`, `ffmpeg` |
| Transcription | `openai-whisper` (local), Sarvam AI API (Hinglish) |
| LLM orchestration | `langchain`, `langchain-mistralai` (LCEL pipelines) |
| Vector store / RAG | `chromadb`, `langchain-chroma`, `sentence-transformers` |
| UI | `streamlit` |
| PDF/export (optional) | `reportlab`, `fpdf2` |

---

## 🐞 Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'langchain_chroma'` | Run `pip install langchain-chroma` (make sure it's listed in `requirements.txt`) |
| `FileNotFoundError` / ffmpeg errors during download or conversion | Ensure FFmpeg is installed and on your system `PATH` — test with `ffmpeg -version` in your terminal |
| Whisper model download is slow on first run | This is expected — Whisper downloads its model weights the first time `load_model()` is called; subsequent runs use the cached model |
| `RuntimeError: SARVAM_API_KEY is not set` | Only occurs when using `language="hinglish"` — add `SARVAM_API_KEY` to your `.env`, or use `language="english"` if you don't need Hinglish support |
| Empty / garbled Hinglish transcripts | Verify your Sarvam API key is valid and has quota remaining |

---

## 📄 License

Add your preferred license here (e.g. MIT, Apache 2.0).

---

## 🙋 Author

**Abhishek Gorya (Avi)**
[GitHub](https://github.com/AbhishekGorya) · [LinkedIn](https://linkedin.com/in/abhishekgorya)
