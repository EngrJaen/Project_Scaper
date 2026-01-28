import json
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException
)

# =========================
# CONFIG
# =========================
edge_options = Options()
BASE_URL = "https://scraping-trial-test.vercel.app"
SEARCH_TEXT = "Silver Tech"
OUTPUT_FILE = "output.json"
LOG_FILE = "scraper.log"

# =========================
# SETUP LOGGING
# =========================
logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

# HELPER FUNCTIONS
def safe_text(parent, by, value):
    """Return text if element exists, else empty string."""
    try:
        return parent.find_element(by, value).text.strip()
    except NoSuchElementException:
        return ""

def scrape_profile(profile_card):
    """Extract data from a business profile card."""
    data = {}
    try:
        data["Business Name"] = safe_text(profile_card, By.TAG_NAME, "h2")
        reg_text = safe_text(profile_card, By.XPATH, ".//div[@class='small muted' and contains(text(),'Registration')]")
        data["Registration ID"] = reg_text.split("-")[0].replace("Registration", "").strip() if reg_text else ""
        data["Status"] = safe_text(profile_card, By.XPATH, ".//span[contains(@class,'status')]")
        data["Filing Date"] = safe_text(profile_card, By.XPATH, ".//div[@class='small muted' and contains(text(),'Filing Date')]/following-sibling::div")
        
        # Registered Agent
        try:
            label = profile_card.find_element(By.XPATH, ".//div[@class='small muted' and text()='Registered Agent']")
            siblings = label.find_elements(By.XPATH, "following-sibling::div")
            data["Registered Agent"] = siblings[0].text.strip() if len(siblings) > 0 else ""
            data["Registered Agent Address"] = siblings[1].text.strip() if len(siblings) > 1 else ""
            data["Email"] = siblings[2].find_element(By.TAG_NAME, "code").text.strip() if len(siblings) > 2 else ""
        except NoSuchElementException:
            data["Registered Agent"] = ""
            data["Registered Agent Address"] = ""
            data["Email"] = ""
    except Exception as e:
        logging.warning(f"Error extracting profile: {e}")
    return data

# DRIVER SETUP
options = Options()
options.add_argument("--log-level=3")

driver = webdriver.Edge(options=options)
wait = WebDriverWait(driver, 10)



logging.info("Driver initialized and browser opened")

try:
    # OPEN BASE PAGE & SEARCH
    driver.get(BASE_URL)
    logging.info(f"Opened URL: {BASE_URL}")

    search_input = wait.until(EC.presence_of_element_located((By.ID, "q")))
    search_input.send_keys(SEARCH_TEXT)
    logging.info(f"Entered search text: {SEARCH_TEXT}")

    # Check for reCAPTCHA
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='recaptcha']")))
        logging.warning("reCAPTCHA detected. Manual intervention required.")
        input("Solve reCAPTCHA in the browser, then press ENTER...")
    except TimeoutException:
        logging.info("No reCAPTCHA detected.")

    search_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn")))
    search_button.click()
    logging.info("Search button clicked")

    # GET ALL BUSINESS LINKS
    table = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    rows = table.find_elements(By.XPATH, ".//tbody/tr")
    hrefs = [row.find_element(By.XPATH, "./td[1]/a").get_attribute("href") for row in rows]
    logging.info(f"Found {len(hrefs)} business links to scrape")

    # LOOP THROUGH LINKS
    all_data = []

    for idx, href in enumerate(hrefs):
        logging.info(f"Opening link {idx+1}/{len(hrefs)}: {href}")
        try:
            # Open in new tab
            driver.execute_script("window.open(arguments[0]);", href)
            driver.switch_to.window(driver.window_handles[-1])

            # Wait for profile card
            profile_card = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.card.fade-up")))
            data = scrape_profile(profile_card)
            all_data.append(data)
            logging.info(f"Scraped {idx+1}: {data.get('Business Name','')}")

            # Close tab and switch back
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            time.sleep(1)

        except Exception as e:
            logging.error(f"Error scraping link {idx+1}: {e}")
            try:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
            except:
                pass
            continue

    # SAVE TO JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)
    logging.info(f"All data saved to {OUTPUT_FILE}")

except Exception as e:
    logging.critical(f"Scraper terminated with error: {e}")

finally:
    logging.info("Scraper finished. Keeping browser open for 1 minute.")
    time.sleep(60)
    driver.quit()
