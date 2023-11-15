
import configparser, os


class ImCompConfig:
    """
        Program configuration
    """    

    @staticmethod
    def user_config():
        config = configparser.ConfigParser()
        config_file = os.path.expanduser('~/.imcomp.cfg')
        if os.path.isfile(config_file): 
            config.read([config_file])
        return config
