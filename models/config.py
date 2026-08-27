from dataclasses import dataclass, asdict
import pathlib
import yaml

@dataclass
class AppConfigData:
    input_path: str = "./documents/input"
    output_path: str = "./documents/output"
    api_url: str = "https://api.assina.rbm.digital/api"

class AppConfig:
    
    def __init__(self, config_path:str="./config/config.yml"):
        self.config_path = pathlib.Path(config_path)
        self.data: AppConfigData = self._load()

    # --- PRIVATE METHODS --- #
    def _load(self) -> AppConfigData:
        if not self.config_path.exists():
            data = AppConfigData()
            self.save(data)
            return data

        with self.config_path.open('r', encoding='utf-8') as file:
            raw = yaml.safe_load(file)
        
        try:
            return AppConfigData(**raw)
        except Exception as e:
            raise ValueError(f"Erro ao carregar configurações: {e}")


    # --- PUBLIC METHODS --- #
    def save(self, data: AppConfigData | None = None) -> None:
        if data is not None:
            self.data = data
        self.config_path.parent.mkdir(exist_ok=True)
        with self.config_path.open('w', encoding='utf-8') as file:
            yaml.safe_dump(asdict(self.data), file, default_flow_style=False, allow_unicode=True)
