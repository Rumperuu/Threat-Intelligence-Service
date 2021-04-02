#
# Secure Digitalisation Monte Carlo Simulation Script
#
# This script runs a Monto Carlo simulation using breach likelihood and cost
# figures derived from the Cyber Security Breaches Survey 2020 (CSBS).
#	This script is an unfinished prototype, and has since been superseded by
# `montecarlo.py`.
#
# Acknowledgements: Dr Dan Prince & Dr Chris Sherlock
#

masses = c(0.54, 0.1058, 0.1012, 0.0966, 0.069, 0.0368, 0.0414)
boundaries = c(1, 2, 8, 18, 80, 400, 8000)

Fs = cumsum(masses)
plot(log(boundaries), log(1 - Fs))

xs = log(boundaries)
ys = log(1 - Fs)
fit = lm(ys ~ xs)
summary(fit)

alogb = fit$coeff[1]
a = -fit$coeff[2]
b = exp(alogb/a)
print(a)
print(b)

n = 10000

us = runif(n)
xs = b / (1 - us)^(1 / a)
print()
p0 = mean(xs < boundaries[1])
p1 = mean(xs < boundaries[2]) - p0
p2 = mean(xs < boundaries[3]) - p0 - p1
p3 = mean(xs < boundaries[4]) - p0 - p1 - p2
p4 = mean(xs < boundaries[5]) - p0 - p1 - p2 - p3
p5 = mean(xs < boundaries[6]) - p0 - p1 - p2 - p3 - p4
ps = c(p0, p1, p2, p3, p4, p5, 1 - (p0 + p1 + p2 + p3 + p4 + p5))

print(ps)
print(masses)

nattacks = floor(xs)
hist(log10(nattacks),
     main = "Histogram of Number of Attacks/Breaches Over 12 Months",
     xlab = expression("Number of Attacks (log"[10]*")"),
     ylab = "Frequency",
     breaks = 0:12)

# Plots the distribution for the average cost of breach(es) over 12 months

mean = 3230
median = 274

logstd = sqrt(2 * (log(mean) - if (median == 0) 0 else log(median)))
std = exp(1)^logstd

curve(dlnorm(x, log(mean), log(std)), from=1, to=5000,
      main = "Average annual breach cost distribution",
      xlab = 'Cost (£)',
      ylab = 'Density',
      lwd = 2)

# Runs the MonteCarlo simulation

simulateCosts <- function(n) {
  return(if (n >= 1) sum(rlnorm(n, loc, shape)) else 0)
}

n = 10000

loc <- log(mean^2 / sqrt(std^2 + mean^2))
shape <- sqrt(log(1 + (std^2 / mean^2)))

numAttacks <- sample(log10(nattacks), n)
results <- sapply(numAttacks, simulateCosts)

hist(results,
     main = "Histogram of Total Costs Over 12 Months (Monte Carlo sim)",
     xlab = "Total cost (£)")

d <- density(results)
plot(d,
     main="Density of Total Costs Over 12 Months (Monte Carlo sim)", 
     xlab=expression("Total Cost (£)"),
     ylab="Density")

# Get loss exceedance
# TODO: needs to be prettier, but `evaluate::loss_exceedance_curve()` is broken

maxValue = 2500
numOver <- length(results[results > maxValue])
risk = numOver/n

plot(d,
     main="Loss Exceedance (Monte Carlo sim)", 
     xlab=expression("Total Cost (£)"),
     ylab="Density")

abline(v = maxValue, col="red", lwd=3, lty=2)
text(3000, 4e-04, labels=paste(floor(risk*100), "% chance of ≥£", maxValue, " losses"), adj=c(0, 0.5))
