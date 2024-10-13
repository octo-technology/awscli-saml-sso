from pathlib import Path
import configparser
import getpass
from subprocess import Popen, PIPE, STDOUT
import keyring
from hashlib import md5
from urllib.parse import urlparse

idp_url_prompt = "⌨️ Please enter your identity provider url of the form https://<fqdn>:<port>/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices"
idp_nickname_prompt = "⌨️ Give a nickame for this new identity provider: "

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except AttributeError:
        return False
    

CONFIG_FOLDER = Path(Path.home(), ".awscli_saml_sso")
DEPRECATED_CREDENTIALS_FILE = Path(Path.home(), ".awscli_saml_sso_credentials")

class CustomConfigParser():

    def __init__(self):
        CONFIG_FOLDER.mkdir(exist_ok=True)
        self.credentials_file = CONFIG_FOLDER / "credentials"
        if DEPRECATED_CREDENTIALS_FILE.exists():
            DEPRECATED_CREDENTIALS_FILE.rename(self.credentials_file.as_posix())
        self.credentials_file.touch(mode=0o600, exist_ok=True)
        with open(self.credentials_file.as_posix(), "r") as fp:
            self.credentials = configparser.ConfigParser()
            self.credentials.read_file(fp)

    @classmethod
    def clean(self):
        if CONFIG_FOLDER.exists():
            CONFIG_FOLDER.rename(CONFIG_FOLDER.as_posix() + ".OLD")

    def store(self):
        with open(self.credentials_file.as_posix(), "w") as fp:
            self.credentials.write(fp)

    def store_browser_details(self, idp_nickname, browser_name, user_data_dir):
        self.credentials[idp_nickname]["browser_name"] = browser_name
        self.credentials[idp_nickname]["user_data_dir"] = user_data_dir
        self.store()

    def get_browser_details(self, idp_nickname, supported_browsers):
        if idp_nickname in self.credentials and "browser_name" in self.credentials[idp_nickname]:
            browser_name = self.credentials[idp_nickname]["browser_name"]
            user_data_dir = self.credentials[idp_nickname]["user_data_dir"]
            first_time = False if Path(user_data_dir).exists() else True
            return browser_name, user_data_dir, first_time
        
        selected_browser_kind = None
        for browser_kind in supported_browsers:
            print("⚠️ Please use a browser that is already installed on your system")
            if input(f"Do you want to use {browser_kind.value['name']} browser ? (y/n) ") == "y":
                selected_browser_kind = browser_kind.value
                break
        if selected_browser_kind == None:
            print("⚠️ You need to choose a browser")
            return self.get_browser_details(idp_nickname=idp_nickname, supported_browsers=supported_browsers)

        user_data_dir = CONFIG_FOLDER / "profile" / selected_browser_kind["name"] / md5(idp_nickname.encode('utf8')).hexdigest()
        user_data_dir.mkdir(parents=True, exist_ok=True)
        self.store_browser_details(idp_nickname, selected_browser_kind["name"], user_data_dir.as_posix())
        first_time = True
        return selected_browser_kind["name"], user_data_dir, first_time

    def new_idp_url(self, new_idp_nickname):
        idp_url = input(f"{idp_url_prompt} :")
        if not is_valid_url(idp_url):
            print("🔴 Your input does not look like a valid URL")
            return self.new_idp_url(new_idp_nickname)
        self.store_idp_url(idp_nickname=new_idp_nickname, idp_url=idp_url)
        return new_idp_nickname, idp_url
    
    def get_idp_url_for_idp_nickname(self, idp_nickname):
        sections = self.credentials.sections()
        if len(sections) > 0 and idp_nickname in self.credentials:
            print(f'✅ {idp_nickname} is already known, cool')
            return idp_nickname, self.credentials[idp_nickname]["idp_url"]
        else:
            print(f'❌ No such IDP nickname as {idp_nickname}')
            return self.get_idp_url()

    def get_idp_url(self, idp_nickname=None):
        if idp_nickname is not None:
            return self.get_idp_url_for_idp_nickname(idp_nickname)
        sections = self.credentials.sections()
        if len(sections) == 0:
            print("❗You don't have any stored identity provider, configure one now")
            new_idp_nickname = input(idp_nickname_prompt)
            return self.new_idp_url(new_idp_nickname)
        else:
            print("⤵️ You have stored these identity providers")
            print()
            for i, idp in enumerate(sections):
                section = self.credentials[idp]
                print(f"[{i}] {idp}")
            print()
            choice_text = 'choose 0'
            if len(sections) > 1:
                choice_text = f'choose between 0 and {len(sections)-1}'
            idp_index = input(f"⌨️ Please {choice_text} or press + to add a new IDP [0]:")
            try:
                if idp_index == '+':
                    new_idp_nickname = input(idp_nickname_prompt)
                    return self.new_idp_url(new_idp_nickname)
                if idp_index == '':
                    idp_index = 0
                elif int(idp_index) < 0 or int(idp_index) >= len(sections):
                    return self.get_idp_url()
            except:
                return self.get_idp_url()
            idp_nickname = sections[int(idp_index)]
            stored_idp_url = self.credentials[idp_nickname]["idp_url"]
            input_idp_url = input(f"⌨{idp_url_prompt} [{stored_idp_url}]: ")
            if input_idp_url == "":
                return idp_nickname, self.credentials[idp_nickname]["idp_url"]
            else:
                self.store_idp_url(idp_nickname=idp_nickname, idp_url=f'{input_idp_url}')
                return idp_nickname, input_idp_url

    def store_idp_url(self, idp_nickname, idp_url):
        self.credentials[idp_nickname] = {}
        self.credentials[idp_nickname]["idp_url"] = idp_url
        self.store()

    def get_login(self, idp_nickname, use_stored):
       stored_login = ""
       if idp_nickname in self.credentials and "login" in self.credentials[idp_nickname]:
          stored_login = self.credentials[idp_nickname]["login"]
          if use_stored and stored_login != "":
              print(f'⚙️ Entering stored login {stored_login}')
              return stored_login
       input_login = input(f"⌨️ Login [{stored_login}]: ")
       if input_login == "":
           if stored_login == "":
               return self.get_login(idp_nickname, use_stored=False)
           else:
               return stored_login
       else:
           self.store_login(idp_nickname=idp_nickname, login=input_login)
           return input_login

    def store_login(self, idp_nickname, login):
        if idp_nickname not in self.credentials:
            self.credentials[idp_nickname] = {}
        self.credentials[idp_nickname]["login"] = login
        self.store()

    def get_password(self, idp_nickname, use_stored):
#        p = Popen(["secret-tool", "lookup", "idp_nickname", idp_nickname], stdout=PIPE)
#        stored_password = p.stdout.read().decode('ascii') # remove trailing \n
        stored_password = keyring.get_password('idp_nickname', idp_nickname)
        if use_stored and stored_password is not None:
              print(f'⚙️ Entering stored password {"*" * len(stored_password)}')
              return stored_password
        if stored_password is None:
            stored_password = ""
        displayed_password = "*" * len(stored_password)
        input_password = getpass.getpass(f"⌨️ Password (type anything if you are passwordless) [{displayed_password}]: ")
        if input_password == "":
            if stored_password == "":
                return self.get_password(idp_nickname, use_stored=False)
            else:
                return stored_password
        else:
            self.store_password(idp_nickname=idp_nickname, password=input_password)
            return input_password

    def store_password(self, idp_nickname, password):
#        p = Popen(["secret-tool", "store", "--label='awscli_saml_sso'",
#                   "idp_nickname", idp_nickname], stdout=PIPE, stdin=PIPE, stderr=PIPE)
#        p.communicate(input=password.encode('ascii'))
        keyring.set_password('idp_nickname', idp_nickname, password)
