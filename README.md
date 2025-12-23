# 🔍 Needle - Legislative Intelligence Tool

**The Compass for Indian Legislation**

---

## 📋 Overview

Needle is a lightweight, sovereign AI tool designed for legislative drafting and analysis. Built for the Office of the MP (Milind Deora), this MVP provides three core modules:

1. **Legislative Co-Pilot** - PDF analysis with local RAG
2. **Parliamentary Question Generator** - Automated Lok Sabha format questions
3. **Zero Hour Drafter** - Urgent matter speech scripts

---

## 🛠️ Technical Stack

- **Frontend/UI**: Streamlit
- **Data Processing**: Pandas
- **RAG Logic**: LangChain, ChromaDB
- **Embeddings**: Sentence-Transformers (all-MiniLM-L6-v2)
- **PDF Processing**: PyPDF
- **Execution**: CPU-only (no GPU dependencies)

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.9 or higher
- pip package manager

### Installation Steps

1. **Clone or navigate to the repository**
   ```bash
   cd /app
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   streamlit run main.py
   ```

4. **Access the application**
   - The app will open automatically in your browser
   - Default URL: `http://localhost:8501`

---

## 📂 Project Structure

```
/app/
├── main.py                 # Main application container with navigation
├── modules/
│   ├── __init__.py        # Module initialization
│   ├── copilot.py         # Legislative Co-Pilot (Reading Engine)
│   └── drafter.py         # Parliamentary drafter (Writing Engine)
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

---

## 🎯 Features

### 1. Legislative Co-Pilot 🤖

**Purpose**: Analyze legislative documents using local RAG

**Features**:
- Upload PDF files (bills, regulations, drafts)
- Automatic text chunking (1000 chars with 100 overlap)
- Local CPU-based embeddings (no external API calls)
- Vector database storage using ChromaDB
- Query interface for document Q&A
- Retrieve top 3 relevant text chunks
- Reference evidence display

**How to Use**:
1. Select "Legislative Co-Pilot" from sidebar
2. Upload a PDF document
3. Wait for processing to complete
4. Ask questions in the chat interface
5. Review retrieved reference chunks

**Note**: AI summarization is mocked in this MVP phase. Phase 2 will integrate live LLM API.

### 2. Parliamentary Question Generator 📋

**Purpose**: Generate formatted parliamentary questions for Lok Sabha

**Features**:
- Topic input
- Ministry selection (32+ ministries)
- Question type selection (Starred/Unstarred)
- Auto-formatted output in official Lok Sabha template
- Downloadable text file

**Output Format**:
```
QUESTION NO. ____

(STARRED/UNSTARRED)

Will the Minister of [Ministry] be pleased to state:

(a) Whether the Government has noted...
(b) If so, the details thereof...
(c) The steps taken or proposed...
(d) The funds allocated...
(e) Whether any assessment has been made...
```

### 3. Zero Hour Drafter ⏰

**Purpose**: Draft speeches for urgent matters during Zero Hour

**Features**:
- Urgent issue description
- Severity level selection (Medium/High)
- Optional constituency input
- Auto-generated 200+ word speech script
- Professional parliamentary format
- Downloadable text file

**Output Format**:
```
Hon'ble Speaker Sir,

I rise to raise a matter of urgent public importance regarding [Issue]...

[Structured speech with clear asks and timeline]

Thank you, Sir.
```

---

## 🔒 Security & Privacy

- **Local Processing**: All embeddings run on CPU locally
- **No External API Calls**: No data sent to external services during operation
- **Sovereign AI**: Complete data sovereignty maintained
- **Secure Mode Active**: Footer indicator confirms local operation

---

## 🎨 Branding

- **Color Theme**: Sovereign Blue (#002D62)
- **App Icon**: 🔍 (Magnifying glass - symbolizing deep analysis)
- **Tagline**: "The Compass for Indian Legislation"

---

## 📊 Performance Specs

- **Embedding Model**: all-MiniLM-L6-v2 (lightweight, CPU-optimized)
- **Chunk Size**: 1000 characters
- **Chunk Overlap**: 100 characters
- **Retrieval**: Top 3 similar chunks
- **Processing**: Single-threaded CPU execution

---

## 🔧 Troubleshooting

### Common Issues

1. **SQLite Error**:
   - Already handled via `pysqlite3-binary` in requirements
   - If persists, reinstall: `pip install pysqlite3-binary --force-reinstall`

2. **Model Download Slow**:
   - First run downloads the embedding model (~80MB)
   - Subsequent runs use cached model

3. **PDF Processing Error**:
   - Ensure PDF is not corrupted
   - Check file is not password-protected
   - Verify file size is reasonable (<50MB recommended)

4. **Memory Issues**:
   - Large PDFs may require more RAM
   - Consider processing in smaller batches

---

## 🛣️ Roadmap

### Phase 1 (Current - MVP)
- ✅ Basic UI with navigation
- ✅ PDF ingestion and chunking
- ✅ Local embeddings and vector storage
- ✅ Document retrieval
- ✅ Parliamentary question generator
- ✅ Zero Hour speech drafter
- ✅ Mock AI summaries

### Phase 2 (Planned)
- 🔄 Live LLM API integration (Groq/OpenAI)
- 🔄 Advanced summarization
- 🔄 Multi-document analysis
- 🔄 Historical question database
- 🔄 Speech analytics
- 🔄 Export to multiple formats (PDF, DOCX)

---

## 👥 Credits

**Client**: Office of the MP (Milind Deora)  
**Product Unit**: Legislative Intelligence Unit  
**Build Type**: MVP (Minimum Viable Product)  
**Version**: 1.0.0  

---

## 📞 Support

For technical issues or feature requests, please contact the Legislative Intelligence Unit.

---

## 📄 License

Proprietary - Office of the MP (Milind Deora)

---

**Built with 🇮🇳 for Indian Legislative Excellence**
