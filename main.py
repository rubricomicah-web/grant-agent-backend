from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ddgs import DDGS
from google import genai
from dotenv import load_dotenv
from typing import Optional
import os
import time

# =========================
# LOAD ENV VARIABLES
# =========================

load_dotenv()

# =========================
# GEMINI CLIENT
# =========================

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

# =========================
# FASTAPI APP
# =========================

app = FastAPI(
    title="Grant Simone API",
    description="AI-powered grant discovery and proposal generation platform",
    version="4.0"
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
# REQUEST MODELS
# =========================

class GrantSearchRequest(BaseModel):

    businessType: str
    state: str

    keywords: Optional[str] = ""

    womanOwned: Optional[str] = ""
    minorityOwned: Optional[str] = ""
    veteranOwned: Optional[str] = ""
    startup: Optional[str] = ""
    nonprofit: Optional[str] = ""


class ProposalRequest(BaseModel):

    businessName: Optional[str] = None
    businessType: Optional[str] = None
    fundingPurpose: Optional[str] = None
    grantName: Optional[str] = None

    requestedAmount: Optional[str] = None
    projectSummary: Optional[str] = None
    timeline: Optional[str] = None
    targetPopulation: Optional[str] = None


# =========================
# ROOT ROUTE
# =========================

@app.get("/")
async def root():

    return {
        "message": "Grant Simone Backend Running",
        "status": "success"
    }


# =========================
# HEALTH CHECK
# =========================

@app.get("/health")
async def health():

    return {
        "healthy": True
    }


# =========================
# GRANT SEARCH
# =========================

@app.post("/grant-search")
async def grant_search(data: GrantSearchRequest):

    try:

        queries = [

            f"{data.businessType} grants {data.state}",
            f"{data.businessType} small business grants",
            f"{data.businessType} funding opportunities",
            f"{data.businessType} expansion grants",
            f"{data.businessType} startup grants",
            f"{data.businessType} workforce development grants",
            f"{data.businessType} equipment grants",
            f"{data.businessType} operational growth grants",

            f"small business grants {data.state}",
            f"business expansion grants {data.state}",
            f"equipment funding grants {data.state}",
            f"marketing grants for small businesses {data.state}",
            f"workforce grants {data.state}",

            f"women owned business grants {data.state}"
            if str(data.womanOwned).lower() in ["true", "yes", "1"] else "",

            f"minority owned business grants {data.state}"
            if str(data.minorityOwned).lower() in ["true", "yes", "1"] else "",

            f"veteran owned business grants {data.state}"
            if str(data.veteranOwned).lower() in ["true", "yes", "1"] else "",

            f"startup business grants {data.state}"
            if str(data.startup).lower() in ["true", "yes", "1"] else "",

            f"nonprofit grants {data.state}"
            if str(data.nonprofit).lower() in ["true", "yes", "1"] else "",

            f"SBA funding programs {data.state}",
            f"federal business grants USA",

            f"{data.keywords} grants",
            f"{data.keywords} funding opportunities",
            f"{data.keywords} grants {data.state}"

        ]

        queries = [q for q in queries if q]

        REAL_GRANT_DOMAINS = [

            ".gov",
            "grants.gov",
            "sba.gov",
            "helloalice.com",
            "skip.com",
            "nav.com",
            "comcastrise.com",
            "fedex.com",
            "ifundwomen.com",
            "lisc.org",
            "foundersfirstcdc.org",
            "ambergrantsforwomen.com",
            "calosba.ca.gov"
        ]

        BAD_KEYWORDS = [

            "tripadvisor",
            "hotel",
            "restaurant menu",
            "food",
            "recipe",
            "news",
            "wikipedia",
            "yelp",
            "bar",
            "tourism"
        ]

        grants = []

        seen_urls = set()

        with DDGS() as ddgs:

            for query in queries:

                time.sleep(1)

                try:

                    results = list(
                        ddgs.text(
                            query,
                            max_results=8
                        )
                    )

                    for r in results:

                        try:

                            url = r.get("href", "")
                            title = r.get("title", "Unknown Grant")
                            description = r.get("body", "Grant opportunity")

                            if not url:
                                continue

                            if url in seen_urls:
                                continue

                            seen_urls.add(url)

                            url_lower = url.lower()
                            title_lower = title.lower()
                            description_lower = description.lower()

                            bad_result = any(
                                word in title_lower
                                or word in description_lower
                                for word in BAD_KEYWORDS
                            )

                            real_domain = any(
                                domain in url_lower
                                for domain in REAL_GRANT_DOMAINS
                            )

                            if bad_result:
                                continue

                            if not real_domain:
                                continue

                            score = 70

                            if data.businessType.lower() in description_lower:
                                score += 10

                            if data.state.lower() in description_lower:
                                score += 5

                            if "grant" in title_lower:
                                score += 5

                            recommendation = "REVIEW CAREFULLY"

                            if score >= 85:
                                recommendation = "APPLY IMMEDIATELY"

                            elif score >= 75:
                                recommendation = "STRONG MATCH"

                            grants.append({

                                "grantName": title,
                                "sponsorOrganization": None,
                                "fundingAmount": None,
                                "deadline": None,
                                "applicationUrl": url,
                                "sourceUrl": url,
                                "eligibilityRequirements": description,
                                "geographicRestrictions": data.state,
                                "matchScore": score,
                                "recommendation": recommendation,
                                "shortEligibilitySummary": description,
                                "fundingCategory": "Business Grant",
                                "rollingOrFixedDeadline": None,
                                "confidenceLevel": "Medium",
                                "safeToApply": True
                            })

                        except Exception:
                            pass

                except Exception:
                    pass

        grants = sorted(
            grants,
            key=lambda x: x["matchScore"],
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
# PROPOSAL GENERATOR
# =========================

last_request_time = 0

@app.post("/generate-proposal")
async def generate_proposal(data: ProposalRequest):

    global last_request_time

    try:

        current_time = time.time()

        if current_time - last_request_time < 5:

            return {
                "success": False,
                "error": "Please wait before generating another proposal."
            }

        last_request_time = current_time

        prompt = f"""
        Write a professional submission-ready grant proposal.

        Business Name:
        {data.businessName or "Business"}

        Industry:
        {data.businessType or "Small Business"}

        Funding Purpose:
        {data.fundingPurpose or "Business Growth"}

        Grant Program:
        {data.grantName or "Grant Opportunity"}

        Requested Amount:
        {data.requestedAmount or "$50,000"}

        Project Summary:
        {data.projectSummary or "Business expansion and operational growth."}

        Timeline:
        {data.timeline or "12 months"}

        Target Population:
        {data.targetPopulation or "Local communities and underserved populations"}

        The proposal must include only:

        Executive Summary
        Project Overview
        Funding Purpose
        Community Impact
        Conclusion

        Make the proposal:
        professional
        persuasive
        concise
        premium quality
        submission-ready
        human-like
        non-repetitive

        At the beginning of the proposal, include this introduction:

        "I’ve prepared a professionally structured grant proposal draft tailored to the grant opportunity, aligned with the business expansion goals, workforce development plans, and operational growth strategy.

        This proposal framework is designed to provide a strong submission-ready foundation that can be further customized based on specific business goals, financial projections, community impact initiatives, and grant requirements.

        For enhanced proposal refinement, strategic optimization, AI editing assistance, and advanced grant personalization, users may further improve this proposal using the FI Grant Plug or the You Are Granted Bot."

        Keep paragraphs short.

        Use clean spacing.

        Avoid giant text walls.

        Write like a premium consultant presentation.

        Keep sections concise and readable.

        Keep proposal under 700 words.

        Avoid overly detailed sections.

        Keep responses concise and fast to generate.
        """

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config={
                "max_output_tokens": 650,
                "temperature": 0.7
            }
        )

        proposal = response.text

        return {

            "success": True,
            "proposalNarrative": proposal
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }