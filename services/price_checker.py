from database.database import SessionLocal
from database.models import Product, PriceHistory

from scraper.amazon import AmazonScraper

from services.email_service import (
    send_price_drop_email
)


def check_product(product_id: int):

    db = SessionLocal()

    try:

        # --------------------------------
        # Get product
        # --------------------------------

        product = (
            db.query(Product)
            .filter(
                Product.id == product_id
            )
            .first()
        )

        if not product:
            print(
                f"Product {product_id} not found"
            )
            return

        print(
            f"Checking: {product.title}"
        )

        # --------------------------------
        # Scrape current price
        # --------------------------------

        scraper = AmazonScraper( product.url )

        product_data = scraper.scrape()

        new_price = product_data.get( "price" )

        if new_price is None:

            print( "Could not find current price" )

            return

        # --------------------------------
        # Get previous price
        # --------------------------------

        previous_price = (
            db.query(PriceHistory)
            .filter(
                PriceHistory.product_id == product.id
            )
            .order_by(
                PriceHistory.checked_at.desc()
            )
            .first()
        )

        # --------------------------------
        # Compare
        # --------------------------------

        old_price = (
            previous_price.price
            if previous_price
            else new_price
        )
        if previous_price:

            print(
                f"Old: ₹{old_price}"
            )

            print(
                f"New: ₹{new_price}"
            )

            if (
                product.target_price is not None
                and new_price <= product.target_price
                and not product.alert_sent
                ):

                print("TARGET PRICE REACHED!")

                # Send email
                try:

                    send_price_drop_email(
                        recipient_email=product.email,
                        product_title=product.title,
                        product_url=product.url,
                        old_price=old_price,
                        new_price=new_price
                    )
                    # Prevent future emails
                    product.alert_sent = True

                    print("Alert sent!")
                    
                except Exception as e:

                    print(
                        f"Email failed: {e}"
                    )
            elif new_price > old_price:
                product.alert_sent = False
                print("Price increased")

            else:

                print("Price unchanged")

        else:

            print(
                "First price recorded"
            )

        # --------------------------------
        # Save new price
        # --------------------------------

        price_record = PriceHistory(
            product_id=product.id,
            price=new_price
        )

        db.add(price_record)

        db.commit()

    except Exception as e:

        db.rollback()

        print(
            f"Error checking product: {e}"
        )

    finally:

        db.close()


def check_all_products():

    db = SessionLocal()

    try:

        products = db.query(Product).all()

        print(
            f"\nChecking {len(products)} products..."
        )

        product_ids = [
            product.id
            for product in products
        ]

    finally:

        db.close()

    # Important:
    # Don't keep one DB session open while
    # making network requests.

    for product_id in product_ids:

        check_product(product_id)