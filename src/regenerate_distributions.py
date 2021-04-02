"""
    Distributions (Re)generation Script

    This script generates likelihood and cost distributions based on threat
    intelligence data stored in a connected Neo4j graph database. It attempts to
    do so for every possible permutation of (size, industry) values.

    These are then consumed by `montecarlo.py`, which runs a Monte Carlo
    simulation based on these figures.

    Acknowledgements: Dr Dan Prince & Dr Chris Sherlock
"""

import os
import sys
import argparse
import warnings
import logging as log

from typing import Tuple

import itertools
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from matplotlib import pyplot as plt
from scipy.stats import lognorm

from graph import GraphInterface as gi

# Used for logging, equivalent to `logging.WARNING` + 1.
SUCCESS = 31

# The arbitrary maximum number of incidents that an organisation can experience
# in a year.
MAX_ANNUAL_INCIDENTS = 8000

# Quantifies the quantitative boundaries for human-readable incident frequencies,
# which many sources (e.g., the CSBS 2020) use to present their results.
#
# 'None' = 0
# 'Annually' = 1
# 'Less than monthly' = 2–7
# 'Monthly' = 8–17
# 'Weekly' = 18–79
# 'Daily' = 80–399
# 'More than daily' = 400–8000
BOUNDARIES = {
    "None": 0,
    "Once per year": 1,
    "Less than once a month": 2,
    "Once a month": 8,
    "Once a week": 18,
    "Once a day": 80,
    "Several times a day": 400,
    "MAX": MAX_ANNUAL_INCIDENTS,
}

OUTPUT_DIR = None
IMAGES = None

# pylint: disable=invalid-name,anomalous-backslash-in-string
def _generate_new_incident_frequency_distribution(pairing: Tuple = (None, None)) -> int:
    """
    Generates a new incident frequency distribution.

    Notes
    -----

    (Re)generates the incident frequency distribution for a
    :math:`\left(\text{size}, \text{industry}\right)` pairing from the data in
    a Neo4j graph database.

    Currently this only produces log-normal distributions. Additional types of
    distribution can be implemented by overloading this method (by importing the
    `multipledispatch` package) and returning the values required for defining
    that distribution (e.g., :math:`\mu` and :math:`\sigma` instead of :math:`a`
    and :math:`b`).
    """
    # pylint: enable=anomalous-backslash-in-string

    log.info("Generating new incident frequency distribution for '%s'...", str(pairing))

    # Attempts to get the incident probabilities for the pairing from the graph
    # database
    incident_frequency_probabilities = gi.get_incident_frequency_probabilities(
        list(BOUNDARIES.values())[:-1], pairing
    )
    if incident_frequency_probabilities is None:
        log.info(
            "No incident frequency distribution generated for '%s'.",
            str(pairing),
        )
        return 0

    log.debug(
        "Returned values are: incident frequency probabilities = %s",
        str(incident_frequency_probabilities),
    )

    # If values are found, generate a distribution
    Fs = np.cumsum(incident_frequency_probabilities)

    xs = np.log(list(BOUNDARIES.values())[1:])
    ys = np.log(1 - Fs)
    data = pd.DataFrame(xs, ys)

    # pylint: disable=line-too-long
    # See <https://www.statsmodels.org/stable/_modules/statsmodels/stats/stattools.html#omni_normtest> for explanation
    # pylint: enable=line-too-long
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = smf.ols(formula="ys ~ xs", data=data).fit()
        log.debug(fit.summary())

    # Get the parameters for the generated distribution and store them in the
    # graph database.
    alogb = fit.params[0]
    a = -fit.params[1]
    b = np.exp(alogb / a)

    gi.create_incident_frequency_distribution_node(pairing, a, b)

    log.log(
        SUCCESS,
        "New incident frequency distribution successfully generated for '%s'.",
        str(pairing),
    )
    return 1


# pylint: enable=invalid-name

# pylint: disable=anomalous-backslash-in-string
def _generate_new_incident_costs_distribution(pairing: Tuple = (None, None)) -> int:
    """
    (Re)generates the incident cost distribution for a
    :math:`\left(\text{size}, \text{industry}\right)` pairing from the data in
    a Neo4j graph database.

    Currently this only produces log-normal distributions. Additional types of
    distribution can be implemented by overloading this method (by importing the
    `multipledispatch` package) and returning the values required for defining
    that distribution (e.g., :math:`\mu` and :math:`\sigma` instead of :math:`a`
    and :math:`b`).
    """
    # pylint: enable=anomalous-backslash-in-string

    # Plots the distribution for the average cost of incident(s) over 12 months
    log.info("Generating new incident cost distribution for '%s'...", str(pairing))

    incident_mean_cost, incident_median_cost = gi.get_incident_cost_averages(pairing)
    if incident_mean_cost is None or incident_median_cost is None:
        log.info(
            "No incident costs distribution generated for '%s'.",
            str(pairing),
        )
        return 0

    log.debug(
        "Returned values are: mean = %s, median = %s",
        str(incident_mean_cost),
        str(incident_median_cost),
    )

    log_stddev = np.sqrt(
        2
        * (
            np.log(incident_mean_cost) - 0
            if (incident_median_cost == 0)
            else np.log(incident_median_cost)
        )
    )
    stddev = np.exp(1) ** log_stddev

    _label_plot(
        "Average annual incident-with-outcome cost distribution", "Cost (£)", "Density"
    )
    plt.plot(
        [
            lognorm.pdf(
                np.log(i),
                np.log(incident_mean_cost),
                np.log(incident_median_cost) if incident_median_cost > 0 else 0,
            )
            for i in range(1, 2500)
        ]
    )
    _save_plot("3 - cost dist")

    gi.create_incident_costs_distribution_node(pairing, incident_mean_cost, stddev)

    log.log(
        SUCCESS,
        "New incident costs distribution successfully generated for '%s'.",
        str(pairing),
    )
    return 1


def _generate_new_distributions(pairing: Tuple = (None, None)) -> Tuple:
    """(Re)generates the cost and likelihood distributions."""

    gi.__init__()

    log.info("Existing distributions deleted: %s", bool(gi.delete_distributions()))

    successful_incidents_dists = 0
    successful_costs_dists = 0

    # If either size or industry is unspecified, gets all possible values.
    sizes = gi.get_sizes() if pairing[0] is None else [pairing[0]]
    industries = gi.get_industries() if pairing[1] is None else [pairing[1]]

    # Attempts to generate new distributions for every combination of size and
    # industry values.
    for pair in list(itertools.product(sizes, industries)):
        successful_incidents_dists += _generate_new_incident_frequency_distribution(
            pair
        )
        successful_costs_dists += _generate_new_incident_costs_distribution(pair)

    return successful_incidents_dists, successful_costs_dists


def main():
    """Called when the script is run from the command-line."""
    # pylint: disable=global-statement
    global OUTPUT_DIR, IMAGES
    # pylint: enable=global-statement

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-s",
        "--size",
        help="Specify the org. size (default: None)",
        choices=["micro", "small", "medium", "large"],
        type=str,
        default=None,
    )
    parser.add_argument(
        "-i",
        "--industry",
        help="Specify the org. industry SIC code (top-level only, e.g. ‘C’ for "
        "Manufacturing’) (default: None)",
        choices=list(map(chr, range(65, 86))),
        type=chr,
        default=None,
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Specify the output directory (default: ./output/)",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "output/"),
        metavar="DIRECTORY",
    )
    parser.add_argument(
        "-p",
        "--images",
        help="Output images at each step of the script (default: false, just "
        "output the final LEC image)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Verbose console output (default: false)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-d",
        "--debug",
        help="Show debug console output (default: false)",
        action="store_true",
        default=False,
    )

    args = parser.parse_args()

    OUTPUT_DIR = args.output
    IMAGES = args.images

    size = args.size
    industry = args.industry

    if args.debug:
        log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
        log.info("Debug output.")
    elif args.verbose:
        log.basicConfig(format="%(levelname)s: %(message)s", level=log.INFO)
        log.info("Verbose output.")
    else:
        log.basicConfig(format="%(levelname)s: %(message)s")

    if not os.path.isdir(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    incidents_dists, costs_dists = _generate_new_distributions((size, industry))

    log.log(
        SUCCESS,
        "Successfully generated %s incident frequency distributions and %s "
        "incident costs distributions!",
        str(incidents_dists),
        str(costs_dists),
    )

    sys.exit(0)


def _label_plot(title="Untitled Plot", xlabel="x axis", ylabel="y axis") -> None:
    """Apply titles and axis labels to a plot."""

    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)


def _save_plot(filename="untitled") -> None:
    """Save a plot and clear the figure."""

    if IMAGES:
        plt.savefig(OUTPUT_DIR + filename + ".png")
    plt.clf()


if __name__ == "__main__":
    main()
