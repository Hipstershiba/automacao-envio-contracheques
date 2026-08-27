# IMPORTS
from rich import print, inspect
from rich.traceback import install
install()

from models.dimensa_api import DimensaAPI
from auth.dimensa_auth import obter_token_dimensa
import models.config
from utils.log_manager import LogManager

def main():
    logger = LogManager()
    logger.start()
    bearer_token = obter_token_dimensa(navegador="edge")
    api_url = "https://api.assina.rbm.digital/api"
    dimensa = DimensaAPI(auth_token=bearer_token, base_url=api_url)
    print(dimensa.get_signatories())
    logger.stop()

if __name__ == "__main__":
    main()