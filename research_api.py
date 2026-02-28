"""
Research Agent API - Financial Markets Research System

This module provides APIs for:
1. Creating and managing research jobs
2. Running the browsing agent to gather information from websites
3. Running the summarization agent to produce reports
4. Real-time pipeline status updates via SSE
"""
import asyncio
import json
import re
import os
import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from copilot import CopilotClient
from contextlib import asynccontextmanager
from typing import Optional
from pydantic import BaseModel

import database as db

# ============ Pydantic Models ============

class CreateJobRequest(BaseModel):
    title: str
    user_query: str
    description: Optional[str] = ""
    stock_symbols: Optional[str] = ""


class AnswerQuestionsRequest(BaseModel):
    job_id: int
    answers: dict


# ============ Financial Research Configuration ============

FINANCIAL_NEWS_SOURCES = [
    {"name": "Yahoo Finance", "base_url": "https://finance.yahoo.com/quote/{symbol}"},
    {"name": "Google Finance", "base_url": "https://www.google.com/finance/quote/{symbol}:NASDAQ"},
]

# Tavily API configuration for web search
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "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")

# Ensure it's set in environment for child processes
os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

TAVILY_MCP_CONFIG = {
    "tavily": {
        "type": "local",
        "command": "tavily-mcp",
        "args": [],
        "env": {"TAVILY_API_KEY": TAVILY_API_KEY},
        "tools": ["tavily_search"],
    }
}

INITIAL_QUESTIONS = [
    {
        "id": "stocks",
        "question": "Which stock(s) would you like to research?",
        "placeholder": "e.g., AAPL, MSFT, GOOGL",
        "type": "text"
    },
    {
        "id": "timeframe",
        "question": "What time frame are you interested in?",
        "options": ["Today's news", "Past week", "Past month", "Past quarter"],
        "type": "select"
    },
    {
        "id": "focus_areas",
        "question": "What aspects interest you most?",
        "options": ["Earnings & Financials", "Market Sentiment", "Technical Analysis", "Company News", "Industry Trends", "Analyst Ratings"],
        "type": "multiselect"
    },
    {
        "id": "investment_goal",
        "question": "What's your investment goal?",
        "options": ["Buy decision", "Sell decision", "Hold analysis", "General research", "Risk assessment"],
        "type": "select"
    }
]


# ============ Agent System Prompts ============

CLARIFYING_AGENT_PROMPT = """You are a financial research assistant. The user wants to research stocks.
Based on their initial query, generate 2-4 follow-up questions to better understand their needs.

Return your response as a JSON object with this structure:
{
    "questions": [
        {
            "id": "unique_id",
            "question": "Your question text",
            "type": "text" | "select" | "multiselect",
            "options": ["option1", "option2"] // only for select/multiselect
        }
    ],
    "extracted_info": {
        "stocks": ["AAPL", "MSFT"],  // any stock symbols detected
        "timeframe": "detected timeframe if any",
        "focus": "detected focus areas if any"
    }
}

Be concise. Focus on understanding:
- Specific stocks or sectors they want to research
- Their investment timeline and goals
- Specific concerns or news they've heard about
- Risk tolerance and decision type (buy/sell/hold)"""

BROWSER_AGENT_PROMPT = """You are a financial research agent. Your task is to browse the provided URLs and extract relevant financial information.

For each URL you visit, extract:
1. Recent news headlines about the stock(s)
2. Key financial metrics mentioned
3. Analyst opinions and ratings
4. Market sentiment indicators
5. Any notable events or announcements

Focus on factual information. Note the source and date of each piece of information.
Return structured data that can be used for analysis."""

SUMMARIZER_AGENT_PROMPT = """You are a financial analyst creating a comprehensive research report.
Based on the gathered research data, create a detailed report with:

1. **Executive Summary**: 2-3 sentence overview
2. **Stock Analysis**: For each stock mentioned:
   - Current sentiment (Bullish/Bearish/Neutral)
   - Key news and events
   - Financial highlights
3. **Market Context**: Broader market conditions affecting the stocks
4. **Risk Factors**: Potential concerns identified
5. **Recommendation**: Clear actionable advice based on the research
6. **Sources**: List all sources used

Format the report in clean Markdown. Be objective and data-driven.

Return your response as a JSON object:
{
    "title": "Report title",
    "summary": "Executive summary text",
    "sentiment": "Bullish" | "Bearish" | "Neutral" | "Mixed",
    "recommendation": "Buy" | "Sell" | "Hold" | "Monitor",
    "full_report": "Complete markdown report",
    "sources": ["source1", "source2"]
}"""


# ============ Global State ============

class AppState:
    copilot_client: Optional[CopilotClient] = None
    job_queues: dict = {}  # job_id -> asyncio.Queue for SSE updates


app_state = AppState()


# ============ FastAPI Setup ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app_state.copilot_client = CopilotClient()
    await app_state.copilot_client.start()
    print("Copilot client started")
    yield
    # Shutdown
    await app_state.copilot_client.stop()
    print("Copilot client stopped")


app = FastAPI(lifespan=lifespan)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Utility Functions ============

def extract_stock_symbols(text: str) -> list:
    """Extract potential stock symbols from text."""
    # Common patterns: $AAPL, AAPL, aapl
    pattern = r'\$?([A-Za-z]{1,5})\b'
    matches = re.findall(pattern, text.upper())
    # Filter to likely stock symbols (uppercase, 1-5 chars)
    common_words = {'A', 'I', 'THE', 'AND', 'OR', 'FOR', 'TO', 'IN', 'IS', 'IT', 'ON', 'AT', 'BE', 'AS', 'BY', 'AN', 'OF'}
    symbols = [m for m in matches if m not in common_words and len(m) >= 2]
    return list(set(symbols))[:10]  # Limit to 10 symbols


async def send_job_update(job_id: int, update: dict):
    """Send an update to all listeners for a job."""
    if job_id in app_state.job_queues:
        for queue in app_state.job_queues[job_id]:
            await queue.put(update)


def create_job_queue(job_id: int) -> asyncio.Queue:
    """Create a queue for job updates."""
    queue = asyncio.Queue()
    if job_id not in app_state.job_queues:
        app_state.job_queues[job_id] = []
    app_state.job_queues[job_id].append(queue)
    return queue


def remove_job_queue(job_id: int, queue: asyncio.Queue):
    """Remove a queue from job listeners."""
    if job_id in app_state.job_queues:
        app_state.job_queues[job_id].remove(queue)
        if not app_state.job_queues[job_id]:
            del app_state.job_queues[job_id]


# ============ Agent Functions ============

async def run_agent_with_prompt(system_prompt: str, user_message: str, job_id: int = None, use_tavily: bool = False) -> str:
    """Run a single agent turn and return the response."""
    print(f"[Agent] Starting agent call for job {job_id}... (tavily={use_tavily})")
    try:
        session_config = {
            "model": "claude-sonnet-4.6",
            "streaming": False,
            "system_message": {"mode": "replace", "content": system_prompt}
        }
        if use_tavily:
            session_config["mcp_servers"] = TAVILY_MCP_CONFIG
        
        session = await app_state.copilot_client.create_session(session_config)
        
        response_content = ""
        error_content = ""
        done_event = asyncio.Event()
        
        def on_event(event):
            nonlocal response_content, error_content
            event_type = event.type.value
            print(f"[Agent] Event: {event_type}")
            if event_type == "assistant.message":
                response_content = event.data.content or ""
                print(f"[Agent] Got response: {len(response_content)} chars")
            elif event_type == "session.idle":
                done_event.set()
            elif event_type == "error":
                error_content = str(getattr(event.data, 'message', event.data))
                print(f"[Agent] Error event: {error_content}")
                done_event.set()
        
        session.on(on_event)
        await session.send({"prompt": user_message})
        
        try:
            await asyncio.wait_for(done_event.wait(), timeout=180)
        except asyncio.TimeoutError:
            print(f"[Agent] Timeout waiting for response")
            await session.destroy()
            raise Exception("Agent response timed out after 180 seconds")
        
        await session.destroy()
        
        if error_content:
            raise Exception(f"Agent error: {error_content}")
        
        if not response_content:
            print(f"[Agent] Warning: Empty response received")
        
        return response_content
    except Exception as e:
        print(f"[Agent] Exception: {str(e)}")
        raise


async def run_browsing_agent(job_id: int, stocks: list, focus_areas: list, user_answers: dict):
    """Run the browsing agent to gather information from websites."""
    await send_job_update(job_id, {"type": "stage", "stage": "browsing", "status": "running"})
    
    gathered_data = []
    
    for symbol in stocks:
        symbol = symbol.upper().strip()
        
        # Step 1: Run Tavily web search first
        step_id = db.create_step(
            job_id=job_id,
            step_type="search",
            step_name=f"Tavily web search for {symbol}",
            url=f"tavily://search/{symbol}"
        )
        
        await send_job_update(job_id, {
            "type": "step",
            "step_id": step_id,
            "step_type": "search",
            "step_name": f"Tavily web search for {symbol}",
            "status": "running"
        })
        
        discovered_urls = []  # URLs discovered from Tavily search to fetch later
        focus_str = ', '.join(focus_areas) if focus_areas else 'financial news, stock price, market sentiment'
        
        try:
            search_prompt = f"""Use the tavily_search tool to search for: "{symbol} stock news {focus_str}"

After getting the search results, extract and return a JSON object with:
{{
    "symbol": "{symbol}",
    "source": "Tavily Web Search",
    "urls_to_fetch": ["https://example.com/article1", "https://example.com/article2"],
    "headlines": ["headline1", "headline2"],
    "sentiment": "positive/negative/neutral",
    "key_points": ["point1", "point2"]
}}

IMPORTANT: 
- Include only 1-2 of the MOST relevant and important URLs from the search results in "urls_to_fetch" for deeper analysis.
- Do NOT include Yahoo Finance URLs (finance.yahoo.com) or Google Finance URLs (google.com/finance) - we already fetch those separately.
- Prefer news articles, analyst reports, or other unique sources."""
            
            search_result = await run_agent_with_prompt(
                BROWSER_AGENT_PROMPT,
                search_prompt,
                job_id,
                use_tavily=True
            )
            
            gathered_data.append({
                "symbol": symbol,
                "source": "Tavily Web Search",
                "url": f"tavily://search/{symbol}",
                "extracted": search_result
            })
            
            # Try to extract URLs from the search result
            try:
                # Find JSON in the response
                json_match = re.search(r'\{[^{}]*"urls_to_fetch"\s*:\s*\[[^\]]*\][^{}]*\}', search_result, re.DOTALL)
                if json_match:
                    result_json = json.loads(json_match.group())
                    discovered_urls = result_json.get("urls_to_fetch", [])[:2]
                else:
                    # Try to find any URLs in the response
                    url_pattern = r'https?://[^\s"<>\]\)]+'
                    found_urls = re.findall(url_pattern, search_result)
                    discovered_urls = [u for u in found_urls if 'tavily' not in u.lower()][:2]
            except Exception as parse_err:
                print(f"[Agent] Could not parse URLs from search result: {parse_err}")
            
            db.update_step(step_id, "completed", search_result)
            await send_job_update(job_id, {
                "type": "step",
                "step_id": step_id,
                "status": "completed",
                "output": search_result[:500]
            })
        except Exception as e:
            error_msg = str(e)[:200]
            db.update_step(step_id, "failed", error_message=error_msg)
            await send_job_update(job_id, {
                "type": "step",
                "step_id": step_id,
                "status": "failed",
                "error": error_msg
            })
        
        # Step 2: Fetch URLs discovered from Tavily search
        for url in discovered_urls:
            step_id = db.create_step(
                job_id=job_id,
                step_type="browse",
                step_name=f"Fetching discovered URL for {symbol}",
                url=url
            )
            
            await send_job_update(job_id, {
                "type": "step",
                "step_id": step_id,
                "step_type": "browse",
                "step_name": f"Fetching discovered URL",
                "url": url,
                "status": "running"
            })
            
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                    response = await client.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        content = response.text[:50000]
                        
                        extraction_prompt = f"""Extract financial information from this webpage content about {symbol}.
Focus on: {focus_str}.
User is interested in: {user_answers.get('investment_goal', 'general research')}.

Webpage content:
{content[:20000]}

Return a JSON object with:
{{
    "symbol": "{symbol}",
    "source": "Web Article",
    "headlines": ["headline1", "headline2"],
    "sentiment": "positive/negative/neutral",
    "key_points": ["point1", "point2"],
    "relevant_for_user": true/false
}}"""
                        
                        extracted = await run_agent_with_prompt(
                            BROWSER_AGENT_PROMPT,
                            extraction_prompt,
                            job_id
                        )
                        
                        gathered_data.append({
                            "symbol": symbol,
                            "source": "Discovered URL",
                            "url": url,
                            "extracted": extracted
                        })
                        
                        db.update_step(step_id, "completed", extracted)
                        await send_job_update(job_id, {
                            "type": "step",
                            "step_id": step_id,
                            "status": "completed",
                            "output": extracted[:500]
                        })
                    else:
                        db.update_step(step_id, "failed", error_message=f"HTTP {response.status_code}")
                        await send_job_update(job_id, {
                            "type": "step",
                            "step_id": step_id,
                            "status": "failed",
                            "error": f"HTTP {response.status_code}"
                        })
            except Exception as e:
                error_msg = str(e)[:200]
                db.update_step(step_id, "failed", error_message=error_msg)
                await send_job_update(job_id, {
                    "type": "step",
                    "step_id": step_id,
                    "status": "failed",
                    "error": error_msg
                })
        
        # Step 3: Browse default financial sources (Yahoo Finance, Google Finance)
        for source in FINANCIAL_NEWS_SOURCES:
            url = source["base_url"].format(symbol=symbol)
            step_id = db.create_step(
                job_id=job_id,
                step_type="browse",
                step_name=f"Fetching {source['name']} for {symbol}",
                url=url
            )
            
            await send_job_update(job_id, {
                "type": "step",
                "step_id": step_id,
                "step_type": "browse",
                "step_name": f"Fetching {source['name']} for {symbol}",
                "url": url,
                "status": "running"
            })
            
            try:
                # Fetch the webpage content
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                    response = await client.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        content = response.text[:50000]  # Limit content size
                        
                        # Use agent to extract relevant info
                        extraction_prompt = f"""Extract financial information from this webpage content about {symbol}.
Focus on: {', '.join(focus_areas) if focus_areas else 'general news and sentiment'}.
User is interested in: {user_answers.get('investment_goal', 'general research')}.

Webpage content:
{content[:20000]}

Return a JSON object with:
{{
    "symbol": "{symbol}",
    "source": "{source['name']}",
    "headlines": ["headline1", "headline2"],
    "sentiment": "positive/negative/neutral",
    "key_points": ["point1", "point2"],
    "metrics": {{"price": "...", "change": "...", etc}},
    "relevant_for_user": true/false
}}"""
                        
                        extracted = await run_agent_with_prompt(
                            BROWSER_AGENT_PROMPT,
                            extraction_prompt,
                            job_id
                        )
                        
                        gathered_data.append({
                            "symbol": symbol,
                            "source": source["name"],
                            "url": url,
                            "extracted": extracted
                        })
                        
                        db.update_step(step_id, "completed", extracted)
                        await send_job_update(job_id, {
                            "type": "step",
                            "step_id": step_id,
                            "status": "completed",
                            "output": extracted[:500]
                        })
                    else:
                        db.update_step(step_id, "failed", error_message=f"HTTP {response.status_code}")
                        await send_job_update(job_id, {
                            "type": "step",
                            "step_id": step_id,
                            "status": "failed",
                            "error": f"HTTP {response.status_code}"
                        })
                        
            except Exception as e:
                error_msg = str(e)[:200]
                db.update_step(step_id, "failed", error_message=error_msg)
                await send_job_update(job_id, {
                    "type": "step",
                    "step_id": step_id,
                    "status": "failed",
                    "error": error_msg
                })
    
    await send_job_update(job_id, {"type": "stage", "stage": "browsing", "status": "completed"})
    return gathered_data


async def run_summarization_agent(job_id: int, gathered_data: list, job_info: dict):
    """Run the summarization agent to create the final report."""
    print(f"[Summarize] Starting summarization for job {job_id} with {len(gathered_data)} data points")
    await send_job_update(job_id, {"type": "stage", "stage": "summarizing", "status": "running"})
    
    db.update_job_status(job_id, db.JobStatus.SUMMARIZING)
    
    step_id = db.create_step(
        job_id=job_id,
        step_type="summarize",
        step_name="Creating comprehensive report",
        input_data=json.dumps({"data_points": len(gathered_data)})
    )
    
    await send_job_update(job_id, {
        "type": "step",
        "step_id": step_id,
        "step_type": "summarize",
        "step_name": "Creating comprehensive report",
        "status": "running"
    })
    
    try:
        # Check if we have any data to summarize
        if not gathered_data:
            print(f"[Summarize] No data gathered, creating minimal report")
            # Create a minimal report when no data was gathered
            report_data = {
                "title": f"Research Report: {job_info.get('stock_symbols', 'Stocks')}",
                "summary": "Unable to gather sufficient data from financial sources. Please try again later.",
                "sentiment": "Neutral",
                "recommendation": "Monitor",
                "full_report": "# Research Report\n\nWe were unable to gather sufficient data from financial sources at this time. This could be due to temporary website issues. Please try again later.",
                "sources": []
            }
        else:
            # Prepare the data for summarization
            user_answers = json.loads(job_info.get('user_answers', '{}') or '{}')
            
            # Filter to only successful extractions
            successful_data = [d for d in gathered_data if d.get('extracted')]
            print(f"[Summarize] Using {len(successful_data)} successful extractions out of {len(gathered_data)} total")
            
            summary_prompt = f"""Create a financial research report based on the following gathered data.

User's Original Query: {job_info.get('user_query', '')}
Stocks Researched: {job_info.get('stock_symbols', '')}
Investment Goal: {user_answers.get('investment_goal', 'General research')}
Time Frame: {user_answers.get('timeframe', 'Recent')}
Focus Areas: {user_answers.get('focus_areas', [])}

Gathered Research Data:
{json.dumps(successful_data, indent=2)[:30000]}

Create a comprehensive report with sentiment analysis and actionable recommendations.
Remember to return valid JSON."""

            print(f"[Summarize] Calling agent with prompt of {len(summary_prompt)} chars")
            report_json = await run_agent_with_prompt(
                SUMMARIZER_AGENT_PROMPT,
                summary_prompt,
                job_id
            )
            print(f"[Summarize] Got response of {len(report_json)} chars")
            
            # Parse the report
            try:
                # Try to extract JSON from the response
                json_match = re.search(r'\{[\s\S]*\}', report_json)
                if json_match:
                    report_data = json.loads(json_match.group())
                    print(f"[Summarize] Successfully parsed JSON report")
                else:
                    print(f"[Summarize] No JSON found, using raw response")
                    report_data = {
                        "title": f"Research Report: {job_info.get('stock_symbols', 'Stocks')}",
                        "summary": report_json[:500] if report_json else "Report generation failed",
                        "sentiment": "Neutral",
                        "recommendation": "Monitor",
                        "full_report": report_json or "No report content generated",
                        "sources": [d["url"] for d in gathered_data if d.get("url")]
                    }
            except json.JSONDecodeError as je:
                print(f"[Summarize] JSON decode error: {je}")
                report_data = {
                    "title": f"Research Report: {job_info.get('stock_symbols', 'Stocks')}",
                    "summary": report_json[:500] if report_json else "Report generation failed",
                    "sentiment": "Neutral",
                    "recommendation": "Monitor",
                    "full_report": report_json or "No report content generated",
                    "sources": [d["url"] for d in gathered_data if d.get("url")]
                }
        
        # Save the report
        print(f"[Summarize] Saving report to database")
        db.create_report(
            job_id=job_id,
            title=report_data.get("title", "Research Report"),
            summary=report_data.get("summary", ""),
            sentiment=report_data.get("sentiment", "Neutral"),
            recommendation=report_data.get("recommendation", "Monitor"),
            full_report=report_data.get("full_report", ""),
            sources=report_data.get("sources", [])
        )
        
        db.update_step(step_id, "completed", json.dumps(report_data))
        await send_job_update(job_id, {
            "type": "step",
            "step_id": step_id,
            "status": "completed"
        })
        
        await send_job_update(job_id, {"type": "stage", "stage": "summarizing", "status": "completed"})
        db.update_job_status(job_id, db.JobStatus.COMPLETED)
        await send_job_update(job_id, {"type": "job_completed", "report": report_data})
        
        return report_data
        
    except Exception as e:
        import traceback
        error_msg = str(e)[:500] if str(e) else "Unknown error occurred"
        print(f"[Summarize] ERROR: {error_msg}")
        print(f"[Summarize] Traceback: {traceback.format_exc()}")
        db.update_step(step_id, "failed", error_message=error_msg)
        db.update_job_status(job_id, db.JobStatus.FAILED, error_msg)
        await send_job_update(job_id, {
            "type": "step",
            "step_id": step_id,
            "status": "failed",
            "error": error_msg
        })
        await send_job_update(job_id, {"type": "job_failed", "error": error_msg})
        raise


async def run_research_pipeline(job_id: int):
    """Run the complete research pipeline for a job."""
    try:
        job = db.get_job(job_id)
        if not job:
            return
        
        user_answers = json.loads(job.get('user_answers', '{}') or '{}')
        
        # Parse stocks
        stocks = []
        if job.get('stock_symbols'):
            stocks = [s.strip() for s in job['stock_symbols'].split(',') if s.strip()]
        if not stocks and user_answers.get('stocks'):
            stocks = [s.strip() for s in user_answers['stocks'].split(',') if s.strip()]
        
        # Get focus areas
        focus_areas = user_answers.get('focus_areas', [])
        if isinstance(focus_areas, str):
            focus_areas = [focus_areas]
        
        if not stocks:
            # Try to extract from the original query
            stocks = extract_stock_symbols(job.get('user_query', ''))
        
        if not stocks:
            db.update_job_status(job_id, db.JobStatus.FAILED, "No stock symbols found")
            await send_job_update(job_id, {"type": "job_failed", "error": "No stock symbols found"})
            return
        
        # Update job with extracted symbols
        if not job.get('stock_symbols'):
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE research_jobs SET stock_symbols = ? WHERE id = ?", 
                          (','.join(stocks), job_id))
            conn.commit()
            conn.close()
        
        db.update_job_status(job_id, db.JobStatus.RESEARCHING)
        
        # Run browsing agent
        gathered_data = await run_browsing_agent(job_id, stocks, focus_areas, user_answers)
        
        # Run summarization agent
        job = db.get_job(job_id)  # Refresh job data
        await run_summarization_agent(job_id, gathered_data, job)
        
    except Exception as e:
        db.update_job_status(job_id, db.JobStatus.FAILED, str(e)[:500])
        await send_job_update(job_id, {"type": "job_failed", "error": str(e)[:500]})


# ============ API Endpoints ============

@app.get("/")
async def root():
    """Serve the frontend."""
    return FileResponse("research_frontend.html")


@app.get("/api/initial-questions")
async def get_initial_questions():
    """Get the initial questions for starting a new job."""
    return {"questions": INITIAL_QUESTIONS}


@app.post("/api/jobs")
async def create_job_endpoint(request: CreateJobRequest, background_tasks: BackgroundTasks):
    """Create a new research job."""
    job_id = db.create_job(
        title=request.title,
        user_query=request.user_query,
        description=request.description,
        stock_symbols=request.stock_symbols
    )
    
    return {"job_id": job_id, "status": "created"}


@app.get("/api/jobs")
async def list_jobs():
    """List all research jobs."""
    jobs = db.get_all_jobs()
    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}")
async def get_job_endpoint(job_id: int):
    """Get a specific job."""
    job = db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    
    steps = db.get_steps_for_job(job_id)
    report = db.get_report_for_job(job_id)
    
    return {"job": job, "steps": steps, "report": report}


@app.delete("/api/jobs/{job_id}")
async def delete_job_endpoint(job_id: int):
    """Delete a job."""
    db.delete_job(job_id)
    return {"status": "deleted"}


@app.post("/api/jobs/{job_id}/clarify")
async def generate_clarifying_questions(job_id: int):
    """Generate clarifying questions for a job using AI."""
    job = db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    
    # Use the clarifying agent
    clarify_prompt = f"""The user wants to research financial markets. Their query is:
"{job['user_query']}"

Additional context:
- Title: {job.get('title', '')}
- Mentioned stocks: {job.get('stock_symbols', 'None specified')}

Generate follow-up questions to better understand their research needs."""
    
    try:
        response = await run_agent_with_prompt(
            CLARIFYING_AGENT_PROMPT,
            clarify_prompt,
            job_id
        )
        
        # Parse the JSON response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
            questions = result.get('questions', INITIAL_QUESTIONS)
            extracted = result.get('extracted_info', {})
            
            # Update job with extracted info
            if extracted.get('stocks'):
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE research_jobs SET stock_symbols = ? WHERE id = ?",
                              (','.join(extracted['stocks']), job_id))
                conn.commit()
                conn.close()
            
            db.update_job_clarification(job_id, questions)
            return {"questions": questions, "extracted_info": extracted}
        else:
            db.update_job_clarification(job_id, INITIAL_QUESTIONS)
            return {"questions": INITIAL_QUESTIONS, "extracted_info": {}}
            
    except Exception as e:
        # Fall back to default questions
        db.update_job_clarification(job_id, INITIAL_QUESTIONS)
        return {"questions": INITIAL_QUESTIONS, "error": str(e)}


@app.post("/api/jobs/{job_id}/answers")
async def submit_answers(job_id: int, request: AnswerQuestionsRequest, background_tasks: BackgroundTasks):
    """Submit answers to clarifying questions and start research."""
    job = db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    
    questions = json.loads(job.get('clarifying_questions', '[]') or '[]')
    db.update_job_clarification(job_id, questions, request.answers)
    
    # Update stock symbols if provided in answers
    if request.answers.get('stocks'):
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE research_jobs SET stock_symbols = ? WHERE id = ?",
                      (request.answers['stocks'], job_id))
        conn.commit()
        conn.close()
    
    # Start the research pipeline in the background
    background_tasks.add_task(run_research_pipeline, job_id)
    
    return {"status": "research_started", "job_id": job_id}


@app.get("/api/jobs/{job_id}/stream")
async def stream_job_updates(job_id: int):
    """Stream real-time updates for a job via SSE."""
    queue = create_job_queue(job_id)
    
    async def event_generator():
        try:
            # Send initial state
            job = db.get_job(job_id)
            steps = db.get_steps_for_job(job_id)
            yield f"data: {json.dumps({'type': 'init', 'job': job, 'steps': steps})}\n\n"
            
            while True:
                try:
                    update = await asyncio.wait_for(queue.get(), timeout=30)
                    if update is None:
                        break
                    yield f"data: {json.dumps(update)}\n\n"
                    
                    # Check if job is complete
                    if update.get('type') in ('job_completed', 'job_failed'):
                        break
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            remove_job_queue(job_id, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@app.get("/api/jobs/{job_id}/report")
async def get_report(job_id: int):
    """Get the final report for a job."""
    report = db.get_report_for_job(job_id)
    if not report:
        return JSONResponse({"error": "Report not found"}, status_code=404)
    return {"report": report}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
