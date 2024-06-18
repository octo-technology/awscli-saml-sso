import base64
import configparser
import logging
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import boto3
import click
from logging.config import fileConfig
from pkg_resources import resource_filename
from h2.exceptions import StreamClosedError
import threading
import traceback

from awscli_saml_sso.driver import get_google_chrome_driver
from awscli_saml_sso.browser import login_and_get_assertion

##########################################################################
# Variables

# supported_log_levels: Supported log levels used to override python logging default level
supported_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# default_log_level: Default python log level to configure when not user provided
default_log_level = "WARNING"


def custom_hook(args):
    # ignore Exception in thread Http2SingleStreamLayer of type h2.exceptions.StreamClosedError
    if not isinstance(args.exc_value, StreamClosedError):
        print(f"Exception {args.exc_type} in thread {args.thread}:")
        traceback.print_tb(args.exc_traceback, file=sys.stdout)

threading.excepthook = custom_hook

##########################################################################


@click.command()
@click.option("--log-level", envvar="ASS_LOG_LEVEL",
              type=click.Choice(supported_log_levels, case_sensitive=False),
              default=default_log_level,
              help=f"Configure python log level to print (default: {default_log_level})")
@click.option("--endpoint-url", envvar="ASS_ENDPOINT_URL",
              help="Override AWS API endpoint url (mainly for testing purpose)")
@click.option('--show-browser', is_flag=True, help="Do not use headless mode")
@click.option('--use-browser', is_flag=True, help="Input username and password in browser")
@click.option('--idp-nickname', help="Nickname of the identity provider URL")
@click.option('--use-stored', is_flag=True, help="Use stored values for username and password without prompt")
@click.option('--get-chrome-driver', is_flag=True, help="Install Google Chrome driver and exit")
@click.option('--role-selection', type=int, default=-1, help="Index of the role to select among available roles")
@click.version_option()

def main(log_level,
         endpoint_url,
         show_browser,
         use_browser,
         idp_nickname,
         use_stored,
         get_chrome_driver,
         role_selection):
    if get_chrome_driver:
        get_google_chrome_driver()
        return

    os.environ["WDM_LOG_LEVEL"] = str(logging.getLevelName(log_level))
    fileConfig(resource_filename("awscli_saml_sso", "logger.cfg"), disable_existing_loggers=False, defaults={
        "log_level": log_level,
    })

    if use_browser:
        show_browser = True

    assertion, idp_nickname = login_and_get_assertion(show_browser=show_browser,
                                                      idp_nickname=idp_nickname,
                                                      use_stored=use_stored,
                                                      use_browser=use_browser)

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
        print("❌ Your account is not associated to any role, can't continue.")
        sys.exit(0)
    else:
        i = 0
        print("⌨️ Please choose the role you would like to assume:")
        for awsrole in awsroles:
            print("[", i, "]: ", awsrole.split(",")[0])
            i += 1

        if len(awsroles) == 1:
            print("✅ Your account is associated to only one role which has been automatically selected.")
            selectedroleindex = 0
        else:
            print("⌨️ Selection: ", end=" ")
            if role_selection >= 0:
                selectedroleindex = role_selection
            else:
                selectedroleindex = input()

        # Basic sanity check of input
        if int(selectedroleindex) > (len(awsroles) - 1):
            print("🔄 You selected an invalid role index, please try again")
            sys.exit(0)

        role_arn = awsroles[int(selectedroleindex)].split(",")[0]
        principal_arn = awsroles[int(selectedroleindex)].split(",")[1]

    # Use the assertion to get an AWS STS token using Assume Role with SAML
    client = boto3.client("sts", endpoint_url=endpoint_url)
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
    print("\n----------------------------------------------------------------")
    print("Your new access key pair has been stored in the AWS configuration file {0} under the saml profile.".format(
        aws_credentials_path))
    print("Note that it will expire at {0}.".format(sts_response["Credentials"]["Expiration"]))
    print("After this time, you may safely rerun this script to refresh your access key pair.")
    print(
        "To use this credential, call the AWS CLI with the --profile option (e.g. aws --profile saml ec2 describe-instances).")
    print("----------------------------------------------------------------\n")

    # Use the AWS STS token to get caller identity
    s3 = boto3.client("sts",
                      aws_access_key_id=sts_response["Credentials"]["AccessKeyId"],
                      aws_secret_access_key=sts_response["Credentials"]["SecretAccessKey"],
                      aws_session_token=sts_response["Credentials"]["SessionToken"],
                      endpoint_url=endpoint_url)
    response = s3.get_caller_identity()
    print(f"UserId = {response['UserId']}")
    print(f"Arn = {response['Arn']}")
    print("----------------------------------------------------------------\n")

    print("✅ Success !")
    next_time_args = [f'--idp-nickname={idp_nickname}', f'--role-selection={selectedroleindex}', '--use-stored']
    if set(sys.argv).union(set(next_time_args)) != sys.argv:
        # print recommendation for next time use if above switches were not all used
        next_time = ' '.join([os.path.basename(sys.argv[0])] +
                            [arg for arg in sys.argv[1:]
                            if
                            arg not in next_time_args and
                            arg not in ['--show-browser']] +
                            next_time_args)
        print("💡 Next time you can go faster by using:")
        print(next_time)


if __name__ == "__main__":
    main()
