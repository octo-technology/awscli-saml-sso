============
Contributing
============

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.

You can contribute in many ways:

Types of Contributions
----------------------

Report Bugs
~~~~~~~~~~~

Report bugs at https://github.com/octo-technology/awscli-saml-sso/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
~~~~~~~~

Look through the GitHub issues for bugs. Anything tagged with "bug" and "help
wanted" is open to whoever wants to implement it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the GitHub issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

Write Documentation
~~~~~~~~~~~~~~~~~~~

AWSCLI SAML SSO could always use more documentation, whether as part of the
official AWSCLI SAML SSO docs, in docstrings, or even on the web in blog posts,
articles, and such.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to file an issue at https://github.com/octo-technology/awscli-saml-sso/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions
  are welcome :)

Get Started!
------------

Ready to contribute? Here's how to set up `awscli_saml_sso` for local development.

1. Fork the `awscli_saml_sso` repo on GitHub.
2. Clone your fork locally::

    $ git clone git@github.com:your_name_here/awscli_saml_sso.git

3. Install your local copy into a virtualenv. Assuming you have python3 installed, this is how you set up your fork for local development::

    $ python3 -m venv .venv
    $ source .venv/bin/activate
    $ pip install -e .

4. Create a branch for local development::

    $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

5. Commit your changes and push your branch to GitHub::

    $ git add .
    $ git commit -m "Your detailed description of your changes."
    $ git push origin name-of-your-bugfix-or-feature

6. Submit a pull request through the GitHub website.

Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring, and add the
   feature to the list in README.rst.
2. The pull request should work for Python 3.8 to 3.11, and for PyPy.


Deploying to PyPI
-----------------

A reminder for the maintainers on how to deploy.

1. Make sure all your changes are committed (including an entry in CHANGELOG.rst **with the new version**).

2. **Do not** update manually version in ``setup.cfg`` or ``setup.py`` or ``__init__.py``. Instead, run::

    $ bump2version patch # possible: major / minor / patch
    $ git push
    $ git push --tags

3. Ask to be added to the `PyPI project <https://pypi.org/project/awscli-saml-sso/) and get an API token from ``https://pypi.org/manage/account/token>`_

4. Add this content to ``~/.pypirc``::

    [distutils]
    index-servers =
        pypi
        awscli-saml-sso

    [pypi]
    username = __token__
    password = <YOUR TOKEN>

5. Deplpy by running  ``make release``