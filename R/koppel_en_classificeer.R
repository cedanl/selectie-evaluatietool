# Koppelt selectiedata aan 1CHO-data en classificeert studenten in drie groepen:
#
#   Groep 1 - Niet gestart:
#     Student is niet geselecteerd OF is wel geselecteerd maar heeft geen jaar-1
#     rij in 1CHO (aanmelding ingetrokken, studie niet gestart).
#
#   Groep 2 - Gestart, niet naar jaar 2:
#     Student heeft een jaar-1 rij in 1CHO maar GEEN jaar-2 rij voor dezelfde
#     opleiding+instelling. Geen tweede jaar = uitval of switch na jaar 1.
#
#   Groep 3 - Doorgestroomd naar jaar 2:
#     Student heeft zowel een jaar-1 als een jaar-2 rij in 1CHO.
#
# Aanname: de koppeling loopt via persoonsgebonden_nummer.
# In de praktijk moet dit via een beveiligd koppelproces verlopen.

library(tidyverse)

selectiedata <- read_csv2("data/synthetic/selectiedata_voorbeeld.csv")
cho_data     <- read_csv2("data/synthetic/EV_DEMO_selectieopleiding.csv")

# Bepaal voor elke pgn in 1CHO of er een jaar-2 rij is
jaar2_pgns <- cho_data |>
  filter(verblijfsjaar_hoger_onderwijs == 2) |>
  pull(persoonsgebonden_nummer) |>
  unique()

jaar1_pgns <- cho_data |>
  filter(verblijfsjaar_hoger_onderwijs == 1) |>
  pull(persoonsgebonden_nummer) |>
  unique()

# Voeg 1CHO jaar-1 info toe aan selectiedata en classificeer
gekoppeld <- selectiedata |>
  left_join(
    cho_data |>
      filter(verblijfsjaar_hoger_onderwijs == 1) |>
      select(
        persoonsgebonden_nummer,
        inschrijvingsjaar,
        verblijfsjaar_hoger_onderwijs,
        indicatie_eerstejaars_continu_type_ho_binnen_ho
      ),
    by = "persoonsgebonden_nummer"
  ) |>
  mutate(
    heeft_jaar1 = persoonsgebonden_nummer %in% jaar1_pgns,
    heeft_jaar2 = persoonsgebonden_nummer %in% jaar2_pgns,
    groep = case_when(
      !heeft_jaar1                    ~ "Niet gestart",
      heeft_jaar1 & !heeft_jaar2      ~ "Gestart, niet naar jaar 2",
      heeft_jaar1 &  heeft_jaar2      ~ "Doorgestroomd naar jaar 2",
      TRUE                            ~ NA_character_
    ),
    groep = factor(groep, levels = c(
      "Niet gestart",
      "Gestart, niet naar jaar 2",
      "Doorgestroomd naar jaar 2"
    ))
  )

saveRDS(gekoppeld, "data/synthetic/gekoppeld.rds")

cat("Groepsindeling per cohort:\n")
gekoppeld |>
  count(selectiejaar, groep) |>
  pivot_wider(names_from = groep, values_from = n, values_fill = 0) |>
  print()
