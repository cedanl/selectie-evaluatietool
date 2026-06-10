import base64
from pathlib import Path

import pandas as pd
import pytest

from cho_transform import transformeer_cho
from transformatie import lees_config, parse_selectiedata, transformeer_naar_lang

DEMO_DIR = Path(__file__).parent.parent / "data" / "demo"


def _uri(path: Path) -> str:
    return f"data:application/octet-stream;base64,{base64.b64encode(path.read_bytes()).decode()}"


@pytest.fixture(params=sorted(DEMO_DIR.iterdir()) if DEMO_DIR.exists() else [])
def demo_dataset(request):
    subdir = request.param
    config = lees_config(_uri(subdir / "config.xlsx"))
    scores_df = transformeer_naar_lang(
        parse_selectiedata(_uri(subdir / "selectiedata.xlsx"), config), config
    )
    cho_df = transformeer_cho(pd.read_csv(subdir / "1cho_data.csv", sep=";"))
    return {
        "config": config,
        "scores_df": scores_df,
        "cho_df": cho_df,
        "name": subdir.name,
    }
