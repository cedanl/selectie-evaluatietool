"""Neemt een korte demo van het dashboard op en zet die om naar docs/img/demo.gif.

Start de app op een losse poort, laadt de demodata en loopt langs de
tabbladen. Opnieuw draaien na een UI-wijziging:

    uv run --with playwright python -m playwright install chromium   # eenmalig
    uv run --with playwright python scripts/maak_readme_gif.py

Vereist ffmpeg op het PATH.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
UIT = ROOT / "docs" / "img" / "demo.gif"
POORT = 8765
BREEDTE, HOOGTE = 1280, 800
GIF_BREEDTE, FPS = 800, 10
DEMO = "Demo Radboud 2026"  # bachelor: boxplots op één schaal, leest het best

# Playwright neemt de muis niet op; deze stip maakt klikken zichtbaar.
CURSOR_JS = """
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.style.cssText = 'position:fixed;z-index:99999;width:22px;height:22px;'
    + 'margin:-11px 0 0 -11px;border-radius:50%;pointer-events:none;'
    + 'background:rgba(220,38,38,.35);border:2px solid rgba(220,38,38,.9);'
    + 'left:-50px;top:-50px;transition:transform .15s';
  document.body.appendChild(c);
  document.addEventListener('mousemove', e => {
    c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
  });
  document.addEventListener('mousedown', () => c.style.transform = 'scale(.6)');
  document.addEventListener('mouseup', () => c.style.transform = '');
});
"""


def wacht_op_app(url, timeout=60):
    eind = time.time() + timeout
    while time.time() < eind:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except OSError:
            time.sleep(0.5)
    sys.exit(f"App reageert niet op {url}")


def klik(pagina, selector, pauze=600):
    doel = pagina.locator(selector).first
    doel.scroll_into_view_if_needed()
    box = doel.bounding_box()
    pagina.mouse.move(
        box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=25
    )
    pagina.wait_for_timeout(pauze)
    pagina.mouse.down()
    pagina.mouse.up()


def scroll(pagina, pixels, stappen=30):
    for _ in range(stappen):
        pagina.mouse.wheel(0, pixels / stappen)
        pagina.wait_for_timeout(40)


def neem_op(url, map_):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": BREEDTE, "height": HOOGTE},
            record_video_dir=map_,
            record_video_size={"width": BREEDTE, "height": HOOGTE},
        )
        context.add_init_script(CURSOR_JS)
        pagina = context.new_page()
        start = time.time()
        pagina.goto(url)
        pagina.wait_for_selector("#btn-demodata")
        pagina.click("#demo-dataset-picker")
        pagina.click(f"text={DEMO}")
        pagina.wait_for_timeout(500)
        begin = time.time() - start  # alles hiervoor is een leeg scherm

        pagina.mouse.move(900, 300)
        pagina.wait_for_timeout(1000)
        klik(pagina, "#btn-demodata")
        pagina.wait_for_selector("text=Over dit dashboard")
        pagina.wait_for_timeout(1000)

        for tab, wacht, omlaag in [
            ("Wat valt op", 2500, 0),
            ("Selectiescores", 1200, 420),
            ("Verschiltoets", 2500, 0),
            ("Correlatie", 2500, 0),
        ]:
            pagina.mouse.wheel(0, -5000)
            klik(pagina, f".nav-link:text-is('{tab}')")
            pagina.wait_for_load_state("networkidle")
            pagina.wait_for_timeout(wacht)
            if omlaag:
                scroll(pagina, omlaag)
                pagina.wait_for_timeout(1500)

        video = pagina.video.path()
        context.close()
        browser.close()
    return Path(video), begin


def naar_gif(video, begin):
    UIT.parent.mkdir(parents=True, exist_ok=True)
    filters = f"fps={FPS},scale={GIF_BREEDTE}:-1:flags=lanczos"
    palet = video.with_suffix(".png")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            f"{begin:.2f}",
            "-i",
            str(video),
            "-vf",
            f"{filters},palettegen=stats_mode=diff",
            str(palet),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            f"{begin:.2f}",
            "-i",
            str(video),
            "-i",
            str(palet),
            "-lavfi",
            f"{filters}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
            str(UIT),
        ],
        check=True,
    )


def main():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg niet gevonden op het PATH")
    url = f"http://127.0.0.1:{POORT}/"
    app = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=ROOT,
        env={**os.environ, "PORT": str(POORT)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wacht_op_app(url)
        with tempfile.TemporaryDirectory() as map_:
            video, begin = neem_op(url, map_)
            naar_gif(video, begin)
    finally:
        app.terminate()
    print(f"{UIT.relative_to(ROOT)}: {UIT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
