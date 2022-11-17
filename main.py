import configparser
import codecs

config = configparser.ConfigParser()
config.read_file(codecs.open("configs/_main.cfg"))

if __name__ == '__main__':
    import API.account
    data = API.account.get_account_data(config["Settings"]["token"])
    print("Username", data.username, sep=": ")
    print("ID", data.id, sep=": ")
    print("Balance", data.balance, sep=": ")
    print("Active sales", data.active_sales, sep=": ")
    print("PHPSESSID", data.session_id, sep=": ")
    print("CSRF TOKEN", data.csrf_token, sep=": ")
    print("Last update", data.last_update, sep=": ")
    print("App Data", data.app_data, sep=": ")