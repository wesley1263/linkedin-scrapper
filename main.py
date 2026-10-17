import os
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import time
import tempfile
import subprocess
import sys
from selenium.webdriver.common.keys import Keys

COOKIES_FILE = "linkedin_cookies.json"
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
            except:
                continue
        return True

    def is_logged_in(self):
        """Verifica se sessão está ativa (sem sessão, /feed redireciona para login/authwall)"""
        self.driver.get("https://www.linkedin.com/feed")
        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except:
            pass
        return "/feed" in self.driver.current_url

    def ensure_login(self, email, password):
        """Login inteligente: reutiliza sessão ou faz login"""
        # O perfil persistente do Chrome já guarda a sessão; checar antes de injetar
        # cookies do arquivo, que podem estar velhos e sobrescrever a sessão válida
        if self.is_logged_in():
            print("✓ Sessão do perfil do Chrome reutilizada")
            self.save_cookies()
            return True

        if self.load_cookies() and self.is_logged_in():
            print("✓ Sessão reutilizada a partir dos cookies salvos")
            self.save_cookies()
            return True

        print("→ Sessão expirada, fazendo login...")
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
                print("Sessão do perfil do Chrome já ativa")
                return True

            # Aguarda e preenche email
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            email_field.send_keys(email)
            
            # Preenche senha
            password_field = self.driver.find_element(By.ID, "password")
            password_field.send_keys(password)
            
            # Clica no botão de login
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Aguarda chegar no feed; se cair em checkpoint (2FA/captcha), dá tempo de resolver manualmente
            WebDriverWait(self.driver, 15).until(
                lambda d: "/feed" in d.current_url or "/checkpoint" in d.current_url
            )
            if "/checkpoint" in self.driver.current_url and self.headless:
                print("Verificação de segurança detectada; rode com --visible para resolvê-la no navegador")
                return False
            if "/checkpoint" in self.driver.current_url:
                print("Verificação de segurança detectada, resolva no navegador (até 2 min)...")
                WebDriverWait(self.driver, 120).until(lambda d: "/feed" in d.current_url)
            
            print("Login realizado com sucesso!")
            return True
            
        except Exception as e:
            print(f"Erro no login ({type(e).__name__}): {str(e).splitlines()[0] if str(e) else 'sem mensagem'}")
            try:
                print(f"  URL atual: {self.driver.current_url} | título: {self.driver.title!r}")
                os.makedirs("output", exist_ok=True)
                self.driver.save_screenshot("output/login_error.png")
                print("  Screenshot salvo em output/login_error.png")
            except Exception:
                pass
            if self.headless:
                print("  Dica: rode com --visible para ver a página e resolver login/verificação manualmente")
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

        print(f"Scroll finalizado. Altura: {get_height(self.driver)}")

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
        print("Containers scrolláveis:", result)
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
            print(f"MHTML salvo: {output_file}")
        except Exception as e:
            print(f"Erro ao salvar MHTML: {e}")

    def save_html_and_screenshot(self, page_name, output_dir):
        try:
            # HTML
            with open(f"{output_dir}/{page_name}", "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            print(f"HTML salvos em: {output_dir}")
        except Exception as e:
            print(f"Erro ao salvar HTML: {e}")
            
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
            except:
                break
        
        print(f"Load more clicado {clicks} vezes")
        return clicks
    
    def click_more_buttons(self):
        """Clica em todos os botões 'more'"""
        try:
            buttons = self.driver.find_elements(
                By.XPATH, "//button[.//span[contains(text(), 'more')]]"
            )
            
            for button in buttons:
                try:
                    self.driver.execute_script("arguments[0].click();", button)
                except:
                    continue

            if buttons:
                self.wait_until_stable(timeout=5, quiet=0.5)
            return len(buttons)
        except:
            return 0

# (arquivo, path relativo ao perfil, binário do parser)
DETAIL_SECTIONS = [
    ("experience", "details/experience/", "experience-parser"),
    ("education", "details/education/", "education-parser"),
    ("languages", "details/languages/", "language-parser"),
]


def run_parser(parser, output_dir, name):
    """Roda o parser Go em background sobre <name>.html, gerando <name>.json"""
    return subprocess.Popen([f"./enrichment/bin/{parser}", f"{output_dir}/{name}.html", f"{output_dir}/{name}.json"])


# Exemplo de uso
if __name__ == "__main__":
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    if not email or not password:
        raise SystemExit("Defina LINKEDIN_EMAIL e LINKEDIN_PASSWORD no ambiente")

    # Uso: python main.py [--visible] [<profile_url>]
    args = sys.argv[1:]
    visible = "--visible" in args
    urls = [a for a in args if a != "--visible"]
    profile_url = urls[0] if urls else input("Insira o URL do perfil a ser analisado: ")
    start_time = time.time()
    scraper = LinkedInScraper(headless=not visible)
    
    try:
        # Fazer login
        if scraper.ensure_login(email, password):
            base_url = profile_url.split("?")[0].rstrip("/") + "/"
            dir_name = base_url.replace("https://www.linkedin.com/in/", "").replace("/", "")
            output_dir = f"./output/{dir_name}"
            os.makedirs(output_dir, exist_ok=True)

            main_tab = scraper.driver.current_window_handle
            # Abre as seções de detalhe em abas para carregarem em paralelo com o perfil
            tabs = {
                name: scraper.open_tab(f"{base_url}{path}?locale=pt_BR")
                for name, path, _ in DETAIL_SECTIONS
            }
            parsers = []

            # Perfil
            scraper.driver.switch_to.window(main_tab)
            scraper.driver.get(base_url + "?locale=pt_BR")
            scraper.wait_until_stable()
            scraper.scroll_to_bottom()  # scroll até o fim
            scraper.click_more_buttons()  # expande todos os textos truncados
            scraper.save_html_and_screenshot("profile.html", output_dir)
            parsers.append(run_parser("linkedin-parser", output_dir, "profile"))

            # Experiências, formação e idiomas (já carregadas nas abas)
            for name, _, parser in DETAIL_SECTIONS:
                scraper.driver.switch_to.window(tabs[name])
                scraper.wait_until_stable()
                scraper.load_all_content()  # carrega tudo
                scraper.save_html_and_screenshot(f"{name}.html", output_dir)
                parsers.append(run_parser(parser, output_dir, name))

            for proc in parsers:
                proc.wait()

        else:
            print("Falha no login")
            
    except Exception as e:
        print(f"Erro geral: {str(e)}")
    
    finally:
        scraper.close()
        print(f"Tempo total: {time.time() - start_time} segundos")
