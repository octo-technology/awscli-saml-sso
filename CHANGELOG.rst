=========
Changelog
=========

0.2.1 (2020-12-11)
------------------

* Configure default log level to WARN in order to get printed text in terminal uncluttered by logs
* Add a ``--log-level`` option and corresponding ``ASS_LOG_LEVEL`` environment variable to override default log level

0.2.0 (2020-12-04)
------------------

* Detect automatically Chrome or Firefox browser install on user operating system to rely on
* Retrieve SAML response from HTTP request body instead of parsing HTML page
* Fix authentication exception raised when no role was attached to the authenticated account
* Fix authentication that remain stuck when user was associated with only one AWS role

0.1.1 (2020-12-02)
------------------

* Fix github homepage from setuptools configuration
* Add a --version option to display current version from command line

0.1.0 (2020-12-01)
------------------

* Authenticate through SAML identity provider in web browser
* Select among retrieved AWS roles you are allowed to assume
* Store temporary credentials in aws configuration files
