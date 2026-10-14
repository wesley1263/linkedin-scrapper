import os
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import tempfile
from selenium.webdriver.common.keys import Keys

COOKIES_FILE = "linkedin_cookies.json"
class LinkedInScraper:
    def __init__(self):
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Configura o driver do Chrome com opções anti-detecção"""
        options = Options()
        # Perfil persistente
        options.add_argument("--user-data-dir=/home/weslei/.linkedin_chrome_profile")
        # options.add_argument("--headless") 
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
            if "/checkpoint" in self.driver.current_url:
                print("Verificação de segurança detectada, resolva no navegador (até 2 min)...")
                WebDriverWait(self.driver, 120).until(lambda d: "/feed" in d.current_url)
            
            print("Login realizado com sucesso!")
            return True
            
        except Exception as e:
            print(f"Erro no login: {str(e)}")
            return False

    def scroll_to_bottom(self):
        """Scroll usando teclas - mais confiável"""
        # Clica em algum lugar da página primeiro pra garantir foco
        self.driver.find_element(By.TAG_NAME, "body").click()
        time.sleep(0.3)
        
        body = self.driver.find_element(By.TAG_NAME, "body")
        
        last_height = self.driver.execute_script("return document.documentElement.scrollTop")
        
        for i in range(20):
            body.send_keys(Keys.END)  # vai direto pro fim
            time.sleep(1)
            
            new_height = self.driver.execute_script("return document.documentElement.scrollTop")
            if new_height == last_height:
                break
            last_height = new_height
        
        print(f"Scroll finalizado. Posição: {last_height}")

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
            
    def load_all_content(self):
        """Clica em Load more até não haver mais"""
        clicks = 0
        while True:
            try:
                button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Load more']]"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView();", button)
                time.sleep(0.5)
                button.click()
                clicks += 1
                time.sleep(2)
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
                    time.sleep(0.3)
                except:
                    continue
            
            return len(buttons)
        except:
            return 0

# Exemplo de uso
if __name__ == "__main__":
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    if not email or not password:
        raise SystemExit("Defina LINKEDIN_EMAIL e LINKEDIN_PASSWORD no ambiente")

    profile_url = input("Insira o URL do perfil a ser analisado: ")
    start_time = time.time()
    scraper = LinkedInScraper()
    
    try:
        # Fazer login
        if scraper.ensure_login(email, password):
            # URL do perfil a ser analisado
            dir_name = profile_url.replace("https://www.linkedin.com/in/", "").replace("/", "")
            output_dir = f"./output/{dir_name}"
            os.makedirs(output_dir, exist_ok=True)

            scraper.driver.get(profile_url + "?locale=pt_BR")
            time.sleep(10)
            scraper.scroll_to_bottom()  # scroll até o fim
            # scraper.find_scrollable_container()  # encontra containers scrolláveis
            scraper.click_more_buttons()  # expande todos os textos truncados
            scraper.save_html_and_screenshot("profile.html", output_dir)
            os.system(f"./linkedin-parser {output_dir}/profile.html {output_dir}/profile.json")
            # os.remove(f"{output_dir}/profile.html")

            # Experiências
            scraper.driver.get(profile_url + "details/experience/?locale=pt_BR")
            time.sleep(3)  # espera inicial
            scraper.load_all_content()  # carrega tudo
            scraper.save_html_and_screenshot("experience.html", output_dir)
            os.system(f"./experience-parser {output_dir}/experience.html {output_dir}/experience.json")
            # os.remove(f"{output_dir}/experience.html")

            # Formação Acadêmica
            scraper.driver.get(profile_url + "details/education/?locale=pt_BR")
            time.sleep(3)  # espera inicial
            scraper.load_all_content()  # carrega tudo
            scraper.save_html_and_screenshot("education.html", output_dir)
            os.system(f"./education-parser {output_dir}/education.html {output_dir}/education.json")
            # os.remove(f"{output_dir}/education.html")

            # Idiomas
            scraper.driver.get(profile_url + "details/languages/?locale=pt_BR")
            time.sleep(3)  # espera inicial
            scraper.load_all_content()  # carrega tudo
            scraper.save_html_and_screenshot("languages.html", output_dir)
            os.system(f"./language-parser {output_dir}/languages.html" f" {output_dir}/languages.json")
            # os.remove(f"{output_dir}/languages.html")
            
        else:
            print("Falha no login")
            
    except Exception as e:
        print(f"Erro geral: {str(e)}")
    
    finally:
        scraper.close()
        print(f"Tempo total: {time.time() - start_time} segundos")
