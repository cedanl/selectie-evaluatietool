# Evaluatietool: selectie & studiesucces dashboard
#
# Toont voor een selectieopleiding de verdeling van drie groepen:
#   1. Niet gestart (niet geselecteerd of aanmelding ingetrokken)
#   2. Gestart, niet naar jaar 2 (uitval na jaar 1)
#   3. Doorgestroomd naar jaar 2
#
# Data: synthetisch (zie R/maak_selectiedata.R en R/maak_1cho_data.R)

library(shiny)
library(bslib)
library(dplyr)
library(tidyr)
library(ggplot2)
library(stringr)
library(scales)

# Laad de gekoppelde dataset (aangemaakt door R/koppel_en_classificeer.R)
if (!file.exists("data/synthetic/gekoppeld.rds")) {
  stop("Draai eerst de scripts in R/ om de synthetische data aan te maken.")
}

data <- readRDS("data/synthetic/gekoppeld.rds")

GROEP_KLEUREN <- c(
  "Niet gestart"              = "#94a3b8",
  "Gestart, niet naar jaar 2" = "#f97316",
  "Doorgestroomd naar jaar 2" = "#22c55e"
)

# --- UI ---

ui <- page_navbar(
  title = "Evaluatietool Selectie",
  theme = bs_theme(bootswatch = "flatly", base_font = font_google("Inter")),

  nav_panel(
    "Overzicht",
    layout_columns(
      col_widths = c(3, 9),

      # Sidebar filters
      card(
        card_header("Filters"),
        selectInput(
          "cohort", "Cohort (instroom jaar)",
          choices = c("Alle cohorten", sort(unique(data$selectiejaar))),
          selected = "Alle cohorten"
        ),
        selectInput(
          "geslacht", "Geslacht",
          choices = c("Alle", sort(unique(data$geslacht))),
          selected = "Alle"
        ),
        selectInput(
          "vooropleiding", "Vooropleiding",
          choices = c("Alle", sort(unique(data$hoogste_vooropleiding))),
          selected = "Alle"
        ),
        hr(),
        p(
          class = "text-muted small",
          "Synthetische voorbeelddata. Voeg echte selectie- en 1CHO-data",
          "toe via de scripts in de map R/."
        )
      ),

      # Hoofdpaneel
      layout_columns(
        col_widths = c(12, 6, 6),

        # Staafdiagram groepen per cohort
        card(
          card_header("Verdeling per groep"),
          plotOutput("plot_groepen", height = "320px")
        ),

        # Demografisch profiel
        card(
          card_header("Geslacht per groep"),
          plotOutput("plot_geslacht", height = "280px")
        ),

        card(
          card_header("Herkomst per groep"),
          plotOutput("plot_herkomst", height = "280px")
        )
      )
    )
  ),

  nav_panel(
    "Selectiescores",
    layout_columns(
      col_widths = c(3, 9),

      card(
        card_header("Filters"),
        selectInput(
          "cohort2", "Cohort (instroom jaar)",
          choices = c("Alle cohorten", sort(unique(data$selectiejaar))),
          selected = "Alle cohorten"
        ),
        p(
          class = "text-muted small",
          "Hogere selectiescores bij doorstromers",
          "wijzen op predictieve validiteit van het selectie-instrument."
        )
      ),

      layout_columns(
        col_widths = c(6, 6, 6, 6),
        card(
          card_header("Totaalscore"),
          plotOutput("plot_totaal", height = "240px")
        ),
        card(
          card_header("Motivatiebrief"),
          plotOutput("plot_motivatie", height = "240px")
        ),
        card(
          card_header("CV"),
          plotOutput("plot_cv", height = "240px")
        ),
        card(
          card_header("Interview"),
          plotOutput("plot_interview", height = "240px")
        )
      )
    )
  ),

  nav_panel(
    "Aantallen",
    card(
      card_header("Samenvatting per cohort"),
      tableOutput("tabel_aantallen")
    )
  )
)

# --- Server ---

server <- function(input, output, session) {

  gefilterd <- reactive({
    d <- data
    if (input$cohort != "Alle cohorten") {
      d <- filter(d, selectiejaar == as.integer(input$cohort))
    }
    if (input$geslacht != "Alle") {
      d <- filter(d, geslacht == input$geslacht)
    }
    if (input$vooropleiding != "Alle") {
      d <- filter(d, hoogste_vooropleiding == input$vooropleiding)
    }
    d
  })

  gefilterd2 <- reactive({
    d <- data
    if (input$cohort2 != "Alle cohorten") {
      d <- filter(d, selectiejaar == as.integer(input$cohort2))
    }
    d
  })

  output$plot_groepen <- renderPlot({
    gefilterd() |>
      count(selectiejaar, groep) |>
      mutate(selectiejaar = factor(selectiejaar)) |>
      ggplot(aes(x = selectiejaar, y = n, fill = groep)) +
      geom_col(position = "fill") +
      scale_fill_manual(values = GROEP_KLEUREN, name = NULL) +
      scale_y_continuous(labels = scales::percent_format()) +
      labs(x = "Cohort", y = "Aandeel") +
      theme_minimal(base_size = 13) +
      theme(legend.position = "bottom")
  })

  output$plot_geslacht <- renderPlot({
    gefilterd() |>
      count(groep, geslacht) |>
      group_by(groep) |>
      mutate(pct = n / sum(n)) |>
      ggplot(aes(x = groep, y = pct, fill = geslacht)) +
      geom_col(position = "fill") +
      scale_y_continuous(labels = scales::percent_format()) +
      scale_x_discrete(labels = function(x) str_wrap(x, 12)) +
      labs(x = NULL, y = "Aandeel", fill = NULL) +
      theme_minimal(base_size = 12) +
      theme(legend.position = "bottom")
  })

  output$plot_herkomst <- renderPlot({
    gefilterd() |>
      mutate(herkomst_kort = if_else(herkomst == "Nederland", "NL", "niet-NL")) |>
      count(groep, herkomst_kort) |>
      group_by(groep) |>
      mutate(pct = n / sum(n)) |>
      ggplot(aes(x = groep, y = pct, fill = herkomst_kort)) +
      geom_col(position = "fill") +
      scale_y_continuous(labels = scales::percent_format()) +
      scale_x_discrete(labels = function(x) str_wrap(x, 12)) +
      scale_fill_manual(values = c("NL" = "#3b82f6", "niet-NL" = "#a78bfa"), name = NULL) +
      labs(x = NULL, y = "Aandeel") +
      theme_minimal(base_size = 12) +
      theme(legend.position = "bottom")
  })

  score_boxplot <- function(df, var, label) {
    df |>
      filter(!is.na(groep)) |>
      ggplot(aes(x = groep, y = .data[[var]], fill = groep)) +
      geom_boxplot(alpha = 0.8, outlier.size = 0.8) +
      scale_fill_manual(values = GROEP_KLEUREN, guide = "none") +
      scale_x_discrete(labels = function(x) str_wrap(x, 10)) +
      labs(x = NULL, y = label) +
      theme_minimal(base_size = 12)
  }

  output$plot_totaal    <- renderPlot(score_boxplot(gefilterd2(), "totaalscore",    "score"))
  output$plot_motivatie <- renderPlot(score_boxplot(gefilterd2(), "motivatiescore", "score"))
  output$plot_cv        <- renderPlot(score_boxplot(gefilterd2(), "cv_score",       "score"))
  output$plot_interview <- renderPlot(score_boxplot(gefilterd2(), "interview_score","score"))

  output$tabel_aantallen <- renderTable({
    data |>
      count(selectiejaar, groep) |>
      pivot_wider(names_from = groep, values_from = n, values_fill = 0) |>
      mutate(totaal = rowSums(across(where(is.numeric)))) |>
      rename(Cohort = selectiejaar)
  }, striped = TRUE, hover = TRUE)
}

shinyApp(ui, server)
