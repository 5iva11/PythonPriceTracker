from playwright.sync_api import sync_playwright
import smtplib
from email.mime.text import MIMEText
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import argparse
import csv
from dotenv import load_dotenv
import os

# Example: Amazon India product URL
load_dotenv()  # Load environment variables from .env file

PRODUCT_URL = os.getenv("PRODUCT_URL")
THRESHOLD_PRICE = int(os.getenv("THRESHOLD_PRICE", "50000"))
USER_EMAIL = os.getenv("USER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")
LOG_FILE = os.getenv("LOG_FILE", "price_log.txt")
CSV_FILE = os.getenv("CSV_FILE", "price_log.csv")


# Custom desktop user-agent (can be rotated later)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

def get_amazon_price(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
        user_agent=USER_AGENT,
        locale="en-IN",                 # English (India)
        timezone_id="Asia/Kolkata",     # Indian time zone
        geolocation={"longitude": 77.2090, "latitude": 28.6139},  # New Delhi
        permissions=["geolocation"]
    )
        page = context.new_page()

        print(f"Navigating to {url}")
        page.goto(url, timeout=60000)
        page.screenshot(path="debug.png")

        # Wait for price element to load (common Amazon price selectors)
        price = None
        #page.pause()  # Pause to allow manual inspection if needed
        try:
            if page.locator("text=Continue shopping").is_visible(timeout=5000):
                print("Continue button is visible, clicking it...")
                page.locator("text=Continue shopping").click()
            price = page.locator("//div[@id='corePriceDisplay_desktop_feature_div']//span[@class='a-price-whole']").inner_text()
            productTitle = page.locator("//span[@id='productTitle']").inner_text()
            print(f"Product Title: {productTitle.strip()}")
        except Exception as e:
            print(f"Error extracting price: {e}")

        browser.close()
        return price, productTitle if price else None

def send_email_alert(product_url, current_price, product_title=None):
    subject = f"Price Drop Alert: ₹{current_price}"
    body = (
        f"The price for {product_title} has dropped below your threshold!\n"
        f"Check the product: {product_url}"
    )
    message = MIMEText(body)
    message['Subject'] = subject
    message['From'] = USER_EMAIL
    message['To'] = TO_EMAIL

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(USER_EMAIL, APP_PASSWORD)
        server.send_message(message)
        print("✅ Email sent!")

# Test it
# ...existing code...

def check_price():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        price_title = get_amazon_price(PRODUCT_URL)
        if price_title:
            current_price, product_title = price_title
            if current_price:
                current_price_int = int(current_price.replace(",", "").strip())
                log_msg = f"{now} | Price: ₹{current_price_int}"
                print(log_msg)
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(log_msg + "\n")
                # Write to CSV
                write_header = False
                try:
                    with open(CSV_FILE, "r", encoding="utf-8") as f:
                        pass
                except FileNotFoundError:
                    write_header = True
                with open(CSV_FILE, "a", encoding="utf-8", newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    if write_header:
                        writer.writerow(["datetime", "price", "product_name"])
                    writer.writerow([now, current_price_int, product_title.strip() if product_title else ""])
                # ...existing code...
                if current_price_int <= THRESHOLD_PRICE:
                    print("✅ Price is below threshold! Sending email...")
                    send_email_alert(PRODUCT_URL, current_price_int, product_title)
                else:
                    print("ℹ️ Price is still above threshold.")
            else:
                log_msg = f"{now} | ❌ Failed to retrieve price."
                print(log_msg)
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(log_msg + "\n")
        else:
            log_msg = f"{now} | ❌ Failed to retrieve price and title."
            print(log_msg)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_msg + "\n")
    except Exception as e:
        err_msg = f"{now} | ❌ Exception occurred: {e}"
        print(err_msg)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(err_msg + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Price Tracker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the price check only once and exit."
    )
    args = parser.parse_args()

    if args.once:
        print("Running price check once...")
        check_price()
    else:
        scheduler = BlockingScheduler()
        scheduler.add_job(check_price, 'interval', minutes=2)
        print("Scheduler started. Checking price every 2 minutes...")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print("Scheduler stopped.")