import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from starlette.middleware.sessions import SessionMiddleware

from database.database import SessionLocal, create_tables
from database.models import PriceHistory, Product, Tracking, User
from scraper.amazon import AmazonScraper
from services.google_auth import oauth
from services.price_checker import check_all_products, check_product
from services.scheduler import start_scheduler, stop_scheduler

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Price Tracker API", version="1.0.0", lifespan=lifespan)
session_secret = os.getenv("SESSION_SECRET") or os.getenv("SECRET_KEY")
if not session_secret:
    raise RuntimeError("SESSION_SECRET must be configured")
app.add_middleware(SessionMiddleware, secret_key=session_secret, same_site="lax",
                   https_only=os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true")


class ProductRequest(BaseModel):
    url: str
    target_price: float = Field(gt=0)


class TargetPriceRequest(BaseModel):
    target_price: float = Field(gt=0)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def get_user_tracking_or_404(tracking_id: int, user: User, db: Session) -> Tracking:
    tracking = (db.query(Tracking).options(joinedload(Tracking.product))
                .filter(Tracking.id == tracking_id, Tracking.user_id == user.id).first())
    if not tracking:
        raise HTTPException(status_code=404, detail="Tracking record not found")
    return tracking


def get_product_tracking_or_404(product_id: int, user: User, db: Session) -> Tracking:
    tracking = (db.query(Tracking).options(joinedload(Tracking.product))
                .filter(Tracking.product_id == product_id, Tracking.user_id == user.id).first())
    if not tracking:
        raise HTTPException(status_code=404, detail="Product not found")
    return tracking


def serialize_tracking(tracking: Tracking, db: Session) -> dict:
    product = tracking.product
    latest_price = (db.query(PriceHistory).filter(PriceHistory.product_id == product.id)
                    .order_by(PriceHistory.checked_at.desc()).first())
    return {"tracking_id": tracking.id, "id": product.id, "url": product.url,
            "title": product.title, "image_url": product.image_url,
            "price": float(latest_price.price) if latest_price else None,
            "target_price": float(tracking.target_price), "alert_sent": tracking.alert_sent}


@app.get("/")
def home():
    return {"message": "Price Tracker API is running"}


@app.get("/auth/google")
async def google_login(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if not redirect_uri:
        raise HTTPException(status_code=500, detail="GOOGLE_REDIRECT_URI is not configured")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Google authentication failed") from exc
    user_info = token.get("userinfo")
    if not user_info:
        user_info = (await oauth.google.get("userinfo", token=token)).json()
    google_id, email = user_info.get("sub"), user_info.get("email")
    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Google did not provide a user identity")
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = User(google_id=google_id, email=email)
        db.add(user)
    user.email, user.name, user.picture = email, user_info.get("name"), user_info.get("picture")
    db.commit()
    db.refresh(user)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse(url="/me", status_code=303)


@app.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out"}


@app.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture}


@app.post("/products")
def add_product(request: ProductRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product = db.query(Product).filter(Product.url == request.url).first()
    if not product:
        try:
            product_data = AmazonScraper(request.url).scrape()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Unable to scrape product: {exc}") from exc
        if not product_data or product_data.get("error"):
            raise HTTPException(status_code=400, detail=(product_data or {}).get("error", "Unable to scrape product"))
        product = Product(url=product_data["url"], title=product_data["title"], image_url=product_data["image_url"], current_price=product_data["price"])
        db.add(product)
        db.flush()
        if product_data["price"] is not None:
            db.add(PriceHistory(product_id=product.id, price=product_data["price"]))
    if db.query(Tracking).filter(Tracking.user_id == user.id, Tracking.product_id == product.id).first():
        raise HTTPException(status_code=409, detail="You are already tracking this product")
    tracking = Tracking(user_id=user.id, product_id=product.id, target_price=request.target_price)
    db.add(tracking)
    db.commit()
    db.refresh(tracking)
    return {"message": "Product is now being tracked", "product": serialize_tracking(tracking, db)}


@app.get("/products")
@app.get("/trackings")
def get_products(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trackings = db.query(Tracking).options(joinedload(Tracking.product)).filter(Tracking.user_id == user.id).all()
    return [serialize_tracking(tracking, db) for tracking in trackings]


@app.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return serialize_tracking(get_product_tracking_or_404(product_id, user, db), db)


@app.get("/trackings/{tracking_id}")
def get_tracking(tracking_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return serialize_tracking(get_user_tracking_or_404(tracking_id, user, db), db)


@app.get("/products/{product_id}/history")
def get_price_history(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_product_tracking_or_404(product_id, user, db)
    history = db.query(PriceHistory).filter(PriceHistory.product_id == product_id).order_by(PriceHistory.checked_at.asc()).all()
    return [{"price": float(item.price), "checked_at": item.checked_at} for item in history]


@app.post("/products/{product_id}/check")
def manually_check_product(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_product_tracking_or_404(product_id, user, db)
    check_product(product_id)
    return {"message": "Price check completed"}


@app.post("/products/check")
def check_products_now(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product_ids = [row[0] for row in db.query(Tracking.product_id).filter(Tracking.user_id == user.id).all()]
    check_all_products(product_ids)
    return {"message": "Price check completed"}


@app.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(get_product_tracking_or_404(product_id, user, db))
    db.commit()
    return {"message": "Product tracking removed"}


@app.delete("/trackings/{tracking_id}")
def delete_tracking(tracking_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(get_user_tracking_or_404(tracking_id, user, db))
    db.commit()
    return {"message": "Product tracking removed"}


@app.put("/products/{product_id}/target")
def update_target_price(product_id: int, request: TargetPriceRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tracking = get_product_tracking_or_404(product_id, user, db)
    tracking.target_price, tracking.alert_sent = request.target_price, False
    db.commit()
    return {"message": "Target price updated", "target_price": tracking.target_price}


@app.put("/trackings/{tracking_id}/target")
def update_tracking_target(tracking_id: int, request: TargetPriceRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tracking = get_user_tracking_or_404(tracking_id, user, db)
    tracking.target_price, tracking.alert_sent = request.target_price, False
    db.commit()
    return {"message": "Target price updated", "target_price": tracking.target_price}
