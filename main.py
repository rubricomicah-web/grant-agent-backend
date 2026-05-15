from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from pydantic import BaseModel
from typing import Optional

from ddgs import DDGS
from groq import Groq

from dotenv import load_dotenv

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

import os
import time

# =========================
# LOAD ENV
# =========================

load_dotenv()

# =========================
# GROQ CLIENT
# =========================

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# =========================
# FASTAPI
# =========================

app = FastAPI(
    title="Grant Simone API",
    description="AI-powered grant discovery and proposal generation platform",
    version="6.0"
)

# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# MODELS
# =========================

class GrantSearchRequest(BaseModel):

    businessType: str
    state: Optional[str] = "USA"

    keywords: Optional[str] = ""

    womanOwned: Optional[str] = ""
    minorityOwned: Optional[str] = ""
    veteranOwned: Optional[str] = ""

    startup: Optional[str] = ""
    nonprofit: Optional[str] = ""


class ProposalRequest(BaseModel):

    businessName: str = ""
    ownerName: str = ""
    businessYears: str = ""
    businessType: str = ""
    fundingPurpose: str = ""
    grantName: str = ""
    requestedAmount: str = ""

    projectSummary: str = ""
    timeline: str = ""
    targetPopulation: str = ""


class ChatRequest(BaseModel):

    message: str


# =========================
# ROOT
# =========================

@app.get("/")
async def root():

    return {

        "message": "Grant Simone Backend Running",
        "status": "success"

    }


# =========================
# HEALTH
# =========================

@app.get("/health")
async def health():

    return {

        "healthy": True

    }


# =========================
# CHAT AI
# =========================

@app.post("/chat")
async def chat(req: ChatRequest):

    try:

        completion = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[

                {
                    "role": "system",
                    "content": """

                    You are Grant Simone,
                    an AI grant funding consultant.

                    Help users:
                    - find grants
                    - funding opportunities
                    - nonprofit funding
                    - startup funding
                    - women-owned business grants
                    - minority business grants
                    - veteran-owned business grants
                    - business growth strategies
                    - proposal strategies

                    Be:
                    professional
                    conversational
                    concise
                    premium-quality
                    helpful

                    """
                },

                {
                    "role": "user",
                    "content": req.message
                }

            ],

            temperature=0.9,
            max_tokens=2200

        )

        return {

            "success": True,
            "response": completion.choices[0].message.content

        }

    except Exception as e:

        return {

            "success": False,
            "error": str(e)

        }


# =========================
# GRANT SEARCH
# =========================

@app.post("/grant-search")
async def grant_search(data: GrantSearchRequest):

    try:

        queries = [

            f"{data.businessType} grants",
            f"{data.businessType} grants {data.state}",
            f"site:grants.gov {data.businessType}",
            f"site:sba.gov {data.businessType}"

        ]

        if data.keywords:

            queries.append(
                f"{data.keywords} grants"
            )

            queries.append(
                f"{data.keywords} funding"
            )

        REAL_DOMAINS = [

            ".gov",
            "grants.gov",
            "sba.gov",
            "helloalice.com",
            "skip.com",
            "ifundwomen.com",
            "lisc.org",
            "fedex.com",
            "nav.com",
            "ambergrantsforwomen.com",
            "comcastrisers.com",
            "usda.gov",
            "nist.gov",
            "nsf.gov",
            "eda.gov",
            "mbda.gov",
            "calosba.ca.gov",
            "cdfifund.gov",
            "grantwatch.com",
            "candid.org"

        ]

        BAD_KEYWORDS = [

            "tripadvisor",
            "recipe",
            "tourism",
            "hotel",
            "yelp",
            "facebook",
            "instagram",
            "linkedin",
            "youtube",
            "reddit",
            "wikipedia",
            "news",
            "conference",
            "seminar",
            "scholarship",
            "university",
            "course",
            "training"

        ]

        grants = []

        seen = set()
        seen_titles = set()

        provider_count = {}

        queries = list(set(queries))

        with DDGS(timeout=20) as ddgs:

            for query in queries:

                try:

                    results = list(
                        ddgs.text(
                            query,
                            max_results=5
                        )
                    )

                except Exception as e:

                    print("SEARCH ERROR:", e)
                    continue

                for r in results:

                    if len(grants) >= 10:
                        break

                    try:

                        url = r.get("href", "")
                        title = r.get("title", "Grant")
                        body = r.get("body") or "Grant funding opportunity"

                        if not url:
                            continue

                        clean_url = url.replace(
                            "https://", ""
                        ).replace(
                            "http://", ""
                        ).split("?")[0]

                        if clean_url in seen:
                            continue

                        seen.add(clean_url)

                        url_lower = url.lower()
                        title_lower = title.lower()
                        body_lower = body.lower()

                        grant_keywords = [
                            "grant",
                            "funding",
                            "loan",
                            "capital",
                            "award"
                        ]

                        if not any(
                            k in title_lower
                            for k in grant_keywords
                        ):
                            continue

                        normalized_title = " ".join(
                            title_lower
                            .replace("-", "")
                            .replace("|", "")
                            .replace(":", "")
                            .replace(",", "")
                            .replace(".", "")
                            .split()
                        )

                        if normalized_title in seen_titles:
                            continue

                        seen_titles.add(normalized_title)

                        if any(
                            b in title_lower or b in body_lower
                            for b in BAD_KEYWORDS
                        ):
                            continue

                        provider = clean_url.split("/")[0]

                        if provider not in provider_count:
                            provider_count[provider] = 0

                        if provider_count[provider] >= 2:
                            continue

                        provider_count[provider] += 1

                        score = 0

                        trusted = any(
                            d in url_lower
                            for d in REAL_DOMAINS
                        )

                        if trusted:
                            score += 25
                        else:
                            score -= 5

                        if "grant" in title_lower:
                            score += 25

                        if "funding" in body_lower:
                            score += 10

                        business_words = data.businessType.lower().split()

                        if any(word in body_lower for word in business_words):
                            score += 20

                        if any(word in title_lower for word in business_words):
                            score += 20

                        if ".gov" in url_lower or "grants" in url_lower:
                            score += 20

                        if "apply" in body_lower:
                            score += 5

                        if "eligibility" in body_lower:
                            score += 5

                        if "award" in body_lower:
                            score += 5

                        if "$" in str(body):
                            score += 10

                        current_year = str(time.localtime().tm_year)

                        if (
                            current_year in body_lower
                            or current_year in title_lower
                        ):
                            score += 15

                        if "closed" in body_lower:
                            score -= 50

                        if "expired" in body_lower:
                            score -= 50

                        if score < 20:
                            continue

                        recommendation = "GOOD MATCH"

                        if score >= 90:
                            recommendation = "APPLY IMMEDIATELY"

                        elif score >= 75:
                            recommendation = "HIGH MATCH"

                        elif score >= 60:
                            recommendation = "GOOD MATCH"

                        else:
                            recommendation = "LOW MATCH"

                        grants.append({

                            "grantName": title,
                            "provider": provider,
                            "applicationUrl": url,
                            "description": body,
                            "deadline": "Check official website",
                            "fundingAmount": "Varies",
                            "eligibility": data.businessType,
                            "grantType": "Business Grant",
                            "source": "Real-time web search",
                            "status": "ACTIVE",
                            "matchScore": min(score, 100),
                            "recommendation": recommendation

                        })

                    except Exception as e:

                        print("INNER ERROR:", e)

                if len(grants) >= 10:
                    break

        grants = sorted(

            grants,

            key=lambda x: (
                x["matchScore"],
                ".gov" in x["applicationUrl"]
            ),

            reverse=True

        )

        return {

            "success": True,
            "totalFound": len(grants),
            "grants": grants[:10]

        }

    except Exception as e:

        return {

            "success": False,
            "error": str(e)

        }


# =========================
# RATE LIMITER
# =========================

limiter = Limiter(key_func=get_remote_address)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):

    return JSONResponse(

        status_code=429,

        content={

            "success": False,
            "error": "Rate limit exceeded."

        }

    )
