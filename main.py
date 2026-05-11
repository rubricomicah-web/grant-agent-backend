import asyncio
import sys
import requests
import os

from fastapi import FastAPI
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
# HOME
# =========================

@app.get("/")
def home():

    return {
        "message": "Grant Agent API Running"
    }

# =========================
# MODELS
# =========================

class GrantSearchRequest(BaseModel):

    businessType: str
    state: str
    keywords: str

    womanOwned: bool = True
    minorityOwned: bool = False
    veteranOwned: bool = False


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
# REAL USA GRANT SEARCH
# =========================

@app.post("/grant-search")
async def grant_search(data: GrantSearchRequest):

    try:

        queries = [

            f"{data.businessType} small business grants {data.state}",

            f"{data.businessType} startup grants {data.state}",

            f"women owned business grants {data.state}",

            f"minority business grants {data.state}",

            f"small business funding programs {data.state}",

            "FedEx small business grant",

            "Visa small business grant",

            "Comcast RISE grant",

            "Hello Alice grants"
        ]

        grants = []

        seen_urls = set()

        bad_keywords = [
            "student",
            "college",
            "university",
            "financial aid",
            "tuition",
            "school",
            "fafsa",
            "scholarship"
        ]

        with DDGS() as ddgs:

            for query in queries:

                try:

                    results = list(
                        ddgs.text(
                            query,
                            max_results=5
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

                            response = requests.get(
                                url,
                                timeout=8,
                                headers={
                                    "User-Agent":
                                    "Mozilla/5.0"
                                }
                            )

                            html = response.text

                            soup = BeautifulSoup(
                                html,
                                "html.parser"
                            )

                            text = soup.get_text(
                                " ",
                                strip=True
                            )

                            lower = text.lower()

                            if len(text) < 100:
                                continue

                            if any(
                                bad in lower
                                for bad in bad_keywords
                            ):
                                continue

                            requires_payment = any(
                                x in lower for x in [
                                    "application fee",
                                    "submit payment",
                                    "processing fee",
                                    "membership fee",
                                    "pay now",
                                    "checkout",
                                    "billing"
                                ]
                            )

                            requires_registration = any(
                                x in lower for x in [
                                    "create account",
                                    "register",
                                    "sign up",
                                    "login required",
                                    "member login"
                                ]
                            )

                            captcha_detected = any(
                                x in lower for x in [
                                    "captcha",
                                    "recaptcha",
                                    "i'm not a robot"
                                ]
                            )

                            grants.append({

                                "grantName":
                                    r.get("title"),

                                "applicationUrl":
                                    url,

                                "description":
                                    r.get("body"),

                                "requiresPayment":
                                    requires_payment,

                                "requiresRegistration":
                                    requires_registration,

                                "captchaDetected":
                                    captcha_detected,

                                "safeToApply":
                                    not requires_payment,

                                "businessType":
                                    data.businessType,

                                "state":
                                    data.state
                            })

                        except Exception:
                            pass

                except Exception:
                    pass

        return {

            "success": True,

            "businessType":
                data.businessType,

            "state":
                data.state,

            "keywords":
                data.keywords,

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
# SIMPLE PROPOSAL GENERATOR
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

Sponsor Organization:
{data.sponsorOrganization}

Requested Amount:
{data.requestedAmount}

Project Summary:
{data.projectSummary}

Timeline:
{data.timeline}

Target Population:
{data.targetPopulation}

Executive Summary:
{data.businessName} is seeking funding support through the
{data.grantName} program to expand operations, improve services,
and create additional economic opportunities within the community.

The requested funding will be used for:
- Business expansion
- Software upgrades
- Marketing initiatives
- Staffing improvements
- Operational support

This project will strengthen long-term sustainability,
increase revenue opportunities, and improve service delivery.

Conclusion:
We appreciate your consideration and support for our business growth initiative.
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
# SAFE APPLICATION ANALYZER
# =========================

@app.post("/submit-application")
async def submit_application(data: SubmissionRequest):

    try:

        response = requests.get(
            data.grantUrl,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        html = response.text

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        text = soup.get_text(
            " ",
            strip=True
        )

        lower = text.lower()

        payment_keywords = [
            "application fee",
            "pay now",
            "checkout",
            "billing",
            "processing fee",
            "membership fee"
        ]

        requires_payment = any(
            keyword in lower
            for keyword in payment_keywords
        )

        auth_keywords = [
            "sign in",
            "log in",
            "create account",
            "register",
            "member login"
        ]

        requires_registration = any(
            keyword in lower
            for keyword in auth_keywords
        )

        captcha_keywords = [
            "captcha",
            "recaptcha",
            "i'm not a robot"
        ]

        captcha_detected = any(
            keyword in lower
            for keyword in captcha_keywords
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

            "captchaDetected":
                captcha_detected,

            "safeToApply":
                not requires_payment
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }