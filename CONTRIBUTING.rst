============
Contributing
============

Contributions are welcome.

Reporting Problems
------------------

Please report problems in the `GitHub issue tracker
<https://github.com/norle/THG_The-Human-GEM-protocol-standalone/issues>`_.

Include, where applicable:

* Your operating system and version.
* Your Python version and THG Protocol version.
* Relevant package, solver, or service versions.
* Detailed steps to reproduce the problem, including a small input or fixture
  when possible.
* The complete error message or traceback.

Do not disclose security-sensitive details in a public issue.

Proposing Changes
-----------------

For substantial changes, open an issue first. Explain the problem, keep the
scope narrow, test the behavior, update its documentation, and record versions
that affect reproducibility.

Getting Started
---------------

THG Protocol supports Python 3.10 through 3.12:

.. code-block:: console

   $ python -m venv .venv
   $ source .venv/bin/activate
   $ python -m pip install -e ".[docs,dev]"

On Windows, activate the environment with
``.venv\\Scripts\\activate`` instead of ``source .venv/bin/activate``.

Run the Local Checks
--------------------

Run the default offline test suite and linter from the repository root:

.. code-block:: console

   $ pytest -m "not slow and not online and not solver and not gurobi and not memote"
   $ ruff check src tests

For documentation changes, also run:

.. code-block:: console

   $ mkdocs build --strict
   $ pytest tests/docs

Run optional marked tests only when their services or dependencies are
available. See the `development guide <docs/contributing/development.md>`_ for
release checks and the `validation guide <docs/workflows/validation.md>`_ for
MEMOTE.

Submitting a Pull Request
-------------------------

Before submitting a pull request:

* Make sure the relevant local checks pass.
* Keep commits focused and describe the reason for the change.
* Do not commit generated build output, local virtual environments, caches, or
  secrets.
* Check that model and other large artifacts follow the repository's Git LFS
  conventions.
* Summarize the change, tests run, and any known limitations in the pull
  request description.

Open the pull request against ``refactoring-cleanup`` unless maintainers specify
another target, then respond to review feedback.
