import urllib.parse
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementNotInteractableException, ElementClickInterceptedException, NoSuchWindowException
from selenium.webdriver.remote.webelement import WebElement
import tempfile
from awscli_saml_sso.config_parser import CustomConfigParser
from urllib.parse import urlparse
from enum import Enum
import importlib
from time import sleep
from awscli_saml_sso import __path__ as module_path
from pathlib import Path

# awssamlhomepage: The AWS SAML start page that end the authentication process
awssamlhomepage = "https://signin.aws.amazon.com/saml"

# supported_browsers: Browsers kind supported by selenium webdriver
class SupportedBrowsers(Enum):
    EDGE = {"name": "Edge",
            "browser_class": "seleniumwire.webdriver.Edge",
            "driver_class": "webdriver_manager.microsoft.EdgeChromiumDriverManager",
            "options_class": "selenium.webdriver.edge.options.Options",
            "service_class": "selenium.webdriver.edge.service.Service",
            "enabled": True}
    CHROME = {"name": "Chrome",
              "browser_class": "seleniumwire.webdriver.Chrome",
              "driver_class": "webdriver_manager.chrome.ChromeDriverManager",
              "options_class": "selenium.webdriver.chrome.options.Options",
              "service_class": "selenium.webdriver.chrome.service.Service",
              "enabled": False}
    FIREFOX = {"name": "Firefox",
              "browser_class": "seleniumwire.webdriver.Firefox",
              "driver_class": "webdriver_manager.firefox.GeckoDriverManager",
              "options_class": "selenium.webdriver.FirefoxOptions",
              "service_class": "selenium.webdriver.FirefoxService",
              "enabled": False}
    
def import_class(class_path):
    _module = importlib.import_module(".".join(class_path.split(".")[:-1]))
    _class = getattr(_module, class_path.split(".")[-1])
    return _class


def mysleep():
    sleep(0.2)

# navigation_timeout: The delay in seconds we wait page changes
# must be high enough for awssamlhomepage
navigation_timeout = 90

ignored_exceptions = (NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException,)

failure_message = 'please try it all again...\nYou can check browser rendering by appending --show-browser'

def start_browser(show_browser: bool, browser_kind: SupportedBrowsers, user_data_dir: str):
    browser = None
    _options_class = import_class(browser_kind.value["options_class"])
    options = _options_class()

    # arguments documentation
    # https://gist.github.com/ntamvl/4f93bbb7c9b4829c601104a2d2f91fe5
    # https://github.com/GoogleChrome/chrome-launcher/blob/main/docs/chrome-flags-for-tools.md
    # https://peter.sh/experiments/chromium-command-line-switches/
    if not show_browser:
        options.add_argument("--headless=new")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument(f"--password-store=basic")
    options.add_argument("--window-position=0,0")
    options.add_argument("--window-size=768,768")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--remote-debugging-pipe")
    print(f"⚙️ Starting{'' if show_browser else ' headless'} {browser_kind.value['name']} browser")
    _service_class = import_class(browser_kind.value["service_class"])
    _driver_class = import_class(browser_kind.value["driver_class"])
    _browser_class = import_class(browser_kind.value["browser_class"])

    if browser_kind == SupportedBrowsers.EDGE:
        browser = _browser_class(
            service=_service_class(
                executable_path=_driver_class(
                    url="https://msedgedriver.microsoft.com/",
                    latest_release_url="https://msedgedriver.microsoft.com/LATEST_RELEASE"
                ).install()),
            options=options
            )
    else:
        browser = _browser_class(service=_service_class(_driver_class().install()), options=options)

    if not browser:
        raise SystemExit(f"🛑 Unable to find browser {browser.value}, please install it first")
    else:
        return browser

    
def loop_input_password(browser, idp_password: str, password_elem):
    mysleep()
    try:
        if password_elem is None:
            # wait till page changes and displays the password element
            password_elem = WebDriverWait(browser, navigation_timeout).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='password']")))
        password_elem.clear()
        password_elem.click()
        # get the password and enter it
        password_elem.send_keys(idp_password)
        password_button = WebDriverWait(browser, navigation_timeout).until(
            EC.any_of(EC.presence_of_element_located((By.XPATH, "//input[@value='Sign in']")),
                      EC.presence_of_element_located((By.XPATH, "//input[@value='Se connecter']"))))
        password_button.click()
    except StaleElementReferenceException as e:
        print("🔄 Trying again")
        loop_input_password(browser, idp_password, None)


def handle_code(browser, element):
    mysleep()
    element.click()
    # prompt for the MFA code and enter it
    mfa_code = input("⌨️ Please enter MFA code: ")
    element.send_keys(mfa_code + Keys.ENTER)
    try:
        # wait 1 second at most and fail if MFA code is rejected
        WebDriverWait(browser, 1).until(EC.presence_of_element_located((By.ID, "idSpan_SAOTCC_Error_OTC")))
        save_page(browser.page_source, "error_wrong_code")
        raise SystemExit("❌ Your MFA code is wrong, " + failure_message)
    except TimeoutException:
        # after 1 second with no rejection, it should mean MFA code is accepted
        pass
    print("✅ MFA code is correct, waiting for AWS SAML homepage...")


def handle_password_and_or_mfa(browser,
                               config_parser: CustomConfigParser,
                               idp_nickname: str,
                               idp_password: str):
    mysleep()
    # wait till page changes and shows passowrd invite or displays the MFA code element
    next_elem = WebDriverWait(browser, navigation_timeout, ignored_exceptions=ignored_exceptions).until(
        EC.any_of(EC.presence_of_element_located((By.NAME, "otc")),
                    EC.presence_of_element_located((By.ID, "idRichContext_DisplaySign")),
                    EC.presence_of_element_located((By.ID, "idRemoteNGC_DisplaySign")),
                    EC.presence_of_element_located((By.ID, "passwordError")),
                    EC.presence_of_element_located((By.ID, "usernameError")),
                    EC.presence_of_element_located((By.XPATH, "//input[@type='password' and @tabindex='0']")),
                    ))
    
    if next_elem.get_attribute('name') == "otc":
        handle_code(browser, next_elem)

    elif next_elem.get_attribute('id') in ["idRichContext_DisplaySign", "idRemoteNGC_DisplaySign"]:
        print(f'⌨️ Enter this on you authentication app, then wait : {next_elem.text}')

    elif next_elem.get_attribute('type') == "password":
        # enter the password
        loop_input_password(browser, idp_password, next_elem)
        handle_password_and_or_mfa(browser, config_parser, idp_nickname, idp_password)

    elif next_elem.get_attribute('id') == "passwordError":
        save_page(browser.page_source, "error_incorrect_passwd")
        raise SystemExit("❌ Your password is incorrect, " + failure_message)

    elif next_elem.get_attribute('id') == "usernameError":
        save_page(browser.page_source, "error_unknown_email")
        raise SystemExit("❌ Your email is not known for the identity provider, " + failure_message)
    
    try:
        # in case any AWS page shows up, no need to perform after mfa handling
        WebDriverWait(browser, navigation_timeout/15, ignored_exceptions=ignored_exceptions).until(
            EC.url_contains("aws.amazon.com"))
    except TimeoutException:
        handle_after_mfa(browser)


def handle_after_mfa(browser):
    mysleep()
    try:
        # in case improve connection shows up
        next_elem = WebDriverWait(browser, navigation_timeout/15, ignored_exceptions=ignored_exceptions).until(
            EC.any_of(EC.presence_of_element_located((By.LINK_TEXT, "Not now")),
                    EC.presence_of_element_located((By.LINK_TEXT, "Plus tard")),
                    EC.presence_of_element_located((By.XPATH, "//input[@value='Non']")),
                    EC.presence_of_element_located((By.XPATH, "//input[@value='No']")),
                    EC.presence_of_element_located((By.ID, "idDiv_SAASDS_Title")),
                    ))

        if next_elem.get_attribute('id') == "idDiv_SAASDS_Title":
            save_page(browser.page_source, "error_request_denied")
            raise SystemExit("❌ Request was denied, could be unsuccessfull MFA, " + failure_message)
        else:
            next_elem.click()
    except TimeoutException: 
        pass


def save_page(page_source: str, prefix: str):
    # usage example : save_page(browser.page_source, "password")
    _, temp_file_name = tempfile.mkstemp(prefix=prefix + '_', suffix='.html', text=True)
    with open(temp_file_name, "w", encoding='utf-8') as f:
        f.write(page_source)
        print(f'💾 Saved page {prefix} to {temp_file_name}, you can send it to support')


def login_and_get_assertion(show_browser: bool=False,
                            use_browser: bool=False,
                            idp_nickname: str=None,
                            use_stored: bool=False):
    config_parser = CustomConfigParser()
    idp_nickname, idpentryurl = config_parser.get_idp_url(idp_nickname)
    mysleep()
    enabled_supported_browsers = [sb for sb in SupportedBrowsers if sb.value["enabled"]]
    browser_name, user_data_dir, first_time = config_parser.get_browser_details(
        idp_nickname=idp_nickname,
        supported_browsers=enabled_supported_browsers)
    browser_kind = [bk for bk in SupportedBrowsers if bk.value["name"] == browser_name][0]
    mysleep()
    if not use_browser:
        idp_login = config_parser.get_login(idp_nickname, use_stored)
        mysleep()
        idp_password = config_parser.get_password(idp_nickname, use_stored)
        mysleep()
    browser = start_browser(show_browser=True if first_time or use_browser else show_browser,
                            browser_kind=browser_kind,
                            user_data_dir=user_data_dir)
    
    idp_is_microsoft = True if urlparse(idpentryurl).netloc.endswith("microsoft.com") else False
    
    def get_next_elem():
        return WebDriverWait(browser, navigation_timeout, ignored_exceptions=ignored_exceptions).until(
            EC.any_of(EC.presence_of_element_located((By.NAME, "loginfmt")),
                      EC.presence_of_element_located((By.XPATH, f"//div[@data-test-id='{idp_login}']")),
                      EC.url_contains("aws.amazon.com")
                      ))

    try:
        if first_time and idp_is_microsoft:
            browser.get(f"file://{Path(module_path[0]) / 'first_time.html'}")
            radio_button = browser.find_element(By.ID, "radio")
            WebDriverWait(browser, navigation_timeout).until(EC.element_to_be_selected(radio_button))
            mysleep()
        
        browser.get(idpentryurl)
        mysleep()

        try:
            if not use_browser:
                # wait until
                # screen shows already known logins OR
                # screen shows the input box with the login element OR
                # screen goes directly to AWS page because every thing is already setup
                next_elem = get_next_elem()
                if isinstance(next_elem, WebElement):
                    # in case screen does not go directlty to AWS page
                    mysleep()
                    try:
                        # in case of login screen
                        next_elem.click()
                        mysleep()
                        next_elem = get_next_elem()
                        # in case of input box, enter the login
                        if next_elem.get_attribute('name') == 'loginfmt':
                            next_elem.send_keys(idp_login + Keys.ENTER)
                    except ElementClickInterceptedException:
                        # this happens when login screen is skipped and password or mfa screen is shown
                        pass
                    if EC.presence_of_element_located((By.XPATH, f"//div[@data-test-id='{idp_login}']")):
                        # if screen shows again known logins, click on it again
                        next_elem.click()
                        mysleep()
                        next_elem = get_next_elem()
                    if isinstance(next_elem, WebElement):
                        # if we are still not directed, handle pasword and/or MFA directly in case of passwordless
                        handle_password_and_or_mfa(browser, config_parser, idp_nickname, idp_password)

            try:
                WebDriverWait(browser, navigation_timeout, ignored_exceptions=ignored_exceptions).until(
                    EC.url_contains("aws.amazon.com"))
                # last step: wait until AWS SAML homepage displays and return assertion
                request = browser.wait_for_request(awssamlhomepage, timeout=navigation_timeout)
                assertion = urllib.parse.unquote(str(request.body).split("=")[1])
                return assertion, idp_nickname
            except TimeoutException:
                save_page(browser.page_source, "error_timeout")
                raise SystemExit(f"❌ Could not complete authentication within {navigation_timeout} seconds, " + failure_message)
        
        except TimeoutException:
            save_page(browser.page_source, "error_login_elem")
            raise SystemExit(f"❌ Could not get login element from {idpentryurl}, check the URL and " + failure_message)

    except NoSuchWindowException:
        raise SystemExit(f"🤷 Seems somebody closed the browser")

    except Exception as e:
        save_page(browser.page_source, "error_unknown")
        raise e
    
    finally:
        # close the headless browser in all circumstances
        print("🗑️ Closing browser")
        browser.quit()
