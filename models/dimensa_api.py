import requests
import pathlib
import logging


class DimensaAPI:
    def __init__(self, base_url:str="https://api.assina.rbm.digital/api", auth_token:str=""):
        self.auth_token = auth_token
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})    

    def get_signatory(self, cpf:str):
        url = f"{self.base_url}/signatario/find"
        data = {"cpfCnpj": cpf}
        try:
            response = self.session.post(url, data=data)
            logging.debug(response.json())
            response.raise_for_status()
            return response.json()["payload"]["signatario"]
        except requests.exceptions.HTTPError as e:
            raise Exception(f"Erro HTTP: {error}\nDetalhes da API: {error.response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro: {e}")

    def get_signatories(self, search:str|None=None, page:int|None=None, limit:int|None=None):
        url = f"{self.base_url}/signatario/list"
        data = {
            "search": search,
            "page": str(page), 
            "limit": str(limit)}
        try:
            response = self.session.get(url, data=data)
            logging.debug(response.json())
            response.raise_for_status()
            return response.json()["payload"]["signatarios"]
        except requests.exceptions.HTTPError as e:
            raise Exception(f"Erro HTTP: {error}\nDetalhes da API: {error.response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro: {e}")

    def send_document(self, file_path:pathlib.Path, doc_name:str, code:str):
        url = f"{self.base_url}/documentos"

        with file_path.open("rb") as file:
            files = {
                "arquivo": (file_path.name, file, "application/pdf")
            }

            data = {
                "fileName": doc_name,
                "numero": code,
            }
            
            try:
                response = self.session.post(url, files=files, data=data)
                logging.debug(response.json())
                response.raise_for_status()
                return response.json()["payload"]["documento"]["id"]
            except requests.exceptions.HTTPError as error:
                raise Exception(f"Erro HTTP: {error}\nDetalhes da API: {error.response.text}")
            except requests.exceptions.RequestException as error:
                raise Exception(f"Erro: {error}")

    def add_sig(self, document_id:str, signatory:dict, signature_type:str):
        url = f"{self.base_url}/documentos/addSig/{document_id}"

        data = {
            "id": signatory["id"],
            "cpfCnpj": signatory["cpfCnpj"],
            "nome": signatory["nome"],
            "tipoAss": signature_type,
            "tipoAut": "email",
            "email": signatory["email"]
        }

        try:
            response = self.session.post(url, data=data)
            logging.debug(response.json())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as error:
            raise Exception(f"Erro HTTP: {error}\nDetalhes da API: {error.response.text}")
        except requests.exceptions.RequestException as error:
            raise Exception(f"Erro: {error}")