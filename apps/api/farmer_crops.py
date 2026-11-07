"""API endpoints for Farmer Crops inventory management supporting all 7 commodities."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from cropmandi.db.models import FarmerCrop, User

router = APIRouter(tags=["farmer_crops"])

SUPPORTED_COMMODITIES = {
    "coffee": "Coffee",
    "pepper": "Black Pepper",
    "cardamom": "Cardamom",
    "paddy": "Paddy",
    "tomato": "Tomato",
    "potato": "Potato",
    "maize": "Maize",
}

COMMODITY_ALIASES = {
    "black pepper": "pepper",
    "black_pepper": "pepper",
    "rice": "paddy",
    "corn": "maize",
}

COMMODITY_IMAGES = {
    "coffee": "assets/crops/coffee.jpg",
    "pepper": "assets/crops/black-pepper.jpg",
    "cardamom": "assets/crops/cardamom.jpg",
    "paddy": "assets/crops/paddy.jpg",
    "tomato": "assets/crops/tomato.jpg",
    "potato": "assets/crops/potato.jpg",
    "maize": "assets/crops/maize.jpg",
}

VARIETY_CATALOG = {
    "coffee": [
        "Arabica Parchment",
        "Arabica Cherry",
        "Robusta Parchment",
        "Robusta Cherry",
    ],
    "pepper": [
        "Cochin Garbled",
        "Cochin Ungarbled",
        "Sirsi",
    ],
    "cardamom": [
        "Small Cardamom (Green)",
        "Medium Grade (7mm)",
        "Bold Grade (8mm+)",
        "Super Bold",
    ],
    "paddy": [
        "Paddy (Dhan) (Common)",
        "Basmati",
        "Sona Masuri",
        "I.R. 64",
        "Jyothi",
        "Jaya",
    ],
    "tomato": [
        "Hybrid Tomato",
        "Local / Desi",
        "Roma",
    ],
    "potato": [
        "Jyoti",
        "Kufri Chandramukhi",
        "Kufri Lauvkar",
        "Common / Desi",
    ],
    "maize": [
        "Yellow Maize (Feed)",
        "White Maize",
        "Sweet Corn",
        "Local",
    ],
}

DEFAULT_LOCATIONS = {
    "coffee": ["Chikkamagaluru", "Sakleshpur", "Madikeri", "Mudigere", "Hassan", "Kushalnagar", "Somwarpet", "Gonikoppal"],
    "pepper": ["Kochi (Cochin)", "Sirsi", "Wayanad", "Idukki", "Shivamogga", "Madikeri", "Chikkamagaluru"],
    "cardamom": ["Sakleshpur", "Madikeri", "Mudigere", "Idukki", "Bodinayakanur"],
    "paddy": ["Davanagere", "Shivamogga", "Mandya", "Haveri", "Mysuru", "Koppal", "Raichur", "Ballari"],
    "tomato": ["Kolar", "Bengaluru", "Chikkaballapura", "Belagavi", "Mysuru", "Hassan"],
    "potato": ["Hassan", "Bengaluru", "Belagavi", "Kolar", "Chikkamagaluru"],
    "maize": ["Davanagere", "Haveri", "Shivamogga", "Chitradurga", "Belagavi", "Ballari"],
}


def _session(request: Request) -> Session:
    factory = request.app.state.session_factory
    return factory()


def normalize_commodity_code(raw: str) -> str:
    cleaned = (raw or "").strip().lower()
    return COMMODITY_ALIASES.get(cleaned, cleaned)


def resolve_image_path(commodity: str, user_image: str | None = None) -> str:
    if user_image and user_image.strip():
        return user_image.strip()
    return COMMODITY_IMAGES.get(commodity, "assets/crops/coffee.jpg")


class CropCreateRequest(BaseModel):
    commodity: str = Field(min_length=1, max_length=64)
    variety: str = Field(min_length=1, max_length=128)
    quantity: float = Field(gt=0)
    unit: str = Field(default="quintal", max_length=32)
    location: str = Field(min_length=1, max_length=128)
    image_url: Optional[str] = None


class CropUpdateRequest(BaseModel):
    commodity: Optional[str] = None
    variety: Optional[str] = None
    quantity: Optional[float] = Field(default=None, gt=0)
    unit: Optional[str] = None
    location: Optional[str] = None
    image_url: Optional[str] = None


def seed_default_crops_if_empty(session: Session) -> list[FarmerCrop]:
    existing = session.query(FarmerCrop).all()
    if existing:
        return existing

    # Find default user
    demo_user = session.query(User).filter_by(code="cropmandi_demo_farmer").first()
    user_id = demo_user.id if demo_user else 1

    seeds = [
        FarmerCrop(
            user_id=user_id,
            commodity="coffee",
            variety="Arabica Parchment",
            quantity=45.0,
            unit="quintal",
            location="Chikkamagaluru",
            image_url="assets/crops/coffee.jpg",
        ),
        FarmerCrop(
            user_id=user_id,
            commodity="pepper",
            variety="Cochin Garbled",
            quantity=20.0,
            unit="quintal",
            location="Madikeri",
            image_url="assets/crops/black-pepper.jpg",
        ),
        FarmerCrop(
            user_id=user_id,
            commodity="coffee",
            variety="Robusta Cherry",
            quantity=35.0,
            unit="quintal",
            location="Sakleshpur",
            image_url="assets/crops/coffee.jpg",
        ),
        FarmerCrop(
            user_id=user_id,
            commodity="cardamom",
            variety="Bold Grade (8mm+)",
            quantity=50.0,
            unit="kg",
            location="Sakleshpur",
            image_url="assets/crops/cardamom.jpg",
        ),
        FarmerCrop(
            user_id=user_id,
            commodity="paddy",
            variety="Sona Masuri",
            quantity=60.0,
            unit="quintal",
            location="Davanagere",
            image_url="assets/crops/paddy.jpg",
        ),
        FarmerCrop(
            user_id=user_id,
            commodity="tomato",
            variety="Hybrid Tomato",
            quantity=30.0,
            unit="quintal",
            location="Kolar",
            image_url="assets/crops/tomato.jpg",
        ),
        FarmerCrop(
            user_id=user_id,
            commodity="potato",
            variety="Jyoti",
            quantity=40.0,
            unit="quintal",
            location="Hassan",
            image_url="assets/crops/potato.jpg",
        ),
        FarmerCrop(
            user_id=user_id,
            commodity="maize",
            variety="Yellow Maize (Feed)",
            quantity=50.0,
            unit="quintal",
            location="Davanagere",
            image_url="assets/crops/maize.jpg",
        ),
    ]
    for s in seeds:
        session.add(s)
    session.commit()
    for s in seeds:
        session.refresh(s)
    return seeds


@router.get("/api/farmer/crops")
def list_farmer_crops(request: Request):
    """Retrieve all crops in the farmer's inventory."""
    session = _session(request)
    try:
        crops = session.query(FarmerCrop).order_by(FarmerCrop.id.asc()).all()
        if not crops:
            crops = seed_default_crops_if_empty(session)
        return {
            "success": True,
            "count": len(crops),
            "crops": [
                {
                    "id": c.id,
                    "user_id": c.user_id,
                    "commodity": c.commodity,
                    "commodity_display": SUPPORTED_COMMODITIES.get(c.commodity, c.commodity.title()),
                    "variety": c.variety,
                    "quantity": c.quantity,
                    "unit": c.unit,
                    "location": c.location,
                    "image_url": resolve_image_path(c.commodity, c.image_url),
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
                for c in crops
            ],
        }
    finally:
        session.close()


@router.post("/api/farmer/crops", status_code=status.HTTP_201_CREATED)
def add_farmer_crop(body: CropCreateRequest, request: Request):
    """Add a new crop to farmer inventory."""
    session = _session(request)
    try:
        commodity = normalize_commodity_code(body.commodity)
        if commodity not in SUPPORTED_COMMODITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Commodity '{body.commodity}' is not supported. Supported: {', '.join(SUPPORTED_COMMODITIES.keys())}",
            )

        demo_user = session.query(User).filter_by(code="cropmandi_demo_farmer").first()
        user_id = demo_user.id if demo_user else 1

        img = resolve_image_path(commodity, body.image_url)

        new_crop = FarmerCrop(
            user_id=user_id,
            commodity=commodity,
            variety=body.variety.strip(),
            quantity=float(body.quantity),
            unit=body.unit.strip().lower() or "quintal",
            location=body.location.strip(),
            image_url=img,
        )
        session.add(new_crop)
        session.commit()
        session.refresh(new_crop)

        return {
            "success": True,
            "message": f"Successfully added {SUPPORTED_COMMODITIES[commodity]} to inventory.",
            "crop": {
                "id": new_crop.id,
                "commodity": new_crop.commodity,
                "commodity_display": SUPPORTED_COMMODITIES.get(new_crop.commodity, new_crop.commodity.title()),
                "variety": new_crop.variety,
                "quantity": new_crop.quantity,
                "unit": new_crop.unit,
                "location": new_crop.location,
                "image_url": resolve_image_path(new_crop.commodity, new_crop.image_url),
                "created_at": new_crop.created_at.isoformat() if new_crop.created_at else None,
            },
        }
    finally:
        session.close()


@router.put("/api/farmer/crops/{crop_id}")
def update_farmer_crop(crop_id: int, body: CropUpdateRequest, request: Request):
    """Update an existing crop record in inventory."""
    session = _session(request)
    try:
        crop = session.query(FarmerCrop).filter_by(id=crop_id).first()
        if not crop:
            raise HTTPException(status_code=404, detail=f"Crop with ID {crop_id} not found.")

        if body.commodity is not None:
            comm = normalize_commodity_code(body.commodity)
            if comm not in SUPPORTED_COMMODITIES:
                raise HTTPException(status_code=400, detail=f"Invalid commodity: {body.commodity}")
            crop.commodity = comm
            if not body.image_url:
                crop.image_url = resolve_image_path(comm)

        if body.variety is not None and body.variety.strip():
            crop.variety = body.variety.strip()
        if body.quantity is not None and body.quantity > 0:
            crop.quantity = float(body.quantity)
        if body.unit is not None and body.unit.strip():
            crop.unit = body.unit.strip().lower()
        if body.location is not None and body.location.strip():
            crop.location = body.location.strip()
        if body.image_url is not None:
            crop.image_url = resolve_image_path(crop.commodity, body.image_url)

        session.commit()
        session.refresh(crop)

        return {
            "success": True,
            "message": "Crop updated successfully.",
            "crop": {
                "id": crop.id,
                "commodity": crop.commodity,
                "commodity_display": SUPPORTED_COMMODITIES.get(crop.commodity, crop.commodity.title()),
                "variety": crop.variety,
                "quantity": crop.quantity,
                "unit": crop.unit,
                "location": crop.location,
                "image_url": resolve_image_path(crop.commodity, crop.image_url),
                "updated_at": crop.updated_at.isoformat() if crop.updated_at else None,
            },
        }
    finally:
        session.close()


@router.delete("/api/farmer/crops/{crop_id}")
def delete_farmer_crop(crop_id: int, request: Request):
    """Delete a crop from farmer inventory."""
    session = _session(request)
    try:
        crop = session.query(FarmerCrop).filter_by(id=crop_id).first()
        if not crop:
            raise HTTPException(status_code=404, detail=f"Crop with ID {crop_id} not found.")

        session.delete(crop)
        session.commit()
        return {
            "success": True,
            "message": f"Successfully removed {crop.variety} ({crop.commodity}) from inventory.",
            "deleted_id": crop_id,
        }
    finally:
        session.close()


@router.get("/api/farmer/crops/metadata")
def crop_metadata():
    """Return catalog of supported commodities, varieties, units, and images."""
    return {
        "success": True,
        "commodities": [
            {
                "code": code,
                "name": name,
                "image_url": COMMODITY_IMAGES[code],
                "varieties": VARIETY_CATALOG[code],
                "suggested_locations": DEFAULT_LOCATIONS[code],
                "has_ml_forecasting": code in {"paddy", "tomato", "potato", "maize"},
                "has_market_intelligence": code in {"coffee", "pepper", "paddy", "tomato", "potato", "maize"},
            }
            for code, name in SUPPORTED_COMMODITIES.items()
        ],
        "units": ["quintal", "kg", "bag (50kg)", "crate (25kg)"],
    }

