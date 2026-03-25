# Pdf2Any

Pdf2Any is a plug-and-play batch processing tool that leverages the high-precision MinerU API for PDF parsing and Pandoc for multi-format output compilation. It supports converting PDF documents to EPUB, DOCX, Markdown, LaTeX, and HTML.

## Prerequisites

- **Python 3.8+**
- **Pandoc**: Must be installed and available in your system's `PATH`.
  - [Download Pandoc](https://pandoc.org/installing.html)
- **LaTeX Engine (Optional)**: If you plan on outputting to PDF format, ensure you have a standard LaTeX distribution installed (e.g., TeXLive or MiKTeX).

## Setup & Installation

1. **Clone the repository:**

   ```bash
   git clone <repo-url>
   cd Pdf2Any
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Copy `.env.example` to `.env` and fill in your MinerU API Token:
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```env
   MINERU_API_TOKEN=your_actual_mineru_api_token
   ```
   MinerU API is free for all users. Obtain it via [MinerU API Manage](https://mineru.net/apiManage/token).

## Usage

### 🖥️ Local Web GUI (Gradio)

Run the script without arguments to start the user-friendly Gradio web application:

```bash
python main.py
```

### ⚡ Command Line Interface (CLI)

The tool serves as a powerful batch processor directly from the CLI.

**Basic Multi-file Epub Usage:**

```bash
python main.py -i file1.pdf file2.pdf -o ./output/
```

**Advanced Usage:**

```bash
# Output multiple formats simultaneously, offline pandoc mode, and custom API-key
python main.py -i input.pdf -o ./output/ -f epub md docx --network offline --formula text --api-key <YOUR_TOKEN>
```

Run `python main.py -h` for full commands list.

## Development & Testing

You can use `pytest` to validate the environment setup, API logic parsing, and core integrations.

```bash
pytest tests/ -v
```

## License

MIT License.
