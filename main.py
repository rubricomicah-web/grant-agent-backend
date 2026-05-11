import asyncio
import sys
import requests
import os

from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

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
# OPENAI
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(
    api_key=OPENAI_API_KEY
)

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
# PROPOSAL GENERATOR
# =========================

@app.post("/generate-proposal")
async def generate_proposal(data: ProposalRequest):

    try:

        prompt = f"""
Write a professional grant proposal.

BUSINESS:
{data.businessName}

INDUSTRY:
{data.industry}

LOCATION:
{data.location}

FUNDING PURPOSE:
{data.fundingPurpose}

GRANT NAME:
{data.grantName}

SPONSOR:
{data.sponsorOrganization}

REQUESTED AMOUNT:
{data.requestedAmount}

PROJECT SUMMARY:
{data.projectSummary}

TIMELINE:
{data.timeline}

TARGET POPULATION:
{data.targetPopulation}
"""

        try:

            completion = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            proposal = completion.choices[0].message.content

        except Exception:

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

Requested Amount:
{data.requestedAmount}

Executive Summary:
{data.businessName} is seeking funding to support business expansion, improve operational capacity, strengthen marketing efforts, acquire software systems, hire additional staff, and improve client services within the community.

Business Overview:
The company provides financial and business services including tax preparation, credit restoration, business funding assistance, and financial education.

Project Goals:
- Expand business operations
- Increase staffing capacity
- Improve software infrastructure
- Strengthen marketing and outreach
- Support underserved entrepreneurs

Timeline:
{data.timeline}

Target Population:
{data.targetPopulation}
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
# GRANT SAFETY SCANNER
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
        ).lower()

        payment_keywords = [
            "application fee",
            "pay now",
            "checkout",
            "billing",
            "processing fee",
            "membership fee"
        ]

        login_keywords = [
            "sign in",
            "log in",
            "create account",
            "register",
            "member login"
        ]

        captcha_keywords = [
            "captcha",
            "recaptcha",
            "i'm not a robot"
        ]

        suspicious_keywords = [
            "wire transfer",
            "gift card",
            "crypto payment",
            "bitcoin",
            "send payment immediately"
        ]

        requires_payment = any(
            x in text for x in payment_keywords
        )

        requires_login = any(
            x in text for x in login_keywords
        )

        captcha_detected = any(
            x in text for x in captcha_keywords
        )

        suspicious_detected = any(
            x in text for x in suspicious_keywords
        )

        return {

            "success": True,

            "grantName":
                data.grantName,

            "grantUrl":
                data.grantUrl,

            "safeToApply":
                not requires_payment and not suspicious_detected,

            "requiresPayment":
                requires_payment,

            "requiresLogin":
                requires_login,

            "captchaDetected":
                captcha_detected,

            "suspiciousWebsite":
                suspicious_detected,

            "message":
                "