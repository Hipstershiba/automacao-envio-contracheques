"""
dimensa_api.py - Module for interacting with the Dimensa Assina API.

This module provides the `DimensaAPI` class, which encapsulates the logic for
authenticating and making requests to the Dimensa digital signature platform,
including finding signatories, uploading documents, and adding signatures.
"""

import requests
import pathlib
import logging


class DimensaAPI:
    """
    Client for interacting with the Dimensa Assina API.

    Handles session management, authentication headers, and provides methods
    to easily perform common API operations like managing signatories and documents.
    """

    def __init__(self, base_url:str="https://api.assina.rbm.digital/api", auth_token:str=""):
        """
        Initializes the DimensaAPI client.

        Args:
            base_url (str): The base URL for the Dimensa API. 
                            Defaults to "https://api.assina.rbm.digital/api".
            auth_token (str): The bearer token for authentication. Defaults to "".
        """
        self.auth_token = auth_token
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})    

    def find_signatory(self, cpf:str):
        """
        Searches for a signatory by their CPF or CNPJ.

        Args:
            cpf (str): The CPF or CNPJ of the signatory to find.

        Returns:
            dict: A dictionary containing the signatory's details.

        Raises:
            Exception: If an HTTP error or request exception occurs during the API call,
                       providing the underlying error details.
        """
        url = f"{self.base_url}/signatario/find"
        data = {"cpfCnpj": cpf}
        try:
            response = self.session.post(url, data=data)
            logging.debug(response.json())
            response.raise_for_status()
            return response.json()["payload"]["signatario"]
        except requests.exceptions.HTTPError as error:
            raise Exception(f"{error}\n{error.response.text}")
        except requests.exceptions.RequestException as error:
            raise Exception(f"{error}")

    def list_signatories(self, search:str|None=None, page:int|None=None, limit:int|None=None):
        """
        Retrieves a paginated list of signatories, optionally filtered by a search term.

        Args:
            search (str | None, optional): Term to filter signatories by name, email, etc. Defaults to None.
            page (int | None, optional): The page number to retrieve. Defaults to None.
            limit (int | None, optional): The maximum number of signatories per page. Defaults to None.

        Returns:
            list: A list of dictionaries, where each dictionary contains a signatory's details.

        Raises:
            Exception: If an HTTP error or request exception occurs during the API call.
        """
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
        except requests.exceptions.HTTPError as error:
            raise Exception(f"{error}\n{error.response.text}")
        except requests.exceptions.RequestException as error:
            raise Exception(f"{error}")

    def upload_document(self, file_path:pathlib.Path, doc_name:str, code:str):
        """
        Uploads a PDF document to the Dimensa API for signing.

        Args:
            file_path (pathlib.Path): The local path to the PDF file to upload.
            doc_name (str): The desired name for the document within the platform.
            code (str): A unique identifier or reference code for the document.

        Returns:
            str: The unique ID assigned to the uploaded document by the Dimensa API.

        Raises:
            Exception: If an HTTP error or request exception occurs during the upload.
        """
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
                raise Exception(f"{error}\n{error.response.text}")
            except requests.exceptions.RequestException as error:
                raise Exception(f"{error}")

    def add_signatory(self, document_id:str, signatory:dict, signature_type:str):
        """
        Adds a signature requirement for a specific signatory to an uploaded document.

        Args:
            document_id (str): The ID of the document (obtained from `upload_document`).
            signatory (dict): A dictionary containing the signatory's details 
                              (e.g., from `find_signatory`), requiring 'id', 'cpfCnpj', 
                              'nome', and 'email' keys.
            signature_type (str): The type of signature required (e.g., 'Assinatura', 'Visto').

        Returns:
            dict: The API response confirming the signature was added.

        Raises:
            Exception: If an HTTP error or request exception occurs.
        """
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
            raise Exception(f"{error}\n{error.response.text}")
        except requests.exceptions.RequestException as error:
            raise Exception(f"{error}")