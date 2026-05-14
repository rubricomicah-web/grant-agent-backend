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
            f"{data.businessType} {data.state} grants 2026 open application",
            f"{data.businessType} {data.state} small business grants 2026",
            f"{data.businessType} {data.state} startup funding 2026",
            f"{data.businessType} federal grants 2026",
            f"{data.businessType} entrepreneur grants 2026",
            f"{data.businessType} business funding 2026",
            f"{data.businessType} government grants 2026"
            
        ]

        # KEYWORDS

        if data.keywords:

            queries.append(
                f"{data.keywords} grants"
            )

            queries.append(
                f"{data.keywords} funding"
            )

        # STATE SEARCHES

        if data.state and data.state.strip().lower() != "usa":
            
            queries.extend([

                f"{data.businessType} grants {data.state}",
                f"{data.businessType} funding {data.state}",
                f"{data.businessType} startup grants in {data.state}",
                f"{data.businessType} small business grants {data.state}"

            ])

        # OWNERSHIP FILTERS

        if str(data.womanOwned).lower() in ["true", "yes", "1"]:

            queries.append(
                f"women owned business grants {data.state}"
            )

        if str(data.minorityOwned).lower() in ["true", "yes", "1"]:

            queries.append(
                f"minority owned business grants {data.state}"
            )

        if str(data.veteranOwned).lower() in ["true", "yes", "1"]:

            queries.append(
                f"veteran owned business grants {data.state}"
            )

        # NONPROFIT FILTER

        if str(data.nonprofit).lower() in ["true", "yes", "1"]:

            queries.append(
                f"{data.businessType} nonprofit grants {data.state}"
            )

        # STARTUP FILTER

        if str(data.startup).lower() in ["true", "yes", "1"]:

            queries.append(
                f"{data.businessType} startup accelerator funding {data.state}"
            )

            queries.append(
                f"{data.businessType} seed funding {data.state}"
            )

        # TRUSTED DOMAINS

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
            "foundationcenter.org",
            "candid.org",
            "grantfinder.com",
            "economicdevelopment.gov",
            "grantsforwomen.org"

        ]

        # BAD RESULTS

        BAD_KEYWORDS = [

            "tripadvisor",
            "restaurant menu",
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

            "event",
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

        # SEARCH
        
        # REMOVE DUPLICATE QUERIES
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

                    try:

                        url = r.get("href", "")
                        title = r.get("title", "Grant")
                        body = r.get("body", "Grant opportunity")

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

                        # REMOVE OLD / EXPIRED GRANTS

                        if any(
                            old_year in body_lower or old_year in title_lower
                            for old_year in [
                                "2020",
                                "2021",
                                "2022",
                                "2023",
                                "2024"
                            ]
                        ):
                            continue

                        if "closed" in body_lower:
                            continue

                        if "expired" in body_lower:
                            continue

                        if "deadline passed" in body_lower:
                            continue

                        if "past deadline" in body_lower:
                            continue

                        # NORMALIZE TITLE
                        normalized_title = " ".join(
                           title_lower
                           .replace("-", "")
                           .replace("|", "")
                           .replace(":", "")
                           .replace(",", "")
                           .replace(".", "")
                           .split()
                        )

                        # DEDUPLICATE SIMILAR TITLES
                        if normalized_title in seen_titles:
                            continue
                        seen_titles.add(normalized_title)
                        
                        # BAD FILTER

                        if any(
                            b in title_lower or b in body_lower
                            for b in BAD_KEYWORDS
                        ):
                            continue

                        # TRUSTED DOMAINS

                        if not any(
                            d in url_lower
                            for d in REAL_DOMAINS
                        ):
                            continue

                        # PROVIDER LIMIT

                        provider = clean_url.split("/")[0]

                        if provider not in provider_count:
                            provider_count[provider] = 0

                        if provider_count[provider] >= 2:
                            continue

                        provider_count[provider] += 1

                        # SCORING

                        score = 0

                        if "grant" in title_lower:
                            score += 25

                        if "funding" in body_lower:
                            score += 10

                        if data.businessType and data.businessType.lower() in body_lower:
                            score += 20

                        if data.businessType and data.businessType.lower() in title_lower:
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
                       
                        if "2026" in body_lower:
                            score += 20

                        elif "2025" in body_lower:
                            score += 5
                        if "small business" in body_lower:
                            score += 5

                        if "closed" in body_lower:
                            score -= 50

                        if "expired" in body_lower:
                            score -= 50

                        if "deadline passed" in body_lower:
                            score -= 50
                            
                        if "2021" in body_lower or "2022" in body_lower:
                            score -= 20
                            
                        # STATE PRIORITY

                        if data.state.strip().lower() != "usa":

                            if (
                                data.state.lower() in body_lower
                                or data.state.lower() in title_lower
                                or data.state.lower() in url_lower
                            ):

                                score += 35

                            else:

                                score -= 10

                        # MINIMUM SCORE

                        if score < 55:
                            continue

                        # RECOMMENDATION

                        recommendation = "GOOD MATCH"

                        if score >= 90:
                            recommendation = "APPLY IMMEDIATELY"

                        elif score >= 75:
                            recommendation = "HIGH MATCH"

                        elif score >= 60:
                            recommendation = "GOOD MATCH"

                        else:
                            recommendation = "LOW MATCH"

                        # SAVE

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
                            "matchScore": score,
                            "recommendation": recommendation

                        })

                    except Exception as e:

                        print("INNER ERROR:", e)

        # PRIORITIZE STATE RESULTS

        if data.state.strip().lower() != "usa":
            
            state_grants = []
            other_grants = []

            for g in grants:

                text_blob = (
                    g["grantName"] +
                    g["description"] +
                    g["applicationUrl"]
                ).lower()

                if data.state.strip().lower() in text_blob:

                    state_grants.append(g)

                else:

                    other_grants.append(g)

            state_grants = sorted(

                state_grants,

                key=lambda x: (
                    x["matchScore"],
                    ".gov" in x["applicationUrl"]
                ),

                reverse=True

            )

            other_grants = sorted(

                other_grants,

                key=lambda x: (
                    x["matchScore"],
                    ".gov" in x["applicationUrl"]
                ),

                reverse=True

            )

            grants = state_grants + other_grants

        else:

            grants = sorted(

                grants,

                key=lambda x: (
                    x["matchScore"],
                    ".gov" in x["applicationUrl"]
                ),

                reverse=True

            )

        # EMPTY RESULTS

        if len(grants) == 0:

            return {

                "success": True,
                "totalFound": 0,
                "message": "No matching grants found.",
                "grants": []

            }

        # SUCCESS

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
            "error": "Rate limit exceeded. Please wait before generating another proposal."

        }

    )

# =========================
# PROPOSAL GENERATOR
# =========================

@app.post("/generate-proposal")
@limiter.limit("3/minute")
async def generate_proposal(
    request: Request,
    data: ProposalRequest
):

    try:

        prompt = f"""

        Create a PROFESSIONAL grant proposal.

        IMPORTANT RULES:

        - Make the proposal look HUMAN-WRITTEN
        - Make it detailed and persuasive
        - Avoid generic wording
        - Use realistic business language

        Business Name:
        {data.businessName or "Business"}

        Owner Name:
        {data.ownerName or "Business Owner"}

        Years In Business:
        {data.businessYears or "1"}

        Industry:
        {data.businessType or "Business"}

        Funding Purpose:
        {data.fundingPurpose or "Growth"}

        Grant Program:
        {data.grantName or "Grant Opportunity"}

        Requested Amount:
        {data.requestedAmount or "$50,000"}

        Project Summary:
        {data.projectSummary or "Business growth and expansion"}

        Timeline:
        {data.timeline or "12 months"}

        Target Population:
        {data.targetPopulation or "Local communities"}

        Include these sections:

        Executive Summary
        Organization Overview
        Statement of Need
        Project Description
        Use of Funds
        Expected Impact
        Sustainability Plan
        Conclusion

        """

        completion = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[

                {
                    "role": "system",
                    "content": "You are a professional grant proposal writer."
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            temperature=0.7,
            max_tokens=2200

        )

        proposal_text = completion.choices[0].message.content

        # CLEAN TEXT

        proposal_text = proposal_text.replace("**", "")

        # PDF FILE

        business_name = data.businessName or "Business"

        filename = os.path.abspath(
            f"{business_name.replace(' ', '_')}_proposal.pdf"
        )

        doc = SimpleDocTemplate(

            filename,

            pagesize=letter,

            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50

        )

        # STYLES

        title_style = ParagraphStyle(

            'Title',

            fontName='Helvetica-Bold',

            fontSize=18,

            leading=22,

            textColor=colors.black,

            spaceAfter=18

        )

        body_style = ParagraphStyle(

            'Body',

            fontName='Helvetica',

            fontSize=11,

            leading=16,

            textColor=colors.black,

            spaceAfter=10

        )

        heading_style = ParagraphStyle(

            'Heading',

            fontName='Helvetica-Bold',

            fontSize=13,

            leading=18,

            textColor=colors.black,

            spaceBefore=12,

            spaceAfter=8

        )

        # BUILD STORY

        story = []

        story.append(

            Paragraph(

                f"{business_name} Grant Proposal",

                title_style

            )

        )

        story.append(Spacer(1, 12))

        story.append(

            Paragraph(

                f"""

                <b>Owner:</b> {data.ownerName or "N/A"}<br/>

                <b>Years in Business:</b> {data.businessYears or "N/A"}<br/>

                <b>Business Type:</b> {data.businessType or "N/A"}<br/>

                <b>Requested Amount:</b> {data.requestedAmount or "N/A"}

                """,

                body_style

            )

        )

        story.append(Spacer(1, 18))

        # FORMAT CONTENT

        lines = proposal_text.split("\n")

        headings = [

            "Executive Summary",
            "Organization Overview",
            "Statement of Need",
            "Project Description",
            "Use of Funds",
            "Expected Impact",
            "Sustainability Plan",
            "Conclusion"

        ]

        for line in lines:

            line = line.strip()

            if not line:
                continue

            if line in headings:

                story.append(

                    Paragraph(

                        line,

                        heading_style

                    )

                )

            else:

                story.append(

                    Paragraph(

                        line,

                        body_style

                    )

                )

        # BUILD PDF

        doc.build(story)

        # RETURN PDF

        return FileResponse(

            path=filename,

            media_type="application/pdf",

            filename=os.path.basename(filename)

        )

    except Exception as e:

        print("PDF ERROR:", str(e))

        return {

            "success": False,
            "error": str(e)

        }
        
