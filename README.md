# Threat Intelligence Service

A tool for collecting threat intelligence data and running Monte Carlo simulations
based on it.

## Table of Contents

* [Tech Stack](#tech-stack)
* [Features](#features)
* [Installation](#installation)
* [Configuration Setup](#configuration-setup)
* [Usage](#usage)
* [Testing](#testing)
* [Code Formatting](#code-formatting)
* [Documentation](#documentation)
* [Acknowledgments](#acknowledgements)
* [License](#license)
* [Contact Information](#contact-information)

## Technology Stack

The risk calculation scripts are written in [Python][python], along with 
prototypes written in [R][r].

The Neo4j graph database uses the [Cypher][cypher] query language.

| Technology | Description                      | Link |
|------------|----------------------------------|------|
| Neo4j	     | Graph database management system | [Link](https://neo4j.com/) |

## Features

This repo. provides:

- Scripts for (re)generating incident number and average cost distributions
  and running Monte Carlo simulations using those distributions;
- a set of Cypher commands to allow for easy initial population of a Neo4j
  threat intelligence graph database with data derived from the
  [_Cyber Security Breaches Survey_ 2020][csbs2020]; and
- a full suite of automated linting functions to ensure codebase standardisation.

## Installation

### Threat Intelligence Database (Neo4j)

1. Install [Neo4j Desktop][neo4j-desktop];
1. in the Neo4j Desktop app, create a new Project;
1. in that project, add either a ‘Local DBMS’ or a ‘Remote Connection’ (depending
   on which environment you are in) and call it ‘Threat Intelligence’:
    - make sure to update the connection details in `src/scripts/graph.py`.
1. add the file `contrib/database.cypher` to the Project;
1. open your server in the Neo4j Browser;
1. go to the ‘Project Files’ tab and press the run button next to `database.cypher`.

### Scripts

1. Clone the repo. to your dev. environment (`git clone git@github.com:Rumperuu/Threat-Intelligence-Service.git`);
1. enter the new folder (`cd Threat-Intelligence-Service`);
1. create a virtual Python environment (`python3.⟨version⟩ -m venv pyvenv`);
1. activate your virtual environment (`source ./pyvenv/bin/activate`); and
1. install Python package with pip (`pip install -r requirements.txt`).

## Configuration Setup

TODO: Add environment config.

## Usage

Run `python src/montecarlo.py` to run a Monte Carlo simulation. Use `-h` to view
the available options.

Run `python src/regenerate-distributions.py` to (re)generate all propability 
distributions. Use `-h` to view the available options.

## Testing

There are not currently any tests.

## Code formatting

There is not currently any automated code formatting or linting.

### Python Code

Python code must conform to [PEP 8][pep8].

- Run `black --target-version=py38 */**/*.py` to format all Python files with [Black][black].
- Use `--check` to view the output without automatically fixing warnings and 
  errors.

- Run `pylint */**/*.py --output-format=colorized` to lint all Python files with [Pylint][pylint].
- Pylint does not have the ability to automatically fix warnings and errors.

Pylint configuration settings are found in `.pylintrc`.

## Documentation

There is currently no documentation.

## Acknowledgements

This project was initially developed as part of [KTP № 11598][ktp], with 
funding provided by [Innovate UK][innovate-uk] & [Mitigate Cyber][mitigate].

This game was inspired by Hubbard & Seiersen's book _How to Measure Anything in Cybersecurity Risk_.

## License

This project is currently released under the [CRAPL][crapl]. It should **NOT** 
be used in a production environment in its current state.

## Contact Information 

| Name          | Link(s)               |
|---------------|-----------------------|
|Ben Goldsworthy| [Email][bgoldsworthy] |

[python]: https://www.python.org/
[r]: https://www.r-project.org/
[cypher]: https://neo4j.com/developer/cypher/
[csbs2020]: https://www.gov.uk/government/statistics/cyber-security-breaches-survey-2020
[neo4j-desktop]: https://neo4j.com/download/?ref=try-neo4j-lp
[pep8]: https://www.python.org/dev/peps/pep-0008/
[black]: https://pypi.org/project/black/
[pylint]: https://pylint.org/
[ktp]: https://info.ktponline.org.uk/action/details/partnership.aspx?id=11598
[innovate-uk]: https://www.gov.uk/government/organisations/innovate-uk
[mitigate]: http://mitigatecyber.com/
[crapl]: https://matt.might.net/articles/crapl/
[bgoldsworthy]: mailto:me+threatintelservice@bengoldsworthy.net
