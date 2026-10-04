import os
import smtplib

from email.message import EmailMessage


SMTP_HOST = os.getenv(
    "SMTP_HOST",
    "smtp.gmail.com"
)

SMTP_PORT = int(
    os.getenv(
        "SMTP_PORT",
        "465"
    )
)

EMAIL_ADDRESS = os.getenv(
    "EMAIL_ADDRESS"
)

EMAIL_PASSWORD = os.getenv(
    "EMAIL_PASSWORD"
)


def send_price_drop_email(
    recipient_email: str,
    product_title: str,
    product_url: str,
    old_price: float,
    new_price: float
):

    drop_amount = old_price - new_price

    drop_percentage = (
        drop_amount / old_price
    ) * 100

    message = EmailMessage()

    message["Subject"] = (
        f"Price Drop Alert: {product_title}"
    )

    message["From"] = EMAIL_ADDRESS
    message["To"] = recipient_email

    message.set_content(
                f"""
        Price Drop Alert!

        Product: {product_title}

        Old Price: ₹{old_price:,.2f}

        New Price: ₹{new_price:,.2f}

        You save: ₹{drop_amount:,.2f}

        Price dropped by: {drop_percentage:.2f}%

        Product URL: {product_url}

        Happy shopping!
        """
    )

    with smtplib.SMTP_SSL( SMTP_HOST, SMTP_PORT ) as smtp:

        smtp.login(
            EMAIL_ADDRESS,
            EMAIL_PASSWORD
        )

        smtp.send_message(message)

    print(
        f"Price drop email sent to "
        f"{recipient_email}"
        )