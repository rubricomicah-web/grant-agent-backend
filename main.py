import asyncio
import sys
import requests

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ddgs import DDGS
from bs4 import BeautifulSoup

# =========================
# WINDOWS ASYNC FIX
# =========================

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

# =========================
# APP
# =========================

app = FastAPI()

# =========================
# CORS FIX
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# HOME
# =========================

@app.get("/")
def home():

    return {
        "message": "Grant Simone API Running"
    }

# =========================
# MODELS
# =========================

class GrantSearchRequest(BaseModel):

    businessType: str
    state: str
    keywords: str = ""


class ProposalRequest(BaseModel):

    businessName: str
    industry: str
    location: str
    fundingPurpose: str
    grantName: str
    sponsorOrganization: str
    requestedAmount: str
    projectSummary: str
    timeline: str
    targetPopulation: str


class SubmissionRequest(BaseModel):

    businessName: str
    ownerName: str
    email: str
    phone: str
    industry: str
    location: str
    fundingPurpose: str
    website: str
    annualRevenue: str
    employees: str
    grantName: str
    grantUrl: str

# =========================
# GRANT SEARCH
# =========================

@app.post("/grant-search")
async def grant_search(data: GrantSearchRequest):

    try:

        queries = [

            f"{data.businessType} grants {data.state}",

            f"small business grants {data.state}",

            "FedEx small business grant",

            "Comcast RISE grant",

            "Hello Alice grants"
        ]

        grants = []

        seen_urls = set()

        with DDGS() as ddgs:

            for query in queries:

                try:

                    results = list(
                        ddgs.text(
                            query,
                            max_results=3
                        )
                    )

                    for r in results:

                        try:

                            url = r.get("href")

                            if not url:
                                continue

                            if url in seen_urls:
                                continue

                            seen_urls.add(url)

                            grants.append({

                                "grantName":
                                    r.get("title", "Unknown Grant"),

                                "applicationUrl":
                                    url,

                                "description":
                                    r.get(
                                        "body",
                                        "Grant opportunity"
                                    ),

                                "safeToApply":
                                    True
                            })

                        except Exception:
                            pass

                except Exception:
                    pass

        return {

            "success": True,

            "totalFound":
                len(grants),

            "grants":
                grants
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }

# =========================
# PROPOSAL GENERATOR
# =========================

@app.post("/generate-proposal")
async def generate_proposal(data: ProposalRequest):

    try:

        proposal = f"""
GRANT PROPOSAL

Business Name:
{data.businessName}

Industry:
{data.industry}

Location:
{data.location}

Funding Purpose:
{data.fundingPurpose}

Grant Name:
{data.grantName}

Requested Amount:
{data.requestedAmount}

Executive Summary:
{data.businessName} is requesting funding support
through the {data.grantName} program to support
business expansion and operational growth.
"""

        return {
            "success": True,
            "proposal": proposal
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }

# =========================
# SAFETY SCANNER
# =========================

@app.post("/submit-application")
async def submit_application(data: SubmissionRequest):

    try:

        response = requests.get(
            data.grantUrl,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        html = response.text.lower()

        requires_payment = any(
            x in html for x in [
                "application fee",
                "pay now",
                "checkout"
            ]
        )

        requires_registration = any(
            x in html for x in [
                "sign in",
                "register",
                "create account"
            ]
        )

        return {

            "success": True,

            "grantName":
                data.grantName,

            "grantUrl":
                data.grantUrl,

            "requiresPayment":
                requires_payment,

            "requiresRegistration":
                requires_registration,

            "safeToApply":
                not requires_payment
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }