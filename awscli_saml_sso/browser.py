import urllib.parse
from seleniumwire import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver import Chrome
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementNotInteractableException
import tempfile
from awscli_saml_sso.config_parser import CustomConfigParser
from urllib.parse import urlparse

# awssamlhomepage: The AWS SAML start page that end the authentication process
awssamlhomepage = "https://signin.aws.amazon.com/saml"

# navigation_timeout: The delay in seconds we wait page changes
# must be high enough for awssamlhomepage
navigation_timeout = 90

ignored_exceptions = (NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException,)

failure_message = 'please try it all again...\nYou can disable automatic input by appending --use-browser'

def start_chrome_browser(show_browser: bool):
    browser = None
    options = ChromeOptions()
    # arguments documentation
    # https://gist.github.com/ntamvl/4f93bbb7c9b4829c601104a2d2f91fe5
    if not show_browser:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--window-position=0,0")
    options.add_argument("--window-size=1024,768")
    options.add_argument("--disable-notifications")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
    print(f"⚙️ Starting{'' if show_browser else ' headless'} browser")
    print("\n⚠️ If you get a WARNING about chromedriver version please run: awscli_saml_sso --get-chrome-driver\n")
    browser = webdriver.Chrome(options=options)
    if not browser:
        raise SystemExit(f"🛑 Unable to find Google Chrome, please install it then run: awscli_saml_sso --get-chrome-driver")
    else:
        return browser

    
def loop_input_password(browser: Chrome, idp_password: str, password_elem):
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


def handle_code(browser: Chrome, element):
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


def handle_password_and_or_mfa(browser: Chrome,
                               config_parser: CustomConfigParser,
                               idp_nickname: str,
                               use_stored: bool):
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
        # get the password and enter it
        idp_password = config_parser.get_password(idp_nickname, use_stored)
        loop_input_password(browser, idp_password, next_elem)
        handle_password_and_or_mfa(browser, config_parser, idp_nickname, use_stored)

    elif next_elem.get_attribute('id') == "passwordError":
        save_page(browser.page_source, "error_incorrect_passwd")
        raise SystemExit("❌ Your password is incorrect, " + failure_message)

    elif next_elem.get_attribute('id') == "usernameError":
        save_page(browser.page_source, "error_unknown_email")
        raise SystemExit("❌ Your email is not known for the identity provider, " + failure_message)
    
    handle_after_mfa(browser)


def handle_after_mfa(browser: Chrome):
    try:
        # in case improve connection shows up
        next_elem = WebDriverWait(browser, navigation_timeout/10, ignored_exceptions=ignored_exceptions).until(
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
                            idp_nickname: str=None,
                            use_stored: bool=False,
                            use_browser: bool=False):
    config_parser = CustomConfigParser()
    idp_nickname, idpentryurl = config_parser.get_idp_url(idp_nickname)
    browser = start_chrome_browser(show_browser=show_browser) 

    try:
        visit_url_host_first=False
        url = idpentryurl
        if visit_url_host_first:
            # load the host of the IDP page
            parsing = urlparse(idpentryurl)
            url = f'{parsing.scheme}://{parsing.netloc}'
            print(f'🌐 Visiting {url} first')
        browser.get(url)
        try:
            if not use_browser:
                # wait the username element
                login_elem = WebDriverWait(browser, navigation_timeout, ignored_exceptions=ignored_exceptions).until(
                    EC.presence_of_element_located((By.NAME, "loginfmt")))
                login_elem.click()
                # get the login and enter it
                idp_login = config_parser.get_login(idp_nickname, use_stored)
                login_elem.send_keys(idp_login + Keys.ENTER)
                # handle pasword and/or MFA directly in case of passwordless
                handle_password_and_or_mfa(browser, config_parser, idp_nickname, use_stored)

            if visit_url_host_first:
                # load the IDP page now that we are authenticated
                browser.get(idpentryurl)

            try:
                # last step: wait till AWS SAML homepage displays and return assertion
                request = browser.wait_for_request(awssamlhomepage, timeout=navigation_timeout)
                assertion = urllib.parse.unquote(str(request.body).split("=")[1])
                return assertion, idp_nickname
            except TimeoutException:
                save_page(browser.page_source, "error_timeout")
                raise SystemExit(f"❌ Could not complete authentication within {navigation_timeout} seconds, " + failure_message)
            
        except TimeoutException:
            save_page(browser.page_source, "error_login_elem")
            raise SystemExit(f"❌ Could not get login element from {idpentryurl}, check the URL and " + failure_message)

    except Exception as e:
        save_page(browser.page_source, "error_unknown")
        raise e
    
    finally:
        # close the headless browser in all circumstances
        print("🗑️ Closing browser")
        browser.quit()
