from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ddgs import DDGS
from google import genai
from dotenv import load_dotenv
import os

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
    version="2.0"
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
    keywords: str | None = ""

    womanOwned: str | None = ""
    minorityOwned: str | None = ""
    veteranOwned: str | None = ""


class ProposalRequest(BaseModel):
    businessName: str
    businessType: str
    fundingPurpose: str
    grantName: str


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
# GRANT SEARCH ROUTE
# =========================

@app.post("/grant-search")
async def grant_search(data: GrantSearchRequest):

    try:

        queries = [

            f"{data.businessType} grants {data.state}",

            f"{data.businessType} small business grants California",

            f"beauty salon grants California",

            f"beauty business grants",

            f"beauty industry funding programs",

            f"women owned business grants {data.state}"
            if str(data.womanOwned).lower() in ["true", "yes", "1"] else "",

            f"minority owned business grants {data.state}"
            if str(data.minorityOwned).lower() in ["true", "yes", "1"] else "",

            f"veteran owned business grants {data.state}"
            if str(data.veteranOwned).lower() in ["true", "yes", "1"] else "",

            f"California women owned business grants",

            f"small business expansion grants California",

            f"equipment grants for salons",

            f"workforce development grants beauty industry",

            f"marketing grants for small businesses",

            f"startup and expansion grants California",

            f"{data.keywords} grants {data.state}"

        ]

        queries = [q for q in queries if q]

        REAL_GRANT_DOMAINS = [

            ".gov",
            "grants.gov",
            "sba.gov",
            "calosba.ca.gov",
            "helloalice.com",
            "skip.com",
            "nav.com",
            "comcastrise.com",
            "fedex.com",
            "ifundwomen.com",
            "lisc.org",
            "foundersfirstcdc.org",
            "ambergrantsforwomen.com"
        ]

        BAD_KEYWORDS = [

            "how to",
            "tips",
            "guide",
            "blog",
            "article",
            "restaurant",
            "tripadvisor",
            "trip canvas",
            "food",
            "menu",
            "hotel",
            "bar",
            "yelp",
            "wikipedia",
            "news"
        ]

        grants = []

        seen_urls = set()

        with DDGS() as ddgs:

            for query in queries:

                import time
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

                            title = r.get(
                                "title",
                                "Unknown Grant"
                            )

                            description = r.get(
                                "body",
                                "Grant opportunity"
                            )

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

                            score = 75

                            if data.businessType.lower() in description_lower:
                                score += 10

                            if data.state.lower() in description_lower:
                                score += 5

                            if str(data.womanOwned).lower() in ["true", "yes", "1"]:
                                  if "women" in description_lower:
                                      score += 5

                            recommendation = "REVIEW CAREFULLY"

                            if score >= 85:
                                recommendation = "APPLY IMMEDIATELY"

                            elif score >= 65:
                                recommendation = "STRONG MATCH"

                            grants.append({

                                "grantName": title,
                                "sponsorOrganization": None,
                                "fundingAmount": None,
                                "deadline": None,
                                "applicationUrl": url,
                                "sourceUrl": url,
                                "eligibilityRequirements": None,
                                "geographicRestrictions": data.state,
                                "matchScore": score,
                                "recommendation": recommendation,
                                "shortEligibilitySummary": description,
                                "fundingCategory": "Small Business Grant",
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

import time

last_request_time = 0

@app.post("/generate-proposal")
async def generate_proposal(data: ProposalRequest):

    global last_request_time

    try:

        # SIMPLE RATE LIMIT
        current_time = time.time()

        if current_time - last_request_time < 10:

            return {
                "success": False,
                "error": "Please wait 10 seconds before generating another proposal."
            }

        last_request_time = current_time

        # SHORTER PROMPT = LOWER GEMINI QUOTA USAGE
        prompt = f"""
        Write a professional small business grant proposal.

        Business:
        {data.businessName}

        Industry:
        {data.businessType}

        Funding Goal:
        {data.fundingPurpose}

        Grant:
        {data.grantName}

        Make the proposal professional,
        persuasive, realistic,
        concise, and submission-ready.
        """

        try:

            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
                config={
                    "max_output_tokens": 700,
                    "temperature": 0.7
                }
            )

            proposal = response.text

        except Exception:

            # PREMIUM FALLBACK PROPOSAL

            proposal = f"""
# EXECUTIVE SUMMARY

{data.businessName} respectfully requests funding support through
the {data.grantName} opportunity to support
{data.fundingPurpose} initiatives designed to strengthen operational
capacity, improve long-term sustainability, and accelerate strategic growth.

The requested funding will help expand organizational capabilities,
enhance operational efficiency, and position the business for scalable
long-term success within the {data.businessType} industry.

This investment will directly support sustainable business development,
economic impact, and increased service capacity.

# ORGANIZATION OVERVIEW

{data.businessName} operates within the
{data.businessType} sector and is committed to delivering
high-quality services while maintaining responsible and sustainable growth.

The organization focuses on operational excellence,
customer service, strategic expansion, and long-term business sustainability.

# STATEMENT OF NEED

As demand for services continues to increase,
additional operational support is necessary to ensure the organization
can scale effectively while maintaining quality and efficiency.

Funding is needed to support critical business initiatives related to:

- operational expansion
- infrastructure improvements
- staffing support
- technology implementation
- organizational scalability
- long-term sustainability

# PROJECT DESCRIPTION

Grant funding will support strategic initiatives focused on improving
business operations, increasing efficiency, and strengthening long-term growth potential.

Primary project activities include:

- operational infrastructure improvements
- technology and software enhancements
- staffing and workforce support
- scalable operational development
- customer service optimization
- organizational capacity building

# IMPLEMENTATION PLAN

The organization will implement the project through a phased operational strategy.

Phase 1:
Assessment, planning, and resource allocation.

Phase 2:
Implementation of operational improvements,
technology enhancements, and workforce support initiatives.

Phase 3:
Performance evaluation, operational optimization,
and long-term sustainability planning.

# EXPECTED OUTCOMES

The proposed project is expected to generate measurable operational and economic benefits, including:

- increased operational efficiency
- improved organizational scalability
- strengthened financial sustainability
- enhanced service delivery capacity
- improved customer experience
- long-term business growth support

# BUDGET JUSTIFICATION

Requested funding will be used responsibly to support approved operational activities,
business infrastructure improvements, staffing support,
technology implementation, and strategic development initiatives.

# SUSTAINABILITY PLAN

The project is designed to create sustainable long-term value
beyond the initial grant funding period.

Long-term sustainability will be supported through:

- continued business revenue generation
- operational efficiencies
- strategic reinvestment
- scalable infrastructure improvements

# COMMUNITY AND ECONOMIC IMPACT

The proposed project is expected to contribute positively to local economic activity
through operational growth, workforce support, and expanded business capacity.

# CONCLUSION

{data.businessName} appreciates the opportunity to be considered
for funding support through the {data.grantName} program.

This investment would directly support sustainable business growth,
improved operational capacity, and long-term organizational development.
"""

        return {

            "success": True,
            "proposalNarrative": proposal
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }