import os
from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

from database.database import SessionLocal, create_tables
from database.models import Product, PriceHistory, User

from scraper.amazon import AmazonScraper

from services.scheduler import start_scheduler, stop_scheduler
from services.price_checker import check_all_products ,check_product

from dotenv import load_dotenv

from starlette.middleware.sessions import (SessionMiddleware)

from fastapi.responses import RedirectResponse

from services.google_auth import oauth

load_dotenv()

class TargetPriceRequest(BaseModel):
    target_price: float = Field(gt=0)

@asynccontextmanager
async def lifespan(app: FastAPI):

    # -----------------------------
    # Startup
    # -----------------------------

    create_tables()

    start_scheduler()

    yield

    # -----------------------------
    # Shutdown
    # -----------------------------

    stop_scheduler()


app = FastAPI(
    title="Price Tracker API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY"),
    same_site="lax",
    https_only=False
)

@app.post("/products/check")
def check_products_now():

    check_all_products()

    return {
        "message": "Price check completed"
    }

# ==========================================
# Database dependency
# ==========================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()



# ==========================================
# Request model
# ==========================================

class ProductRequest(BaseModel):

    url: str

    email: EmailStr

    target_price: float | None = None

# ==========================================
# Health check
# ==========================================

@app.get("/")
def home():

    return {
        "message": "Price Tracker API is running"
    }


# ==========================================
# Add product
# ==========================================

@app.post("/products")
def add_product(
    request: ProductRequest,
    db: Session = Depends(get_db)
):

    # Check if URL already exists
    existing_product = (
        db.query(Product)
        .filter(Product.url == request.url)
        .first()
    )

    if existing_product:

        raise HTTPException(
            status_code=409,
            detail="Product already exists"
        )

    # -------------------------
    # Scrape product
    # -------------------------

    try:

        scraper = AmazonScraper(request.url)

        product_data = scraper.scrape()

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=f"Unable to scrape product: {str(e)}"
        )

    # Check scraper result
    if not product_data:
        raise HTTPException(
            status_code=400,
            detail="Unable to scrape product"
        )

    if product_data.get("error"):
        raise HTTPException(
            status_code=400,
            detail=product_data["error"]
        )

    # -------------------------
    # Create product
    # -------------------------

    product = Product(
        url=product_data["url"],
        title=product_data["title"],
        image_url=product_data["image_url"],
        email=request.email,
        target_price=request.target_price,
        alert_sent=False
    )

    try:
        db.add(product)
        db.flush()

        if product_data["price"] is not None:
            price_history = PriceHistory(
                product_id=product.id,
                price=product_data["price"]
            )
            db.add(price_history)

        db.commit()
        db.refresh(product)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

    return {
        "message": "Product added successfully",

        "product": {
            "id": product.id,
            "url": product.url,
            "title": product.title,
            "image_url": product.image_url,
            "price": product_data["price"]
        }
    }


@app.post("/products/{product_id}/check")
def manually_check_product(
    product_id: int
):

    check_product(product_id)

    return {
        "message": "Price check completed"
    }


# ==========================================
# Get all products
# ==========================================

@app.get("/products")
def get_products(
    db: Session = Depends(get_db)
):

    products = db.query(Product).all()

    result = []

    for product in products:

        latest_price = (
            db.query(PriceHistory)
            .filter(
                PriceHistory.product_id == product.id
            )
            .order_by(
                PriceHistory.checked_at.desc()
            )
            .first()
        )

        result.append({
            "id": product.id,
            "url": product.url,
            "title": product.title,
            "image_url": product.image_url,
            "price": (
                latest_price.price
                if latest_price
                else None
            )
        })

    return result


# ==========================================
# Get one product
# ==========================================

@app.get("/products/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_db)
):

    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    latest_price = (
        db.query(PriceHistory)
        .filter(
            PriceHistory.product_id == product.id
        )
        .order_by(
            PriceHistory.checked_at.desc()
        )
        .first()
    )

    return {
        "id": product.id,
        "url": product.url,
        "title": product.title,
        "image_url": product.image_url,
        "price": (
            latest_price.price
            if latest_price
            else None
        )
    }


# ==========================================
# Get price history
# ==========================================

@app.get("/products/{product_id}/history")
def get_price_history(
    product_id: int,
    db: Session = Depends(get_db)
):

    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    history = (
        db.query(PriceHistory)
        .filter(
            PriceHistory.product_id == product_id
        )
        .order_by(
            PriceHistory.checked_at.asc()
        )
        .all()
    )

    return [
        {
            "price": item.price,
            "checked_at": item.checked_at
        }
        for item in history
    ]


# ==========================================
# Delete product
# ==========================================

@app.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db)
):

    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    db.delete(product)

    db.commit()

    return {
        "message": "Product deleted successfully"
    }


# ==========================================
# Update Target
# ==========================================


@app.put("/products/{product_id}/target")
def update_target_price(
    product_id: int,
    request: TargetPriceRequest,
    db: Session = Depends(get_db)
):

    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    product.target_price = request.target_price

    # Allow another alert
    product.alert_sent = False

    db.commit()

    return {
        "message": "Target price updated",
        "target_price": product.target_price
    }

@app.get("/auth/google")
async def google_login(request: Request):

    redirect_uri = (
        os.getenv("GOOGLE_REDIRECT_URI")
    )

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri
    )

@app.get("/auth/google/callback")
async def google_callback( request: Request ):

    token = await oauth.google.authorize_access_token(
        request
    )

    user_info = token.get("userinfo")

    if not user_info:

        raise HTTPException(
            status_code=400,
            detail="Could not get Google user information"
        )

    google_id = user_info["sub"]

    email = user_info.get("email")

    name = user_info.get("name")

    picture = user_info.get("picture")