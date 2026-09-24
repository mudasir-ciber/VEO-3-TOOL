"""Intelligent scene prompt batch parser with project continuity support."""
import re
from typing import List, Dict, Tuple, Optional

class ScenePrompt:
    def __init__(self, scene_number: int, prompt_text: str):
        self.scene_number = scene_number
        self.prompt_text = prompt_text.strip()

    def to_dict(self) -> Dict[str, any]:
        return {
            "scene_number": self.scene_number,
            "prompt_text": self.prompt_text
        }

    def __repr__(self) -> str:
        return f"<ScenePrompt {self.scene_number}: {self.prompt_text[:30]}...>"


class PromptParser:
    # Regex to match headers like "SCENE 1", "Scene 01:", "Scene #1 -", "1. ", "[SCENE 1]"
    SCENE_HEADER_PATTERN = re.compile(
        r'^(?:\[?\s*SCENE\s*#?\s*(\d+)\s*\]?|(\d+)[\.\)]\s+)(?:[:\-\s]*)(.*)$',
        re.IGNORECASE
    )

    @classmethod
    def parse_batch(cls, raw_text: str, default_start_number: int = 1) -> List[ScenePrompt]:
        """
        Parse raw user input into ordered ScenePrompt objects.

        If explicit scene numbers are detected (e.g. 'SCENE 11', '11.'), they are preserved.
        If no explicit numbers are found, items are numbered sequentially starting
        from `default_start_number` (crucial for batch 2 continuing from 11).
        """
        if not raw_text or not raw_text.strip():
            return []

        lines = raw_text.splitlines()
        scenes: List[ScenePrompt] = []

        current_scene_num: Optional[int] = None
        current_buffer: List[str] = []

        has_explicit_headers = False

        # First pass: check if there are explicit headers like "SCENE X"
        for line in lines:
            line_str = line.strip()
            match = cls.SCENE_HEADER_PATTERN.match(line_str)
            if match:
                has_explicit_headers = True
                break

        if has_explicit_headers:
            for line in lines:
                line_str = line.strip()
                match = cls.SCENE_HEADER_PATTERN.match(line_str)
                if match:
                    # Flush previous scene
                    if current_scene_num is not None and current_buffer:
                        text = "\n".join(current_buffer).strip()
                        if text:
                            scenes.append(ScenePrompt(current_scene_num, text))
                        current_buffer = []

                    # Parse new scene number
                    num_str = match.group(1) or match.group(2)
                    current_scene_num = int(num_str)
                    remainder = match.group(3).strip()
                    if remainder:
                        current_buffer.append(remainder)
                else:
                    if current_scene_num is not None:
                        current_buffer.append(line)

            # Flush last scene
            if current_scene_num is not None and current_buffer:
                text = "\n".join(current_buffer).strip()
                if text:
                    scenes.append(ScenePrompt(current_scene_num, text))

        else:
            # No explicit headers: split by blank lines or paragraphs
            blocks = re.split(r'\n\s*\n+', raw_text.strip())
            curr_num = default_start_number
            for block in blocks:
                clean_block = block.strip()
                if clean_block:
                    scenes.append(ScenePrompt(curr_num, clean_block))
                    curr_num += 1

        # Sort scenes by scene_number to guarantee strict sequential ordering
        scenes.sort(key=lambda s: s.scene_number)
        return scenes


if __name__ == "__main__":
    sample_explicit = """
    SCENE 1: Master airplane on runway
    SCENE 2: Airplane takes off into clouds
    SCENE 3: Supersonic wings expand
    """
    res1 = PromptParser.parse_batch(sample_explicit, default_start_number=1)
    print("Explicit:", res1)

    sample_batch2 = """
    SCENE 11: Flying in outer stratosphere
    SCENE 12: Approaching orbital station
    """
    res2 = PromptParser.parse_batch(sample_batch2, default_start_number=11)
    print("Batch 2 with explicit 11-12:", res2)

    sample_blocks = """
    First scene plain text description.

    Second scene with another plain text description.
    """
    res3 = PromptParser.parse_batch(sample_blocks, default_start_number=21)
    print("Batch 3 plain blocks starting at 21:", res3)
