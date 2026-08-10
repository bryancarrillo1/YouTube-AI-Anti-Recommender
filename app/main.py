import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.errors import AppError
from app.models import AntiRecommendationRequest, AntiRecommendationResponse, ErrorResponse
from app.services.recommender import RecommenderService

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="YouTube Anti-Recommender")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    logger.warning("Request failed: code=%s status=%s", exc.code, exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(code=exc.code, message=exc.message).model_dump(),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/anti-recommendations", response_model=AntiRecommendationResponse)
@limiter.limit("10/minute")
async def anti_recommendations(request: Request, payload: AntiRecommendationRequest) -> AntiRecommendationResponse:
    service = RecommenderService()
    return service.generate_anti_recommendations(payload)
