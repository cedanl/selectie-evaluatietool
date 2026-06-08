GROEP_NIET_GESTART = "Niet gestart"
GROEP_GESTART_GEEN_VERVOLG = "Gestart, niet naar jaar 2"
GROEP_DOORGESTROOMD = "Doorgestroomd naar jaar 2"
# Voor eenjarige opleidingen (bijv. masters) is er geen jaar 2; succes is dan
# het halen van het diploma in het cohortjaar.
GROEP_DIPLOMA = "Gestart, diploma gehaald"

GROEP_VOLGORDE = [
    GROEP_NIET_GESTART,
    GROEP_GESTART_GEEN_VERVOLG,
    GROEP_DOORGESTROOMD,
    GROEP_DIPLOMA,
]

# Studenten die daadwerkelijk zijn begonnen (alles behalve 'Niet gestart').
GROEP_INGESCHREVEN = [
    GROEP_GESTART_GEEN_VERVOLG,
    GROEP_DOORGESTROOMD,
    GROEP_DIPLOMA,
]

# Positieve uitkomsten: doorstroom naar jaar 2 of diploma in het eerste jaar.
GROEP_SUCCES = [GROEP_DOORGESTROOMD, GROEP_DIPLOMA]

GROEP_KLEUREN = {
    GROEP_NIET_GESTART: "#94a3b8",
    GROEP_GESTART_GEEN_VERVOLG: "#f97316",
    GROEP_DOORGESTROOMD: "#22c55e",
    GROEP_DIPLOMA: "#3b82f6",
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
