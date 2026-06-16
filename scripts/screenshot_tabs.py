"""Maakt screenshots van elk dashboard-tabblad met de demo-data geladen.

Vereist een draaiende app op localhost:8050 en playwright + chromium.
Output belandt in screenshots/.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

UITVOER = Path("screenshots")
UITVOER.mkdir(exist_ok=True)

TABS = [
    "Wat valt op",
    "Selectiescores",
    "Demografie",
    "Verschiltoets",
    "Correlatie",
    "Regressie",
]


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto("http://127.0.0.1:8050/", wait_until="networkidle")

        # Demo-data laden (de picker staat al op de eerste dataset).
        page.click("#btn-demodata")
        # Wachten tot de upload-overlay verdwijnt.
        page.wait_for_selector("#upload-overlay", state="hidden", timeout=30000)
        page.wait_for_timeout(2000)

        for i, label in enumerate(TABS, start=1):
            page.get_by_role("tab", name=label).click()
            # Grafieken/tabellen renderen via callbacks; even laten settelen.
            page.wait_for_timeout(4000)
            bestand = UITVOER / f"{i:02d}_{label.lower().replace(' ', '_')}.png"
            page.screenshot(path=str(bestand), full_page=True)
            print("opgeslagen:", bestand)

        browser.close()


if __name__ == "__main__":
    main()
