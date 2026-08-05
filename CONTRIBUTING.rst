============
Contributing
============

Contributions are welcome and appreciated. You can help by reporting a
problem, fixing a bug, implementing a feature, improving the documentation,
or sharing feedback.

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

Before opening an issue, search the existing issues and documentation. For
security-sensitive problems, do not disclose details in a public issue.

Proposing Changes
-----------------

Bug fixes, focused features, tests, and documentation improvements are all
welcome. For a substantial change, open an issue first so that the scope and
design can be discussed before implementation.

When proposing a feature:

* Explain the problem it solves and how the proposed behavior would work.
* Keep the scope as narrow as possible.
* Add or update tests for behavior that can be checked automatically.
* Update the relevant documentation and command/API examples.
* Preserve reproducibility: record input, output, package, service, and solver
  versions when they affect the result.

Getting Started
---------------

THG Protocol supports Python 3.10 through 3.12. Create a virtual environment
and install the package with its development dependencies:

.. code-block:: console

   $ git clone https://github.com/norle/THG_The-Human-GEM-protocol-standalone.git
   $ cd THG_The-Human-GEM-protocol-standalone
   $ python -m venv .venv
   $ source .venv/bin/activate
   $ python -m pip install --upgrade pip
   $ python -m pip install -e ".[dev]"

On Windows, activate the environment with
``.venv\\Scripts\\activate`` instead of ``source .venv/bin/activate``.

Create a branch for your change:

.. code-block:: console

   $ git switch -c name-of-your-change

Run the Local Checks
--------------------

Run the default offline test suite and linter from the repository root:

.. code-block:: console

   $ pytest -m "not slow and not online and not solver and not gurobi and not memote"
   $ ruff check src tests

If you change documentation, install the documentation extra and build it in
strict mode:

.. code-block:: console

   $ python -m pip install -e ".[docs,dev]"
   $ mkdocs build --strict
   $ pytest tests/docs

Some tests are marked ``slow``, ``online``, ``solver``, ``gurobi``, or
``memote``. Run those only when their required services or dependencies are
available. Solver reproducibility uses the constraints file documented in
``docs/development.md``.

For changes involving model quality or validation, install MEMOTE with
``python -m pip install -e ".[memote]"`` and follow the
`MEMOTE and task analysis guide
<docs/workflows/memote.md>`_.

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

Push your branch to your fork and open a pull request against the repository's
``refactoring-cleanup`` branch, unless the maintainers specify another target:

.. code-block:: console

   $ git add path/to/changed-file
   $ git commit -m "Describe the change"
   $ git push origin name-of-your-change

Please respond to review feedback and keep the pull request up to date with
the target branch.
