"""
    Neo4j Graph Database Interface

    This module defines:
        a) the interface for interacting with the Neo4j graph database; and
        b) subclasses of `Relationship`.
"""

import re
import sys
import logging as log
from typing import List, Tuple, Union, Dict
from datetime import datetime
from py2neo import Graph, Node, NodeMatcher, Relationship, DatabaseError
import numpy as np


class GraphInterface:
    """
    An interface for the Neo4j graph database used to hold TI data.

    This interface abstracts out the actual transactions, allowing a user
    to use more friendly methods without worrying about the implementation or
    learning the Cypher query language syntax.

    This class should:
        a) determine the correct transactions to use based on the called
           method and any arguments;
        b) return only `Node`s, `Relationship`s, `SubGraph`s or lists thereof,
           so that the values can be assigned to subclasses of those at the
           point of calling; and
        c) deal with any `Exception`s, but not issues like returning 0 results,
           which should be dealt with at the point of calling.
    """

    g: Graph = None

    @staticmethod
    def __init__():
        try:
            if GraphInterface.g is None:
                GraphInterface.g = Graph(password="test")
                log.info("Neo4j database connection opened successfully.")
            else:
                log.warning(
                    "Neo4j database already connected - this branch "
                    "shouldn't have been hit though!"
                )
        except DatabaseError:
            log.error("ERR: Neo4j database connection not successfully opened.")
            sys.exit()

    @staticmethod
    def delete_distributions() -> bool:
        """Deletes any pre-existing distributions."""
        GraphInterface.g.run(
            "MATCH (n) "
            "WHERE n:IncidentFrequencyDistribution OR n:IncidentCostsDistribution "
            "DETACH DELETE n;"
        )
        return True

    @staticmethod
    def get_incident_frequency_probabilities(
        boundaries, pairing: Tuple = ("All", "All")
    ) -> List[float]:
        """
        Attempts to get a list of probabilities for different annual incident
        frequencies, specific to the organisational details provided.

        It first gets (the average of) any sets of base frequencies, then looks
        up the provided size/industry values to see if they have any assigned
        breach probability values in the graph database. If multiple values are
        found, the average is taken.

        Once the specific base (i.e., >0) probability is found, it then recalculates
        the overall set of probabilities as proportions of that base figure.
        """
        size = pairing[0]
        industry = pairing[1]

        log.info(
            "Attempting to get breach frequency probabilities specific to ('%s', '%s')...",
            size,
            industry,
        )

        base_frequency_probabilities_nodes = GraphInterface._get_nodes(
            "IncidentBaseFrequencyProbabilities"
        )
        base_frequency_probabilities = [
            node["probabilities"]
            for node in base_frequency_probabilities_nodes
            if len(node["probabilities"]) == (len(boundaries) - 1)
        ]

        # If there are >1 sets of likelihoods, gets the mean for each boundary value.
        if len(base_frequency_probabilities) > 1:
            log.info("Multiple sets of base frequencies found, averaging...")
            base_frequency_probabilities = np.array(base_frequency_probabilities)
            base_frequency_probabilities = [
                np.mean(base_frequency_probabilities[:, i])
                for i in range(len(boundaries))
            ]

        probability_of_breach = GraphInterface.get_probability_of_breach(size, industry)
        if probability_of_breach:
            log.info(
                "Found specific >0 breaches probability value for one or both "
                "of ('%s', '%s'), calculating follow-on values...",
                size,
                industry,
            )
            # Sets the probability of having 0 breaches.
            breach_frequency_probabilities = [(100 - probability_of_breach) / 100]

            # Calculates the remaining probabilities proportional to the sum
            # >0 breaches probability.
            for base_frequency_probability in base_frequency_probabilities[0]:
                breach_frequency_probabilities.append(
                    (probability_of_breach * base_frequency_probability) / 100
                )

            if len(breach_frequency_probabilities) != len(boundaries):
                raise Exception("Mismatched boundaries!")

            return breach_frequency_probabilities

        log.info("No breach probability value found.")
        return None

    # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    @staticmethod
    def get_probability_of_breach(size="All", industry="All") -> float:
        """
        Returns the probability of an organisation of a given size and/or
        industry experiencing a breach with an outcome in the next year.

        Where a match exists for both size and industry, size is chosen as it
        assumed that organisations of a similar size will have a more similar
        threat model than organisations within the same industry. This assumption
        is not empirically grounded, however, so it may be that the opposite
        is true.
        """
        size_probability = None
        industry_probability = None

        size_node = GraphInterface._get_node("Size", name=size)
        if size_node:
            log.info("Found node for size '%s'.", size)
        else:
            log.info("No node found for size '%s'.", size)

        industry_node = GraphInterface._get_node("Industry", name=industry)
        if industry_node:
            log.info("Found node for industry '%s'.", industry)
        else:
            log.info("No node found for industry '%s'.", industry)

        # If no figures were found for this pairing, returns None.
        if size_node is None and industry_node is None:
            return None

        if size_node:
            size_relations = GraphInterface.g.match({size_node}, r_type=FOR_SIZE)

            size_probabilities = []
            for rel in size_relations:
                if rel.start_node.has_label("IncidentProbability"):
                    size_probabilities.append(rel.start_node["probability"])

            if len(size_probabilities) > 1:
                log.info(
                    "Multiple probabilities found for size '%s', averaging...", size
                )
                size_probability = sum(size_probabilities) / len(size_probabilities)
            elif len(size_probabilities) == 1:
                log.info("Probability value found for size '%s'.", size)
                size_probability = size_probabilities[0]
            else:
                log.info("No probability value found for size '%s'.", size)

        if industry_node:
            industry_relations = GraphInterface.g.match(
                {industry_node}, r_type=FOR_INDUSTRY
            )
            industry_probabilities = []
            for rel in industry_relations:
                if rel.start_node.has_label("IncidentProbability"):
                    industry_probabilities.append(rel.start_node["probability"])

            if len(industry_probabilities) > 1:
                log.info(
                    "Multiple probabilities found for industry '%s', averaging...",
                    industry,
                )
                industry_probability = sum(industry_probabilities) / len(
                    industry_probabilities
                )
            elif len(industry_probabilities) == 1:
                log.info("Probability value found for industry '%s'.", industry)
                industry_probability = industry_probabilities[0]
            else:
                log.info("No probability value found for industry '%s'.", industry)

        if size_probability and industry_probability:
            log.info(
                "Probabilities found for both size '%s' and industry '%s', averaging...",
                size,
                industry,
            )
            probability = (size_probability + industry_probability) / 2
        else:
            probability = size_probability or industry_probability

        return probability

    # pylint: enable=too-many-branches,too-many-locals,too-many-statements

    # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    @staticmethod
    def get_incident_cost_averages(
        pairing: Tuple = ("All", "All")
    ) -> Tuple[float, float]:
        """
        Attempts to get the average incident costs over a year, specific to the
        organisational details provided.

        The CSBS specifies figures for breaches both 'with' and 'without outcomes'.
        We have ignored the latter here.
        """
        size = pairing[0]
        industry = pairing[1]

        size_mean = None
        size_median = None
        industry_mean = None
        industry_median = None

        log.info(
            "Attempting to get incident cost averages specific to ('%s', '%s')...",
            size,
            industry,
        )

        size_node = GraphInterface._get_node("Size", name=size)
        if size_node:
            log.info("Found node for size '%s'.", size)
        else:
            log.info("No node found for size '%s'.", size)

        industry_node = GraphInterface._get_node("Industry", name=industry)
        if industry_node:
            log.info("Found node for industry '%s'.", industry)
        else:
            log.info("No node found for industry '%s'.", industry)

        # If no figures were found for this pairing, returns None.
        if size_node is None and industry_node is None:
            return None

        if size_node:
            size_relations = GraphInterface.g.match({size_node}, r_type=FOR_SIZE)

            size_means = []
            size_medians = []
            for rel in size_relations:
                if rel.start_node.has_label("IncidentCostAverages"):
                    size_means.append(rel.start_node["mean"])
                    size_medians.append(rel.start_node["median"])

            # Converts however many mean and median values returned into one of
            # each.
            if len(size_means) > 1:
                log.info("Multiple mean values found for size '%s', averaging...", size)
                size_mean = sum(size_means) / len(size_means)
            elif len(size_means) == 1:
                log.info("Mean value found for size '%s'.", size)
                size_mean = size_means[0]
            else:
                log.info("No mean values found for size '%s'.", size)
            if len(size_medians) > 1:
                log.info(
                    "Multiple median values found for size '%s', averaging...", size
                )
                size_median = sum(size_medians) / len(size_medians)
            elif len(size_medians) == 1:
                log.info("Median value found for size '%s'.", size)
                size_median = size_medians[0]
            else:
                log.info("No median values found for size '%s'.", size)

        if industry_node:
            industry_relations = GraphInterface.g.match(
                {industry_node}, r_type=FOR_INDUSTRY
            )

            industry_means = []
            industry_medians = []
            for rel in industry_relations:
                if rel.start_node.has_label("IncidentCostAverages"):
                    industry_means.append(rel.start_node["mean"])
                    industry_medians.append(rel.start_node["median"])

            # Converts however many mean and median values returned into one of
            # each.
            if len(industry_means) > 1:
                log.info(
                    "Multiple mean values found for industry '%s', averaging...",
                    industry,
                )
                industry_mean = sum(industry_means) / len(industry_means)
            elif len(industry_means) == 1:
                log.info("Mean value found for industry '%s'.", industry)
                industry_mean = industry_means[0]
            else:
                log.info("No mean values found for industry '%s'.", industry)
            if len(industry_medians) > 1:
                log.info(
                    "Multiple median values found for industry '%s', averaging...",
                    industry,
                )
                industry_median = sum(industry_medians) / len(industry_medians)
            elif len(industry_medians) == 1:
                log.info("Median value found for industry '%s'.", industry)
                industry_median = industry_medians[0]
            else:
                log.info("No median values found for industry '%s'.", industry)

        if size_mean and industry_mean:
            log.info(
                "Mean values found for both size '%s' and industry '%s', averaging...",
                size,
                industry,
            )
            mean = (size_mean + industry_mean) / 2
        else:
            mean = size_mean or industry_mean

        if size_median and industry_median:
            log.info(
                "Median values found for both size '%s' and industry '%s', averaging...",
                size,
                industry,
            )
            median = (size_median + industry_median) / 2
        else:
            median = size_median or industry_median

        return mean, median

    # pylint: enable=too-many-branches,too-many-locals,too-many-statements

    # pylint: disable=invalid-name,anomalous-backslash-in-string
    @staticmethod
    def get_incident_frequency_distribution(
        pairing: Tuple = ("All", "All")
    ) -> Union[Tuple[float, float], None]:
        """
        Returns the most relevant available incident frequency distribution for
        a given pairing.

        The algorithm for determining this is currently very basic:

        1. search for an exact match for the pairing, and return that if found; else
        2. return the distribution for :math:`\left(\text{All}, \text{All}\right)`.

        In future, this can and should be expanded to follow complex heuristics
        for similarity (and some relationships for doing so are provided at the
        end of this module). For example, two industries can be joined using the
        SIMILAR_TO relationship, which would allow the algorithm to traverse
        laterally to other leaf nodes.

        An even simpler improvement would be to add handling for partial matches
        (e.g., returning :math:`\left(\text{Micro}, \text{All}\right)`, which
        should be more relevant to a :math:`\left(\text{Micro}, \text{IT}\right)`
        organisation than the fallback :math:`\left(\text{All}, \text{All}\right)`
        values will be.
        """
        # pylint: enable=anomalous-backslash-in-string

        size = pairing[0]
        industry = pairing[1]

        size_node = GraphInterface._get_node("Size", name=size)
        if size_node:
            log.info("Found node for size '%s'.", size)
        else:
            log.info("No node found for size '%s'.", size)

        industry_node = GraphInterface._get_node("Industry", name=industry)
        if industry_node:
            log.info("Found node for industry '%s'.", industry)
        else:
            log.info("No node found for industry '%s'.", industry)

        # If no figures were found for this pairing, returns the fallback values.
        if size_node is None and industry_node is None:
            return GraphInterface._get_frequency_distribution()

        dist: Union[
            Dict[float, float], None
        ] = GraphInterface._get_frequency_distribution(size, industry)

        if dist is not None:
            log.debug(
                "Returned values are: a = %s, b = %s", str(dist["a"]), str(dist["b"])
            )

        return dist

    # pylint: enable=invalid-name

    # pylint: disable=anomalous-backslash-in-string
    @staticmethod
    def get_incident_costs_distribution(
        pairing: Tuple = ("All", "All")
    ) -> Union[Tuple[float, float], None]:
        """
        Returns the most relevant available incident costs distribution for
        a given pairing.

        The algorithm for determining this is currently very basic:

        1. search for an exact match for the pairing, and return that if found; else
        2. return the distribution for :math:`\left(\text{All}, \text{All}\right)`.

        In future, this can and should be expanded to follow complex heuristics
        for similarity (and some relationships for doing so are provided at the
        end of this module). For example, two industries can be joined using the
        SIMILAR_TO relationship, which would allow the algorithm to traverse
        laterally to other leaf nodes.

        An even simpler improvement would be to add handling for partial matches
        (e.g., returning :math:`\left(\text{Micro}, \text{All}\right)`, which
        should be more relevant to a :math:`\left(\text{Micro}, \text{IT}\right)`
        organisation than the fallback :math:`\left(\text{All}, \text{All}\right)`
        values will be.
        """
        # pylint: enable=anomalous-backslash-in-string

        size = pairing[0]
        industry = pairing[1]

        size_node = GraphInterface._get_node("Size", name=size)
        if size_node:
            log.info("Found node for size '%s'.", size)
        else:
            log.info("No node found for size '%s'.", size)

        industry_node = GraphInterface._get_node("Industry", name=industry)
        if industry_node:
            log.info("Found node for industry '%s'.", industry)
        else:
            log.info("No node found for industry '%s'.", industry)

        # If no figures were found for this pairing, returns the fallback values.
        if size_node is None and industry_node is None:
            return GraphInterface._get_costs_distribution()

        dist: Union[Dict[float, float], None] = GraphInterface._get_costs_distribution(
            size, industry
        )

        if dist is not None:
            log.debug(
                "Returned values are: mean = %s, stddev = %s",
                str(dist["mean"]),
                str(dist["stddev"]),
            )

        return dist

    @staticmethod
    def get_sizes() -> List[str]:
        """Returns a list of all of the organisation size values."""
        nodes = GraphInterface._get_nodes("Size")

        return [node["name"] for node in nodes]

    @staticmethod
    def get_industries() -> List[str]:
        """Returns a list of all of the organisation industry values."""
        nodes = GraphInterface._get_nodes("Industry")

        return [node["name"] for node in nodes]

    @staticmethod
    def get_sizes_and_industries() -> Tuple[list, list]:
        """Returns all available organisation size and industry values."""
        return GraphInterface.get_sizes(), GraphInterface.get_industries()

    # pylint: disable=invalid-name
    @staticmethod
    def create_incident_frequency_distribution_node(
        pairing: Tuple, a: float, b: float
    ) -> Node:
        """Adds an `IncidentFrequencyDistribution` node to the Neo4j graph database."""
        size_node = GraphInterface._get_node("Size", name=pairing[0])
        industry_node = GraphInterface._get_node("Industry", name=pairing[1])

        node = GraphInterface._create_node(
            "IncidentFrequencyDistribution", a=a, b=b, calculated_at=datetime.now()
        )
        GraphInterface._create_relationship(node, FOR_SIZE, size_node)
        GraphInterface._create_relationship(node, FOR_INDUSTRY, industry_node)
        return node

    # pylint: enable=invalid-name

    @staticmethod
    def create_incident_costs_distribution_node(
        pairing: Tuple, mean: float, stddev: float
    ) -> Node:
        """Adds an `IncidentCostsDistribution` node to the Neo4j graph database."""
        size_node = GraphInterface._get_node("Size", name=pairing[0])
        industry_node = GraphInterface._get_node("Industry", name=pairing[1])

        node = GraphInterface._create_node(
            "IncidentCostsDistribution",
            mean=mean,
            stddev=stddev,
            calculated_at=datetime.now(),
        )
        GraphInterface._create_relationship(node, FOR_SIZE, size_node)
        GraphInterface._create_relationship(node, FOR_INDUSTRY, industry_node)
        return node

    # pylint: disable=anomalous-backslash-in-string,invalid-name
    @staticmethod
    def _get_frequency_distribution(
        size: str = "All", industry: str = "All"
    ) -> Dict[float, float]:
        """
        Returns the :math:`a` and :math:`b` values from the requested incident
        frequency distribution node (if it exists). Call with no arguments to
        use the fallback (:math:`\left(\text{All}, \text{All}\right)`) node.
        """
        # pylint: enable=anomalous-backslash-in-string

        # pylint: disable=line-too-long
        result = GraphInterface.g.run(
            "MATCH (:Size {{name:'{}'}})<-[:FOR_SIZE]-(node:IncidentFrequencyDistribution)-[:FOR_INDUSTRY]->(:Industry {{name:'{}'}}) "
            "RETURN node;".format(size, industry)
        )
        # pylint: enable=line-too-long

        nodes = [record["node"] for record in result]

        if len(nodes) == 0:
            # There should always be a (All, All) distribution at least.
            if size == "All" and industry == "All":
                raise Exception("No fallback node found!")

            log.debug(
                "No incident frequency distribution found for (%s, %s).",
                str(size),
                str(industry),
            )
            return None, None
        log.debug("Results: %s", str(nodes))

        a = [node["a"] for node in nodes]
        b = [node["b"] for node in nodes]

        if len(nodes) > 0:
            log.info("Multiple fallback nodes found, averaging parameters...")
            a = sum(a) / len(a)
            b = sum(b) / len(b)
        else:
            a = a[0]
            b = b[0]

        return {"a": a, "b": b}

    # pylint: enable=invalid-name

    # pylint: disable=anomalous-backslash-in-string
    @staticmethod
    def _get_costs_distribution(
        size: str = "All", industry: str = "All"
    ) -> Dict[float, float]:
        """
        Returns the :math:`a` and :math:`b` values from the requested incident
        frequency distribution node (if it exists). Call with no arguments to
        use the fallback (:math:`\left(\text{All}, \text{All}\right)`) node.
        """
        # pylint: enable=anomalous-backslash-in-string

        # pylint: disable=line-too-long
        result = GraphInterface.g.run(
            "MATCH (:Size {{name:'{}'}})<-[:FOR_SIZE]-(node:IncidentCostsDistribution)-[:FOR_INDUSTRY]->(:Industry {{name:'{}'}}) "
            "RETURN node;".format(size, industry)
        )
        # pylint: enable=line-too-long

        nodes = [record["node"] for record in result]

        if len(nodes) == 0:
            # There should always be a (All, All) distribution at least.
            if size == "All" and industry == "All":
                raise Exception("No fallback node found!")

            log.debug(
                "No incident frequency distribution found for (%s, %s).",
                str(size),
                str(industry),
            )
            return None, None
        log.debug("Results: %s", str(nodes))

        mean = [node["mean"] for node in nodes]
        stddev = [node["stddev"] for node in nodes]

        if len(nodes) > 1:
            log.info("Multiple fallback nodes found, averaging parameters...")
            mean = sum(mean) / len(mean)
            stddev = sum(stddev) / len(stddev)
        else:
            mean = mean[0]
            stddev = stddev[0]

        return {"mean": mean, "stddev": stddev}

    # pylint: disable=invalid-name
    @staticmethod
    def _create_node(*labels, **properties) -> Node:
        """Creates a new node in the Neo4j graph database."""
        tx = GraphInterface.g.begin()
        node = Node(*labels, **properties)
        tx.create(node)
        tx.commit()
        return node

    # pylint: enable=invalid-name

    # pylint: disable=invalid-name
    @staticmethod
    def _create_relationship(
        start_node, relationship, end_node, **properties
    ) -> Relationship:
        """Creates a new relationship in the Neo4j graph database."""
        tx = GraphInterface.g.begin()
        relationship = Relationship(
            start_node, relationship.__name__, end_node, **properties
        )
        tx.create(relationship)
        tx.commit()
        return relationship

    # pylint: enable=invalid-name

    @staticmethod
    def _get_node(*labels, **properties) -> Union[Node, None]:
        """Returns a node from the Neo4j graph database."""
        return GraphInterface.g.nodes.match(*labels, **properties).first()

    @staticmethod
    def _get_nodes(*labels, **properties) -> NodeMatcher:
        """Returns a node from the Neo4j graph database."""
        return GraphInterface.g.nodes.match(*labels, **properties)

    @staticmethod
    def _dict_to_jsobj(properties) -> str:
        """Recursively converts a Python `dict` into a JS `Object`."""
        if isinstance(properties, dict):
            return re.sub("'([a-z_]*)':", "\\1:", str(properties))

        if isinstance(properties, str):
            return GraphInterface._dict_to_jsobj({"name": properties})

        return "{}"


# pylint: disable=invalid-name,missing-class-docstring
class SUBSECTION_OF(Relationship):
    pass


class SECTION_OF(Relationship):
    pass


class SIMILAR_TO(Relationship):
    pass


class FOR_SIZE(Relationship):
    pass


class FOR_INDUSTRY(Relationship):
    pass


# pylint: enable=invalid-name,missing-class-docstring
