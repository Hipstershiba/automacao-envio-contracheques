from abc import ABC, abstractmethod
from datetime import datetime as dt
import pathlib


class Document(ABC):
    def __init__(self, file_path: pathlib.Path, signer: "Employee"):
        self.status = "PENDDING"
        self.file_path = file_path
        self.file_name = file_path.name
        self.file_code = None
        self.signer = signer
        self.date = None