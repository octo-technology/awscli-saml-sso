import base64
import configparser
import logging
import os
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from os.path import devnull
from pathlib import Path

import boto3
import click
from seleniumwire import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from logging.config import fileConfig
from pkg_resources import resource_filename

##########################################################################
# Variables

# awssamlhomepage: The AWS SAML start page that end the authentication process
awssamlhomepage = "https://signin.aws.amazon.com/saml"

# awssamlhomepage_wait_timeout: The delay in second we wait for awssamlhomepage
awssamlhomepage_wait_timeout = 120

# supported_browsers: Browsers kind supported by selenium webdriver
supported_browsers = ["CHROME", "FIREFOX"]

# supported_log_levels: Supported log levels used to override python logging default level
supported_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# default_log_level: Default python log level to configure when not user provided
default_log_level = "WARNING"

##########################################################################


@click.command()
@click.option("--log-level", envvar="ASS_LOG_LEVEL",
              type=click.Choice(supported_log_levels, case_sensitive=False),
              default=default_log_level,
              help=f"Configure python log level to print (default: {default_log_level})")
@click.version_option()
def main(log_level):
    os.environ["WDM_LOG_LEVEL"] = str(logging.getLevelName(log_level))
    fileConfig(resource_filename("awscli_saml_sso", "logger.cfg"), disable_existing_loggers=False, defaults={
        "log_level": log_level,
    })

    print("Please configure your identity provider url [https://<fqdn>:<port>/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices]:")
    idpentryurl = input()

    print("Try to find browser on operating system...")
    browser = _find_installed_browser()
    if not browser:
        raise RuntimeError(f"Unable to find browser install on operating system among {supported_browsers}")
    browser.get(idpentryurl)

    print("Waiting for AWS SAML homepage...", end="")
    request = browser.wait_for_request(awssamlhomepage, timeout=awssamlhomepage_wait_timeout)
    assertion = urllib.parse.unquote(str(request.body).split("=")[1])
    browser.quit()

    # Parse the returned assertion and extract the authorized roles
    awsroles = []
    root = ET.fromstring(base64.b64decode(assertion))
    for saml2attribute in root.iter("{urn:oasis:names:tc:SAML:2.0:assertion}Attribute"):
        if (saml2attribute.get("Name") == "https://aws.amazon.com/SAML/Attributes/Role"):
            for saml2attributevalue in saml2attribute.iter("{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue"):
                awsroles.append(saml2attributevalue.text)

    # Note the format of the attribute value should be role_arn,principal_arn
    # but lots of blogs list it as principal_arn,role_arn so let's reverse
    # them if needed
    for awsrole in awsroles:
        chunks = awsrole.split(",")
        if "saml-provider" in chunks[0]:
            newawsrole = chunks[1] + "," + chunks[0]
            index = awsroles.index(awsrole)
            awsroles.insert(index, newawsrole)
            awsroles.remove(awsrole)

    # If I have more than one role, ask the user which one they want,
    # otherwise just proceed
    print("")
    if len(awsroles) == 0:
        print("Your account is not associated to any role, can't continue.")
        sys.exit(0)
    else:
        i = 0
        print("Please choose the role you would like to assume:")
        for awsrole in awsroles:
            print("[", i, "]: ", awsrole.split(",")[0])
            i += 1

        if len(awsroles) == 1:
            print("Your account is associated to only one role which has been automatically selected.")
            selectedroleindex = 0
        else:
            print("Selection: ", end=" ")
            selectedroleindex = input()

        # Basic sanity check of input
        if int(selectedroleindex) > (len(awsroles) - 1):
            print("You selected an invalid role index, please try again")
            sys.exit(0)

        role_arn = awsroles[int(selectedroleindex)].split(",")[0]
        principal_arn = awsroles[int(selectedroleindex)].split(",")[1]

    # Use the assertion to get an AWS STS token using Assume Role with SAML
    client = boto3.client("sts")
    sts_response = client.assume_role_with_saml(RoleArn=role_arn, PrincipalArn=principal_arn, SAMLAssertion=assertion)

    # Write the AWS STS token into the AWS credential file
    aws_credentials_path = Path.home() / ".aws" / "credentials"

    # Read in the existing config file
    config = configparser.RawConfigParser()
    config.read(aws_credentials_path)

    # Put the credentials into a saml specific section instead of clobbering
    # the default credentials
    if not config.has_section("saml"):
        config.add_section("saml")

    config.set("saml", "aws_access_key_id", sts_response["Credentials"]["AccessKeyId"])
    config.set("saml", "aws_secret_access_key", sts_response["Credentials"]["SecretAccessKey"])
    config.set("saml", "aws_session_token", sts_response["Credentials"]["SessionToken"])
    config.set("saml", "aws_security_token", sts_response["Credentials"]["SessionToken"])

    # Write the updated config file
    with aws_credentials_path.open(mode="w+") as configfile:
        config.write(configfile)

    # Give the user some basic info as to what has just happened
    print("\n\n----------------------------------------------------------------")
    print("Your new access key pair has been stored in the AWS configuration file {0} under the saml profile.".format(
        aws_credentials_path))
    print("Note that it will expire at {0}.".format(sts_response["Credentials"]["Expiration"]))
    print("After this time, you may safely rerun this script to refresh your access key pair.")
    print(
        "To use this credential, call the AWS CLI with the --profile option (e.g. aws --profile saml ec2 describe-instances).")
    print("----------------------------------------------------------------\n\n")

    # Use the AWS STS token to list all of the S3 buckets
    s3 = boto3.client("s3",
                      aws_access_key_id=sts_response["Credentials"]["AccessKeyId"],
                      aws_secret_access_key=sts_response["Credentials"]["SecretAccessKey"],
                      aws_session_token=sts_response["Credentials"]["SessionToken"])
    response = s3.list_buckets()
    buckets = [bucket["Name"] for bucket in response["Buckets"]]

    print("Simple API example listing all S3 buckets:")
    print(buckets)


def _find_installed_browser():
    browser = None
    for browser_kind in supported_browsers:
        try:
            if browser_kind == "CHROME":
                browser = webdriver.Chrome(executable_path=ChromeDriverManager().install(), service_log_path=devnull)
            elif browser_kind == "FIREFOX":
                browser = webdriver.Firefox(executable_path=GeckoDriverManager().install(), service_log_path=devnull)
            else:
                raise ValueError(f"Unsupported \"{browser_kind}\" webdriver browser")
            break
        except Exception as e:
            logging.debug(f"Exception occurred while loading {browser_kind}.", e)
    return browser


if __name__ == "__main__":
    main()
