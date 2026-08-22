from datetime import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
import pathlib
import sys

class DualFormatter(logging.Formatter):
    def __init__(self, fmt: str, datefmt: str = None):
        super().__init__(fmt, datefmt)
        self.clean_fmt = logging.Formatter('%(message)s')

    def format(self, record: logging.LogRecord) -> str:
        if record.name == "Boundary":
            return self.clean_fmt.format(record)
        return super().format(record)

class LogManager:
    def __init__(
        self,
        app_name:str = "App",
        logs_dir:pathlib.Path = pathlib.Path("logs"),
        backup_count:int = 7,
        debug_mode: bool = False
    ):
        if not isinstance(app_name, str):
            raise TypeError("App name must be a string.")
        if not isinstance(logs_dir, pathlib.Path):
            raise TypeError("Logs directory must be a pathlib.Path object.")
        if not isinstance(backup_count, int):
            raise TypeError("Backup count must be an integer.")
        if not  isinstance(debug_mode, bool):
            raise TypeError("Debug mode must be a boolean.")
        
        self._app_name = app_name
        self._logs_dir = logs_dir
        self._backup_count = backup_count
        self._debug_mode = debug_mode
        self._log_level = logging.DEBUG if debug_mode else logging.INFO
        
        # Aqui a mágica: criamos um logger exclusivo chamado "boundary"
        self._boundary_logger = logging.getLogger("Boundary")
        
        self._setup_logger()

    def _setup_logger(self) -> None:
        """
        Creates and configures the root logger for the application.
        """
        # 1. Ensure logs directory exists
        self._logs_dir.mkdir(exist_ok=True)
        
        # 2. Generate filename with current date
        current_date = datetime.now().strftime("%Y-%m-%d")
        file_name = f"{self._app_name}_{current_date}.log"
        file_path = self._logs_dir / file_name

        # 3. Get the root logger
        root_logger = logging.getLogger()
        
        # 4. Clear old handlers
        root_logger.handlers.clear()
        
        # 5. Set the global log level
        root_logger.setLevel(logging.DEBUG)
        
        # 6. Create our Custom Formatter
        file_fmt = '%(asctime)s - %(name)s: [%(levelname)s] %(message)s'
        file_datefmt = '%Y-%m-%d %H:%M:%S'
        file_formatter = DualFormatter(file_fmt, file_datefmt)
        
        console_fmt = '[%(levelname)s] %(message)s'
        console_datefmt = '%H:%M:%S'
        console_formatter = DualFormatter(console_fmt, console_datefmt)

        
        # 7. Create a file handler
        file_handler = TimedRotatingFileHandler(
            file_path, 
            when='midnight', 
            interval=1, 
            backupCount=self._backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(file_formatter)
        
        # 8. Create a console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self._log_level)
        console_handler.setFormatter(console_formatter)
        
        # 9. Add handlers to the root logger
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    # ========================= BOUNDARIES ========================= #
    def start(self) -> None:
        """Log the start of the application."""
        self._boundary_logger.info("=" * 100)
        self._boundary_logger.info(f" INICIANDO {self._app_name.upper()} ".center(100, "="))
        self._boundary_logger.info("=" * 100)

    def stop(self) -> None:
        """Log the end of the application."""
        self._boundary_logger.info("=" * 100)
        self._boundary_logger.info(f" ENCERRANDO {self._app_name.upper()} ".center(100, "="))
        self._boundary_logger.info("=" * 100 + "\n" * 2)



if __name__ == "__main__":
    logger = LogManager(
        "Teste",
        # logs_dir=pathlib.Path("logs"),
        backup_count=7,
    )
    logger.start()
    logging.debug("This is a debug message")
    logging.info("This is an info message")
    logging.warning("This is a warning message")
    logging.error("This is an error message")
    logging.critical("This is a critical message")
    logger.stop()