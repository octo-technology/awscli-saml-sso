import sys
import re
import subprocess
import requests
import platform
import urllib.request
from os import environ

def get_google_chrome_driver():
    _platform = sys.platform

    try:
        if _platform == "linux":
            binary = "google-chrome"
        elif _platform == "darwin":
            print("You are on darwin, please run: brew install --cask chromedriver")
            raise SystemExit
        else:
            print("Cannot run on {_platform}, only on linux and darwin")
            raise SystemExit
        full_version = subprocess.check_output([binary, "--version"])

    except FileNotFoundError as e:
        print("Please install Google Chrome browser")
        raise SystemExit

    regexp = r'^Google Chrome ([0-9][0-9][0-9])\..*'
    match = re.match(regexp, full_version.decode())
    if match is None:
        print("Could not get your Google Chrome version")
        raise SystemExit
    else:
        major_version = match.group(1)

    # TODO read this instead : https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json
    driver_version_base_url = environ.get("CHROME_DRIVER_VERISON_BASE_URL", "googlechromelabs.github.io/chrome-for-testing")
    driver_version_url = f"https://{driver_version_base_url}/LATEST_RELEASE_{major_version}"
    response = requests.get(driver_version_url)
    if response.ok:
        driver_version = response.text
    else:
        print("Could not get driver version suitbale for your Google Chrome version")
        raise SystemExit

    os = "linux"
    arch = "64"
    if _platform == "darwin":
        os = "mac-"
        if platform.machine() == "x86_64":
            arch = "x64"
        else:
            arch = "arm64"

    driver_base_url = environ.get("CHROME_DRIVER_BASE_URL", "storage.googleapis.com/chrome-for-testing-public")
    driver_url = f"https://{driver_base_url}/{driver_version}/{os}{arch}/chromedriver-{os}{arch}.zip"

    temporary_zip_file = "/tmp/chromedriver.zip"
    driver_final_location = "/usr/local/bin/chromedriver"
    try:
        urllib.request.urlretrieve(driver_url, temporary_zip_file, )
    except Exception as e:
        print(f"Could not download Google Chrome driver from {driver_url}: {str(e)}")
        raise SystemExit

    import zipfile
    with zipfile.ZipFile(temporary_zip_file,"r") as zip_ref:
        zip_ref.extractall("/tmp")

    print(f"We need admin privileges to place driver in {driver_final_location}")
    move_driver_command = subprocess.run(["sudo",
                                        "mv", f"/tmp/chromedriver-{os}{arch}/chromedriver",
                                        driver_final_location])
    if move_driver_command.returncode != 0:
        print(f"Could not place driver in {driver_final_location}")
        raise SystemExit

    chmod_driver_command = subprocess.run(["sudo", "chmod", "a+x", driver_final_location])
    if chmod_driver_command.returncode != 0:
        print(f"Could not make {driver_final_location} executable")
        raise SystemExit
    else:
        print("Success !")
        print(f"Google Chrome Driver was successfully downloaded from {driver_url} and placed in {driver_final_location}")
