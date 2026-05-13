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
    version="5.0"
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


class ChatRequest(BaseModel):

    message: str

# =========================
# ROOT
# =========================

@app.get("/")
async def root():

    return {

        "message":
        "Grant Simone Backend Running",

        "status":
        "success"

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
                    "role":"system",
                    "content":"""

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
                    "role":"user",
                    "content":req.message
                }

            ],

            temperature=0.7,
            max_tokens=400

        )

        return {

    "success": True,

    "grants":[

        {

            "title":"SBA Microloan Program",

            "amount":"$50,000 Funding",

            "description":"Small business funding for startups and salons.",

            "link":"https://www.sba.gov"

        },

        {

            "title":"Amber Grant",

            "amount":"Women-Owned",

            "description":"Monthly grants for women entrepreneurs.",

            "link":"https://ambergrantsforwomen.com"

        },

        {

            "title":"IFundWomen Grant",

            "amount":"Startup Funding",

            "description":"Funding opportunities for women-led startups and businesses.",

            "link":"https://ifundwomen.com"

        }

    ]

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

            f"{data.businessType} grants {data.state}",
            f"{data.businessType} funding opportunities {data.state}",
            f"{data.businessType} grants USA",
            f"small business grants {data.state}",
            f"startup grants {data.state}",
            f"nonprofit grants {data.state}",
            f"federal grants for businesses",
            f"{data.keywords} grants {data.state}",
            f"{data.keywords} funding opportunities"

        ]

        if str(data.womanOwned).lower() in ["true","yes","1"]:

            queries.append(
                f"women owned business grants {data.state}"
            )

        if str(data.minorityOwned).lower() in ["true","yes","1"]:

            queries.append(
                f"minority owned business grants {data.state}"
            )

        if str(data.veteranOwned).lower() in ["true","yes","1"]:

            queries.append(
                f"veteran owned business grants {data.state}"
            )

        REAL_DOMAINS = [

            ".gov",
            "grants.gov",
            "sba.gov",
            "helloalice.com",
            "skip.com",
            "ifundwomen.com",
            "lisc.org"

        ]

        BAD_KEYWORDS = [

            "tripadvisor",
            "restaurant menu",
            "recipe",
            "tourism",
            "hotel",
            "yelp"

        ]

        grants = []

        seen = set()

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

                            url = r.get("href","")
                            title = r.get("title","Grant")
                            body = r.get("body","Grant opportunity")

                            if not url:
                                continue

                            if url in seen:
                                continue

                            seen.add(url)

                            url_lower = url.lower()
                            title_lower = title.lower()
                            body_lower = body.lower()

                            if any(
                                b in title_lower
                                or b in body_lower
                                for b in BAD_KEYWORDS
                            ):
                                continue

                            if not any(
                                d in url_lower
                                for d in REAL_DOMAINS
                            ):
                                continue

                            score = 75

                            if data.state.lower() in body_lower:
                                score += 5

                            if "grant" in title_lower:
                                score += 5

                            if data.businessType.lower() in body_lower:
                                score += 10

                            recommendation = "STRONG MATCH"

                            if score >= 90:
                                recommendation = "APPLY IMMEDIATELY"

                            grants.append({

                                "grantName": title,

                                "applicationUrl": url,

                                "description": body,

                                "matchScore": score,

                                "recommendation": recommendation

                            })

                        except:
                            pass

                except:
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

                "error":
                "Please wait before generating another proposal."

            }

        last_request_time = current_time

        prompt = f"""

        Write a professional grant proposal.

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

        Include:

        Executive Summary
        Project Overview
        Funding Purpose
        Community Impact
        Conclusion

        Keep proposal:
        concise
        persuasive
        professional
        premium-quality
        submission-ready

        """

        completion = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[

                {
                    "role":"system",
                    "content":"You are an expert grant proposal writer."
                },

                {
                    "role":"user",
                    "content":prompt
                }

            ],

            temperature=0.7,
            max_tokens=900

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
