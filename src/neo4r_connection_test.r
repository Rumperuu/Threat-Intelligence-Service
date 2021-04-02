#
# Secure Digitalisation Neo4j Connection Script
#
# This script is intended to establish a connection to a Neo4j graph database
# and submit commands.
#	This script is an unfinished prototype, and has since been superseded by
# `graph.py`.
#

install.packages('tidyverse')
library(tidyverse)
install.packages('purrr')
library(purrr)
install.packages('devtools')
library(devtools)
install_github("davidlrosenblum/neo4r@4.x")
library(neo4r)

RUNS <- 1000
DECISION.STEPS <- 12

get_likelihood <- function() {
  res <- 'MATCH (i:Incident) WHERE EXISTS (i.probability) AND NOT (i)-[:FOR_SIZE]-() AND NOT (i)-[:FOR_INDUSTRY]-() AND NOT (i)-[:FOR_AREA]-() RETURN i.probability AS probability;' %>%
    call_neo4j(con, type = 'row')
  
  res$probability / 100
}

# Currently only does direct costs
get_costs <- function() {
 res <- 'MATCH (i:Incident) WHERE EXISTS (i.direct_costs) AND NOT (i)-[:FOR_SIZE]-() AND NOT (i)-[:FOR_INDUSTRY]-() AND NOT (i)-[:FOR_AREA]-() RETURN i.direct_costs[0] AS cost;' %>%
    call_neo4j(con, type = 'row')
 
 res$cost
}

calculate_cost <- function(alpha) {
  l <- get_likelihood()
  happen <- runif(1, 0, 1)
  if (happen >= l) {
    cost <- as.numeric(get_costs())
    s <- log(sd(580:630))
    m <- log(get_costs())
    #location <- log(m^2 / sqrt(s^2 + m^2))
    #shape <- sqrt(log(1 + (s^2 / m^2)))
    rlnorm(1, )
  } else {
    0
  }
}

con <- neo4j_api$new(
  url="http://localhost:7474", 
  db="neo4j", 
  user="neo4j", 
  password="password"
)

simulations <- rerun(RUNS, replicate(DECISION.STEPS, runif(1) %>% calculate_cost())) %>%
  set_names(paste0("sim", 1:RUNS)) %>%
  map(~ accumulate(., ~ .x * .y)) %>%
  map_dfr(~ tibble(value = .x, step = 1:DECISION.STEPS), .id = "simulation")

simulations %>%
  ggplot(aes(x = step, y = value)) +
  geom_line(aes(color = simulation)) +
  theme(legend.position = "none") +
  ggtitle("Simulations of costs from breaches")

summary_values <- simulations %>%
  group_by(step) %>%
  summarise(mean_return = mean(value), max_return = max(value), min_return = min(value)) %>%
  gather("series", "value", -step)

summary_values %>%
  ggplot(aes(x = step, y = value)) +
  geom_line(aes(color = series)) +
  ggtitle("Mean values from simulations")
