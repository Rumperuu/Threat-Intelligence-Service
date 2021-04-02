"""
    Monte Carlo Simulation Script

    This script runs a Monte Carlo simulation for an organisation of a given
    size and industry, utilising the most relevant available available.

    Acknowledgements: Dr Dan Prince & Dr Chris Sherlock
"""

import os
import sys
import argparse
import pickle
import logging as log

from typing import Tuple, Dict, Union

import random
import math
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from graph import GraphInterface as gi

# Used for logging, equivalent to `logging.INFO`.
SUCCESS = 20

# If not specified, the default number of Monte Carlo simulation runs to perform.
DEFAULT_RUNS = 5000

# The arbitrary maximum number of incidents that an organisation can experience
# in a year.
MAX_ANNUAL_INCIDENTS = 8000

# The maximum value of a company; any yearly losses over result in a bankruptcy
COMPANY_VALUE = 100000

# A smaller value increases the curviness of the loss exeedence curve.
# Less than 30 starts to get a bit steppy though.
LEC_PRECISION = math.floor(COMPANY_VALUE / 30)

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

N = None
OUTPUT_DIR = None
IMAGES = None
FORCE = None


def _calculate_num_of_incidents(incidents_dist: Dict[float, float]) -> float:
    """Calculate how many incidents have occurred in a given year."""

    log.debug("Incident distribution: %s", str(incidents_dist))

    num_of_incidents = incidents_dist["b"] / (1 - np.random.uniform()) ** (
        1 / incidents_dist["a"]
    )
    log.debug("Number of incidents (as `int`): %s", str(int(num_of_incidents)))

    return (
        int(num_of_incidents)
        if num_of_incidents <= MAX_ANNUAL_INCIDENTS
        else MAX_ANNUAL_INCIDENTS
    )


def _calculate_sum_cost_of_incidents(
    num_of_incidents: int, costs_dist: Dict[float, float], idx: int = None
) -> float:
    """For a list of incident numbers, calculate how much each breach cost and
    return the sum."""

    log.debug("Costs distribution: %s", str(costs_dist))

    if (N < 1000) or (N >= 1000 and idx % math.floor(N / 100) == 0):
        log.info(
            "Running Monte Carlo simulation... (%s/%s iterations)", str(idx), str(N)
        )

    if num_of_incidents == 0:
        return 0

    loc = np.log(
        costs_dist["mean"] ** 2
        / np.sqrt(costs_dist["stddev"] ** 2 + costs_dist["mean"] ** 2)
    )
    shape = np.sqrt(np.log(1 + (costs_dist["stddev"] ** 2 / costs_dist["mean"] ** 2)))

    costs = [random.lognormvariate(loc, shape) for r in range(num_of_incidents)]

    return sum(costs)


# pylint: disable=invalid-name
def _get_most_relevant_incident_frequency_distribution(
    pairing: Tuple = ("All", "All")
) -> Union[Dict[float, float], None]:
    """Gets the distribution for incident frequency from the data in the Neo4j
    graph database."""

    log.info(
        "Finding most relevant incident frequency distribution for %s...", str(pairing)
    )
    return gi.get_incident_frequency_distribution(pairing)


# pylint: enable=invalid-name


def _get_most_relevant_incident_costs_distribution(
    pairing: Tuple = ("All", "All")
) -> Union[Dict[float, float], None]:
    """Gets the distribution for incident costs from the data in the Neo4j
    graph database."""

    log.info(
        "Finding most relevant incident costs distribution for %s...", str(pairing)
    )
    return gi.get_incident_costs_distribution(pairing)


def _get_most_relevant_distributions(
    pairing: Tuple = ("All", "All")
) -> Dict[Union[Dict[float, float], None], Union[Dict[float, float], None]]:
    """Generate (or retrieve) a population of annual incident quantities and a
    distribution of incident-with-outcome cost values."""

    # -- caching --
    # Retrieves previously-calculated values if possible
    if not FORCE and OUTPUT_DIR is not None:
        try:
            filename = "{}-{}.pickle".format(pairing[0], pairing[1])
            dists = pickle.load(open(OUTPUT_DIR + filename, "rb"))

            log.info("Previously-calculated distributions found")
            return dists["incidents"], dists["costs"]
        except (OSError, IOError):
            log.info("Previously-calculated distributions not found")

    # Otherwise, generates fresh ones
    gi.__init__()

    incidents_dist = _get_most_relevant_incident_frequency_distribution(pairing)
    costs_dist = _get_most_relevant_incident_costs_distribution(pairing)

    log.debug(
        "Returned values are: incidents_dist = %s, costs_dist = %s",
        str(incidents_dist),
        str(costs_dist),
    )

    # Saves the figures for faster analysis in future
    if OUTPUT_DIR is not None and incidents_dist is not None and costs_dist is not None:
        dists = {
            "incidents": incidents_dist,
            "costs": costs_dist,
        }
        filename = "{}-{}.pickle".format(pairing[0], pairing[1])
        pickle.dump(dists, open(OUTPUT_DIR + filename, "wb"))

    return incidents_dist, costs_dist


# pylint: disable=anomalous-backslash-in-string
def _run_monte_carlo_simulation(pairing: Tuple = ("All", "All")) -> None:
    """
    Runs :math:`n` simulations of a 12-month  period, calculating the number
    of incidents encountered each time and their cumulative costs.
    """
    # pylint: enable=anomalous-backslash-in-string

    # Generates both distributions
    incidents_dist, costs_dist = _get_most_relevant_distributions(pairing)

    if incidents_dist is None and costs_dist is None:
        return incidents_dist, costs_dist

    # Calculates the number of incidents suffered over $n$ simulated years
    nums_of_incidents = np.array(
        [_calculate_num_of_incidents(incidents_dist) for i in range(N)]
    )
    log.debug("Number of incidents: %s", str(nums_of_incidents))

    _label_plot(
        "Histogram of Incident Frequencies (over 12 months)",
        "Number of Incidents ($log_{10}$)",
        "Frequency",
    )
    plt.hist(
        [np.log10(i) if i > 0 else 0 for i in nums_of_incidents],
        align="left",
        bins=range(12),
    )
    _save_plot("2 - histogram of incident frequencies")

    # Calculates the annual costs for each simulated year
    log.info("Running Monte Carlo simulation... (0/%s iterations)", str(N))
    sum_costs = [
        _calculate_sum_cost_of_incidents(num_of_incidents, costs_dist, idx)
        for idx, num_of_incidents in enumerate(nums_of_incidents, start=1)
    ]
    log.info("Running Monte Carlo simulation... (%s/%s iterations)", str(N), str(N))

    _label_plot(
        "Histogram of Sum Costs (over 12 months)", "Total Cost (£)", "Frequency"
    )
    plt.ticklabel_format(style="plain")
    plt.hist(sum_costs, align="left", bins=15, range=(0, COMPANY_VALUE))
    _save_plot("4 - histogram of sum costs")

    _label_plot("Density of Sum Costs (over 12 months)", "Total Cost (£)", "Density")
    pd.Series(sum_costs).plot(kind="density")
    plt.xlim(0, COMPANY_VALUE * 2)
    plt.ticklabel_format(style="plain")
    _save_plot("5 - density of sum costs")

    # Get loss exceedance curve
    log.info("Generating loss exceedance curve")

    hist, edges = np.histogram(sum_costs, bins=LEC_PRECISION)
    cumrev = np.cumsum(hist[::-1])[::-1] * 100 / len(sum_costs)

    _label_plot(
        "Loss Exceedance Curve (Monte Carlo sim)",
        "Loss (£, 99th percentile)",
        "Chance of Loss or Greater (%)",
    )
    plt.ticklabel_format(style="plain")
    plt.xlim(0, COMPANY_VALUE)
    plt.plot(edges[:-1], cumrev)
    _save_plot("6 - lec" if IMAGES else "lec")

    log.info("Simulation complete!")

    return nums_of_incidents, sum_costs


def main():
    """Called when the script is run from the command-line"""
    # pylint: disable=global-statement
    global N, OUTPUT_DIR, IMAGES, FORCE
    # pylint: enable=global-statement

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-n",
        "--number",
        help="The number of simulations to run (default: " + str(DEFAULT_RUNS) + ")",
        type=int,
        default=DEFAULT_RUNS,
    )
    parser.add_argument(
        "-s",
        "--size",
        help="The size of the organisation to simulate (default: all)",
        type=str,
        default="All",
    )
    parser.add_argument(
        "-i",
        "--industry",
        help="The industry of the organisation to simulate (default: all)",
        type=str,
        default="All",
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
        help="Output images at each step of the script (default: false, just \
            output the final LEC image)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-f",
        "--force",
        help="Force re-generation of incident and cost distributions (default: false)",
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

    N = args.number
    OUTPUT_DIR = args.output
    IMAGES = args.images
    FORCE = args.force

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

    if size or industry:
        print("Running simulation for ({}, {})".format(size, industry))
        nums_of_incidents, sum_costs = _run_monte_carlo_simulation((size, industry))
        if nums_of_incidents is not None and sum_costs is not None:
            log.info(
                "Results:\nNumbers of incidents: %s\nSum costs: %s\n",
                str(nums_of_incidents),
                str(sum_costs),
            )

            avg_num_of_incidents = int(sum(nums_of_incidents) / len(nums_of_incidents))
            avg_sum_costs = sum(sum_costs) / len(sum_costs)
            log.log(
                SUCCESS,
                "Results:\nAverage number of incidents: %d\nAverage cost: £%.2f",
                avg_num_of_incidents,
                avg_sum_costs,
            )

            # Print output that will be picked up by game server.
            # pylint: disable=fixme
            # TODO: For some reason the results at the moment are orders of magnitude
            # too high, so for now I've plugged it by dividing both results by 100.
            # pylint: enable=fixme
            print(int(avg_num_of_incidents / 100))
            print("%.2f" % (avg_sum_costs / 100))
        else:
            log.warning("No data found.")
            print("No data found.")

    print("Running simulation for (All, All)")
    gen_nums_of_incidents, gen_sum_costs = _run_monte_carlo_simulation()
    log.info(
        "Results:\nNumbers of incidents: %s\nSum costs: %s\n",
        str(gen_nums_of_incidents),
        str(gen_sum_costs),
    )

    avg_gen_num_of_incidents = int(
        sum(gen_nums_of_incidents) / len(gen_nums_of_incidents)
    )
    avg_gen_sum_costs = sum(gen_sum_costs) / len(gen_sum_costs)
    log.log(
        SUCCESS,
        "Results:\nAverage number of incidents: %d\nAverage cost: £%.2f",
        avg_gen_num_of_incidents,
        avg_gen_sum_costs,
    )

    # Print output that will be picked up by the game server.
    print(int(avg_gen_num_of_incidents / 100))
    print("%.2f" % (avg_gen_sum_costs / 100))

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
