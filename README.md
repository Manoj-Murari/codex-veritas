Codex Veritas
An AI software engineering platform built on the principle of Structural Honesty.

What is This?
Codex Veritas is a next-generation AI developer tool designed to provide reliable, verifiable insights into your codebase. Unlike other AI tools that can "hallucinate" or provide untrustworthy suggestions, Codex Veritas grounds all of its analysis and code generation in a deterministic structural graph of your project. This repository contains the core engine, analysis tools, and the web application.

Getting Started
This project is managed with Poetry. You'll need to install it first.

Clone the repository:

git clone [https://github.com/your-org/codex-veritas.git](https://github.com/your-org/codex-veritas.git)
cd codex-veritas

Install dependencies:
Poetry will create a virtual environment automatically and install all necessary production and development dependencies.

poetry install

Run the analysis pipeline:
Before you can query the codebase, you need to build the structural graph and the semantic database. You will need a target_repo folder in the root of this project containing the code you want to analyze.

poetry run codex analyze

Run the web application:

poetry run flask --app src/codex_veritas/app/main:app run

The application will be available at http://127.0.0.1:5000.

Running Tests
To run the full suite of tests, use pytest:

poetry run pytest

Contributing
Contribution guidelines are forthcoming. For now, please feel free to open issues for bugs or feature requests.