"""
dimensa_auth.py - Módulo encapsulado para obtenção de Bearer Token do Dimensa Sign.

Abre um navegador Chrome via Selenium, apresenta a página de login do Dimensa Sign,
aguarda o login do usuário, intercepta o Bearer Token das respostas de rede,
fecha o navegador e retorna o token.

Cria um perfil de usuário persistente (user_profile/) na pasta do script para que
o navegador lembre senhas salvas entre execuções.

Uso standalone:
    python dimensa_auth.py

Uso como módulo:
    from auth.dimensa_auth import obter_token_dimensa
    token = obter_token_dimensa()
"""

import os
import sys
import json
import time
import logging
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException, TimeoutException

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

# URL de login do portal Dimensa Sign
LOGIN_URL = "https://sign.dimensa.com.br/"

# Domínio da API cujas respostas contêm o Bearer Token
API_DOMAIN = "api.assina.rbm.digital"

# Tempo máximo (em segundos) para aguardar o usuário fazer login
LOGIN_TIMEOUT = 300  # 5 minutos

# Intervalo de polling para verificar as respostas de rede (em segundos)
POLL_INTERVAL = 2

# Nome da pasta do perfil do Chrome (criada junto ao script)
PROFILE_DIR_NAME = "user_profile"

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = logging.getLogger("dimensa_auth")


def _configurar_logger(verbose: bool = False) -> None:
    """Configura o logger do módulo."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s - %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


# ---------------------------------------------------------------------------
# Funções internas
# ---------------------------------------------------------------------------

def _obter_caminho_perfil() -> str:
    """
    Retorna o caminho absoluto para a pasta de perfil do Chrome.
    A pasta é criada ao lado do próprio script (dimensa_auth.py).
    """
    script_dir = Path(__file__).resolve().parent
    profile_path = script_dir / PROFILE_DIR_NAME
    profile_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Caminho do perfil do Chrome: {profile_path}")
    return str(profile_path)


def _criar_driver(headless: bool = False) -> webdriver.Chrome:
    """
    Cria e retorna uma instância do ChromeDriver configurada com:
    - Perfil de usuário persistente (para salvar senhas)
    - Performance logging habilitado (para capturar tráfego de rede)
    """
    profile_path = _obter_caminho_perfil()

    options = ChromeOptions()

    # Perfil persistente — permite salvar senhas e cookies entre sessões
    options.add_argument(f"--user-data-dir={profile_path}")

    # Habilita logging de performance para capturar respostas de rede
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    # Desativa a barra "Chrome está sendo controlado por software de teste"
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if headless:
        options.add_argument("--headless=new")

    # Desativa notificações do navegador
    options.add_argument("--disable-notifications")

    # Inicia maximizado para melhor experiência do usuário
    options.add_argument("--start-maximized")

    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        logger.error(
            "Falha ao iniciar o Chrome. Verifique se o Chrome e o "
            "ChromeDriver estão instalados e compatíveis."
        )
        raise RuntimeError(
            "Não foi possível iniciar o navegador Chrome. "
            "Certifique-se de que o Google Chrome está instalado."
        ) from e

    logger.info("Navegador Chrome iniciado com sucesso.")
    return driver


def _extrair_token_dos_logs(driver: webdriver.Chrome) -> str | None:
    """
    Analisa os logs de performance do Selenium para encontrar o Bearer Token
    nas respostas HTTP da API do Dimensa Sign.

    O token é procurado nos headers de resposta (Authorization) e também
    no corpo das respostas JSON que contenham campos como 'token', 
    'access_token' ou 'accessToken'.
    """
    try:
        logs = driver.get_log("performance")
    except WebDriverException:
        logger.debug("Não foi possível obter logs de performance.")
        return None

    for entry in logs:
        try:
            log_data = json.loads(entry["message"])
            message = log_data.get("message", {})
            method = message.get("method", "")

            # 1) Procura nas respostas HTTP (headers)
            if method == "Network.responseReceived":
                response = message.get("params", {}).get("response", {})
                url = response.get("url", "")

                if API_DOMAIN not in url:
                    continue

                headers = response.get("headers", {})

                # Verifica o header Authorization
                for header_name, header_value in headers.items():
                    if header_name.lower() == "authorization":
                        token = header_value
                        if token.lower().startswith("bearer "):
                            token = token[7:]
                        if len(token) > 20:  # token mínimo razoável
                            logger.debug(f"Token encontrado no header da URL: {url}")
                            return token

            # 2) Procura no corpo das respostas (responseReceived + getResponseBody)
            if method == "Network.responseReceived":
                response = message.get("params", {}).get("response", {})
                url = response.get("url", "")
                request_id = message.get("params", {}).get("requestId")

                if API_DOMAIN not in url or not request_id:
                    continue

                try:
                    body_response = driver.execute_cdp_cmd(
                        "Network.getResponseBody",
                        {"requestId": request_id}
                    )
                    body_text = body_response.get("body", "")
                    if body_text:
                        try:
                            body_json = json.loads(body_text)
                            # Procura campos comuns que contenham tokens
                            for key in ("token", "access_token", "accessToken",
                                        "bearer", "jwt", "id_token"):
                                if key in body_json and isinstance(body_json[key], str):
                                    token = body_json[key]
                                    if len(token) > 20:
                                        logger.debug(
                                            f"Token encontrado no body (campo '{key}') "
                                            f"da URL: {url}"
                                        )
                                        return token
                            # Procura dentro de objetos 'data' aninhados
                            if isinstance(body_json.get("data"), dict):
                                for key in ("token", "access_token", "accessToken",
                                            "bearer", "jwt", "id_token"):
                                    if key in body_json["data"] and isinstance(
                                        body_json["data"][key], str
                                    ):
                                        token = body_json["data"][key]
                                        if len(token) > 20:
                                            logger.debug(
                                                f"Token encontrado em data.{key} "
                                                f"da URL: {url}"
                                            )
                                            return token
                        except (json.JSONDecodeError, ValueError):
                            pass
                except WebDriverException:
                    # O body pode não estar mais disponível (ex: streaming)
                    pass

            # 3) Procura em requests enviados (headers de request com Authorization)
            if method == "Network.requestWillBeSent":
                request = message.get("params", {}).get("request", {})
                url = request.get("url", "")

                if API_DOMAIN not in url:
                    continue

                headers = request.get("headers", {})
                for header_name, header_value in headers.items():
                    if header_name.lower() == "authorization":
                        token = header_value
                        if token.lower().startswith("bearer "):
                            token = token[7:]
                        if len(token) > 20:
                            logger.debug(
                                f"Token encontrado no request header da URL: {url}"
                            )
                            return token

        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    return None


# ---------------------------------------------------------------------------
# Função pública principal
# ---------------------------------------------------------------------------

def obter_token_dimensa(
    login_url: str = LOGIN_URL,
    timeout: int = LOGIN_TIMEOUT,
    verbose: bool = False,
    headless: bool = False,
) -> str:
    """
    Abre o navegador Chrome na página de login do Dimensa Sign, aguarda o
    usuário fazer login, captura o Bearer Token das respostas de rede e
    retorna o token como string.

    Args:
        login_url: URL da página de login do Dimensa Sign.
        timeout: Tempo máximo (em segundos) para aguardar o login.
        verbose: Se True, ativa logs detalhados (DEBUG).
        headless: Se True, executa o navegador em modo headless (sem janela).

    Returns:
        O Bearer Token capturado (string).

    Raises:
        TimeoutError: Se o login não for realizado dentro do tempo limite.
        RuntimeError: Se não for possível iniciar o navegador.
    """
    _configurar_logger(verbose)
    logger.info("Iniciando processo de autenticação no Dimensa Sign...")

    driver = _criar_driver(headless=headless)

    try:
        # Habilita interceptação de rede via CDP (Chrome DevTools Protocol)
        driver.execute_cdp_cmd("Network.enable", {})
        logger.info(f"Abrindo página de login: {login_url}")
        driver.get(login_url)

        logger.info(
            f"Aguardando login do usuário (timeout: {timeout}s)... "
            "Faça login no navegador que foi aberto."
        )

        start_time = time.time()
        token = None

        while time.time() - start_time < timeout:
            token = _extrair_token_dos_logs(driver)
            if token:
                break
            time.sleep(POLL_INTERVAL)

        if not token:
            raise TimeoutError(
                f"Tempo limite de {timeout}s excedido. "
                "Nenhum Bearer Token foi capturado. "
                "Certifique-se de fazer login no portal Dimensa Sign."
            )

        logger.info("✅ Bearer Token capturado com sucesso!")
        logger.debug(f"Token (primeiros 30 chars): {token[:30]}...")
        return token

    finally:
        logger.info("Fechando navegador...")
        try:
            driver.quit()
        except Exception:
            pass
        logger.info("Navegador fechado.")


# ---------------------------------------------------------------------------
# Execução standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  Dimensa Sign — Captura de Bearer Token")
    print("=" * 60)
    print()

    try:
        token = obter_token_dimensa(verbose=True)
        print()
        print("=" * 60)
        print("  TOKEN CAPTURADO:")
        print("=" * 60)
        print(token)
        print("=" * 60)
    except TimeoutError as e:
        print(f"\n❌ ERRO: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n❌ ERRO: {e}")
        sys.exit(1)
