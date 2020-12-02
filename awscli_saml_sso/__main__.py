import sys
from pathlib import Path

import boto3
import configparser
import base64
import xml.etree.ElementTree as ET
from os.path import expanduser, devnull

from time import sleep

import click
from selenium import webdriver
from webdriver_manager.firefox import GeckoDriverManager

##########################################################################
# Variables

# awssamlhomepage: The AWS SAML start page that end the authentication process
awssamlhomepage = "https://signin.aws.amazon.com/saml"


##########################################################################

@click.command()
@click.version_option()
def main(args=None):
    print("Please configure your identity provider url [https://<fqdn>:<port>/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices]:")
    idpentryurl = input()

    print("Waiting for AWS SAML homepage...", end="")
    browser = webdriver.Firefox(executable_path=GeckoDriverManager().install(), service_log_path=devnull)
    browser.implicitly_wait(30)
    browser.get(idpentryurl)
    while browser.current_url != awssamlhomepage:
        print(".", end="")
        sleep(1)
    print()
    assertion = browser.find_element_by_css_selector("input[name=\"SAMLResponse\"]").get_property("value")
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
    if len(awsroles) > 1:
        i = 0
        print("Please choose the role you would like to assume:")
        for awsrole in awsroles:
            print("[", i, "]: ", awsrole.split(",")[0])
            i += 1
        print("Selection: ", end=" ")
        selectedroleindex = input()

        # Basic sanity check of input
        if int(selectedroleindex) > (len(awsroles) - 1):
            print("You selected an invalid role index, please try again")
            sys.exit(0)

        role_arn = awsroles[int(selectedroleindex)].split(",")[0]
        principal_arn = awsroles[int(selectedroleindex)].split(",")[1]
    else:
        role_arn = awsroles[0].split(",")[0]
        principal_arn = awsroles[0].split(",")[1]

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


if __name__ == "__main__":
    main()
