"""
dimensa_auth.py - Módulo encapsulado para obtenção de Bearer Token do Dimensa Sign.

Abre um navegador (Chrome ou Edge) via Selenium, apresenta a página de login
do Dimensa Sign, aguarda o login do usuário, intercepta o Bearer Token das
respostas de rede, fecha o navegador e retorna o token.

Cria um perfil de usuário persistente (user_profile/<navegador>/) na pasta do
script para que o navegador lembre senhas salvas entre execuções.

Navegadores suportados: chrome (padrão), edge.
Firefox não é suportado pois não possui CDP (Chrome DevTools Protocol).

Uso standalone:
    python dimensa_auth.py              # usa Chrome
    python dimensa_auth.py --edge       # usa Edge

Uso como módulo:
    from auth.dimensa_auth import obter_token_dimensa
    token = obter_token_dimensa()                        # Chrome
    token = obter_token_dimensa(navegador="edge")        # Edge
"""

import os
import sys
import json
import time
import logging

import requests
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.common.exceptions import WebDriverException

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

# URL de login do portal Dimensa Sign
LOGIN_URL = "https://sign.app.dimensa.com.br/adminsign"

# Domínio da API cujas respostas contêm o Bearer Token
API_DOMAIN = "api.assina.rbm.digital"

# Caminho da URL de login (usado para detectar se estamos na tela de login)
LOGIN_PATH = "/adminsign/login"

# Endpoint autenticado para validação do token capturado
TOKEN_VALIDATION_URL = "https://api.assina.rbm.digital/api/v2/usuarios/info"

# Timeout para a chamada HTTP de validação do token (segundos)
TOKEN_VALIDATION_TIMEOUT = 5

# Tempo máximo (em segundos) para aguardar o usuário fazer login
LOGIN_TIMEOUT = 300  # 5 minutos

# Intervalo de polling para verificar as respostas de rede (em segundos)
POLL_INTERVAL = 2

# Nome da pasta-raiz dos perfis de navegador (criada junto ao script)
PROFILE_DIR_NAME = "user_profile"

# Navegadores suportados (ambos Chromium, compatíveis com CDP)
NAVEGADORES_SUPORTADOS = ("chrome", "edge")

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

def _obter_caminho_perfil(navegador: str = "chrome") -> str:
    """
    Retorna o caminho absoluto para a pasta de perfil do navegador.
    Cada navegador tem sua própria subpasta em user_profile/<navegador>/.
    A pasta é criada ao lado do próprio script (dimensa_auth.py).
    """
    script_dir = Path(__file__).resolve().parent
    profile_path = script_dir / PROFILE_DIR_NAME / navegador
    profile_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Caminho do perfil ({navegador}): {profile_path}")
    return str(profile_path)


def _criar_driver(
    navegador: str = "chrome",
    headless: bool = False,
) -> webdriver.Chrome | webdriver.Edge:
    """
    Cria e retorna uma instância do WebDriver (Chrome ou Edge) configurada com:
    - Perfil de usuário persistente (para salvar senhas)
    - Performance logging habilitado (para capturar tráfego de rede via CDP)
    """
    navegador = navegador.lower().strip()
    if navegador not in NAVEGADORES_SUPORTADOS:
        raise ValueError(
            f"Navegador '{navegador}' não suportado. "
            f"Opções: {', '.join(NAVEGADORES_SUPORTADOS)}"
        )

    profile_path = _obter_caminho_perfil(navegador)

    # Seleciona a classe de Options e Driver conforme o navegador
    if navegador == "edge":
        options = EdgeOptions()
        logging_pref_key = "ms:loggingPrefs"
        driver_class = webdriver.Edge
        browser_label = "Microsoft Edge"
    else:  # chrome (padrão)
        options = ChromeOptions()
        logging_pref_key = "goog:loggingPrefs"
        driver_class = webdriver.Chrome
        browser_label = "Google Chrome"

    # --- Configurações comuns (ambos são Chromium) ---

    # Perfil persistente — permite salvar senhas e cookies entre sessões
    options.add_argument(f"--user-data-dir={profile_path}")

    # Habilita logging de performance para capturar respostas de rede
    options.set_capability(logging_pref_key, {"performance": "ALL"})

    # Desativa a barra "controlado por software de teste"
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if headless:
        options.add_argument("--headless=new")

    # Desativa notificações do navegador
    options.add_argument("--disable-notifications")

    # Inicia maximizado para melhor experiência do usuário
    options.add_argument("--start-maximized")

    try:
        driver = driver_class(options=options)
    except WebDriverException as e:
        logger.error(
            f"Falha ao iniciar o {browser_label}. Verifique se o navegador "
            "e o driver estão instalados e compatíveis."
        )
        raise RuntimeError(
            f"Não foi possível iniciar o {browser_label}. "
            f"Certifique-se de que o {browser_label} está instalado."
        ) from e

    logger.info(f"{browser_label} iniciado com sucesso.")
    return driver


def _extrair_token_dos_logs(driver: webdriver.Chrome | webdriver.Edge) -> str | None:
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


def _validar_token(token: str) -> bool:
    """
    Valida o token capturado fazendo uma chamada autenticada à API.

    Faz GET em /api/v2/usuarios/info com o token no header Authorization.
    Se a API retornar 2xx, o token é válido. Qualquer outro status ou
    erro de conexão indica token inválido.

    Returns:
        True se o token for válido (API retornou 2xx), False caso contrário.
    """
    try:
        response = requests.get(
            TOKEN_VALIDATION_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=TOKEN_VALIDATION_TIMEOUT,
        )
        if response.ok:
            logger.debug("Token validado com sucesso pela API.")
            return True
        else:
            logger.debug(
                f"Token inválido — API retornou status {response.status_code}."
            )
            return False
    except requests.RequestException as e:
        logger.debug(f"Erro ao validar token: {e}")
        return False


def _aguardar_pagina_login(
    driver: webdriver.Chrome | webdriver.Edge,
    timeout: float,
) -> None:
    """
    Aguarda até que a URL do navegador contenha o caminho de login.

    Quando o navegador tem uma sessão anterior (cookies/perfil persistente),
    o portal pode redirecionar brevemente para o dashboard antes de invalidar
    a sessão e redirecionar de volta para o login. Esta função aguarda essa
    transição e, ao detectar a página de login, descarta todos os logs de
    performance acumulados (flush) para eliminar tokens expirados.

    Chamada apenas quando um token capturado falha na validação (sessão
    expirada), sinalizando que o usuário precisará fazer login novamente.

    Raises:
        TimeoutError: Se a página de login não aparecer dentro do timeout.
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        current_url = driver.current_url
        if LOGIN_PATH in current_url:
            logger.info("Página de login detectada. Descartando logs antigos...")
            # Flush: descarta logs de performance acumulados durante
            # redirecionamentos (podem conter tokens expirados)
            try:
                driver.get_log("performance")
            except WebDriverException:
                pass
            logger.info(
                "Aguardando login do usuário... "
                "Faça login no navegador que foi aberto."
            )
            return
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(
        f"Tempo limite de {timeout:.0f}s excedido aguardando a página de login. "
        "A página de login do Dimensa Sign não foi carregada."
    )


# ---------------------------------------------------------------------------
# Função pública principal
# ---------------------------------------------------------------------------

def obter_token_dimensa(
    login_url: str = LOGIN_URL,
    timeout: int = LOGIN_TIMEOUT,
    verbose: bool = False,
    headless: bool = False,
    navegador: str = "chrome",
) -> str:
    """
    Abre o navegador na página de login do Dimensa Sign, aguarda o
    usuário fazer login, captura o Bearer Token das respostas de rede e
    retorna o token como string.

    Args:
        login_url: URL da página de login do Dimensa Sign.
        timeout: Tempo máximo (em segundos) para aguardar o login.
        verbose: Se True, ativa logs detalhados (DEBUG).
        headless: Se True, executa o navegador em modo headless (sem janela).
        navegador: Navegador a utilizar — "chrome" (padrão) ou "edge".

    Returns:
        O Bearer Token capturado (string).

    Raises:
        TimeoutError: Se o login não for realizado dentro do tempo limite.
        RuntimeError: Se não for possível iniciar o navegador.
        ValueError: Se o navegador informado não for suportado.
    """
    _configurar_logger(verbose)
    logger.info("Iniciando processo de autenticação no Dimensa Sign...")

    driver = _criar_driver(navegador=navegador, headless=headless)

    try:
        # Habilita interceptação de rede via CDP (Chrome DevTools Protocol)
        driver.execute_cdp_cmd("Network.enable", {})
        logger.info(f"Abrindo página de login: {login_url}")
        driver.get(login_url)

        logger.info(f"Aguardando autenticação (timeout: {timeout}s)...")

        start_time = time.time()
        token = None
        login_aguardado = False

        while time.time() - start_time < timeout:
            token = _extrair_token_dos_logs(driver)
            if token:
                # Valida o token capturado via chamada à API.
                # Se a sessão anterior ainda estiver ativa, o token será
                # válido e o script retorna imediatamente (sem re-login).
                if _validar_token(token):
                    break

                # Token inválido (sessão expirada). Aguarda a página de
                # login carregar e faz flush dos logs antigos — apenas
                # na primeira vez que isso acontece.
                if not login_aguardado:
                    logger.info(
                        "Token da sessão anterior é inválido (expirado). "
                        "Aguardando página de login..."
                    )
                    tempo_restante = timeout - (time.time() - start_time)
                    _aguardar_pagina_login(driver, tempo_restante)
                    login_aguardado = True

                token = None

            time.sleep(POLL_INTERVAL)

        if not token:
            raise TimeoutError(
                f"Tempo limite de {timeout}s excedido. "
                "Nenhum Bearer Token válido foi capturado. "
                "Certifique-se de fazer login no portal Dimensa Sign."
            )

        logger.info("✅ Bearer Token capturado e validado com sucesso!")
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
    import argparse

    parser = argparse.ArgumentParser(
        description="Captura Bearer Token do Dimensa Sign via login no navegador."
    )
    parser.add_argument(
        "--edge",
        action="store_const",
        const="edge",
        default="chrome",
        dest="navegador",
        help="Usar Microsoft Edge em vez do Google Chrome.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Dimensa Sign — Captura de Bearer Token")
    print(f"  Navegador: {args.navegador}")
    print("=" * 60)
    print()

    try:
        token = obter_token_dimensa(verbose=True, navegador=args.navegador)
        print()
        print("=" * 60)
        print("  TOKEN CAPTURADO:")
        print("=" * 60)
        print(token)
        print("=" * 60)
    except TimeoutError as e:
        print(f"\n❌ ERRO: {e}")
        sys.exit(1)
    except (RuntimeError, ValueError) as e:
        print(f"\n❌ ERRO: {e}")
        sys.exit(1)
