# Contributing to AEON-ZTPS

So you want to help, excellent! Here's some guidelines to follow.
## What to Contribute
We're always looking for help with documentation, bug fixes, support for more devices, and even new features.

## How to Contribute
1. Fork the develop branch as a start.
2. Run tests using tox and verify that they pass. 
3. Write code tests for bug you are fixing or feature you are adding.
4. Write code to fix the bug or add a feature.
5. Document code using [Sphinx-autodoc syntax](http://www.sphinx-doc.org/en/stable/ext/autodoc.html#module-sphinx.ext.autodoc).
6. Re-run tox and make sure all tests pass.
7. Submit a pull request. Be sure to fully document the bug/fix or feature in the pull request.

## Code Requirements
All code must follow pep8 style guides, and will be checked with flake8.

Any new code added must be tested by a unit test.

Any new code added must have the appropriate sphinx autodoc syntax.