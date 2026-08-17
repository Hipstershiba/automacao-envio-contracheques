import os
from pathlib import Path
import yaml

class AppConfig:
    config_path = "./config/config.yml"
    default_input_path = "./documents/input"
    default_output_path = "./documents/output"
    default_api_url = "https://api.assina.rbm.digital/api"

    def __init__(self):
        self._input_path = None
        self._output_path = None
        self._api_url = None

    @property
    def input_path(self):
        return self._input_path

    @input_path.setter
    def input_path(self, path:Path):
        if not os.path.exists(path):
            raise ValueError(f"Input path {path} does not exist")
        self._input_path = path
        self.__update_config()


    @property
    def output_path(self):
        return self._output_path

    @output_path.setter
    def output_path(self, path:Path):
        if not os.path.exists(path):
            raise ValueError(f"Output path {path} does not exist")
        self._output_path = path
        self.__update_config()

    @property
    def api_url(self):
        return self._api_url

    @api_url.setter
    def api_url(self, url:str):
        if not url.startswith('http'):
            raise ValueError(f"API URL must start with 'https://'")
        self._api_url = url
        self.__update_config()

    # --- PRIVATE METHODS --- #
    def __create_default_config(self):
        config_data = {
            'paths': {
                'input_path': AppConfig.default_input_path,
                'output_path': AppConfig.default_output_path
            },
            'urls':{
                'api_url': AppConfig.default_api_url
            }
        }

        with open(AppConfig.config_path, 'w', encoding='utf-8') as config_file:
            yaml.safe_dump(config_data, config_file, default_flow_style=False, allow_unicode=True)

    def __update_config(self):
        with open(AppConfig.config_path, 'r', encoding='utf-8') as config_file:
            config = yaml.safe_load(config_file)
        config['paths']['input_path'] = self.input_path
        config['paths']['output_path'] = self.output_path
        config['urls']['api_url'] = self._api_url
        with open(AppConfig.config_path, 'w', encoding='utf-8') as config_file:
            yaml.safe_dump(config, config_file, default_flow_style=False, allow_unicode=True)

    # --- PUBLIC METHODS --- #
    def load(self):
        if not os.path.exists(AppConfig.config_path):
            self.__create_default_config()
        with open(AppConfig.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            self._input_path = config['paths']['input_path']
            self._output_path = config['paths']['output_path']
            self._api_url = config['urls']['api_url']

