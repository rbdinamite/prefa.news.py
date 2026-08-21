from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import crud, schemas
from app.config import get_settings
from app.database import Base, engine, get_db

settings = get_settings()

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["current_year"] = datetime.utcnow().year


@app.on_event("startup")
def on_startup() -> None:
    # In production prefer Alembic; for simplicity local/demo we create the tables automatically if they don't exist.
    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# Pages (server-side rendering with Jinja2)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    news = crud.load_main_news(db, sector=None, search=None)
    insights = crud.load_insights(db)
    #sectors = crud.load_sector_news(db, search=None)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "news": news, "insights": insights, "active_page": "home"},
    )


@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: str = "", db: Session = Depends(get_db)):
    news = crud.load_main_news(db, sector=None, search=q) if q else {"main": [], "side": [], "roller": [], "more": []}
    return templates.TemplateResponse(
        "search.html",
        {"request": request, "news": news, "query": q, "active_page": "search"},
    )


@app.get("/about", response_class=HTMLResponse)
def about_page(request: Request, db: Session = Depends(get_db)):
    cities = crud.load_active_cities(db)
    return templates.TemplateResponse(
        "about.html", {"request": request, "cities": cities, "active_page": "about"}
    )


@app.get("/support", response_class=HTMLResponse)
def support_page(request: Request):
    return templates.TemplateResponse("support.html", {"request": request, "active_page": "support"})


# ---------------------------------------------------------------------------
# API JSON (equivalent to the actions of the old sys/controller.php)
# ---------------------------------------------------------------------------

api = APIRouter()


@api.get("/news/main", response_model=schemas.NewsBlock)
def api_main_news(
    sector: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    data = crud.load_main_news(db, sector, search)
    return data


@api.get("/news/more-fixed", response_model=list[schemas.NewsOut])
def api_more_fixed(
    sector: str | None = None, search: str | None = None, db: Session = Depends(get_db)
):
    return crud.load_more_fixed_news(db, sector, search)


@api.get("/news/more", response_model=list[schemas.NewsOut])
def api_more_by_pointer(
    pointer: int = 0,
    sector: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    return crud.load_more_by_pointer(db, pointer, sector, search)


@api.get("/news/highlights", response_model=list[schemas.NewsOut])
def api_star_news(db: Session = Depends(get_db)):
    return crud.get_star_news(db)


@api.get("/cities/active", response_model=list[str])
def api_active_cities(db: Session = Depends(get_db)):
    return crud.load_active_cities(db)


@api.get("/cities/highlight", response_model=schemas.StarCityOut)
def api_star_city(db: Session = Depends(get_db)):
    return crud.get_star_city(db)


@api.post("/access", response_model=schemas.MessageOut)
def api_save_click(payload: schemas.AccessIn, request: Request, db: Session = Depends(get_db)):
    server_meta = json.dumps(
        {
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
    )
    crud.save_click(db, payload.news_id, payload.type, server_meta)
    return {"result": True, "message": "Data registered successfully"}


@api.post("/newsletter", response_model=schemas.MessageOut)
def api_save_newsletter(payload: schemas.NewsletterIn, db: Session = Depends(get_db)):
    if crud.newsletter_email_exists(db, payload.mail):
        raise HTTPException(status_code=409, detail="Email already registered")
    crud.save_newsletter(db, payload.mail)
    return {"result": True, "message": "Email registered successfully"}


app.include_router(api, prefix="/api")
