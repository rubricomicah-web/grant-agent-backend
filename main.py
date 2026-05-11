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
# AUTONOMOUS SUBMISSION
# =========================

@app.post("/submit-application")
async def submit_application(data: SubmissionRequest):

    from playwright.async_api import async_playwright

    try:

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )

            page = await browser.new_page()

            await page.goto(
                data.grantUrl,
                wait_until="domcontentloaded",
                timeout=120000
            )

            await page.wait_for_timeout(5000)

            page_text = await page.locator("body").inner_text()

            lower = page_text.lower()

            payment_keywords = [
                "application fee",
                "pay now",
                "checkout",
                "billing",
                "processing fee",
                "membership fee"
            ]

            for keyword in payment_keywords:

                if keyword in lower:

                    await browser.close()

                    return {
                        "success": False,
                        "requiresPayment": True,
                        "message": f"Grant requires payment ({keyword})"
                    }

            auth_keywords = [
                "sign in",
                "log in",
                "create account",
                "register",
                "member login"
            ]

            for keyword in auth_keywords:

                if keyword in lower:

                    await browser.close()

                    return {
                        "success": False,
                        "requiresRegistration": True,
                        "message": f"Grant requires registration ({keyword})"
                    }

            captcha_keywords = [
                "captcha",
                "recaptcha",
                "i'm not a robot"
            ]

            for keyword in captcha_keywords:

                if keyword in lower:

                    await browser.close()

                    return {
                        "success": False,
                        "captchaDetected": True,
                        "message": f"Captcha detected ({keyword})"
                    }

            print("PAGE PASSED SCAN")

            try:
                await page.locator(
                    'input[type="email"]'
                ).first.fill(data.email)
            except:
                pass

            try:
                await page.locator(
                    'input[type="text"]'
                ).nth(0).fill(data.ownerName)
            except:
                pass

            try:
                await page.locator(
                    'input[type="text"]'
                ).nth(1).fill(data.businessName)
            except:
                pass

            try:
                await page.locator(
                    'input[type="tel"]'
                ).fill(data.phone)
            except:
                pass

            await page.screenshot(
                path="grant_submission.png"
            )

            await browser.close()

            return {
                "success": True,
                "message": "Automation completed successfully"
            }

    except Exception as e:

        return {
            "success": False,
            "error": repr(e)
        }