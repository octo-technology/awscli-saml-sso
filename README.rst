===============
AWSCLI SAML SSO
===============

.. image:: https://img.shields.io/pypi/v/awscli_saml_sso
        :target: https://pypi.org/pypi/awscli_saml_sso

.. image:: https://img.shields.io/pypi/l/awscli_saml_sso
        :target: https://pypi.org/pypi/awscli_saml_sso

.. image:: https://img.shields.io/pypi/pyversions/awscli_saml_sso
        :target: https://pypi.org/pypi/awscli_saml_sso

awscli_saml_sso is a command line tool that aims to get temporary credentials from SAML identity provider in order to authenticate to awscli.

Installation
------------

You need a fully functional python 3 environment, then you can install tool from pypi:

.. code-block:: shell

    pip install awscli-saml-sso

Usage
-----

You only need to run the following command in terminal:

.. code-block:: shell

    awscli_saml_sso

    # Please configure your identity provider url [https://<fqdn>:<port>/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices]:
    > ...

    # Please choose the role you would like to assume:
    # [ 0 ]:  arn:aws:iam::<account_number>:role/<role_name>
    # [ 1 ]:  arn:aws:iam::<account_number>:role/<role_name>
    # ...
    # Selection: <select among numbered roles>


    # ----------------------------------------------------------------
    # Your new access key pair has been stored in the AWS configuration file /home/.aws/credentials under the saml profile.
    # Note that it will expire at 2020-12-01 13:17:27+00:00.
    # After this time, you may safely rerun this script to refresh your access key pair.
    # To use this credential, call the AWS CLI with the --profile option (e.g. aws --profile saml ec2 describe-instances).
    # ----------------------------------------------------------------


    # Simple API example listing all S3 buckets:
    # ['your-lovely-bucket', ...]

1. ask you to fill in required identity provider url in the form of ``https://<fqdn>:<port>/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices``
2. open web browser to fulfil SSO authentication through your identity provider
3. retrieve attached AWS roles and ask you to choose role you would like to assume
4. provide a ``saml`` profile in ``/home/.aws/credentials`` filled with temporary credentials

At the end, you just need to use AWS cofigured ``saml`` profile to authenticate your ``awscli`` calls

.. code-block:: shell

    aws --profile saml ec2 describe-instances

OR

.. code-block:: shell

    AWS_PROFILE=saml aws ec2 describe-instances


Features
--------

* Authenticate through SAML identity provider in web browser
* Select among retrieved AWS roles you are allowed to assume
* Store temporary credentials in aws configuration files

Contributing
------------

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

License
-------

``awscli_saml_sso`` is open source software released under the `GNU GPLv3 <https://choosealicense.com/licenses/gpl-3.0>`_.
