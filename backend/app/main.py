from decimal import Decimal
import uuid
from datetime import datetime, date, timedelta, timezone

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import AuditLog, Company, CompanyMember, OfferSelection, Product, ProductPrice, PurchaseOrder, PurchaseOrderItem, PurchaseRequest, PurchaseRequestItem, Supplier, SupplierOffer, SupplierOfferItem, User


# ============================================================
# PASSWORD HASHING
# ============================================================

password_hash = PasswordHash.recommended()


# ============================================================
# RATE LIMITING
# ============================================================

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="BIZAZ API",
    version="0.1.0",
    description="BIZAZ Azerbaijan B2B Platform API",
)

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)


# ============================================================
# CORS
# ============================================================

cors_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST SCHEMAS
# ============================================================

class RegisterSchema(BaseModel):
    company_name: str = Field(
        min_length=2,
        max_length=255,
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    full_name: str = Field(
        min_length=2,
        max_length=255,
    )

    legal_form: str = "MMC"

    tax_id: str | None = Field(
        default=None,
        pattern=r"^\d{10}$",
    )


class LoginSchema(BaseModel):
    email: EmailStr

    password: str = Field(
        min_length=1,
        max_length=128,
    )


class CompanyUpdateSchema(BaseModel):
    legal_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )

    tax_id: str | None = Field(
        default=None,
        pattern=r"^\d{10}$",
    )

    legal_form: str | None = None

    vat_registered: bool | None = None

    vat_rate: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )


# ============================================================
# JWT ACCESS TOKEN
# ============================================================

def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )

    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm="HS256",
    )


# ============================================================
# JWT AUTHENTICATION
# ============================================================

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:

    token = credentials.credentials

    # --------------------------------------------------------
    # Decode and verify JWT
    # --------------------------------------------------------

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Tokenin mudd?ti bitib.",
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Etibars?z token.",
        )

    # --------------------------------------------------------
    # Check token type
    # --------------------------------------------------------

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=401,
            detail="Etibars?z access token.",
        )

    # --------------------------------------------------------
    # Get user ID
    # --------------------------------------------------------

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Token istifad?ci m?lumat? ehtiva etmir.",
        )

    # --------------------------------------------------------
    # Find user in database
    # --------------------------------------------------------

    try:
        user = db.get(User, user_id)

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Etibars?z istifad?ci identifikatoru.",
        )

    # --------------------------------------------------------
    # Check user status
    # --------------------------------------------------------

    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Istifad?ci aktiv deyil v? ya movcud deyil.",
        )

    return user


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get(
    "/health",
    tags=["system"],
)
@limiter.limit("30/minute")
def health(request: Request):

    return {
        "status": "ok",
        "service": "bizaz-api",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# BIZAZ SYSTEM META
# ============================================================

@app.get(
    "/api/v1/meta",
    tags=["system"],
)
@limiter.limit("30/minute")
def meta(request: Request):

    return {
        "currency": "AZN",
        "vat_rate_default": 18,
        "country": "AZ",
        "language_default": "az",
    }


# ============================================================
# CURRENT USER
# ============================================================

@app.get(
    "/api/v1/me",
    tags=["auth"],
)
@limiter.limit("60/minute")
def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    membership = db.scalar(
        select(CompanyMember).where(
            CompanyMember.user_id == current_user.id
        )
    )

    company = None

    if membership:
        company = db.get(
            Company,
            membership.company_id,
        )

    return {
        "status": "success",

        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "is_active": current_user.is_active,
        },

        "company": {
            "id": str(company.id),
            "name": company.legal_name,
            "role": membership.role,
        }
        if company and membership
        else None,
    }


# ============================================================
# REGISTER COMPANY
# ============================================================

@app.post(
    "/api/v1/register",
    tags=["auth"],
)
@limiter.limit("10/minute")
def register_company(
    request: Request,
    data: RegisterSchema,
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # Check existing user
    # --------------------------------------------------------

    existing_user = db.scalar(
        select(User).where(
            User.email == str(data.email).lower()
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Bu e-poct unvan? art?q qeydiyyatdan kecib.",
        )

    # --------------------------------------------------------
    # Validate legal form
    # --------------------------------------------------------

    if data.legal_form not in {
        "MMC",
        "FERDI_SAHIBKAR",
        "ASC",
        "OTHER",
    }:

        raise HTTPException(
            status_code=422,
              detail="Yanl?s huquqi forma.",
        )

    # --------------------------------------------------------
    # Create user
    # --------------------------------------------------------

    user = User(
        email=str(data.email).lower(),
        password_hash=password_hash.hash(data.password),
        full_name=data.full_name,
    )

    # --------------------------------------------------------
    # Create company
    # --------------------------------------------------------

    company = Company(
        legal_name=data.company_name,
        tax_id=data.tax_id,
        legal_form=data.legal_form,
        vat_registered=False,
        vat_rate=18.00,
        currency="AZN",
    )

    db.add(user)
    db.add(company)

    db.flush()

    # --------------------------------------------------------
    # Create company membership
    # --------------------------------------------------------

    membership = CompanyMember(
        user_id=user.id,
        company_id=company.id,
        role="OWNER",
    )

    db.add(membership)

    # --------------------------------------------------------
    # Audit log
    # --------------------------------------------------------

    audit = AuditLog(
        user_id=user.id,
        company_id=company.id,
        action="REGISTER",
        entity_type="company",
        entity_id=company.id,
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
        log_metadata={
            "email": str(data.email).lower(),
            "legal_form": data.legal_form,
        },
    )

    db.add(audit)

    # --------------------------------------------------------
    # Commit transaction
    # --------------------------------------------------------

    db.commit()

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "status": "success",
        "message": (
            f"'{data.company_name}' "
            "sirk?ti ugurla qeydiyyatdan kecdi!"
        ),

        "data": {
            "user_id": str(user.id),
            "company_id": str(company.id),
            "company_name": company.legal_name,
            "email": user.email,
            "role": "OWNER",
        },
    }


# ============================================================
# LOGIN
# ============================================================

@app.post(
    "/api/v1/login",
    tags=["auth"],
)
@limiter.limit("10/minute")
def login_company(
    request: Request,
    data: LoginSchema,
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # Find user
    # --------------------------------------------------------

    user = db.scalar(
        select(User).where(
            User.email == str(data.email).lower()
        )
    )

    if not user or not user.is_active:

        raise HTTPException(
            status_code=401,
            detail="E-poct v? ya sifr? yanl?sd?r.",
        )

    # --------------------------------------------------------
    # Verify password
    # --------------------------------------------------------

    if not password_hash.verify(
        data.password,
        user.password_hash,
    ):

        raise HTTPException(
            status_code=401,
            detail="E-poct v? ya sifr? yanl?sd?r.",
        )

    # --------------------------------------------------------
    # Create JWT
    # --------------------------------------------------------

    token = create_access_token(
        str(user.id)
    )

    # --------------------------------------------------------
    # Find company membership
    # --------------------------------------------------------

    membership = db.scalar(
        select(CompanyMember).where(
            CompanyMember.user_id == user.id
        )
    )

    # --------------------------------------------------------
    # Audit LOGIN
    # --------------------------------------------------------

    if membership:

        audit = AuditLog(
            user_id=user.id,
            company_id=membership.company_id,
            action="LOGIN",
            entity_type="user",
            entity_id=user.id,
            ip_address=(
                request.client.host
                if request.client
                else None
            ),
            log_metadata={},
        )

        db.add(audit)

        db.commit()

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "status": "success",
        "message": "Ugurla daxil oldunuz!",
        "token": token,
        "token_type": "bearer",

        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
        },
    }
# ============================================================
# CURRENT COMPANY
# ============================================================

@app.get(
    "/api/v1/company/me",
    tags=["company"],
)
@limiter.limit("60/minute")
def get_my_company(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    membership = db.scalar(
        select(CompanyMember).where(
            CompanyMember.user_id == current_user.id
        )
    )

    if not membership:
        raise HTTPException(
            status_code=404,
            detail="Istifad?cinin sirk?t uzvluyu tap?lmad?.",
        )

    company = db.get(
        Company,
        membership.company_id,
    )

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Sirk?t tap?lmad?.",
        )

    return {
        "status": "success",
        "company": {
            "id": str(company.id),
            "legal_name": company.legal_name,
            "tax_id": company.tax_id,
            "legal_form": company.legal_form,
            "vat_registered": company.vat_registered,
            "vat_rate": float(company.vat_rate),
            "currency": company.currency.strip(),
            "role": membership.role,
            "created_at": company.created_at.isoformat(),
            "updated_at": company.updated_at.isoformat(),
        },
    }

# ============================================================
# RBAC вЂ” ROLE CHECK
# ============================================================

def require_role(*allowed_roles: str):
    def role_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:

        membership = db.scalar(
            select(CompanyMember).where(
                CompanyMember.user_id == current_user.id
            )
        )

        if not membership:
            raise HTTPException(
                status_code=403,
                detail="Istifad?cinin sirk?t uzvluyu yoxdur.",
            )

        if membership.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Bu ?m?liyyat ucun kifay?t q?d?r s?lahiyy?tiniz yoxdur.",
            )

        return current_user

    return role_checker

# RBAC TEST вЂ” OWNER ONLY
# ============================================================

@app.put(
    "/api/v1/company/me",
    tags=["company"],
)
@limiter.limit("30/minute")
def update_my_company(
    request: Request,
    payload: CompanyUpdateSchema,
    current_user: User = Depends(require_role("OWNER", "ADMIN")),
    db: Session = Depends(get_db),
):
    membership = db.scalar(
        select(CompanyMember).where(
            CompanyMember.user_id == current_user.id
        )
    )

    if not membership:
        raise HTTPException(
            status_code=404,
            detail="?stifad??inin ?irk?t ?zvl?y? tap?lmad?.",
        )

    company = db.get(Company, membership.company_id)

    if not company:
        raise HTTPException(
            status_code=404,
            detail="?irk?t tap?lmad?.",
        )

    changes = {}

    if payload.legal_name is not None and payload.legal_name != company.legal_name:
        changes["legal_name"] = {
            "old": company.legal_name,
            "new": payload.legal_name,
        }
        company.legal_name = payload.legal_name

    if payload.tax_id is not None and payload.tax_id != company.tax_id:
        existing_company = db.scalar(
            select(Company).where(
                Company.tax_id == payload.tax_id,
                Company.id != company.id,
            )
        )

        if existing_company:
            raise HTTPException(
                status_code=409,
                detail="Bu V?EN art?q ba?qa ?irk?t? m?xsusdur.",
            )

        changes["tax_id"] = {
            "old": company.tax_id,
            "new": payload.tax_id,
        }
        company.tax_id = payload.tax_id

    if payload.legal_form is not None and payload.legal_form != company.legal_form:
        allowed_forms = {"MMC", "FERDI_SAHIBKAR", "ASC", "OTHER"}

        if payload.legal_form not in allowed_forms:
            raise HTTPException(
                status_code=422,
                detail="Etibars?z h?quqi forma.",
            )

        changes["legal_form"] = {
            "old": company.legal_form,
            "new": payload.legal_form,
        }
        company.legal_form = payload.legal_form

    if (
        payload.vat_registered is not None
        and payload.vat_registered != company.vat_registered
    ):
        changes["vat_registered"] = {
            "old": company.vat_registered,
            "new": payload.vat_registered,
        }
        company.vat_registered = payload.vat_registered

    if (
        payload.vat_rate is not None
        and float(payload.vat_rate) != float(company.vat_rate)
    ):
        changes["vat_rate"] = {
            "old": float(company.vat_rate),
            "new": float(payload.vat_rate),
        }
        company.vat_rate = payload.vat_rate

    company.updated_at = datetime.now(timezone.utc)

    if changes:
        audit = AuditLog(
            user_id=current_user.id,
            company_id=company.id,
            action="COMPANY_UPDATED",
            entity_type="company",
            entity_id=company.id,
            ip_address=request.client.host if request.client else None,
            log_metadata={"changes": changes},
        )
        db.add(audit)

    db.commit()
    db.refresh(company)

    return {
        "status": "success",
        "message": "?irk?t m?lumatlar? yenil?ndi.",
        "company": {
            "id": str(company.id),
            "legal_name": company.legal_name,
            "tax_id": company.tax_id,
            "legal_form": company.legal_form,
            "vat_registered": company.vat_registered,
            "vat_rate": float(company.vat_rate),
            "currency": company.currency.strip(),
            "role": membership.role,
            "created_at": company.created_at.isoformat(),
            "updated_at": company.updated_at.isoformat(),
        },
    }

@app.get("/api/v1/company/rbac-test-owner", tags=["company", "rbac"])
@limiter.limit("60/minute")
def rbac_test_owner(
    request: Request,
    current_user: User = Depends(require_role("OWNER")),
):
    return {
        "status": "success",
        "message": "RBAC isl?yir.",
        "role_required": "OWNER",
        "user": current_user.email,
    }





# ============================================================
# PRODUCT SCHEMAS
# ============================================================


class ProductPriceCreateSchema(BaseModel):
    price_type: str = Field(
        pattern="^(PURCHASE|SALE)$"
    )
    amount: Decimal = Field(
        gt=0
    )
    currency: str = Field(
        default="AZN",
        min_length=3,
        max_length=3
    )
    vat_included: bool = False
    supplier_id: uuid.UUID | None = None
    valid_from: datetime | None = None


class ProductPriceUpdateSchema(BaseModel):
    price_type: str | None = Field(
        default=None,
        pattern="^(PURCHASE|SALE)$"
    )
    amount: Decimal | None = Field(
        default=None,
        gt=0
    )
    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3
    )
    vat_included: bool | None = None
    supplier_id: uuid.UUID | None = None
    valid_from: datetime | None = None


class ProductPriceResponseSchema(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    price_type: str
    amount: Decimal
    currency: str
    vat_included: bool
    supplier_id: uuid.UUID | None
    valid_from: datetime
    created_at: datetime
    updated_at: datetime

class SupplierCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    tax_id: str | None = Field(default=None, min_length=10, max_length=10, pattern=r"^\d{10}$")
    contact_person: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    bank_name: str | None = Field(default=None, max_length=255)
    bank_account: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool = True


class SupplierUpdateSchema(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    tax_id: str | None = Field(default=None, min_length=10, max_length=10, pattern=r"^\d{10}$")
    contact_person: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    bank_name: str | None = Field(default=None, max_length=255)
    bank_account: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class SupplierResponseSchema(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    tax_id: str | None
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    bank_name: str | None
    bank_account: str | None
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime



SupplierCreateSchema.model_rebuild()
SupplierUpdateSchema.model_rebuild()
SupplierResponseSchema.model_rebuild()

class ProductCreateSchema(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=255,
    )

    sku: str | None = Field(
        default=None,
        max_length=100,
    )

    category: str | None = Field(
        default=None,
        max_length=255,
    )

    unit: str = Field(
        default="?d?d",
        min_length=1,
        max_length=30,
    )

    description: str | None = Field(
        default=None,
        max_length=2000,
    )

    is_active: bool = True


class ProductUpdateSchema(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )

    sku: str | None = Field(
        default=None,
        max_length=100,
    )

    category: str | None = Field(
        default=None,
        max_length=255,
    )

    unit: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )

    description: str | None = Field(
        default=None,
        max_length=2000,
    )

    is_active: bool | None = None


# ============================================================
# PRODUCT HELPERS
# ============================================================

PRODUCT_WRITE_ROLES = {
    "OWNER",
    "ADMIN",
    "PROCUREMENT",
}


def get_current_membership(
    current_user: User,
    db: Session,
) -> CompanyMember:

    membership = db.scalar(
        select(CompanyMember).where(
            CompanyMember.user_id == current_user.id
        )
    )

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="Istifad?cinin sirk?t uzvluyu yoxdur.",
        )

    return membership


def product_response(product: Product) -> dict:
    return {
        "id": str(product.id),
        "company_id": str(product.company_id),
        "name": product.name,
        "sku": product.sku,
        "category": product.category,
        "unit": product.unit,
        "description": product.description,
        "is_active": product.is_active,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


# ============================================================
# PRODUCT вЂ” LIST
# ============================================================

@app.get(
    "/api/v1/products",
    tags=["products"],
)
@limiter.limit("60/minute")
def list_products(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    membership = get_current_membership(
        current_user,
        db,
    )

    products = db.scalars(
        select(Product)
        .where(
            Product.company_id == membership.company_id
        )
        .order_by(Product.created_at.desc())
    ).all()

    return {
        "status": "success",
        "count": len(products),
        "products": [
            product_response(product)
            for product in products
        ],
    }


# ============================================================
# PRODUCT вЂ” CREATE
# ============================================================

@app.post(
    "/api/v1/products",
    tags=["products"],
)
@limiter.limit("30/minute")
def create_product(
    request: Request,
    payload: ProductCreateSchema,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):

    membership = get_current_membership(
        current_user,
        db,
    )

    # --------------------------------------------------------
    # Check duplicate SKU inside the same company
    # --------------------------------------------------------

    if payload.sku is not None:

        existing_product = db.scalar(
            select(Product).where(
                Product.company_id == membership.company_id,
                Product.sku == payload.sku,
            )
        )

        if existing_product:
            raise HTTPException(
                status_code=409,
                detail="Bu SKU art?q sirk?t daxilind? movcuddur.",
            )

    # --------------------------------------------------------
    # Create product
    # --------------------------------------------------------

    product = Product(
        company_id=membership.company_id,
        name=payload.name,
        sku=payload.sku,
        category=payload.category,
        unit=payload.unit,
        description=payload.description,
        is_active=payload.is_active,
    )

    db.add(product)
    db.flush()

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------

    audit = AuditLog(
        user_id=current_user.id,
        company_id=membership.company_id,
        action="PRODUCT_CREATED",
        entity_type="product",
        entity_id=product.id,
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
        log_metadata={
            "name": product.name,
            "sku": product.sku,
            "category": product.category,
            "unit": product.unit,
            "is_active": product.is_active,
        },
    )

    db.add(audit)

    db.commit()
    db.refresh(product)

    return {
        "status": "success",
        "message": "M?hsul ugurla yarad?ld?.",
        "product": product_response(product),
    }


# ============================================================
# PRODUCT вЂ” GET ONE
# ============================================================

@app.get(
    "/api/v1/products/{product_id}",
    tags=["products"],
)
@limiter.limit("60/minute")
def get_product(
    request: Request,
    product_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    membership = get_current_membership(
        current_user,
        db,
    )

    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.company_id == membership.company_id,
        )
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="M?hsul tap?lmad?.",
        )

    return {
        "status": "success",
        "product": product_response(product),
    }


# ============================================================
# PRODUCT вЂ” UPDATE
# ============================================================

@app.put(
    "/api/v1/products/{product_id}",
    tags=["products"],
)
@limiter.limit("30/minute")
def update_product(
    request: Request,
    product_id: uuid.UUID,
    payload: ProductUpdateSchema,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):

    membership = get_current_membership(
        current_user,
        db,
    )

    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.company_id == membership.company_id,
        )
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="M?hsul tap?lmad?.",
        )

    changes = {}

    # --------------------------------------------------------
    # Apply only supplied fields
    # --------------------------------------------------------

    updates = payload.model_dump(
        exclude_unset=True
    )

    if "sku" in updates and updates["sku"] is not None:

        existing_product = db.scalar(
            select(Product).where(
                Product.company_id == membership.company_id,
                Product.sku == updates["sku"],
                Product.id != product.id,
            )
        )

        if existing_product:
            raise HTTPException(
                status_code=409,
                detail="Bu SKU art?q sirk?t daxilind? movcuddur.",
            )

    for field, new_value in updates.items():

        old_value = getattr(
            product,
            field,
        )

        if old_value != new_value:

            changes[field] = {
                "old": old_value,
                "new": new_value,
            }

            setattr(
                product,
                field,
                new_value,
            )

    product.updated_at = datetime.now(timezone.utc)

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------

    if changes:

        audit = AuditLog(
            user_id=current_user.id,
            company_id=membership.company_id,
            action="PRODUCT_UPDATED",
            entity_type="product",
            entity_id=product.id,
            ip_address=(
                request.client.host
                if request.client
                else None
            ),
            log_metadata={
                "changes": changes
            },
        )

        db.add(audit)

    db.commit()
    db.refresh(product)

    return {
        "status": "success",
        "message": "M?hsul m?lumatlar? yenil?ndi.",
        "product": product_response(product),
    }


# ============================================================
# PRODUCT вЂ” DELETE
# ============================================================

@app.delete(
    "/api/v1/products/{product_id}",
    tags=["products"],
)
@limiter.limit("30/minute")
def delete_product(
    request: Request,
    product_id: uuid.UUID,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):

    membership = get_current_membership(
        current_user,
        db,
    )

    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.company_id == membership.company_id,
        )
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="M?hsul tap?lmad?.",
        )

    # --------------------------------------------------------
    # Save audit information before deletion
    # --------------------------------------------------------

    audit = AuditLog(
        user_id=current_user.id,
        company_id=membership.company_id,
        action="PRODUCT_DELETED",
        entity_type="product",
        entity_id=product.id,
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
        log_metadata={
            "name": product.name,
            "sku": product.sku,
        },
    )

    db.add(audit)

    db.delete(product)

    db.commit()

    return {
        "status": "success",
        "message": "M?hsul ugurla silindi.",
        "product_id": str(product_id),
    }


# ============================================================
# PRODUCT PRICE CRUD
# ============================================================


ProductPriceCreateSchema.model_rebuild()
ProductPriceUpdateSchema.model_rebuild()
ProductPriceResponseSchema.model_rebuild()
@app.post(
    "/api/v1/products/{product_id}/prices",
    response_model=ProductPriceResponseSchema,
    status_code=201,
    tags=["products", "prices"],
)
@limiter.limit("60/minute")
def create_product_price(
    request: Request,
    product_id: uuid.UUID,
    payload: ProductPriceCreateSchema,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(
        current_user,
        db,
    )

    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.company_id == membership.company_id,
        )
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="MЙ™hsul tapД±lmadД±.",
        )

    price = ProductPrice(
        company_id=membership.company_id,
        product_id=product.id,
        price_type=payload.price_type,
        amount=payload.amount,
        currency=payload.currency.upper(),
        vat_included=payload.vat_included,
        supplier_id=payload.supplier_id,
        valid_from=(
            payload.valid_from
            or datetime.now(timezone.utc)
        ),
    )

    db.add(price)
    db.flush()

    audit = AuditLog(
        user_id=current_user.id,
        company_id=membership.company_id,
        action="PRODUCT_PRICE_CREATED",
        entity_type="product_price",
        entity_id=price.id,
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
        log_metadata={
            "product_id": str(product.id),
            "price_type": price.price_type,
            "amount": str(price.amount),
            "currency": price.currency,
            "vat_included": price.vat_included,
        },
    )

    db.add(audit)
    db.commit()
    db.refresh(price)

    return price


@app.get(
    "/api/v1/products/{product_id}/prices",
    response_model=list[ProductPriceResponseSchema],
    tags=["products", "prices"],
)
@limiter.limit("120/minute")
def list_product_prices(
    request: Request,
    product_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(
        current_user,
        db,
    )

    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.company_id == membership.company_id,
        )
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="MЙ™hsul tapД±lmadД±.",
        )

    prices = db.scalars(
        select(ProductPrice)
        .where(
            ProductPrice.company_id == membership.company_id,
            ProductPrice.product_id == product_id,
        )
        .order_by(
            ProductPrice.valid_from.desc(),
            ProductPrice.created_at.desc(),
        )
    ).all()

    return list(prices)


@app.put(
    "/api/v1/products/{product_id}/prices/{price_id}",
    response_model=ProductPriceResponseSchema,
    tags=["products", "prices"],
)
@limiter.limit("60/minute")
def update_product_price(
    request: Request,
    product_id: uuid.UUID,
    price_id: uuid.UUID,
    payload: ProductPriceUpdateSchema,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(
        current_user,
        db,
    )

    price = db.scalar(
        select(ProductPrice).where(
            ProductPrice.id == price_id,
            ProductPrice.product_id == product_id,
            ProductPrice.company_id == membership.company_id,
        )
    )

    if not price:
        raise HTTPException(
            status_code=404,
            detail="QiymЙ™t tapД±lmadД±.",
        )

    updates = payload.model_dump(
        exclude_unset=True
    )

    changes = {}

    for field_name, new_value in updates.items():

        if field_name == "currency" and new_value:
            new_value = new_value.upper()

        old_value = getattr(
            price,
            field_name,
        )

        if old_value != new_value:

            changes[field_name] = {
                "old": (
                    str(old_value)
                    if old_value is not None
                    else None
                ),
                "new": (
                    str(new_value)
                    if new_value is not None
                    else None
                ),
            }

            setattr(
                price,
                field_name,
                new_value,
            )

    price.updated_at = datetime.now(timezone.utc)

    audit = AuditLog(
        user_id=current_user.id,
        company_id=membership.company_id,
        action="PRODUCT_PRICE_UPDATED",
        entity_type="product_price",
        entity_id=price.id,
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
        log_metadata={
            "product_id": str(product_id),
            "changes": changes,
        },
    )

    db.add(audit)
    db.commit()
    db.refresh(price)

    return price


@app.delete(
    "/api/v1/products/{product_id}/prices/{price_id}",
    tags=["products", "prices"],
)
@limiter.limit("60/minute")
def delete_product_price(
    request: Request,
    product_id: uuid.UUID,
    price_id: uuid.UUID,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(
        current_user,
        db,
    )

    price = db.scalar(
        select(ProductPrice).where(
            ProductPrice.id == price_id,
            ProductPrice.product_id == product_id,
            ProductPrice.company_id == membership.company_id,
        )
    )

    if not price:
        raise HTTPException(
            status_code=404,
            detail="QiymЙ™t tapД±lmadД±.",
        )

    audit = AuditLog(
        user_id=current_user.id,
        company_id=membership.company_id,
        action="PRODUCT_PRICE_DELETED",
        entity_type="product_price",
        entity_id=price.id,
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
        log_metadata={
            "product_id": str(product_id),
            "price_type": price.price_type,
            "amount": str(price.amount),
            "currency": price.currency,
        },
    )

    db.add(audit)

    db.delete(price)
    db.commit()

    return {
        "status": "success",
        "message": "MЙ™hsul qiymЙ™ti silindi.",
    }







# ============================================================
# SUPPLIER CRUD
# ============================================================

@app.post(
    "/api/v1/suppliers",
    response_model=SupplierResponseSchema,
    status_code=201,
    tags=["suppliers"],
)
@limiter.limit("60/minute")
def create_supplier(
    request: Request,
    payload: SupplierCreateSchema,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(current_user, db)

    if payload.tax_id:
        existing = db.scalar(
            select(Supplier).where(
                Supplier.company_id == membership.company_id,
                Supplier.tax_id == payload.tax_id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Bu VГ–EN ГјzrЙ™ tЙ™chizatГ§Д± artД±q mГ¶vcuddur.",
            )

    supplier = Supplier(
        company_id=membership.company_id,
        name=payload.name.strip(),
        tax_id=payload.tax_id,
        contact_person=payload.contact_person,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
        address=payload.address,
        bank_name=payload.bank_name,
        bank_account=payload.bank_account,
        description=payload.description,
        is_active=payload.is_active,
    )

    db.add(supplier)
    db.flush()

    audit = AuditLog(
        user_id=current_user.id,
        company_id=membership.company_id,
        action="SUPPLIER_CREATED",
        entity_type="supplier",
        entity_id=supplier.id,
        ip_address=request.client.host if request.client else None,
        log_metadata={
            "name": supplier.name,
            "tax_id": supplier.tax_id,
        },
    )

    db.add(audit)
    db.commit()
    db.refresh(supplier)

    return supplier


@app.get(
    "/api/v1/suppliers",
    response_model=list[SupplierResponseSchema],
    tags=["suppliers"],
)
@limiter.limit("120/minute")
def list_suppliers(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(current_user, db)

    suppliers = db.scalars(
        select(Supplier)
        .where(
            Supplier.company_id == membership.company_id,
        )
        .order_by(
            Supplier.name.asc(),
        )
    ).all()

    return list(suppliers)


@app.get(
    "/api/v1/suppliers/{supplier_id}",
    response_model=SupplierResponseSchema,
    tags=["suppliers"],
)
@limiter.limit("120/minute")
def get_supplier(
    request: Request,
    supplier_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(current_user, db)

    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.company_id == membership.company_id,
        )
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="TЙ™chizatГ§Д± tapД±lmadД±.",
        )

    return supplier


@app.put(
    "/api/v1/suppliers/{supplier_id}",
    response_model=SupplierResponseSchema,
    tags=["suppliers"],
)
@limiter.limit("60/minute")
def update_supplier(
    request: Request,
    supplier_id: uuid.UUID,
    payload: SupplierUpdateSchema,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(current_user, db)

    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.company_id == membership.company_id,
        )
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="TЙ™chizatГ§Д± tapД±lmadД±.",
        )

    updates = payload.model_dump(exclude_unset=True)

    if "tax_id" in updates and updates["tax_id"]:
        existing = db.scalar(
            select(Supplier).where(
                Supplier.company_id == membership.company_id,
                Supplier.tax_id == updates["tax_id"],
                Supplier.id != supplier.id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Bu VГ–EN ГјzrЙ™ baЕџqa tЙ™chizatГ§Д± mГ¶vcuddur.",
            )

    changes = {}

    for field_name, new_value in updates.items():
        if field_name == "name" and new_value:
            new_value = new_value.strip()

        old_value = getattr(supplier, field_name)

        if old_value != new_value:
            changes[field_name] = {
                "old": str(old_value) if old_value is not None else None,
                "new": str(new_value) if new_value is not None else None,
            }
            setattr(supplier, field_name, new_value)

    supplier.updated_at = datetime.now(timezone.utc)

    audit = AuditLog(
        user_id=current_user.id,
        company_id=membership.company_id,
        action="SUPPLIER_UPDATED",
        entity_type="supplier",
        entity_id=supplier.id,
        ip_address=request.client.host if request.client else None,
        log_metadata={
            "changes": changes,
        },
    )

    db.add(audit)
    db.commit()
    db.refresh(supplier)

    return supplier


@app.delete(
    "/api/v1/suppliers/{supplier_id}",
    tags=["suppliers"],
)
@limiter.limit("60/minute")
def delete_supplier(
    request: Request,
    supplier_id: uuid.UUID,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(current_user, db)

    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.company_id == membership.company_id,
        )
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="TЙ™chizatГ§Д± tapД±lmadД±.",
        )

    audit = AuditLog(
        user_id=current_user.id,
        company_id=membership.company_id,
        action="SUPPLIER_DELETED",
        entity_type="supplier",
        entity_id=supplier.id,
        ip_address=request.client.host if request.client else None,
        log_metadata={
            "name": supplier.name,
            "tax_id": supplier.tax_id,
        },
    )

    db.add(audit)
    db.delete(supplier)
    db.commit()

    return {
        "status": "success",
        "message": "TЙ™chizatГ§Д± silindi.",
    }

# ============================================================
# PROCUREMENT SCHEMAS
# ============================================================

class PurchaseRequestItemCreateSchema(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=30)
    required_date: date | None = None
    specifications: str | None = Field(default=None, max_length=5000)
    notes: str | None = Field(default=None, max_length=5000)


class PurchaseRequestCreateSchema(BaseModel):
    request_number: str = Field(min_length=1, max_length=50)
    request_date: date | None = None
    status: str = Field(default="DRAFT", pattern="^(DRAFT|SUBMITTED)$")
    notes: str | None = Field(default=None, max_length=5000)
    items: list[PurchaseRequestItemCreateSchema] = Field(min_length=1)


class SupplierOfferItemCreateSchema(BaseModel):
    purchase_request_item_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=30)
    unit_price: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(default=Decimal("18.00"), ge=0, le=100)
    delivery_days: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=5000)


class SupplierOfferCreateSchema(BaseModel):
    purchase_request_id: uuid.UUID
    supplier_id: uuid.UUID
    offer_number: str = Field(min_length=1, max_length=50)
    offer_date: date | None = None
    valid_until: date | None = None
    currency: str = Field(default="AZN", min_length=3, max_length=3)
    status: str = Field(default="DRAFT", pattern="^(DRAFT|SUBMITTED)$")
    notes: str | None = Field(default=None, max_length=5000)
    items: list[SupplierOfferItemCreateSchema] = Field(min_length=1)


class OfferSelectionCreateSchema(BaseModel):
    purchase_request_id: uuid.UUID
    supplier_offer_id: uuid.UUID
    justification: str = Field(min_length=1, max_length=5000)


class ProcurementPurchaseOrderCreateSchema(BaseModel):
    order_number: str = Field(min_length=1, max_length=50)
    order_date: date | None = None
    notes: str | None = Field(default=None, max_length=5000)


class ProcurementPurchaseOrderResponseSchema(BaseModel):
    purchase_order_id: uuid.UUID
    selection_id: uuid.UUID
    purchase_request_id: uuid.UUID
    supplier_offer_id: uuid.UUID
    supplier_id: uuid.UUID
    order_number: str
    status: str
    currency: str
    subtotal: Decimal
    vat_amount: Decimal
    total_amount: Decimal

# PURCHASE ORDER SCHEMAS
# ============================================================

class PurchaseOrderItemCreateSchema(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit: str = Field(
        default="Й™dЙ™d",
        min_length=1,
        max_length=30,
    )
    unit_price: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(
        default=Decimal("18.00"),
        ge=0,
        le=100,
    )


class PurchaseOrderItemUpdateSchema(BaseModel):
    product_id: uuid.UUID | None = None
    quantity: Decimal | None = Field(
        default=None,
        gt=0,
    )
    unit: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    unit_price: Decimal | None = Field(
        default=None,
        ge=0,
    )
    vat_rate: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
    )


class PurchaseOrderItemResponseSchema(BaseModel):
    id: uuid.UUID
    purchase_order_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal
    unit: str
    unit_price: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    line_total: Decimal
    created_at: datetime
    updated_at: datetime



class PurchaseOrderStatusUpdateSchema(BaseModel):
    status: str = Field(
        pattern="^(DRAFT|SUBMITTED|APPROVED|RECEIVED|CANCELLED)$"
    )


class PurchaseOrderStatusResponseSchema(BaseModel):
    status: str
    message: str
    id: str
    order_number: str
    old_status: str
    new_status: str
class PurchaseOrderCreateSchema(BaseModel):
    supplier_id: uuid.UUID
    order_number: str = Field(
        min_length=1,
        max_length=50,
    )
    order_date: date | None = None
    status: str = Field(
        default="DRAFT",
        pattern="^(DRAFT|SUBMITTED|APPROVED|RECEIVED|CANCELLED)$",
    )
    currency: str = Field(
        default="AZN",
        min_length=3,
        max_length=3,
    )
    notes: str | None = None
    items: list[PurchaseOrderItemCreateSchema] = Field(
        min_length=1,
    )


class PurchaseOrderUpdateSchema(BaseModel):
    supplier_id: uuid.UUID | None = None
    order_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    order_date: date | None = None
    status: str | None = Field(
        default=None,
        pattern="^(DRAFT|SUBMITTED|APPROVED|RECEIVED|CANCELLED)$",
    )
    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )
    notes: str | None = None
    items: list[PurchaseOrderItemUpdateSchema] | None = None


class PurchaseOrderListResponseSchema(BaseModel):
    items: list["PurchaseOrderResponseSchema"]
    total: int
    page: int
    limit: int
    pages: int


class PurchaseOrderResponseSchema(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    supplier_id: uuid.UUID
    order_number: str
    order_date: date
    status: str
    currency: str
    subtotal: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    notes: str | None
    created_at: datetime
    updated_at: datetime
    items: list[PurchaseOrderItemResponseSchema] = []


PurchaseOrderItemCreateSchema.model_rebuild()
PurchaseOrderItemUpdateSchema.model_rebuild()
PurchaseOrderItemResponseSchema.model_rebuild()
PurchaseOrderCreateSchema.model_rebuild()
PurchaseOrderUpdateSchema.model_rebuild()
PurchaseOrderResponseSchema.model_rebuild()
PurchaseOrderListResponseSchema.model_rebuild()




# ============================================================
# PURCHASE ORDER вЂ” CREATE
# ============================================================


# ============================================================
# PROCUREMENT ? PURCHASE REQUEST CREATE
# ============================================================

@app.post(
    "/api/v1/procurement/purchase-requests",
    tags=["procurement"],
)
@limiter.limit("60/minute")
def create_purchase_request(
    request: Request,
    payload: PurchaseRequestCreateSchema,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(
        current_user,
        db,
    )

    existing_request = db.scalar(
        select(PurchaseRequest).where(
            PurchaseRequest.company_id == membership.company_id,
            PurchaseRequest.request_number == payload.request_number,
        )
    )

    if existing_request:
        raise HTTPException(
            status_code=409,
            detail="Bu sat?nalma sor?usu n?mr?si art?q m?vcuddur.",
        )

    product_ids = [item.product_id for item in payload.items]

    products = db.scalars(
        select(Product).where(
            Product.id.in_(product_ids),
            Product.company_id == membership.company_id,
            Product.is_active.is_(True),
        )
    ).all()

    product_map = {
        product.id: product
        for product in products
    }

    missing_products = [
        str(product_id)
        for product_id in product_ids
        if product_id not in product_map
    ]

    if missing_products:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Bir v? ya daha ?ox m?hsul tap?lmad? v? ya bu ?irk?t? aid deyil.",
                "product_ids": missing_products,
            },
        )

    request_date = (
        payload.request_date
        if payload.request_date
        else datetime.now(timezone.utc).date()
    )

    purchase_request = PurchaseRequest(
        company_id=membership.company_id,
        request_number=payload.request_number,
        request_date=request_date,
        status=payload.status,
        requested_by=current_user.id,
        notes=payload.notes,
    )

    db.add(purchase_request)
    db.flush()

    for item in payload.items:
        db.add(
            PurchaseRequestItem(
                purchase_request_id=purchase_request.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit=item.unit,
                required_date=item.required_date,
                specifications=item.specifications,
                notes=item.notes,
            )
        )

    db.add(
        AuditLog(
            company_id=membership.company_id,
            user_id=current_user.id,
            action="PURCHASE_REQUEST_CREATED",
            entity_type="PURCHASE_REQUEST",
            entity_id=purchase_request.id,
            metadata={
                "request_number": purchase_request.request_number,
                "item_count": len(payload.items),
                "status": purchase_request.status,
            },
        )
    )

    db.commit()
    db.refresh(purchase_request)

    return {
        "id": purchase_request.id,
        "company_id": purchase_request.company_id,
        "request_number": purchase_request.request_number,
        "request_date": purchase_request.request_date,
        "status": purchase_request.status,
        "requested_by": purchase_request.requested_by,
        "notes": purchase_request.notes,
        "items": len(payload.items),
    }


@app.post(
    "/api/v1/procurement/supplier-offers",
    tags=["procurement"],
)
@limiter.limit("60/minute")
def create_supplier_offer(
    request: Request,
    payload: SupplierOfferCreateSchema,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(current_user, db)

    purchase_request = db.scalar(
        select(PurchaseRequest).where(
            PurchaseRequest.id == payload.purchase_request_id,
            PurchaseRequest.company_id == membership.company_id,
        )
    )
    if purchase_request is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase request not found",
        )

    if purchase_request.status in {"CLOSED", "CANCELLED"}:
        raise HTTPException(
            status_code=422,
            detail="Purchase request is not eligible for supplier offer",
        )

    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == payload.supplier_id,
            Supplier.company_id == membership.company_id,
            Supplier.is_active.is_(True),
        )
    )
    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Active supplier not found",
        )

    existing_offer = db.scalar(
        select(SupplierOffer).where(
            SupplierOffer.company_id == membership.company_id,
            SupplierOffer.offer_number == payload.offer_number,
        )
    )
    if existing_offer is not None:
        raise HTTPException(
            status_code=409,
            detail="Offer number already exists",
        )

    offer_date = payload.offer_date or date.today()

    if payload.valid_until is not None and payload.valid_until < offer_date:
        raise HTTPException(
            status_code=422,
            detail="valid_until cannot be earlier than offer_date",
        )

    request_items = db.scalars(
        select(PurchaseRequestItem).where(
            PurchaseRequestItem.purchase_request_id
            == purchase_request.id
        )
    ).all()

    request_items_by_id = {
        item.id: item
        for item in request_items
    }

    for item in payload.items:
        request_item = request_items_by_id.get(
            item.purchase_request_item_id
        )

        if request_item is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Purchase request item does not belong "
                    "to the selected purchase request"
                ),
            )

        if request_item.product_id != item.product_id:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Offer product does not match "
                    "purchase request item product"
                ),
            )

        if item.quantity > request_item.quantity:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Offer quantity cannot exceed "
                    "purchase request quantity"
                ),
            )

    supplier_offer = SupplierOffer(
        company_id=membership.company_id,
        purchase_request_id=purchase_request.id,
        supplier_id=supplier.id,
        offer_number=payload.offer_number,
        offer_date=offer_date,
        valid_until=payload.valid_until,
        currency=payload.currency,
        status=payload.status,
        notes=payload.notes,
    )

    db.add(supplier_offer)
    db.flush()

    subtotal = Decimal("0")
    total_vat = Decimal("0")
    total_amount = Decimal("0")

    for item in payload.items:
        net_amount = (
            item.quantity * item.unit_price
        ).quantize(Decimal("0.0001"))

        vat_amount = (
            net_amount * item.vat_rate / Decimal("100")
        ).quantize(Decimal("0.0001"))

        line_total = (
            net_amount + vat_amount
        ).quantize(Decimal("0.0001"))

        subtotal += net_amount
        total_vat += vat_amount
        total_amount += line_total

        db.add(
            SupplierOfferItem(
                supplier_offer_id=supplier_offer.id,
                purchase_request_item_id=item.purchase_request_item_id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                vat_rate=item.vat_rate,
                vat_amount=vat_amount,
                line_total=line_total,
                delivery_days=item.delivery_days,
                notes=item.notes,
            )
        )

    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=membership.company_id,
            action="SUPPLIER_OFFER_CREATED",
            entity_type="SUPPLIER_OFFER",
            entity_id=supplier_offer.id,
            log_metadata={
                "offer_number": supplier_offer.offer_number,
                "purchase_request_id": str(
                    supplier_offer.purchase_request_id
                ),
                "supplier_id": str(
                    supplier_offer.supplier_id
                ),
                "subtotal": str(subtotal),
                "vat_amount": str(total_vat),
                "total_amount": str(total_amount),
                "items_count": len(payload.items),
            },
        )
    )

    db.commit()
    db.refresh(supplier_offer)

    return {
        "id": supplier_offer.id,
        "company_id": supplier_offer.company_id,
        "purchase_request_id": supplier_offer.purchase_request_id,
        "supplier_id": supplier_offer.supplier_id,
        "offer_number": supplier_offer.offer_number,
        "offer_date": supplier_offer.offer_date,
        "valid_until": supplier_offer.valid_until,
        "currency": supplier_offer.currency,
        "status": supplier_offer.status,
        "notes": supplier_offer.notes,
        "items": len(payload.items),
        "subtotal": subtotal,
        "vat_amount": total_vat,
        "total_amount": total_amount,
    }

@app.post(
    "/api/v1/procurement/offer-selections",
    tags=["procurement"],
)
@limiter.limit("60/minute")
def create_offer_selection(
    request: Request,
    payload: OfferSelectionCreateSchema,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(
        current_user,
        db,
    )

    purchase_request = db.scalar(
        select(PurchaseRequest).where(
            PurchaseRequest.id == payload.purchase_request_id,
            PurchaseRequest.company_id == membership.company_id,
        )
    )

    if purchase_request is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase request not found",
        )

    if purchase_request.status in {"CLOSED", "CANCELLED"}:
        raise HTTPException(
            status_code=422,
            detail="Purchase request is not eligible for selection",
        )

    supplier_offer = db.scalar(
        select(SupplierOffer).where(
            SupplierOffer.id == payload.supplier_offer_id,
            SupplierOffer.company_id == membership.company_id,
        )
    )

    if supplier_offer is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier offer not found",
        )

    if supplier_offer.purchase_request_id != purchase_request.id:
        raise HTTPException(
            status_code=422,
            detail="Supplier offer does not belong to the purchase request",
        )

    if supplier_offer.status != "SUBMITTED":
        raise HTTPException(
            status_code=422,
            detail="Only SUBMITTED supplier offers can be selected",
        )

    existing_selection = db.scalar(
        select(OfferSelection).where(
            OfferSelection.company_id == membership.company_id,
            OfferSelection.purchase_request_id == purchase_request.id,
            OfferSelection.status == "SELECTED",
        )
    )

    if existing_selection is not None:
        raise HTTPException(
            status_code=409,
            detail="An active selection already exists for this purchase request",
        )

    selection = OfferSelection(
        company_id=membership.company_id,
        purchase_request_id=purchase_request.id,
        supplier_offer_id=supplier_offer.id,
        selected_by=current_user.id,
        justification=payload.justification,
        status="SELECTED",
    )

    db.add(selection)
    db.flush()

    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=membership.company_id,
            action="SUPPLIER_OFFER_SELECTED",
            entity_type="OFFER_SELECTION",
            entity_id=selection.id,
            log_metadata={
                "purchase_request_id": str(
                    purchase_request.id
                ),
                "supplier_offer_id": str(
                    supplier_offer.id
                ),
                "justification": payload.justification,
            },
        )
    )

    db.commit()
    db.refresh(selection)

    return {
        "id": selection.id,
        "company_id": selection.company_id,
        "purchase_request_id": selection.purchase_request_id,
        "supplier_offer_id": selection.supplier_offer_id,
        "selected_by": selection.selected_by,
        "selected_at": selection.selected_at,
        "status": selection.status,
        "justification": selection.justification,
        "purchase_order_id": selection.purchase_order_id,
        "created_at": selection.created_at,
        "updated_at": selection.updated_at,
    }

@app.post(
    "/api/v1/purchase-orders/{purchase_order_id}/status",
    response_model=PurchaseOrderStatusResponseSchema,
    tags=["purchase-orders"],
)
@limiter.limit("60/minute")
def update_purchase_order_status(
    request: Request,
    purchase_order_id: uuid.UUID,
    payload: PurchaseOrderStatusUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(current_user, db)

    if membership.role not in ("OWNER", "ADMIN", "PROCUREMENT"):
        raise HTTPException(
            status_code=403,
            detail="Bu Й™mЙ™liyyat ГјГ§Гјn kifayЙ™t qЙ™dЙ™r sЙ™lahiyyЙ™tiniz yoxdur.",
        )

    purchase_order = db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.company_id == membership.company_id,
        )
    )

    if not purchase_order:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order tapД±lmadД±",
        )

    current_status = purchase_order.status
    new_status = payload.status

    allowed_transitions = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "CANCELLED"},
        "APPROVED": {"RECEIVED"},
        "RECEIVED": set(),
        "CANCELLED": set(),
    }

    if new_status not in allowed_transitions.get(current_status, set()):
        raise HTTPException(
            status_code=400,
            detail=f"YanlД±Еџ status keГ§idi: {current_status} -> {new_status}",
        )

    purchase_order.status = new_status
    purchase_order.updated_at = datetime.now(timezone.utc)

    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=membership.company_id,
            action="PURCHASE_ORDER_STATUS_CHANGED",
            entity_type="purchase_order",
            entity_id=purchase_order.id,
        )
    )

    db.commit()
    db.refresh(purchase_order)

    return {
        "status": "success",
        "message": "Purchase Order statusu dЙ™yiЕџdirildi.",
        "id": str(purchase_order.id),
        "order_number": purchase_order.order_number,
        "old_status": current_status,
        "new_status": purchase_order.status,
    }
@app.post(
    "/api/v1/purchase-orders",
    response_model=PurchaseOrderResponseSchema,
    tags=["purchase-orders"],
)
@limiter.limit("60/minute")
@app.post(
    "/api/v1/procurement/offer-selections/{selection_id}/purchase-order",
    response_model=ProcurementPurchaseOrderResponseSchema,
    status_code=201,
    tags=["procurement"],
)
@limiter.limit("60/minute")
def create_purchase_order_from_selection(
    request: Request,
    selection_id: uuid.UUID,
    payload: ProcurementPurchaseOrderCreateSchema,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(
        current_user,
        db,
    )

    selection = db.scalar(
        select(OfferSelection)
        .where(
            OfferSelection.id == selection_id,
            OfferSelection.company_id == membership.company_id,
        )
        .with_for_update()
    )

    if selection is None:
        raise HTTPException(
            status_code=404,
            detail="Offer selection not found",
        )

    if selection.status != "SELECTED":
        raise HTTPException(
            status_code=422,
            detail="Only SELECTED offer selections can create purchase orders",
        )

    if selection.purchase_order_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Offer selection already has a purchase order",
        )

    purchase_request = db.scalar(
        select(PurchaseRequest).where(
            PurchaseRequest.id == selection.purchase_request_id,
            PurchaseRequest.company_id == membership.company_id,
        )
    )

    if purchase_request is None:
        raise HTTPException(
            status_code=422,
            detail="Purchase request is not available",
        )

    if purchase_request.status in {"CLOSED", "CANCELLED"}:
        raise HTTPException(
            status_code=422,
            detail="Purchase request is not eligible for purchase order",
        )

    supplier_offer = db.scalar(
        select(SupplierOffer).where(
            SupplierOffer.id == selection.supplier_offer_id,
            SupplierOffer.company_id == membership.company_id,
        )
    )

    if supplier_offer is None:
        raise HTTPException(
            status_code=422,
            detail="Supplier offer is not available",
        )

    if supplier_offer.purchase_request_id != purchase_request.id:
        raise HTTPException(
            status_code=422,
            detail="Supplier offer does not belong to the purchase request",
        )

    if supplier_offer.status != "SUBMITTED":
        raise HTTPException(
            status_code=422,
            detail="Only SUBMITTED supplier offers can create purchase orders",
        )

    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_offer.supplier_id,
            Supplier.company_id == membership.company_id,
            Supplier.is_active.is_(True),
        )
    )

    if supplier is None:
        raise HTTPException(
            status_code=422,
            detail="Supplier is not available or inactive",
        )

    offer_items = db.scalars(
        select(SupplierOfferItem).where(
            SupplierOfferItem.supplier_offer_id == supplier_offer.id
        )
    ).all()

    if not offer_items:
        raise HTTPException(
            status_code=422,
            detail="Supplier offer has no items",
        )

    request_items = db.scalars(
        select(PurchaseRequestItem).where(
            PurchaseRequestItem.purchase_request_id
            == purchase_request.id
        )
    ).all()

    request_items_by_id = {
        item.id: item
        for item in request_items
    }

    for offer_item in offer_items:
        request_item = request_items_by_id.get(
            offer_item.purchase_request_item_id
        )

        if request_item is None:
            raise HTTPException(
                status_code=422,
                detail="Supplier offer item does not belong to the purchase request",
            )

        if offer_item.product_id != request_item.product_id:
            raise HTTPException(
                status_code=422,
                detail="Supplier offer item product does not match purchase request item",
            )

        if offer_item.quantity > request_item.quantity:
            raise HTTPException(
                status_code=422,
                detail="Supplier offer quantity cannot exceed purchase request quantity",
            )

    existing_order = db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.company_id == membership.company_id,
            PurchaseOrder.order_number == payload.order_number,
        )
    )

    if existing_order is not None:
        raise HTTPException(
            status_code=409,
            detail="Purchase order number already exists",
        )

    order_date = (
        payload.order_date
        if payload.order_date
        else datetime.now(timezone.utc).date()
    )

    purchase_order = PurchaseOrder(
        company_id=membership.company_id,
        supplier_id=supplier.id,
        order_number=payload.order_number,
        order_date=order_date,
        status="DRAFT",
        currency=supplier_offer.currency,
        notes=payload.notes,
        subtotal=Decimal("0"),
        vat_amount=Decimal("0"),
        total_amount=Decimal("0"),
    )

    db.add(purchase_order)

    try:
        db.flush()

        subtotal = Decimal("0")
        vat_total = Decimal("0")

        for offer_item in offer_items:
            line_total = (
                offer_item.quantity
                * offer_item.unit_price
            )

            line_vat = (
                line_total
                * offer_item.vat_rate
                / Decimal("100")
            )

            subtotal += line_total
            vat_total += line_vat

            db.add(
                PurchaseOrderItem(
                    purchase_order_id=purchase_order.id,
                    product_id=offer_item.product_id,
                    quantity=offer_item.quantity,
                    unit=offer_item.unit,
                    unit_price=offer_item.unit_price,
                    vat_rate=offer_item.vat_rate,
                    vat_amount=line_vat,
                    line_total=line_total,
                )
            )

        purchase_order.subtotal = subtotal
        purchase_order.vat_amount = vat_total
        purchase_order.total_amount = subtotal + vat_total

        selection.purchase_order_id = purchase_order.id

        db.add(
            AuditLog(
                user_id=current_user.id,
                company_id=membership.company_id,
                action="PURCHASE_ORDER_CREATED",
                entity_type="purchase_order",
                entity_id=purchase_order.id,
                log_metadata={
                    "source": "OFFER_SELECTION",
                    "selection_id": str(selection.id),
                    "purchase_request_id": str(
                        purchase_request.id
                    ),
                    "supplier_offer_id": str(
                        supplier_offer.id
                    ),
                    "order_number": purchase_order.order_number,
                    "supplier_id": str(
                        purchase_order.supplier_id
                    ),
                    "subtotal": str(subtotal),
                    "vat_amount": str(vat_total),
                    "total_amount": str(
                        subtotal + vat_total
                    ),
                    "items_count": len(offer_items),
                },
            )
        )

        db.commit()

    except IntegrityError:
        db.rollback()

        existing_order = db.scalar(
            select(PurchaseOrder).where(
                PurchaseOrder.company_id == membership.company_id,
                PurchaseOrder.order_number == payload.order_number,
            )
        )

        if existing_order is not None:
            raise HTTPException(
                status_code=409,
                detail="Purchase order number already exists",
            )

        raise

    db.refresh(purchase_order)

    return ProcurementPurchaseOrderResponseSchema(
        purchase_order_id=purchase_order.id,
        selection_id=selection.id,
        purchase_request_id=purchase_request.id,
        supplier_offer_id=supplier_offer.id,
        supplier_id=supplier.id,
        order_number=purchase_order.order_number,
        status=purchase_order.status,
        currency=purchase_order.currency,
        subtotal=purchase_order.subtotal,
        vat_amount=purchase_order.vat_amount,
        total_amount=purchase_order.total_amount,
    )
def create_purchase_order(
    request: Request,
    payload: PurchaseOrderCreateSchema,
    current_user: User = Depends(
        require_role(
            "OWNER",
            "ADMIN",
            "PROCUREMENT",
        )
    ),
    db: Session = Depends(get_db),
):

    membership = get_current_membership(
        current_user,
        db,
    )

    # --------------------------------------------------------
    # Supplier вЂ” company isolation
    # --------------------------------------------------------

    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == payload.supplier_id,
            Supplier.company_id == membership.company_id,
            Supplier.is_active.is_(True),
        )
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="T?chizat?? tap?lmad? v? ya bu ?irk?t? aid deyil.",
        )

    # --------------------------------------------------------
    # Order number uniqueness вЂ” company isolation
    # --------------------------------------------------------

    existing_order = db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.company_id == membership.company_id,
            PurchaseOrder.order_number == payload.order_number,
        )
    )

    if existing_order:
        raise HTTPException(
            status_code=409,
            detail="Bu sifari? n?mr?si art?q m?vcuddur.",
        )

    # --------------------------------------------------------
    # Validate all products first
    # --------------------------------------------------------

    product_ids = [item.product_id for item in payload.items]

    products = db.scalars(
        select(Product).where(
            Product.id.in_(product_ids),
            Product.company_id == membership.company_id,
            Product.is_active.is_(True),
        )
    ).all()

    product_map = {
        product.id: product
        for product in products
    }

    missing_products = [
        str(product_id)
        for product_id in product_ids
        if product_id not in product_map
    ]

    if missing_products:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Bir v? ya daha ?ox m?hsul tap?lmad? v? ya bu ?irk?t? aid deyil.",
                "product_ids": missing_products,
            },
        )

    # --------------------------------------------------------
    # Create Purchase Order
    # --------------------------------------------------------

    order_date = payload.order_date if payload.order_date else datetime.now(timezone.utc).date()

    purchase_order = PurchaseOrder(
        company_id=membership.company_id,
        supplier_id=supplier.id,
        order_number=payload.order_number,
        order_date=order_date,
        status=payload.status,
        currency=payload.currency.upper(),
        notes=payload.notes,
        subtotal=Decimal("0"),
        vat_amount=Decimal("0"),
        total_amount=Decimal("0"),
    )

    db.add(purchase_order)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()

        existing_order = db.scalar(
            select(PurchaseOrder).where(
                PurchaseOrder.company_id == membership.company_id,
                PurchaseOrder.order_number == payload.order_number,
            )
        )

        if existing_order:
            raise HTTPException(
                status_code=409,
                detail="Bu sifariЕџ nГ¶mrЙ™si artД±q mГ¶vcuddur.",
            )

        raise

    # --------------------------------------------------------
    # Create items + calculate totals
    # --------------------------------------------------------

    subtotal = Decimal("0")
    vat_total = Decimal("0")

    for item_data in payload.items:

        line_total = (
            item_data.quantity *
            item_data.unit_price
        )

        line_vat = (
            line_total *
            item_data.vat_rate /
            Decimal("100")
        )

        subtotal += line_total
        vat_total += line_vat

        item = PurchaseOrderItem(
            purchase_order_id=purchase_order.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            unit=item_data.unit,
            unit_price=item_data.unit_price,
            vat_rate=item_data.vat_rate,
            vat_amount=line_vat,
            line_total=line_total,
        )

        db.add(item)

    purchase_order.subtotal = subtotal
    purchase_order.vat_amount = vat_total
    purchase_order.total_amount = subtotal + vat_total

    # --------------------------------------------------------
    # Audit Log
    # --------------------------------------------------------

    audit = AuditLog(
        user_id=current_user.id,
        company_id=membership.company_id,
        action="PURCHASE_ORDER_CREATED",
        entity_type="purchase_order",
        entity_id=purchase_order.id,
        log_metadata={
            "order_number": purchase_order.order_number,
            "supplier_id": str(purchase_order.supplier_id),
            "subtotal": str(subtotal),
            "vat_amount": str(vat_total),
            "total_amount": str(subtotal + vat_total),
            "items_count": len(payload.items),
        },
    )

    db.add(audit)

    db.commit()
    db.refresh(purchase_order)

    # --------------------------------------------------------
    # Load items for response
    # --------------------------------------------------------

    items = db.scalars(
        select(PurchaseOrderItem).where(
            PurchaseOrderItem.purchase_order_id == purchase_order.id
        )
    ).all()

    return PurchaseOrderResponseSchema(
        id=purchase_order.id,
        company_id=purchase_order.company_id,
        supplier_id=purchase_order.supplier_id,
        order_number=purchase_order.order_number,
        order_date=purchase_order.order_date,
        status=purchase_order.status,
        currency=purchase_order.currency,
        subtotal=purchase_order.subtotal,
        vat_amount=purchase_order.vat_amount,
        total_amount=purchase_order.total_amount,
        notes=purchase_order.notes,
        created_at=purchase_order.created_at,
        updated_at=purchase_order.updated_at,
        items=[
            PurchaseOrderItemResponseSchema(
                id=item.id,
                purchase_order_id=purchase_order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                vat_rate=item.vat_rate,
                vat_amount=item.vat_amount,
                line_total=item.line_total,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
    )


@app.delete(
    "/api/v1/purchase-orders/{purchase_order_id}",
    tags=["purchase-orders"],
)
@limiter.limit("60/minute")
def delete_purchase_order(
    request: Request,
    purchase_order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(current_user, db)

    if membership.role not in ("OWNER", "ADMIN", "PROCUREMENT"):
        raise HTTPException(
            status_code=403,
            detail="Bu Й™mЙ™liyyat ГјГ§Гјn kifayЙ™t qЙ™dЙ™r sЙ™lahiyyЙ™tiniz yoxdur.",
        )

    purchase_order = db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.company_id == membership.company_id,
        )
    )

    if not purchase_order:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order tapД±lmadД±",
        )
    if purchase_order.status != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail=f"{purchase_order.status} statuslu Purchase Order silinЙ™ bilmЙ™z.",
        )

    deleted_order_id = purchase_order.id
    deleted_order_number = purchase_order.order_number
    company_id = purchase_order.company_id

    db.delete(purchase_order)

    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company_id,
            action="PURCHASE_ORDER_DELETED",
            entity_type="purchase_order",
            entity_id=deleted_order_id,
        )
    )

    db.commit()

    return {
        "status": "success",
        "message": "Purchase Order silindi.",
        "id": str(deleted_order_id),
        "order_number": deleted_order_number,
    }
@app.put(
    "/api/v1/purchase-orders/{purchase_order_id}",
    response_model=PurchaseOrderResponseSchema,
    tags=["purchase-orders"],
)
@limiter.limit("60/minute")
def update_purchase_order(
    request: Request,
    purchase_order_id: uuid.UUID,
    payload: PurchaseOrderUpdateSchema,
    current_user: User = Depends(require_role("OWNER", "ADMIN", "PROCUREMENT")),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(current_user, db)

    purchase_order = db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.company_id == membership.company_id,
        )
    )

    if not purchase_order:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order tapД±lmadД±",
        )

    if purchase_order.status != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail=f"{purchase_order.status} statuslu Purchase Order dЙ™yiЕџdirilЙ™ bilmЙ™z.",
        )
    if payload.supplier_id is not None:
        supplier = db.scalar(
            select(Supplier).where(
                Supplier.id == payload.supplier_id,
                Supplier.company_id == membership.company_id,
                Supplier.is_active.is_(True),
            )
        )

        if not supplier:
            raise HTTPException(
                status_code=400,
                detail="TЙ™chizatГ§Д± tapД±lmadД± vЙ™ ya bu ЕџirkЙ™tЙ™ aid deyil",
            )

        purchase_order.supplier_id = payload.supplier_id

    if payload.order_number is not None:
        duplicate = db.scalar(
            select(PurchaseOrder).where(
                PurchaseOrder.company_id == membership.company_id,
                PurchaseOrder.order_number == payload.order_number,
                PurchaseOrder.id != purchase_order.id,
            )
        )

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="Bu order number artД±q mГ¶vcuddur",
            )

        purchase_order.order_number = payload.order_number

    if payload.order_date is not None:
        purchase_order.order_date = payload.order_date

    if payload.status is not None:
        raise HTTPException(
            status_code=400,
            detail="Purchase Order statusu yalnД±z /status endpointi vasitЙ™silЙ™ dЙ™yiЕџdirilЙ™ bilЙ™r.",
        )

    if payload.currency is not None:
        purchase_order.currency = payload.currency.upper()

    if payload.notes is not None:
        purchase_order.notes = payload.notes

    if payload.items is not None:
        old_items = db.scalars(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.purchase_order_id == purchase_order.id
            )
        ).all()

        for old_item in old_items:
            db.delete(old_item)

        db.flush()

        subtotal = Decimal("0")
        vat_amount = Decimal("0")

        for item_payload in payload.items:
            product = db.scalar(
                select(Product).where(
                    Product.id == item_payload.product_id,
                    Product.company_id == membership.company_id,
                    Product.is_active.is_(True),
                )
            )

            if not product:
                raise HTTPException(
                    status_code=400,
                    detail="MЙ™hsul tapД±lmadД± vЙ™ ya bu ЕџirkЙ™tЙ™ aid deyil",
                )

            line_total = (
                item_payload.quantity * item_payload.unit_price
            ).quantize(Decimal("0.0001"))

            item_vat = (
                line_total * item_payload.vat_rate / Decimal("100")
            ).quantize(Decimal("0.0001"))

            new_item = PurchaseOrderItem(
                purchase_order_id=purchase_order.id,
                product_id=item_payload.product_id,
                quantity=item_payload.quantity,
                unit=item_payload.unit,
                unit_price=item_payload.unit_price,
                vat_rate=item_payload.vat_rate,
                vat_amount=item_vat,
                line_total=line_total,
            )

            db.add(new_item)

            subtotal += line_total
            vat_amount += item_vat

        purchase_order.subtotal = subtotal.quantize(
            Decimal("0.0001")
        )
        purchase_order.vat_amount = vat_amount.quantize(
            Decimal("0.0001")
        )
        purchase_order.total_amount = (
            purchase_order.subtotal + purchase_order.vat_amount
        ).quantize(Decimal("0.0001"))

    purchase_order.updated_at = datetime.now(timezone.utc)

    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=membership.company_id,
            action="PURCHASE_ORDER_UPDATED",
            entity_type="purchase_order",
            entity_id=purchase_order.id,
        )
    )

    db.commit()
    db.refresh(purchase_order)

    items = db.scalars(
        select(PurchaseOrderItem)
        .where(
            PurchaseOrderItem.purchase_order_id == purchase_order.id
        )
        .order_by(PurchaseOrderItem.created_at.asc())
    ).all()

    return PurchaseOrderResponseSchema(
        id=purchase_order.id,
        company_id=purchase_order.company_id,
        supplier_id=purchase_order.supplier_id,
        order_number=purchase_order.order_number,
        order_date=purchase_order.order_date,
        status=purchase_order.status,
        currency=purchase_order.currency,
        subtotal=purchase_order.subtotal,
        vat_amount=purchase_order.vat_amount,
        total_amount=purchase_order.total_amount,
        notes=purchase_order.notes,
        created_at=purchase_order.created_at,
        updated_at=purchase_order.updated_at,
        items=[
            PurchaseOrderItemResponseSchema(
                id=item.id,
                purchase_order_id=item.purchase_order_id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                vat_rate=item.vat_rate,
                vat_amount=item.vat_amount,
                line_total=item.line_total,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
    )
# ============================================================
# PURCHASE ORDER вЂ” GET LIST
# ============================================================

@app.get(
    "/api/v1/purchase-orders",
    response_model=PurchaseOrderListResponseSchema,
    tags=["purchase-orders"],
)
@limiter.limit("60/minute")
def list_purchase_orders(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(
        current_user,
        db,
    )

    total = db.scalar(
        select(func.count(PurchaseOrder.id))
        .where(
            PurchaseOrder.company_id == membership.company_id
        )
    ) or 0

    pages = (total + limit - 1) // limit if total > 0 else 0
    offset = (page - 1) * limit

    purchase_orders = db.scalars(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.company_id == membership.company_id
        )
        .order_by(
            PurchaseOrder.order_date.desc(),
            PurchaseOrder.created_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    results = []

    for purchase_order in purchase_orders:

        items = db.scalars(
            select(PurchaseOrderItem)
            .where(
                PurchaseOrderItem.purchase_order_id
                == purchase_order.id
            )
            .order_by(PurchaseOrderItem.created_at.asc())
        ).all()

        results.append(
            PurchaseOrderResponseSchema(
                id=purchase_order.id,
                company_id=purchase_order.company_id,
                supplier_id=purchase_order.supplier_id,
                order_number=purchase_order.order_number,
                order_date=purchase_order.order_date,
                status=purchase_order.status,
                currency=purchase_order.currency,
                subtotal=purchase_order.subtotal,
                vat_amount=purchase_order.vat_amount,
                total_amount=purchase_order.total_amount,
                notes=purchase_order.notes,
                created_at=purchase_order.created_at,
                updated_at=purchase_order.updated_at,
                items=[
                    PurchaseOrderItemResponseSchema(
                        id=item.id,
                        purchase_order_id=item.purchase_order_id,
                        product_id=item.product_id,
                        quantity=item.quantity,
                        unit=item.unit,
                        unit_price=item.unit_price,
                        vat_rate=item.vat_rate,
                        vat_amount=item.vat_amount,
                        line_total=item.line_total,
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                    )
                    for item in items
                ],
            )
        )

    return PurchaseOrderListResponseSchema(
        items=results,
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@app.get(
    "/api/v1/purchase-orders/{purchase_order_id}",
    response_model=PurchaseOrderResponseSchema,
    tags=["purchase-orders"],
)
@limiter.limit("60/minute")
def get_purchase_order(
    request: Request,
    purchase_order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = get_current_membership(current_user, db)

    purchase_order = db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.company_id == membership.company_id,
        )
    )

    if not purchase_order:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order tapД±lmadД±",
        )

    items = db.scalars(
        select(PurchaseOrderItem)
        .where(
            PurchaseOrderItem.purchase_order_id == purchase_order.id
        )
        .order_by(PurchaseOrderItem.created_at.asc())
    ).all()

    return PurchaseOrderResponseSchema(
        id=purchase_order.id,
        company_id=purchase_order.company_id,
        supplier_id=purchase_order.supplier_id,
        order_number=purchase_order.order_number,
        order_date=purchase_order.order_date,
        status=purchase_order.status,
        currency=purchase_order.currency,
        subtotal=purchase_order.subtotal,
        vat_amount=purchase_order.vat_amount,
        total_amount=purchase_order.total_amount,
        notes=purchase_order.notes,
        created_at=purchase_order.created_at,
        updated_at=purchase_order.updated_at,
        items=[
            PurchaseOrderItemResponseSchema(
                id=item.id,
                purchase_order_id=item.purchase_order_id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                vat_rate=item.vat_rate,
                vat_amount=item.vat_amount,
                line_total=item.line_total,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
    )
