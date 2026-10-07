"""Make docs/demo.gif, the animation at the top of the README.

Runs the real commands against the public practice sites, captures what they
print, and draws it as a terminal: the command typed out, then the output.
Nothing in the output is written by hand, with one exception noted below.

    pip install pillow
    python docs/make_demo.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "demo.gif"

COLUMNS, ROWS = 84, 30
FONT_SIZE, LINE_HEIGHT, MARGIN = 16, 21, 18
BACKGROUND, TEXT, DIM, PROMPT, COMMAND = "#0d1117", "#c9d1d9", "#8b949e", "#3fb950", "#ffffff"
FONTS = [
    "C:/Windows/Fonts/consola.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]

# The question is only asked when a person is at the keyboard. Captured output has no
# keyboard, so these two lines (the tool's own wording) are put back where they appear.
QUESTION_AFTER = "This list continues on more pages."
QUESTION = ["Save?  [Enter] this page   [a] all pages   [q] quit", "> "]

SCENES = [
    # (what is typed, arguments actually run, the question is asked, clear the screen first)
    ("scrapewizard https://books.toscrape.com", ["https://books.toscrape.com"], True, False),
    ("scrapewizard run books.recipe.yaml", ["run", "books.recipe.yaml"], False, False),
    ("scrapewizard https://quotes.toscrape.com/js/ --all-pages",
     ["https://quotes.toscrape.com/js/", "--all-pages"], False, True),
]


def run(arguments, folder):
    env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING="utf-8", COLUMNS=str(COLUMNS), NO_COLOR="1")
    # Input is an empty pipe, never the keyboard, so the tool does not stop to ask.
    done = subprocess.run([sys.executable, "-m", "scrapewizard.cli.main", *arguments], cwd=folder, env=env,
                          capture_output=True, input=b"", timeout=300)
    text = (done.stdout + done.stderr).decode("utf-8", errors="replace")
    if done.returncode != 0:
        raise SystemExit(f"scrapewizard {' '.join(arguments)} failed:\n{text}")
    return [line.rstrip() for line in text.replace("\r\n", "\n").rstrip("\n").split("\n")]


def load_font():
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, FONT_SIZE)
    raise SystemExit("No monospace font found. Add the path of one to FONTS.")


class Terminal:
    def __init__(self):
        self.font = load_font()
        self.cell = self.font.getlength("M")
        self.size = (int(2 * MARGIN + COLUMNS * self.cell), 2 * MARGIN + ROWS * LINE_HEIGHT)
        self.lines = []     # each line: list of (text, colour)
        self.frames = []    # (image, milliseconds)

    def snap(self, milliseconds):
        image = Image.new("RGB", self.size, BACKGROUND)
        draw = ImageDraw.Draw(image)
        for row, parts in enumerate(self.lines[-ROWS:]):
            x = MARGIN
            for text, colour in parts:
                draw.text((x, MARGIN + row * LINE_HEIGHT), text, font=self.font, fill=colour)
                x += self.cell * len(text)
        self.frames.append((image, milliseconds))

    def type_command(self, command):
        self.lines.append([("$ ", PROMPT), ("", COMMAND)])
        self.snap(500)
        for end in range(2, len(command) + 2, 2):
            self.lines[-1] = [("$ ", PROMPT), (command[:end], COMMAND)]
            self.snap(45)
        self.snap(350)

    def print_output(self, output):
        for number, line in enumerate(output):
            colour = DIM if line.startswith(("  ...", "  (+", "  page ")) else TEXT
            self.lines.append([(line, colour)])
            if line == QUESTION[1]:
                self.snap(1300)          # the pause before Enter is pressed
            elif number == 0:
                self.snap(650)           # "Looking at ..." while the page is fetched
            else:
                self.snap(110 if line.startswith("  page ") else 45)
        self.lines.append([("", TEXT)])
        self.snap(1900)

    def save(self, path):
        # A fixed palette: every text colour in eight steps towards the background, for smooth
        # letter edges. Letting the library pick one from a frame loses the rarely used colours.
        back = tuple(int(BACKGROUND[i:i + 2], 16) for i in (1, 3, 5))
        colours = []
        for colour in (TEXT, DIM, PROMPT, COMMAND):
            front = tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
            for step in range(1, 9):
                colours.extend(round(b + (f - b) * step / 8) for f, b in zip(front, back))
        palette = Image.new("P", (1, 1))
        palette.putpalette(list(back) + colours)
        images = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image, _ in self.frames]
        images[0].save(path, save_all=True, append_images=images[1:], loop=0, optimize=True,
                       duration=[milliseconds for _, milliseconds in self.frames])


def main():
    terminal = Terminal()
    with tempfile.TemporaryDirectory() as folder:
        for typed, arguments, asks, clear in SCENES:
            output = run(arguments, folder)
            if asks and QUESTION_AFTER in output:
                at = output.index(QUESTION_AFTER) + 1
                output[at:at] = QUESTION
            if clear:
                terminal.lines = []
            terminal.type_command(typed)
            terminal.print_output(output)
    terminal.snap(1500)
    terminal.save(OUT)
    seconds = sum(milliseconds for _, milliseconds in terminal.frames) / 1000
    print(f"{OUT.relative_to(REPO)}: {len(terminal.frames)} frames, {seconds:.0f} seconds, "
          f"{OUT.stat().st_size // 1024} KB, {terminal.size[0]}x{terminal.size[1]}")


if __name__ == "__main__":
    main()
