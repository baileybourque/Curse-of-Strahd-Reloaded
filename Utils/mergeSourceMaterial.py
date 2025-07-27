#!/usr/bin/env python3
import re
import argparse
from pathlib import Path
from textwrap import dedent
import logging
from difflib import get_close_matches

CITATION_TAG = re.compile(r'<span class="citation">([^<]+?)</span>')
TAKES_PLACE_IN   = re.compile(r'This scene takes place in ([^.]+?)\.')
CORRESPONDS_TO   = re.compile(r'This scene corresponds to ([^.]+?)\.')
LARGELY_TAG  = re.compile(r'as described in <span class="citation">([^<]+?)</span>')

PATTERNS = [TAKES_PLACE_IN, CORRESPONDS_TO]

SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')

# Configure the logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Patch Reloaded .md file with canon excerpts")
    # parser.add_argument('-i', '--input', type=Path, required=True, help='Path to the input .md file')
    # parser.add_argument('-o', '--output', type=Path, help='Path to save the output file (default: stdout)')
    parser.add_argument(
        '-l', '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set the logging level (default: INFO)'
    )
    return parser.parse_args()

def build_canon_index(canon_dirs):
    index = {}
    heading_re = re.compile(r"^(#{1,3})\s+(.*)$", re.M)  # Match headings with # and title
    link_re = re.compile(r'\[\]\((https?://[^\)]+)\)(.+)')
    for canon_dir in canon_dirs:
        canon_dir = Path(canon_dir).resolve()
        for md_file in canon_dir.rglob("*.md"):
            logger.info(f'Loading canon from {md_file}')  # Replaced print with logger.info
            content = md_file.read_text(encoding="utf-8")
            parts = heading_re.split(content)
            current_title = None
            current_subtitle = None
            for i in range(1, len(parts), 3):
                level, heading, body = parts[i], parts[i + 1], parts[i + 2]
                if len(level) == 1:  # Single # indicates a title
                    current_title = heading
                    current_subtitle = None
                elif len(level) > 1:  # Two or more # indicates a subtitle
                    current_subtitle = heading
                    match = link_re.search(current_subtitle)
                    if match:
                        link, current_subtitle = match.groups()
                    else:
                        link = None
                    
                    check_keys = [current_subtitle,
                                  current_subtitle.split('.')[0],
                                  "Area " + current_subtitle,
                                  "Area " + current_subtitle.split('.')[0]]
                    
                    if ":" in current_title:
                        titles = current_title.split(":") + [current_title]
                    else:
                        titles = [current_title]
                    titles = [title.strip() for title in titles if title.strip()]

                    for title in titles:
                        for key in check_keys:
                            index.setdefault(title, {})
                            index[title][key] = { "link": link, "body": body }
                            logger.info(f'Added to index: {title} -> {key}')
                    

    return index

def find_closest_match(target: str, candidates: list[str], cutoff: float = 0.6) -> str | None:
    """
    Finds the closest match to 'target' in the list 'candidates' using difflib.
    Returns the closest match or None if no match above the cutoff is found.
    """
    # Check if target string is in candidates
    if target in candidates:
        return target
    
    # Check for substring matches
    likely_candidates = [c for c in candidates if target in c or c in target]
    if likely_candidates:
        matches = get_close_matches(target, likely_candidates, n=1, cutoff=cutoff)
        return matches[0] if matches else None
    
    # Use difflib to find the closest match
    matches = get_close_matches(target, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None

def patch_sentence(sent: str, index) -> str:
    for pat in PATTERNS:
        m = pat.search(sent)
        if m:
            if ":" in m.group(1):
                split_by = ":"
            elif "," in m.group(1):
                split_by = ","
            else:
                split_by = " "
            chapter, scene = m.group(1).split(split_by, 1)
            chapter = chapter.strip()
            scene = scene.strip()
            if "," in scene or "and" in scene or "&" in scene:
                scenes = [s.strip() for s in re.split(r',| and |&', scene)]
            else:
                scenes = [scene]
            scenes = [s.replace("Areas", "Area") for s in scenes if s]
            logger.info(f'Looking up citation for Chapter: {chapter}, Scene(s): {scene} -> {scenes}')
            candidate_chapter = find_closest_match(chapter, index.keys())
            if candidate_chapter:
                logger.info(f'Found closest match for chapter: {candidate_chapter}')
                for scene_to_check in scenes:
                    candidate_scene = find_closest_match(scene_to_check, index[candidate_chapter].keys())
                    if candidate_scene:
                        logger.info(f'Found closest match for scene: {scene_to_check} -> {candidate_scene}')
                        excerpt = index[candidate_chapter][candidate_scene]
                        sent += "\n"
                        sent += f'>[!source]+ {excerpt["link"]}\n'
                        for line in excerpt["body"].splitlines():
                            sent += f'> {line}\n'
                    else:
                        logger.warning(f'No matching scene found for {scene_to_check} in chapter {candidate_chapter}')
            else:
                logger.warning(f'No matching chapter found for {chapter}')

    return sent

def patch_file(infile: Path, outfile: Path, canon_index):
    logger.info(f'Patching file: {infile} -> {outfile}')
    text = infile.read_text(encoding='utf-8')
    output_lines = []
    for line in text.splitlines():
        patched_line = patch_sentence(line, canon_index)
        output_lines.append(patched_line)
    outfile.write_text('\n'.join(output_lines), encoding='utf-8')

def patch_files(prefixes, canon_index):
    process_dirs = []
    for reloaded_directory in Path('.').glob('*'):
        if not reloaded_directory.is_dir() or reloaded_directory.name.startswith('.'):
            continue
        for prefix in prefixes:
            if reloaded_directory.name.startswith(prefix):
                process_dirs.append(reloaded_directory)
    
    if not process_dirs:
        logger.error("No directories found to process with the specified prefixes.")
        return
    
    logger.info(f"Found {len(process_dirs)} directories to process: {', '.join(d.name for d in process_dirs)}")
    
    for reloaded_directory in process_dirs:
        logger.info(f'Processing directory: {reloaded_directory}')
        for infile in reloaded_directory.rglob('*.md'):
            fullpath = infile.resolve()
            logger.info(f'Processing file: {fullpath}')
            outfile = Path('Patched') / infile.relative_to('.')
            outfile.parent.mkdir(parents=True, exist_ok=True)
            patch_file(infile, outfile, canon_index)


def main():
    args = parse_arguments()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), 'DEBUG'),
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    logger.info("Logger initialized with level: %s", args.log_level)
    canon_index = build_canon_index(["../Source Book"])
    patch_files(["Act ", "Chapter ", "Appendices"], canon_index)

if __name__ == '__main__':
    main()
