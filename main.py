import os
import json
import logging
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
import observability as obs
import time
import tempfile
import subprocess
import sys
from selenium.webdriver.common.keys import Keys

load_dotenv()  # carrega LINKEDIN_EMAIL/LINKEDIN_PASSWORD do .env, sem sobrescrever o ambiente

log = logging.getLogger("scraper")

COOKIES_FILE = "linkedin_cookies.json"


class ProfileNotFound(Exception):
    """A URL do perfil não existe (página 404 do LinkedIn)."""


class LinkedInScraper:
    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless
        self.setup_driver()
    
    def setup_driver(self):
        """Configura o driver do Chrome com opções anti-detecção"""
        options = Options()
        # Perfil persistente
        profile_dir = os.path.expanduser(os.environ.get("CHROME_PROFILE_DIR", "~/.linkedin_chrome_profile"))
        options.add_argument(f"--user-data-dir={profile_dir}")
        if self.headless:
            options.add_argument("--headless=new")
            # Sem tamanho explícito o headless abre em 800x600 e o LinkedIn pode servir layout mobile
            options.add_argument("--window-size=1920,1080")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("prefs", {
        "download.default_directory": tempfile.gettempdir(),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True
    })
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    



    def save_cookies(self):
        """Salva cookies após login bem-sucedido"""
        with open(COOKIES_FILE, "w") as f:
            json.dump(self.driver.get_cookies(), f)

    def load_cookies(self):
        """Carrega cookies salvos"""
        if not os.path.exists(COOKIES_FILE):
            return False

        self.driver.get("https://www.linkedin.com")
        with open(COOKIES_FILE, "r") as f:
            cookies = json.load(f)

        now = time.time()
        for cookie in cookies:
            # Remove campos problemáticos
            cookie.pop("sameSite", None)
            # Mantém a validade (sem ela o cookie vira de sessão e some ao fechar o Chrome)
            if "expiry" in cookie:
                if cookie["expiry"] < now:
                    continue
                cookie["expiry"] = int(cookie["expiry"])
            try:
                self.driver.add_cookie(cookie)
            except WebDriverException as e:
                log.debug("cookie %s ignorado: %s", cookie.get("name"), type(e).__name__)
        return True

    def is_logged_in(self):
        """Verifica se sessão está ativa (sem sessão, /feed redireciona para login/authwall)"""
        self.driver.get("https://www.linkedin.com/feed")
        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            log.warning("página /feed não ficou 'complete' em 10s; decidindo pela URL")
        return "/feed" in self.driver.current_url

    def ensure_login(self, email, password):
        """Login inteligente: reutiliza sessão ou faz login"""
        # O perfil persistente do Chrome já guarda a sessão; checar antes de injetar
        # cookies do arquivo, que podem estar velhos e sobrescrever a sessão válida
        if self.is_logged_in():
            log.info("Sessão do perfil do Chrome reutilizada")
            self.save_cookies()
            return True

        if self.load_cookies() and self.is_logged_in():
            log.info("Sessão reutilizada a partir dos cookies salvos")
            self.save_cookies()
            return True

        log.info("Sessão expirada, fazendo login...")
        if self.login(email, password):
            self.save_cookies()
            return True
        return False

        
    def login(self, email, password):
        """Faz login no LinkedIn"""
        try:
            self.driver.get('https://www.linkedin.com/login')

            # Perfil persistente do Chrome já autenticado: /login redireciona direto pro feed
            if "/feed" in self.driver.current_url:
                log.info("Sessão do perfil do Chrome já ativa")
                return True

            # O layout novo não tem mais #username/#password (ids aleatórios) e renderiza o formulário
            # duas vezes, uma oculta: usa sempre o primeiro campo visível
            def first_visible(css):
                return lambda d: next((e for e in d.find_elements(By.CSS_SELECTOR, css) if e.is_displayed()), False)

            email_field = WebDriverWait(self.driver, 10).until(
                first_visible("#username, input[name='session_key'], input[autocomplete~='username'], input[type='email']")
            )
            email_field.send_keys(email)

            password_field = WebDriverWait(self.driver, 5).until(
                first_visible("#password, input[name='session_password'], input[type='password']")
            )
            password_field.send_keys(password)

            # Enter no campo de senha envia o formulário sem depender do markup do botão
            password_field.send_keys(Keys.RETURN)

            # Aguarda chegar no feed; se cair em checkpoint (2FA/captcha), dá tempo de resolver manualmente
            WebDriverWait(self.driver, 15).until(
                lambda d: "/feed" in d.current_url or "/checkpoint" in d.current_url
            )
            if "/checkpoint" in self.driver.current_url and self.headless:
                log.error("Verificação de segurança detectada; rode com --visible para resolvê-la no navegador")
                return False
            if "/checkpoint" in self.driver.current_url:
                log.warning("Verificação de segurança detectada, resolva no navegador (até 2 min)...")
                WebDriverWait(self.driver, 120).until(lambda d: "/feed" in d.current_url)
            
            log.info("Login realizado com sucesso")
            return True
            
        except WebDriverException as e:
            log.error("Erro no login (%s): %s", type(e).__name__, str(e).splitlines()[0] if str(e) else "sem mensagem")
            self.save_failure_artifacts("output", "login_error")
            if self.headless:
                log.error("Dica: rode com --visible para ver a página e resolver login/verificação manualmente")
            return False

    def scroll_to_bottom(self):
        """Scroll usando teclas - mais confiável"""
        # Clica em algum lugar da página primeiro pra garantir foco
        self.driver.find_element(By.TAG_NAME, "body").click()
        time.sleep(0.3)
        
        body = self.driver.find_element(By.TAG_NAME, "body")
        
        get_height = lambda d: d.execute_script("return document.documentElement.scrollHeight")

        for i in range(20):
            last_height = get_height(self.driver)
            body.send_keys(Keys.END)  # vai direto pro fim
            # Sai assim que a página parar de crescer (lazy load terminou)
            try:
                WebDriverWait(self.driver, 1.5, poll_frequency=0.2).until(
                    lambda d: get_height(d) > last_height
                )
            except TimeoutException:
                break

        log.debug("Scroll finalizado. Altura: %s", get_height(self.driver))

    def find_scrollable_container(self):
        """Encontra qual elemento é scrollável"""
        script = """
        const elements = document.querySelectorAll('*');
        const scrollable = [];
        elements.forEach(el => {
            if (el.scrollHeight > el.clientHeight) {
                scrollable.push({
                    tag: el.tagName,
                    class: el.className,
                    id: el.id
                });
            }
        });
        return scrollable.slice(0, 10);
        """
        result = self.driver.execute_script(script)
        log.debug("Containers scrolláveis: %s", result)
        return result
        
    def close(self):
        """Fecha o navegador"""
        if self.driver:
            self.driver.quit()

    def save_as_mhtml(self, output_file):
        try:
            response = self.driver.execute_cdp_cmd("Page.captureSnapshot", {"format": "mhtml"})
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(response["data"])
            log.info("MHTML salvo: %s", output_file)
        except (WebDriverException, OSError):
            log.exception("Erro ao salvar MHTML")

    def save_html(self, page_name, output_dir):
        """Grava o HTML da aba atual; erros de disco/driver sobem para o chamador marcar a seção como falha"""
        path = f"{output_dir}/{page_name}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.driver.page_source)
        log.debug("HTML salvo: %s", path)
        return path

    def save_failure_artifacts(self, directory, name):
        """Screenshot e HTML da aba atual em <directory>/<name>.{png,html}, para diagnosticar a falha"""
        try:
            os.makedirs(directory, exist_ok=True)
            self.driver.save_screenshot(f"{directory}/{name}.png")
            with open(f"{directory}/{name}.html", "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            log.error("Artefatos de falha salvos em %s/%s.{png,html} (URL: %s | título: %r)",
                      directory, name, self.driver.current_url, self.driver.title)
        except (WebDriverException, OSError):
            log.exception("Não foi possível salvar os artefatos de falha de %s", name)

    def is_not_found(self):
        """A aba atual mostra a página 404 do LinkedIn ("Page not found")"""
        title = (self.driver.title or "").lower()
        return "page not found" in title or "página não encontrada" in title or "/404" in self.driver.current_url

    def wait_until_stable(self, timeout=15, quiet=1.0):
        """Espera a página carregar e o DOM ficar `quiet` segundos sem mudar de tamanho"""
        end = time.time() + timeout
        last_size = None
        stable_since = time.time()
        while time.time() < end:
            size = self.driver.execute_script(
                "return document.readyState === 'complete' ? document.body.innerHTML.length : -1"
            )
            if size != last_size:
                last_size = size
                stable_since = time.time()
            elif size >= 0 and time.time() - stable_since >= quiet:
                return True
            time.sleep(0.2)
        return False

    def open_tab(self, url):
        """Abre url em nova aba sem bloquear (carrega em paralelo) e retorna o handle"""
        before = set(self.driver.window_handles)
        self.driver.execute_script("window.open(arguments[0], '_blank');", url)
        try:
            WebDriverWait(self.driver, 5).until(lambda d: len(d.window_handles) > len(before))
            return (set(self.driver.window_handles) - before).pop()
        except TimeoutException:
            # window.open bloqueado: abre a aba pelo Selenium (carregamento bloqueante)
            self.driver.switch_to.new_window("tab")
            self.driver.get(url)
            return self.driver.current_window_handle

    def load_all_content(self):
        """Clica em Load more até não haver mais"""
        clicks = 0
        while True:
            # Página já estável: se não há botão agora, não há o que carregar
            buttons = self.driver.find_elements(By.XPATH, "//button[.//span[text()='Load more']]")
            if not buttons:
                break
            try:
                self.driver.execute_script("arguments[0].scrollIntoView(); arguments[0].click();", buttons[0])
                clicks += 1
                self.wait_until_stable(timeout=5, quiet=0.7)
            except WebDriverException as e:
                log.warning("Falha ao clicar em 'Load more' (%s); seguindo com o que já carregou", type(e).__name__)
                break

        log.info("Load more clicado %d vezes", clicks)
        return clicks
    
    # Acha o título da seção About/Sobre e sobe na árvore até o menor ancestral que tenha um botão
    # "more"/"mais"; clica só nesse botão. Retorna o texto do botão clicado ou None.
    CLICK_ABOUT_MORE_JS = """
    const titles = ['about', 'sobre', 'acerca de', 'info'];
    const heading = [...document.querySelectorAll('h1, h2, h3, p, span')].find(
        e => e.children.length === 0 && titles.includes(e.textContent.trim().toLowerCase())
             && e.offsetParent !== null && !e.closest('header, nav, footer')
    );
    if (!heading) return null;
    let node = heading;
    for (let i = 0; i < 8 && node.parentElement; i++) {
        node = node.parentElement;
        const btn = [...node.querySelectorAll('button')].find(b => /^\\W*(more|mais)\\b/i.test(b.textContent.trim())
                                                              || /\\b(more|mais)$/i.test(b.textContent.trim()));
        if (btn) {
            btn.scrollIntoView({block: 'center'});
            btn.click();
            return btn.textContent.trim();
        }
    }
    return null;
    """

    def click_more_buttons(self, page_url=None):
        """Expande só o texto da seção About ("…more"), sem tocar nos outros botões "more" da página
        (posts da atividade, por exemplo, navegam para fora do perfil). Retorna 1 se clicou, 0 se não."""
        try:
            label = self.driver.execute_script(self.CLICK_ABOUT_MORE_JS)
        except WebDriverException as e:
            log.warning("Falha ao expandir About: %s", type(e).__name__)
            return 0
        if not label:
            log.info("Botão 'more' do About não encontrado (texto já completo ou seção ausente)")
            return 0
        log.info("About expandido (botão: %r)", label)
        self.wait_until_stable(timeout=5, quiet=0.5)
        if page_url and self.driver.current_url.split("?")[0].rstrip("/") != page_url.split("?")[0].rstrip("/"):
            log.warning("Clique navegou para %s; voltando ao perfil", self.driver.current_url)
            self.driver.get(page_url)
            self.wait_until_stable()
        return 1

# (arquivo, path relativo ao perfil, binário do parser)
DETAIL_SECTIONS = [
    ("experience", "details/experience/", "experience-parser"),
    ("education", "details/education/", "education-parser"),
    ("languages", "details/languages/", "language-parser"),
]


def collect_profile(scraper, tab, base_url, output_dir):
    """Carrega o perfil na aba principal, expande o About e grava profile.html"""
    scraper.driver.switch_to.window(tab)
    scraper.driver.get(base_url + "?locale=pt_BR")
    scraper.wait_until_stable()
    if scraper.is_not_found():
        raise ProfileNotFound(base_url)
    scraper.scroll_to_bottom()
    scraper.click_more_buttons(base_url)
    scraper.save_html("profile.html", output_dir)


def collect_detail(scraper, tab, name, output_dir):
    """Visita a aba da seção (já carregada em paralelo), carrega todo o conteúdo e grava <name>.html"""
    scraper.driver.switch_to.window(tab)
    scraper.wait_until_stable()
    scraper.load_all_content()
    scraper.save_html(f"{name}.html", output_dir)


def process_section(scraper, name, collect, parser, output_dir):
    """Coleta e parseia uma seção; qualquer falha vira um SectionResult em vez de derrubar o job.

    O parser roda na hora (leva milissegundos) para que, se falhar, o screenshot ainda seja da aba da seção.
    """
    extra = {"section": name}
    start = time.time()
    try:
        collect()
    except ProfileNotFound:
        raise
    except (WebDriverException, OSError) as e:
        message = str(e).splitlines()[0] if str(e) else ""
        log.error("Falha ao coletar: %s %s", type(e).__name__, message, extra=extra)
        result = obs.SectionResult(section=name, collect_status="failed", error=f"{type(e).__name__}: {message}")
    else:
        result = obs.run_parser(f"./enrichment/bin/{parser}", f"{output_dir}/{name}.html",
                                f"{output_dir}/{name}.json", name)

    result.duration_ms = int((time.time() - start) * 1000)
    extra["duration_ms"] = result.duration_ms
    if result.ok:
        log.info("Seção %s: %s (%d itens)", name, result.parse_status, result.items, extra=extra)
    else:
        log.error("Seção %s falhou: %s", name, result.error or result.parse_status, extra=extra)
        scraper.save_failure_artifacts(f"{output_dir}/failures", name)
    return result


# Uso: python main.py [--visible] [<profile_url>]
# Código de saída: 0 success, 2 partial, 1 demais status (failed, auth_required, not_found)
if __name__ == "__main__":
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    if not email or not password:
        raise SystemExit("Defina LINKEDIN_EMAIL e LINKEDIN_PASSWORD no ambiente")

    args = sys.argv[1:]
    visible = "--visible" in args
    urls = [a for a in args if a != "--visible"]
    profile_url = urls[0] if urls else input("Insira o URL do perfil a ser analisado: ")

    base_url = profile_url.split("?")[0].rstrip("/") + "/"
    dir_name = base_url.replace("https://www.linkedin.com/in/", "").replace("/", "")
    output_dir = f"./output/{dir_name}"
    os.makedirs(output_dir, exist_ok=True)

    obs.setup_logging()
    job_id = uuid.uuid4().hex[:8]
    obs.CONTEXT.update(job_id=job_id, profile=base_url)
    started_at = datetime.now(timezone.utc)
    start_time = time.time()
    log.info("Iniciando job para %s", base_url)

    all_sections = [("profile", "linkedin-parser")] + [(name, parser) for name, _, parser in DETAIL_SECTIONS]
    results = []
    auth_ok, found = True, True
    scraper = LinkedInScraper(headless=not visible)

    try:
        if not scraper.ensure_login(email, password):
            auth_ok = False
            log.error("Login não concluído")
        else:
            main_tab = scraper.driver.current_window_handle
            # Abre as seções de detalhe em abas para carregarem em paralelo com o perfil
            tabs = {
                name: scraper.open_tab(f"{base_url}{path}?locale=pt_BR")
                for name, path, _ in DETAIL_SECTIONS
            }

            results.append(process_section(
                scraper, "profile", lambda: collect_profile(scraper, main_tab, base_url, output_dir),
                "linkedin-parser", output_dir))
            for name, _, parser in DETAIL_SECTIONS:
                results.append(process_section(
                    scraper, name, lambda name=name: collect_detail(scraper, tabs[name], name, output_dir),
                    parser, output_dir))
    except ProfileNotFound:
        found = False
        log.error("Perfil não encontrado: %s", base_url)
    except Exception:
        # Erro inesperado (bug ou driver morto): registra com stack trace; seções não processadas contam como falha
        log.exception("Erro inesperado durante a coleta")
    finally:
        scraper.close()

    if auth_ok and found:
        done = {r.section for r in results}
        results += [obs.SectionResult(section=name, collect_status="failed", error="não processada")
                    for name, _ in all_sections if name not in done]

    status = obs.job_status(results, auth_ok=auth_ok, found=found)
    duration_ms = int((time.time() - start_time) * 1000)
    obs.write_status_json(f"{output_dir}/status.json", job_id, base_url, status, results, started_at, duration_ms)
    log.info("Job finalizado: %s em %.1fs (detalhes em %s/status.json)", status, duration_ms / 1000, output_dir,
             extra={"duration_ms": duration_ms})
    sys.exit(obs.exit_code(status))
