from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from duckduckgo_search import DDGS

app = FastAPI()

# CORS FIX
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REQUEST MODEL
class GrantSearchRequest(BaseModel):
    businessType: str
    state: str


# ROOT ROUTE
@app.get("/")
async def root():
    return {
        "message": "Grant Simone Backend Running"
    }


# GRANT SEARCH ROUTE
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

        REAL_GRANT_DOMAINS = [

            ".gov",

            "grants.gov",

            "sba.gov",

            "calosba.ca.gov",

            "helloalice.com",

            "skip.com",

            "nav.com",

            "ambergrantsforwomen.com",

            "comcastrise.com",

            "fedex.com"
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

            "bar"
        ]

        grants = []

        seen_urls = set()

        with DDGS() as ddgs:

            for query in queries:

                try:

                    results = list(
                        ddgs.text(
                            query,
                            max_results=10
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

                            bad_result = any(
                                word in title_lower
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

                            grants.append({

                                "grantName":
                                    title,

                                "applicationUrl":
                                    url,

                                "description":
                                    description,

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