# Genereert synthetische selectiedata voor een fictieve selectieopleiding.
#
# Echte selectiedata verschilt per opleiding in formaat en variabelen.
# Dit script simuleert een veelvoorkomend format: scorelijst met meerdere
# selectie-instrumenten en een einduitkomst.
#
# Output: data/synthetic/selectiedata_voorbeeld.csv

library(tidyverse)

set.seed(2024)

# Parameters
JAREN         <- 2021:2023
N_KANDIDATEN  <- 400   # aanmeldingen per jaar
N_GESELECTEERD <- 100  # geselecteerden per jaar (25% selectieratio)
OPLEIDING     <- "B Gezondheidswetenschappen"
INSTELLINGSCODE <- "DEMO"

# Basisverdeling demografisch profiel (representatief voor selectie-HO NL)
prob_geslacht  <- c(vrouw = 0.65, man = 0.32, anders = 0.03)
prob_vooropl   <- c(
  "vwo profiel natuur & gezondheid"     = 0.45,
  "vwo profiel natuur & techniek"       = 0.15,
  "vwo profiel cultuur & maatschappij"  = 0.20,
  "vwo profiel economie & maatschappij" = 0.10,
  "hbo-propedeuse"                      = 0.07,
  "anders"                              = 0.03
)
prob_herkomst  <- c(
  "Nederland"             = 0.72,
  "westerse achtergrond"  = 0.08,
  "Marokko"               = 0.05,
  "Turkije"               = 0.04,
  "Suriname/Antillen"     = 0.05,
  "overig niet-westers"   = 0.06
)

# Startpunt voor pgn (persoonsgebonden nummers) die ook in 1CHO voorkomen.
# Geselecteerde kandidaten krijgen een pgn dat in de 1CHO-data terugkomt.
PGN_START <- 10000

maak_cohort <- function(jaar, pgn_offset) {
  n <- N_KANDIDATEN

  geslacht   <- sample(names(prob_geslacht), n, replace = TRUE, prob = prob_geslacht)
  vooropl    <- sample(names(prob_vooropl),  n, replace = TRUE, prob = prob_vooropl)
  herkomst   <- sample(names(prob_herkomst), n, replace = TRUE, prob = prob_herkomst)
  leeftijd   <- round(rnorm(n, mean = 19.2, sd = 1.4)) |> pmax(17) |> pmin(26)

  # Gemiddeld VO-cijfer: correleert licht met vooropleiding
  gem_vo_base <- case_match(
    vooropl,
    "vwo profiel natuur & gezondheid"     ~ 7.2,
    "vwo profiel natuur & techniek"       ~ 7.1,
    "vwo profiel cultuur & maatschappij"  ~ 6.9,
    "vwo profiel economie & maatschappij" ~ 6.8,
    "hbo-propedeuse"                      ~ 6.5,
    .default                              ~ 6.4
  )
  gem_vo <- round(rnorm(n, mean = gem_vo_base, sd = 0.6) |> pmax(4) |> pmin(10), 1)

  # Selectiescores: motivatiebrief, cv, interview (schaal 1-10)
  # Scores correleren licht met elkaar (zelfde student, zelfde kwaliteit)
  latente_kwaliteit <- rnorm(n, 0, 1)
  motivatiescore <- round(5 + 1.2 * latente_kwaliteit + rnorm(n, 0, 0.8), 1) |>
    pmax(1) |> pmin(10)
  cv_score <- round(5 + 1.0 * latente_kwaliteit + rnorm(n, 0, 0.9), 1) |>
    pmax(1) |> pmin(10)
  interview_score <- round(5 + 1.3 * latente_kwaliteit + rnorm(n, 0, 0.7), 1) |>
    pmax(1) |> pmin(10)

  totaalscore <- round(
    0.30 * motivatiescore + 0.20 * cv_score + 0.50 * interview_score, 2
  )

  # Rangorde bepalen op basis van totaalscore
  rangorde <- rank(-totaalscore, ties.method = "random") |> as.integer()

  # Selectie-uitkomst: top N_GESELECTEERD is geselecteerd, volgende 20 reserve
  selectie_uitkomst <- case_when(
    rangorde <= N_GESELECTEERD                         ~ "geselecteerd",
    rangorde <= N_GESELECTEERD + 20                    ~ "reserve",
    TRUE                                               ~ "niet geselecteerd"
  )

  # Persoonsgebonden nummer: alleen geselecteerden/reserve krijgen een pgn
  # dat in de 1CHO-data kan voorkomen. Niet-geselecteerden staan nooit in 1CHO.
  kandidaat_id <- pgn_offset + seq_len(n)
  pgn <- ifelse(
    selectie_uitkomst %in% c("geselecteerd", "reserve"),
    kandidaat_id,
    NA_integer_
  )

  tibble(
    kandidaat_id      = kandidaat_id,
    persoonsgebonden_nummer = pgn,
    selectiejaar      = jaar,
    opleiding         = OPLEIDING,
    instellingscode   = INSTELLINGSCODE,
    geslacht          = geslacht,
    leeftijd          = leeftijd,
    herkomst          = herkomst,
    hoogste_vooropleiding = vooropl,
    gem_eindcijfer_vo = gem_vo,
    motivatiescore    = motivatiescore,
    cv_score          = cv_score,
    interview_score   = interview_score,
    totaalscore       = totaalscore,
    rangorde          = rangorde,
    selectie_uitkomst = selectie_uitkomst
  )
}

# Genereer data voor alle jaren
selectiedata <- map2(
  JAREN,
  seq(PGN_START, by = N_KANDIDATEN, length.out = length(JAREN)),
  maak_cohort
) |> list_rbind()

write_csv2(selectiedata, "data/synthetic/selectiedata_voorbeeld.csv")

cat(sprintf(
  "Selectiedata aangemaakt: %d kandidaten over %d cohorten\n",
  nrow(selectiedata), length(JAREN)
))
cat(sprintf(
  "Verdeling uitkomsten:\n%s\n",
  selectiedata |>
    count(selectie_uitkomst) |>
    mutate(pct = round(n / sum(n) * 100, 1)) |>
    format() |>
    paste(collapse = "\n")
))
