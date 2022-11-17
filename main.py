import configparser
import codecs

config = configparser.ConfigParser()
config.read_file(codecs.open("configs/_main.cfg"))