"""Neemt een demo van het dashboard op en zet die om naar docs/img/demo.gif.

Start de app op een losse poort, laadt de demodata en loopt langs alle
tabbladen, de keuzelijsten (groeperen, achtergrond) en de rapportknop.
Wachttijd terwijl de app rekent wordt weggeknipt. Opnieuw draaien na een
UI-wijziging:

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

from playwright.sync_api import TimeoutError, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
UIT = ROOT / "docs" / "img" / "demo.gif"
POORT = 8765
BREEDTE, HOOGTE = 1280, 800
GIF_BREEDTE, FPS = 720, 8
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

# Klaar als niets in het actieve tabblad meer laadt, elke grafiek er datapunten
# heeft en er tekst staat. Alle tabbladen staan tegelijk in de DOM en outputs
# in verborgen tabbladen blijven op "loading", dus alleen het actieve telt.
INHOUD_JS = """() => {
  const tab = document.querySelector('.tab-pane.active');
  if (!tab || tab.querySelector('[data-dash-is-loading="true"]')) return false;
  const plots = [...tab.querySelectorAll('.js-plotly-plot')];
  // Een heatmap tekent een afbeelding in plaats van g.trace
  if (!plots.every(p => p.querySelector('g.trace, .hm image'))) return false;
  return (tab.innerText || '').trim().length > 200;
}"""


class Laadtijd:
    """Houdt bij wanneer de app aan het rekenen is; die stukken knipt ffmpeg eruit."""

    def __init__(self, start):
        self.start = start
        self.stukken = []

    def nu(self):
        return time.time() - self.start

    def knip(self, van, tot):
        if tot > van:
            self.stukken.append((van, tot))

    def wacht(self, pagina, marge=0.15, timeout=20000):
        van = self.nu() + marge  # de klik zelf blijft zichtbaar
        pagina.wait_for_timeout(250)  # Dash zet de laadstatus niet meteen
        try:
            pagina.wait_for_function(INHOUD_JS, timeout=timeout)
        except TimeoutError:
            print("  let op: inhoud niet herkend, niet geknipt", flush=True)
            return
        pagina.wait_for_timeout(300)  # grafiek tekenen
        self.knip(van, self.nu() - 0.2)


def wacht_op_app(url, timeout=60):
    eind = time.time() + timeout
    while time.time() < eind:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except OSError:
            time.sleep(0.5)
    sys.exit(f"App reageert niet op {url}")


def beweeg_naar(pagina, doel, pauze=500):
    doel.scroll_into_view_if_needed()
    box = doel.bounding_box()
    pagina.mouse.move(
        box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=20
    )
    pagina.wait_for_timeout(pauze)


def klik(pagina, doel, pauze=500):
    """Klik met de echte muis, zodat de cursorstip meebeweegt."""
    if isinstance(doel, str):
        doel = pagina.locator(doel)
    beweeg_naar(pagina, doel.locator("visible=true").first, pauze)
    pagina.mouse.down()
    pagina.mouse.up()


def kies(pagina, dropdown_id, optie):
    """Kies een optie in een dcc.Dropdown."""
    klik(pagina, f"#{dropdown_id}")
    pagina.wait_for_timeout(400)
    klik(pagina, pagina.get_by_role("option", name=optie, exact=True), pauze=400)


def scroll(pagina, pixels, stappen=12):
    for _ in range(stappen):
        pagina.mouse.wheel(0, pixels / stappen)
        pagina.wait_for_timeout(60)


def tab(pagina, laadtijd, naam, wacht=1500):
    print(f"  tabblad {naam}", flush=True)
    pagina.mouse.wheel(0, -5000)
    pagina.wait_for_timeout(300)
    klik(pagina, f".nav-link:text-is('{naam}')")
    laadtijd.wacht(pagina)
    pagina.wait_for_timeout(wacht)


def neem_op(url, map_):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": BREEDTE, "height": HOOGTE},
            record_video_dir=map_,
            record_video_size={"width": BREEDTE, "height": HOOGTE},
            accept_downloads=True,
        )
        context.add_init_script(CURSOR_JS)
        pagina = context.new_page()
        laadtijd = Laadtijd(time.time())
        pagina.goto(url)
        pagina.wait_for_selector("#btn-demodata")
        pagina.wait_for_timeout(800)
        begin = laadtijd.nu()  # alles hiervoor is een leeg scherm

        # Startscherm: demodata kiezen en laden
        print("  demodata laden", flush=True)
        pagina.mouse.move(900, 300)
        pagina.wait_for_timeout(600)
        kies(pagina, "demo-dataset-picker", DEMO)
        pagina.wait_for_timeout(500)
        klik(pagina, "#btn-demodata")
        van = laadtijd.nu() + 0.3
        pagina.wait_for_selector("text=Over dit dashboard", timeout=60000)
        laadtijd.knip(van, laadtijd.nu() - 0.2)
        pagina.wait_for_timeout(1500)

        tab(pagina, laadtijd, "Wat valt op", wacht=2000)
        scroll(pagina, 400)
        pagina.wait_for_timeout(1500)

        tab(pagina, laadtijd, "Selectiescores", wacht=800)
        scroll(pagina, 420)
        pagina.wait_for_timeout(1500)
        pagina.mouse.wheel(0, -5000)
        kies(pagina, "groepeer-op", "Geslacht")
        laadtijd.wacht(pagina)
        scroll(pagina, 420)
        pagina.wait_for_timeout(2000)

        tab(pagina, laadtijd, "Demografie", wacht=1500)
        kies(pagina, "demo-dimensie", "Vooropleiding")
        laadtijd.wacht(pagina)
        pagina.wait_for_timeout(2000)

        tab(pagina, laadtijd, "Verschiltoets", wacht=2000)
        scroll(pagina, 450)
        pagina.wait_for_timeout(1500)

        tab(pagina, laadtijd, "Correlatie", wacht=2500)

        tab(pagina, laadtijd, "Regressie", wacht=1500)
        scroll(pagina, 350)
        pagina.wait_for_timeout(1500)

        # Het PDF-rapport duurt ~30 s (kaleido); dat wachten knippen we weg.
        print("  rapport downloaden", flush=True)
        pagina.mouse.wheel(0, -5000)
        with pagina.expect_download(timeout=180000):
            klik(pagina, "#btn-download-rapport")
            van = laadtijd.nu() + 2.0  # spinner en melding even laten zien
        laadtijd.knip(van, laadtijd.nu() - 0.3)
        pagina.wait_for_timeout(2000)

        video = pagina.video.path()
        context.close()
        browser.close()
    return Path(video), begin, laadtijd.stukken


def naar_gif(video, begin, weg):
    UIT.parent.mkdir(parents=True, exist_ok=True)
    filters = f"fps={FPS},scale={GIF_BREEDTE}:-1:flags=lanczos"
    if weg:
        print(
            "  knippen:", ", ".join(f"{a - begin:.1f}-{b - begin:.1f}s" for a, b in weg)
        )
        # Met -ss voor -i begint t bij 0 op het moment begin: trek dat af.
        knip = "+".join(f"between(t,{a - begin:.2f},{b - begin:.2f})" for a, b in weg)
        filters = f"select='not({knip})',setpts=N/FRAME_RATE/TB,{filters}"
    palet = video.with_suffix(".png")
    invoer = ["ffmpeg", "-v", "error", "-y", "-ss", f"{begin:.2f}", "-i", str(video)]
    subprocess.run(
        [
            *invoer,
            "-vf",  # 64 kleuren zonder dithering: scherp voor tekst en tabellen, half zo groot
            f"{filters},palettegen=max_colors=64:stats_mode=diff",
            str(palet),
        ],
        check=True,
    )
    subprocess.run(
        [
            *invoer,
            "-i",
            str(palet),
            "-lavfi",
            f"{filters}[x];[x][1:v]paletteuse=dither=none:diff_mode=rectangle",
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
            video, begin, weg = neem_op(url, map_)
            naar_gif(video, begin, weg)
    finally:
        app.terminate()
    print(f"{UIT.relative_to(ROOT)}: {UIT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
