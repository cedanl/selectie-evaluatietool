# Genereert synthetische 1CHO-data (EV-stijl, enriched formaat) voor
# geselecteerde studenten van de fictieve selectieopleiding.
#
# De structuur volgt het output-formaat van 1cijferho (EV_*_enriched.csv):
# - Elke inschrijving = 1 rij
# - Studenten die doorgaan naar jaar 2 hebben twee rijen (jaar N en jaar N+1)
# - Studenten die stoppen na jaar 1 hebben alleen een jaar-1 rij
# - Niet-geselecteerden komen nooit voor in 1CHO
#
# Koppelsleutel: persoonsgebonden_nummer (selectiedata) <-> persoonsgebonden_nummer (1CHO)
#
# Output: data/synthetic/EV_DEMO_selectieopleiding.csv

library(tidyverse)

set.seed(2024)

# Inlezen selectiedata (nodig voor de geselecteerde studenten)
selectiedata <- read_csv2("data/synthetic/selectiedata_voorbeeld.csv")

# Kansen op doorstroom naar jaar 2 (realistisch voor selectie-WO in NL: ~75%)
KANS_JAAR2 <- 0.74

# Studenten die daadwerkelijk zijn gaan studeren:
# - Geselecteerden: vrijwel allemaal (95%)
# - Reserve: deel gaat alsnog (40%, vanwege uitval bij geselecteerden)
ingeschrevenen <- selectiedata |>
  filter(selectie_uitkomst %in% c("geselecteerd", "reserve")) |>
  mutate(
    gaat_studeren = case_when(
      selectie_uitkomst == "geselecteerd" ~ runif(n()) < 0.95,
      selectie_uitkomst == "reserve"      ~ runif(n()) < 0.38,
      TRUE                                ~ FALSE
    )
  ) |>
  filter(gaat_studeren) |>
  # Kans op doorstroom correleert licht met interview_score (hogere selectiescore = iets meer kans)
  mutate(
    doorstroom_kans = plogis(-0.3 + 0.12 * interview_score),
    doorstroomt_naar_jaar2 = runif(n()) < doorstroom_kans
  )

# Hulpfunctie: maak een 1CHO rij voor een student en een bepaald inschrijvingsjaar
maak_inschrijving <- function(student, inschrijvingsjaar, verblijfsjaar) {
  is_eerstejaars <- verblijfsjaar == 1

  tibble(
    persoonsgebonden_nummer           = student$persoonsgebonden_nummer,
    inschrijvingsjaar                 = inschrijvingsjaar,
    instellingscode                   = "DEMO",
    actuele_instelling_naam           = "DEMO Hogeschool",
    opleidingscode_naam_opleiding     = student$opleiding,
    opleidingsvorm                    = "voltijd",
    opleidingsfase                    = "bachelor",
    eerste_jaar_aan_deze_instelling   = student$selectiejaar,
    eerste_jaar_in_het_hoger_onderwijs = if_else(
      # Simuleer: 10% heeft al eerder HO gevolgd (hbo-propedeuse)
      student$hoogste_vooropleiding == "hbo-propedeuse",
      student$selectiejaar - sample(1:3, 1),
      student$selectiejaar
    ),
    eerste_jaar_aan_deze_opleiding_instelling = student$selectiejaar,
    verblijfsjaar_hoger_onderwijs     = verblijfsjaar,
    geslacht                          = student$geslacht,
    leeftijd_per_peildatum_1_oktober  = student$leeftijd + (verblijfsjaar - 1),
    herkomstland_naam                 = student$herkomst,
    hoogste_vooropleiding_omschrijving_vooropleiding = student$hoogste_vooropleiding,
    diplomajaar_hoogste_vooropleiding = student$selectiejaar - sample(0:2, 1),
    gem_eindcijfer_vo_van_de_hoogste_vooropl_voor_het_ho = student$gem_eindcijfer_vo,
    indicatie_eerstejaars_continu_type_ho_binnen_ho = if_else(
      is_eerstejaars,
      "ingeschrevene is eerstejaars type hoger onderwijs binnen hoger onderwijs",
      "ingeschrevene is hogerejaars type hoger onderwijs binnen hoger onderwijs"
    ),
    soort_inschrijving_continu_hoger_onderwijs = if_else(
      is_eerstejaars,
      "hoofdinschrijving binnen het domein hoger onderwijs",
      "hoofdinschrijving binnen het domein hoger onderwijs"
    ),
    datum_inschrijving = sprintf("%d0901", inschrijvingsjaar),
    datum_uitschrijving = sprintf("%d0831", inschrijvingsjaar + 1)
  )
}

# Genereer de 1CHO rijen
cho_rijen <- ingeschrevenen |>
  pmap(function(...) {
    student <- list(...)
    jaar1_rij <- maak_inschrijving(student, student$selectiejaar, verblijfsjaar = 1)
    if (student$doorstroomt_naar_jaar2) {
      jaar2_rij <- maak_inschrijving(student, student$selectiejaar + 1, verblijfsjaar = 2)
      bind_rows(jaar1_rij, jaar2_rij)
    } else {
      jaar1_rij
    }
  }) |>
  list_rbind()

write_csv2(cho_rijen, "data/synthetic/EV_DEMO_selectieopleiding.csv")

n_jaar1 <- cho_rijen |> filter(verblijfsjaar_hoger_onderwijs == 1) |> nrow()
n_jaar2 <- cho_rijen |> filter(verblijfsjaar_hoger_onderwijs == 2) |> nrow()

cat(sprintf(
  "1CHO-data aangemaakt: %d rijen totaal\n  jaar 1: %d studenten\n  jaar 2: %d studenten\n  uitval na jaar 1: %d studenten\n",
  nrow(cho_rijen), n_jaar1, n_jaar2, n_jaar1 - n_jaar2
))
