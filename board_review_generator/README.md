# Board Review One-Pager Generator

Converts any board-review PPTX or PDF into a single executive slide (HTML + optional PDF) — exactly the format produced by the Chief of Staff workflow.

## How it works

```
Input deck (.pptx / .pdf)
        │
        ▼
 Text extraction
 (python-pptx / pdfplumber)
        │
        ▼
 LLM (OpenAI gpt-4o)
 structures data into JSON:
   • Key Metrics (scorecard)
   • Areas of Focus (watch-outs)
   • Takeaways (insights)
        │
        ▼
 HTML renderer
 → slide.html  (1280 × 720 px)
 → slide.pdf   (via WeasyPrint)
```

## Quick start

### 1. Install dependencies

```bash
cd board_review_generator
pip install -r requirements.txt
```

### 2. Set your API key

```bash
cp .env.example .env
# edit .env and add your OPENAI_API_KEY
export $(cat .env | xargs)
```

### 3. Run

```bash
# HTML only
python generate_slide.py --input your_deck.pptx --output slide.html

# HTML + PDF
python generate_slide.py --input your_deck.pptx --output slide.html --pdf slide.pdf

# Also save the structured JSON (useful for debugging / re-runs)
python generate_slide.py --input your_deck.pptx --output slide.html --pdf slide.pdf --json data.json
```

Open `slide.html` in any browser, or distribute `slide.pdf`.

## Do I need an LLM API key?

**Yes — an OpenAI API key is required.** The LLM is the brain that reads the raw deck text and structures it into the scorecard, areas of focus, and takeaways.

| Option | Cost estimate per run | Notes |
|---|---|---|
| `gpt-4o` (default) | ~$0.05–$0.15 | Best quality; recommended |
| `gpt-4o-mini` | ~$0.005–$0.02 | 90 % of the quality at ~10 % of the cost |
| Local Ollama (e.g. `llama3`) | Free | Set `OPENAI_BASE_URL=http://localhost:11434/v1` and `OPENAI_MODEL=llama3`; quality varies |

To use `gpt-4o-mini` (cheapest cloud option):

```bash
export OPENAI_MODEL=gpt-4o-mini
```

To use a **local model via Ollama** (no API cost):

```bash
# Install Ollama: https://ollama.com
ollama pull llama3
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_MODEL=llama3
export OPENAI_API_KEY=ollama   # any non-empty string
```

## Customising the slide

The HTML template and CSS live entirely inside `generate_slide.py` — search for the `CSS` and `render_html` constants. Change colours, fonts, or layout there and re-run.

## File structure

```
board_review_generator/
├── generate_slide.py   # main script
├── requirements.txt    # Python dependencies
├── .env.example        # environment variable template
└── README.md           # this file
```
