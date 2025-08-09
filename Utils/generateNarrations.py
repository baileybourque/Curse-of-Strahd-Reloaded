from pathlib import Path
import markdown
from bs4 import BeautifulSoup
from gtts import gTTS  # You can replace this with ElevenLabs or another TTS

PATCHED_DIR = Path("patched")
NARRATIONS_DIR = Path("narrations")
NARRATIONS_DIR.mkdir(exist_ok=True)

def clean_markdown(md_text):
    """Convert markdown to plain text using HTML parsing."""
    html = markdown.markdown(md_text)
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text()

def generate_narration(text, output_path):
    """Generate MP3 narration using Google TTS."""
    tts = gTTS(text, lang="en")
    tts.save(str(output_path))

def main():
    md_files = list(PATCHED_DIR.rglob("*.md"))
    print(f"Found {len(md_files)} markdown files to narrate.")
    
    for md_file in md_files:
        print(f"Processing {md_file.name}")
        raw = md_file.read_text(encoding="utf-8")
        clean = clean_markdown(raw)

        # Optional: truncate long files or split into chunks if needed

        output_file = NARRATIONS_DIR / (md_file.stem + ".mp3")
        generate_narration(clean, output_file)
        print(f"Saved narration to {output_file}")

if __name__ == "__main__":
    main()
