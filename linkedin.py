"""
LinkedIn PDF Downloader
Uso: python linkedin.py <profile_url>
Exemplo: python linkedin.py https://www.linkedin.com/in/wansilvasan/
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import os
import sys
import logging
import random

# -------------------------
# Configuração de logging
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# -------------------------
# CONFIGURAÇÕES
# -------------------------
EMAIL = "weslei.souza.flowef@gmail.com"
PASSWORD = "Raqwes252123@3"
DOWNLOAD_DIR = "./resumes"
TIMEOUT = 30
# -------------------------
# FUNÇÕES AUXILIARES
# -------------------------

def setup_driver():
    """Configura e retorna o driver Chrome"""
    print("🔧 Configurando navegador...")
    
    # Criar diretório de downloads se não existir
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    abs_download_path = os.path.abspath(DOWNLOAD_DIR)
    
    chrome_options = Options()
    
    # Configurações básicas
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Anti-detecção
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Configurar downloads
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": abs_download_path,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(TIMEOUT)
    
    # Remover indicadores de automação
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    print("✅ Navegador configurado")
    return driver

def wait_and_find(driver, by, value, timeout=TIMEOUT):
    """Aguarda e retorna elemento"""
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, value))
    )

def wait_and_click(driver, by, value, timeout=TIMEOUT):
    """Aguarda elemento ser clicável e retorna"""
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )

def login(driver):
    """Faz login no LinkedIn"""
    print("🔐 Fazendo login...")
    
    try:
        driver.get("https://www.linkedin.com/login")
        time.sleep(2)
        
        # Preencher email
        email_input = wait_and_find(driver, By.ID, "username")
        email_input.clear()
        email_input.send_keys(EMAIL)
        
        # Preencher senha
        password_input = wait_and_find(driver, By.ID, "password")
        password_input.clear()
        password_input.send_keys(PASSWORD)
        
        time.sleep(1)
        
        # Clicar em login
        login_button = wait_and_click(driver, By.XPATH, "//button[@type='submit']")
        login_button.click()
        
        # Aguardar redirecionamento
        print("⏳ Aguardando login...")
        WebDriverWait(driver, TIMEOUT).until(
            lambda d: "feed" in d.current_url or "checkpoint" in d.current_url
        )
        
        if "feed" in driver.current_url or "checkpoint" in driver.current_url:
            print("✅ Login realizado com sucesso!")
            time.sleep(3)
            return True
        else:
            print("❌ Falha no login")
            return False
            
    except Exception as e:
        print(f"❌ Erro durante login: {e}")
        return False

def download_profile_pdf(driver, profile_url):
    """Baixa o PDF do perfil"""
    print(f"📄 Acessando perfil: {profile_url}")
    
    try:
        # Acessar perfil
        driver.get(profile_url)
        time.sleep(15)
        
        # Extrair username do perfil para nome do arquivo
        profile_username = profile_url.rstrip('/').split('/')[-1]
        
        print("🔍 Procurando botão de menu...")
        
        # Tentar encontrar botão "Mais ações" / "More actions"
        overflow_selectors = [
            # Busca por aria-label exato
            '//button[@aria-label="More actions"]',
            '//button[@aria-label="Mais ações"]',
            # Busca por classe + texto "More"
            '//button[contains(@class, "artdeco-dropdown__trigger")]//span[text()="More"]',
            '//button[contains(@class, "artdeco-dropdown__trigger")]//span[text()="Mais"]',
            # Busca apenas pela classe artdeco-dropdown__trigger
            '//button[contains(@class, "artdeco-dropdown__trigger")][contains(@class, "artdeco-button--secondary")]',
            # Busca por ID pattern (se existir)
            '//button[contains(@id, "profile-overflow-action")]',
            # Fallback: qualquer botão com "More" ou "Mais"
            '//button[contains(@aria-label, "More")]',
            '//button[contains(@aria-label, "Mais")]'
        ]
        
        overflow_btn = None
        for selector in overflow_selectors:
            try:
                if selector.startswith("//"):
                    overflow_btn = wait_and_click(driver, By.XPATH, selector, timeout=5)
                else:
                    overflow_btn = wait_and_click(driver, By.CSS_SELECTOR, selector, timeout=5)
                
                if overflow_btn:
                    print("✅ Botão de menu encontrado")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", overflow_btn)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", overflow_btn)
                    print("✅ Menu aberto")
                    time.sleep(2)
                    break
            except:
                continue
        
        if not overflow_btn:
            print("❌ Botão de menu não encontrado")
            return None
        
        print("🔍 Procurando opção 'Salvar como PDF'...")
        
        # Tentar encontrar botão "Salvar como PDF" / "Save as PDF"
        pdf_selectors = [
            # Buscar pelo aria-label (mais confiável)
            '//div[@aria-label="Save to PDF"]',
            '//div[@aria-label="Salvar como PDF"]',
            # Buscar pelo texto do span
            '//span[text()="Save to PDF"]/parent::div',
            '//span[text()="Salvar como PDF"]/parent::div',
            # Buscar por contains no texto
            '//div[contains(@class, "artdeco-dropdown__item")]//span[contains(text(), "Save to PDF")]',
            '//div[contains(@class, "artdeco-dropdown__item")]//span[contains(text(), "Salvar como PDF")]',
            # Buscar pelo SVG de download + texto
            '//div[contains(@class, "artdeco-dropdown__item")][.//use[@href="#download-medium"]]',
        ]
        
        pdf_btn = None
        for selector in pdf_selectors:
            try:
                pdf_btn = wait_and_click(driver, By.XPATH, selector, timeout=5)
                if pdf_btn:
                    print("✅ Opção 'Salvar como PDF' encontrada")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pdf_btn)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", pdf_btn)
                    print("✅ Download iniciado")
                    break
            except:
                continue
        
        if not pdf_btn:
            print("❌ Opção 'Salvar como PDF' não encontrada")
            return None
        
        # Aguardar download
        print("⏳ Aguardando conclusão do download...")
        time.sleep(10)
        
        # Verificar se arquivo foi baixado
        expected_patterns = [
            f"{profile_username}.pdf",
            "Profile.pdf",
            "Perfil.pdf"
        ]
        
        max_wait = 60  # 1 minuto
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            for file in os.listdir(DOWNLOAD_DIR):
                if file.endswith('.pdf'):
                    file_path = os.path.join(DOWNLOAD_DIR, file)
                    file_size = os.path.getsize(file_path)
                    
                    if file_size > 1024:  # Pelo menos 1KB
                        # Renomear para padrão
                        new_name = f"{profile_username}.pdf"
                        new_path = os.path.join(DOWNLOAD_DIR, new_name)
                        
                        if file_path != new_path:
                            os.rename(file_path, new_path)
                        
                        print(f"✅ PDF baixado com sucesso: {new_path}")
                        print(f"📊 Tamanho: {file_size / 1024:.2f} KB")
                        return new_path
            
            time.sleep(2)
        
        print("⚠️ Download não concluído no tempo esperado")
        return None
        
    except Exception as e:
        print(f"❌ Erro ao baixar PDF: {e}")
        return 

def human_like_delay(min_seconds=1, max_seconds=3):
    """Adiciona um delay aleatório para simular comportamento humano"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

def try_download(perfil, driver):
    """Tenta baixar o PDF do perfil"""
    
    if driver is None:
        return None
        
    logging.info(f"Tentando baixar PDF de: {perfil}")
    
    try:
        logging.info(f"Carregando perfil: {perfil}")
        driver.get(perfil)
        human_like_delay(10, 15)
        
        
        # Verificar se carregou corretamente
        if perfil not in driver.current_url:
            logging.error(f"Redirecionado para: {driver.current_url}")
            return None
        
        # PRIMEIRO: Abrir o menu de overflow (botão "Mais")
        overflow_selectors = [
            'button[aria-label="Mais ações"]',
            'button[aria-label*="Mais ações"]',
            'button[aria-label*="More actions"]',
            'button[aria-label="More actions"]',
            '//button[contains(., "Mais")]',
            '//button[contains(., "More")]',
            '//span[contains(., "Mais")]/parent::button',
            '//span[contains(., "More")]/parent::button',
        ]
        
        overflow_btn = None
        for selector in overflow_selectors:
            try:
                logging.info(f"Tentando seletor de overflow: {selector}")
                if selector.startswith("//"):
                    overflow_btn = wait_and_click(driver, By.XPATH, selector, timeout=5)
                else:
                    overflow_btn = wait_and_click(driver, By.CSS_SELECTOR, selector, timeout=5)
                
                # Verificar se o botão está visível e habilitado
                if overflow_btn.is_displayed() and overflow_btn.is_enabled():
                    # Rolar até o botão para garantir visibilidade
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", overflow_btn)
                    human_like_delay(1, 2)
                    
                    # Tentar clicar via JavaScript (mais robusto)
                    driver.execute_script("arguments[0].click();", overflow_btn)
                    logging.info("Menu de overflow aberto com sucesso (via JS)")
                    human_like_delay(3, 5)  # Esperar o menu abrir completamente
                    
                    break
                else:
                    logging.warning("Botão de overflow encontrado mas não está clicável")
                    continue
                
            except TimeoutException:
                logging.warning(f"Seletor de overflow não encontrado: {selector}")
                continue
            except Exception as e:
                logging.warning(f"Erro ao clicar no overflow {selector}: {e}")
                continue
        
        if not overflow_btn:
            logging.error("Nenhum botão de overflow encontrado após tentar todos os seletores")
            return None
        
        # SEGUNDO: Procurar o botão de download PDF no menu aberto
        pdf_selectors = [
            '//*[contains(text(), "Salvar como PDF")]',
            '//*[contains(text(), "Save as PDF")]',
            '//span[contains(., "Salvar como PDF")]',
            '//span[contains(., "Save as PDF")]',
            'button[aria-label*="Salvar como PDF"]',
            'button[aria-label*="Save as PDF"]',
        ]
        
        pdf_btn = None
        for selector in pdf_selectors:
            try:
                logging.info(f"Tentando seletor de PDF: {selector}")
                if selector.startswith("//"):
                    pdf_btn = wait_and_click(driver, By.XPATH, selector, timeout=5)
                else:
                    pdf_btn = wait_and_click(driver, By.CSS_SELECTOR, selector, timeout=5)
                
                if pdf_btn.is_displayed() and pdf_btn.is_enabled():
                    # Rolar até o elemento
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pdf_btn)
                    human_like_delay(1, 2)
                    
                    # Clicar via JavaScript (mais confiável)
                    driver.execute_script("arguments[0].click();", pdf_btn)
                    logging.info("Botão de PDF clicado com sucesso (via JS)")
                    
                    # Tirar screenshot após clicar no PDF
                    break
                else:
                    logging.warning("Botão de PDF encontrado mas não está clicável")
                    continue
                    
            except TimeoutException:
                logging.warning(f"Seletor de PDF não encontrado: {selector}")
                continue
            except Exception as e:
                logging.warning(f"Erro ao clicar no PDF {selector}: {e}")
                continue
        
        if not pdf_btn:
            logging.error("Nenhum botão de PDF encontrado após abrir o menu")
            return None
        
        # Aguardar download iniciar
        logging.info("Aguardando download iniciar...")
        human_like_delay(10, 15)
        
        
        # Verificar se arquivo foi baixado
        expected_file = f"/{DOWNLOAD_DIR}/{perfil}.pdf"
        max_wait = 300  # 5 minutos para download
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if os.path.exists(expected_file):
                current_size = os.path.getsize(expected_file)
                if current_size > 1024:  # Pelo menos 1KB
                    logging.info(f"PDF baixado com sucesso: {expected_file} ({current_size} bytes)")
                    return expected_file
            
            logging.info("Aguardando conclusão do download...")
            time.sleep(5)
        
        logging.warning("Download não concluído dentro do tempo esperado")
        return None
        
    except TimeoutException as e:
        logging.error(f"Timeout ao processar perfil {perfil}: {e}")
        return None
    except Exception as e:
        logging.error(f"Erro ao baixar PDF: {e}")
        return None

# -------------------------
# FUNÇÃO PRINCIPAL
# -------------------------

def main(profile_url):
    """Função principal"""
    driver = None
    
    try:
        # Validar URL
        if not profile_url.startswith("https://www.linkedin.com/in/"):
            print("❌ URL inválida. Use: https://www.linkedin.com/in/<username>/")
            return
        
        # Setup
        driver = setup_driver()
        
        # Login
        if not login(driver):
            print("❌ Não foi possível fazer login")
            return
        
        # Download PDF
        #pdf_path = download_profile_pdf(driver, profile_url)
        pdf_path = try_download(profile_url, driver)
        
        if pdf_path:
            print("\n" + "="*50)
            print("🎉 SUCESSO!")
            print(f"📁 Arquivo salvo em: {pdf_path}")
            print("="*50)
        else:
            print("\n" + "="*50)
            print("❌ Falha ao baixar PDF")
            print("="*50)
        
    except KeyboardInterrupt:
        print("\n⚠️ Operação cancelada pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro geral: {e}")
    finally:
        if driver:
            print("\n🔒 Fechando navegador...")
            driver.quit()
            print("✅ Concluído")

# -------------------------
# EXECUÇÃO
# -------------------------

if __name__ == "__main__":
    print("\n" + "="*50)
    print("LinkedIn PDF Downloader")
    print("="*50 + "\n")
    
    # Verificar argumentos
    if len(sys.argv) < 2:
        print("❌ Uso: python linkedin.py <profile_url>")
        print("\nExemplo:")
        print("python linkedin.py https://www.linkedin.com/in/wansilvasan/")
        sys.exit(1)
    
    profile_url = sys.argv[1]
    main(profile_url)