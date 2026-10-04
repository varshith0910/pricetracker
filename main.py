from database.database import create_tables, SessionLocal
from scraper.amazon import AmazonScraper
from database.models import Product, PriceHistory


def save_product(product_data, email, target_price):
    if not product_data:
        print("No product data received")
        return None

    db = SessionLocal()

    try:
        # Check if product already exists
        product = (
            db.query(Product)
            .filter(Product.url == product_data["url"])
            .first()
        )

        if product:
            # Existing product
            product.title = product_data["title"]
            product.image_url = product_data["image_url"]
            product.email = email
            product.target_price = target_price

            print("Existing product")

        else:
            # New product
            product = Product(
                url=product_data["url"],
                title=product_data["title"],
                image_url=product_data["image_url"],
                email=email,
                current_price=product_data["price"],
                target_price=target_price
            )

            db.add(product)

            # Generate product.id
            db.flush()

            print("New product")

        # Update current price
        if product_data["price"] is not None:
            product.current_price = product_data["price"]

            # Add price to price history
            price_record = PriceHistory(
                product_id=product.id,
                price=product_data["price"]
            )

            db.add(price_record)

        db.commit()
        db.refresh(product)

        return product

    except Exception as e:
        db.rollback()
        print("Database error:", e)
        return None

    finally:
        db.close()


def main():

    # Create database tables
    create_tables()

    # Product information
    url = "https://amzn.in/d/002E4AH4"

    email = "your_email@gmail.com"

    target_price = 75000

    # Scrape
    scraper = AmazonScraper(url)

    product_data = scraper.scrape()

    print("\nScraped data:")
    print(product_data)

    # Stop if scraping failed
    if not product_data:
        return

    # Save to database
    product = save_product(
        product_data,
        email,
        target_price
    )

    if product:
        print("\nDatabase:")
        print("ID:", product.id)
        print("Title:", product.title)
        print("Current Price:", product.current_price)
        print("Target Price:", product.target_price)
        print("Email:", product.email)
        print("Image:", product.image_url)


if __name__ == "__main__":
    main()