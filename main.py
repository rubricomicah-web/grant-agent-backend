from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ddgs import DDGS
from groq import Groq
from dotenv import load_dotenv
from typing import Optional
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

    businessName: Optional[str] = None
    businessType: Optional[str] = None
    fundingPurpose: Optional[str] = None
    grantName: Optional[str] = None

    requestedAmount: Optional[str] = None
    projectSummary: Optional[str] = None
    timeline: Optional[str] = None
    targetPopulation: Optional[str] = None


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

            f"{data.businessType} grants USA",
            f"{data.businessType} small business grants",
            f"{data.businessType} startup funding",
            f"{data.businessType} federal grants",
            f"{data.businessType} grant program",
            f"{data.businessType} entrepreneur grants",
            f"{data.businessType} business funding"

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

        if data.state and data.state.lower() != "usa":

            queries.extend([

                f"{data.businessType} grants {data.state}",
                f"{data.businessType} funding {data.state}",
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
            "news"

        ]

        grants = []

        seen = set()
        seen_titles = set()

        provider_count = {}

        # SEARCH

        with DDGS() as ddgs:

            for query in queries:

                time.sleep(0.3)

                try:

                    results = list(
                        ddgs.text(
                            query,
                            max_results=15
                        )
                    )[:15]

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

                        if title_lower in seen_titles:
                            continue

                        seen_titles.add(title_lower)

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

                        if data.businessType.lower() in body_lower:
                            score += 20

                        if data.businessType.lower() in title_lower:
                            score += 20

                        if ".gov" in url_lower or "grants" in url_lower:
                            score += 20

                        if "apply" in body_lower:
                            score += 5

                        if "eligibility" in body_lower:
                            score += 5

                        if "award" in body_lower:
                            score += 5

                        if "small business" in body_lower:
                            score += 5

                        if "closed" in body_lower:
                            score -= 50

                        if "expired" in body_lower:
                            score -= 50

                        if "deadline passed" in body_lower:
                            score -= 50

                        if data.state.lower() != "usa":

                            if data.state.lower() in body_lower:
                                score += 10

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

        # SORT RESULTS

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

                "error":
                "Please wait before generating another proposal."

            }

        last_request_time = current_time

        prompt = f"""

        Create a PROFESSIONAL grant proposal.

        IMPORTANT RULES:

        - Make the proposal look HUMAN-WRITTEN
        - Make it detailed and persuasive
        - Use clean formatting
        - Wrap ALL section titles in double asterisks

        Business Name:
        {data.businessName or "Business"}

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

        Use these EXACT sections:

        **Executive Summary**
        **Organization Overview**
        **Statement of Need**
        **Project Description**
        **Use of Funds**
        **Expected Impact**
        **Sustainability Plan**
        **Conclusion**

        """

        completion = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[

                {
                    "role": "system",
                    "content": "You are an expert grant proposal writer."
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            temperature=0.7,
            max_tokens=2200

        )

        return {

            "success": True,

            "proposalNarrative":
            completion.choices[0].message.content

        }

    except Exception as e:

        return {

            "success": False,
            "error": str(e)

        }
