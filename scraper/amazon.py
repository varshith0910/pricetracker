import requests
from bs4 import BeautifulSoup


class AmazonScraper:

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
    }

    def __init__(self, url):

        self.url = url
        self.soup = None

    # -------------------------
    # Fetch page
    # -------------------------

    def fetch_page(self):

        response = requests.get(
            self.url,
            headers=self.HEADERS,
            timeout=10
        )

        response.raise_for_status()

        self.soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

    # -------------------------
    # Get title
    # -------------------------

    def get_title(self):

        title = self.soup.find(
            "span",
            id="productTitle"
        )

        if not title:
            return None

        return title.get_text(strip=True)

    # -------------------------
    # Get price
    # -------------------------

    def get_price(self):

        price = self.soup.select_one(
            "span.a-price span.a-offscreen"
        )

        if price:

            price_text = price.get_text(strip=True)

            # ₹49,999.00 → 49999.00
            price_text = (
                price_text
                .replace("₹", "")
                .replace(",", "")
                .strip()
            )

            try:
                return float(price_text)

            except ValueError:
                return None

        # Fallback
        whole = self.soup.select_one(
            "span.a-price-whole"
        )

        fraction = self.soup.select_one(
            "span.a-price-fraction"
        )

        if whole:

            whole_text = (
                whole.get_text(strip=True)
                .replace(",", "")
                .replace(".", "")
            )

            fraction_text = (
                fraction.get_text(strip=True)
                if fraction
                else "00"
            )

            try:
                return float(
                    f"{whole_text}.{fraction_text}"
                )

            except ValueError:
                return None

        return None

    # -------------------------
    # Get image
    # -------------------------

    def get_image(self):

        image = self.soup.find(
            "img",
            id="landingImage"
        )

        if not image:
            return None

        return image.get("src")

    # -------------------------
    # Scrape everything
    # -------------------------

    def scrape(self):

        self.fetch_page()

        return {
            "url": self.url,
            "title": self.get_title(),
            "price": self.get_price(),
            "image_url": self.get_image()
        }