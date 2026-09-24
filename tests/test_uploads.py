"""
Tests voor de upload-callbacks: validatie en laden moeten dezelfde config
gebruiken (pitch #36), ook als er zowel een configbestand als een
wizardconfig is.
"""

import base64
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import uploads
from transformatie import lees_config

DEMO = Path(__file__).parent.parent / "data" / "demo" / "demo_radboud_2026"


def _uri(pad: Path) -> str:
    return "data:x;base64," + base64.b64encode(pad.read_bytes()).decode()


class _FakeApp:
    def __init__(self):
        self.functies = {}

    def callback(self, *args, **kwargs):
        def registreer(fn):
            self.functies[fn.__name__] = fn
            return fn

        return registreer

    def clientside_callback(self, *args, **kwargs):
        pass


@pytest.fixture
def callbacks():
    app = _FakeApp()
    uploads.registreer_callbacks(app)
    return app.functies


def _server_upload(pad: Path) -> dict:
    """Zet een bestand klaar zoals de uploadroute dat doet en geef de
    store-waarde van 'cho-bestand' terug."""
    import shutil
    import uuid

    import bestandsopslag

    bestandsopslag.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    shutil.copy(pad, bestandsopslag.UPLOAD_DIR / f"{token}{pad.suffix}")
    return {"token": token, "filename": pad.name, "grootte": pad.stat().st_size}


def _met_trigger(trigger):
    class Ctx:
        triggered_id = trigger

    return patch.object(uploads, "ctx", Ctx)


class TestActieveConfigBron:
    @pytest.mark.parametrize(
        "trigger, bron, cfg, wiz, verwacht",
        [
            ("upload-config", "wizard", "c", "w", "upload"),
            ("wiz-config-store", "upload", "c", "w", "wizard"),
            ("upload-1cho", "wizard", "c", "w", "wizard"),
            ("upload-1cho", "upload", "c", "w", "upload"),
            ("upload-1cho", None, "c", None, "upload"),
            ("upload-1cho", None, None, "w", "wizard"),
            ("upload-1cho", "upload", None, "w", "wizard"),
            ("upload-1cho", None, None, None, None),
        ],
    )
    def test_laatst_aangeleverde_wint(self, trigger, bron, cfg, wiz, verwacht):
        assert uploads.actieve_config_bron(trigger, bron, cfg, wiz) == verwacht


def test_wizard_na_upload_wordt_ook_geladen(callbacks):
    """Scenario uit de pitch: eerst een (andere) config uploaden, daarna de
    wizard gebruiken. Validatie en laden moeten allebei de wizard volgen."""
    sel, cfg = _uri(DEMO / "selectiedata.xlsx"), _uri(DEMO / "config.xlsx")
    cho = _server_upload(DEMO / "1cho_data.csv")
    wiz = lees_config(cfg)
    wiz["opleiding"] = "Wizardopleiding"
    wiz_json = json.dumps(wiz)

    with _met_trigger("wiz-config-store"):
        uit = callbacks["valideer_uploads"](
            sel, cfg, cho, wiz_json, None, "s.xlsx", "c.xlsx", "upload"
        )
    bron = uit[-1]
    assert bron == "wizard"
    assert "gegenereerd met de wizard" in str(uit[2])

    with _met_trigger("btn-open-dashboard"):
        data, _ = callbacks["laad_dashboard"](
            1, None, None, sel, cfg, cho, None, wiz_json, None, bron
        )
    assert "Wizardopleiding" in data
