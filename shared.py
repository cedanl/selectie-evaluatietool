GROEP_VOLGORDE = [
    "Niet gestart",
    "Gestart, niet naar jaar 2",
    "Doorgestroomd naar jaar 2",
]
GROEP_KLEUREN = {
    "Niet gestart": "#94a3b8",
    "Gestart, niet naar jaar 2": "#f97316",
    "Doorgestroomd naar jaar 2": "#22c55e",
}

CHART_BASE = dict(plot_bgcolor="white", paper_bgcolor="white")


def shorten_item(name: str) -> str:
    for suffix in [" schaalscore", " Schaalscore", " (1-2-3)"]:
        name = name.replace(suffix, "")
    return name


def sig_sym(p: float) -> str:
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"


def fmt_p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"
