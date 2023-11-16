from pathlib import Path
import configparser
import getpass
from subprocess import Popen, PIPE, STDOUT
import keyring

class CustomConfigParser():

    def __init__(self):
        self.credentials_file = Path(Path.home(), ".awscli_saml_sso_credentials")
        self.credentials_file.touch(mode=0o600, exist_ok=True)
        with open(self.credentials_file.as_posix(), "r") as fp:
            self.credentials = configparser.ConfigParser()
            self.credentials.read_file(fp)

    def store(self):
        with open(self.credentials_file.as_posix(), "w") as fp:
            self.credentials.write(fp)

    def new_idp_url(self):
        prompt = "Give a nickame for this new identity provider: "
        idp_nickname = input(prompt)
        idp_url = input("Identity provider URL: ")
        self.store_idp_url(idp_nickname=idp_nickname, idp_url=idp_url)
        return idp_nickname, idp_url
    
    def get_idp_url_for_idp_nickname(self, idp_nickname):
        sections = self.credentials.sections()
        if len(sections) > 0 and idp_nickname in self.credentials:
            print(f'{idp_nickname} is already known, cool')
            return idp_nickname, self.credentials[idp_nickname]["idp_url"]
        else:
            print(f'No such IDP nickname as {idp_nickname}')
            return self.get_idp_url()

    def get_idp_url(self, idp_nickname=None):
        if idp_nickname is not None:
            return self.get_idp_url_for_idp_nickname(idp_nickname)
        prompt = "Please enter your identity provider url of the form https://<fqdn>:<port>/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices"
        sections = self.credentials.sections()
        if len(sections) == 0:
            print(prompt)
            return self.new_idp_url()
        else:
            print("You have stored these identity providers")
            print()
            for i, idp in enumerate(sections):
                section = self.credentials[idp]
                print(f"[{i}] {idp}")
            print()
            choice_text = 'choose 0'
            if len(sections) > 1:
                choice_text = f'choose between 0 and {len(sections)-1}'
            idp_index = input(f"Please {choice_text} or press + to add a new IDP [0]:")
            if idp_index == '':
                idp_index = 0
            if idp_index == '+':
                return self.new_idp_url()
            idp_nickname = sections[int(idp_index)]
            stored_idp_url = self.credentials[idp_nickname]["idp_url"]
            input_idp_url = input(f"Identity provider URL [{stored_idp_url}]: ")
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
              print(f'Entering stored login {stored_login}')
              return stored_login
       input_login = input(f"Login [{stored_login}]: ")
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
              print(f'Entering stored password {"*" * len(stored_password)}')
              return stored_password
        if stored_password is None:
            stored_password = ''
        displayed_password = "*" * len(stored_password)
        input_password = getpass.getpass(f"Password [{displayed_password}]: ")
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
