import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from copilot import CopilotClient, PermissionHandler
from contextlib import asynccontextmanager

async def create_session(app):
    """Create a new Copilot session and register the event handler."""
    loop = asyncio.get_event_loop()
    session_config = {"model": "claude-sonnet-4.6", "streaming": True, "on_permission_request": PermissionHandler.approve_all}
    instructions = getattr(app.state, "custom_instructions", "")
    if instructions:
        session_config["system_message"] = {"mode": "append", "content": instructions}
    session = await app.state.copilot_client.create_session(session_config)
    app.state.session = session

    def on_event(event):
        event_type = event.type.value
        q = app.state.active_queue
        if q is None:
            return
        if event_type == "assistant.reasoning_delta":
            delta = event.data.delta_content or ""
            loop.call_soon_threadsafe(q.put_nowait, {"type": "reasoning", "content": delta})
        elif event_type == "assistant.reasoning":
            loop.call_soon_threadsafe(q.put_nowait, {"type": "reasoning", "block_end": True})
        elif event_type == "assistant.message_delta":
            delta = event.data.delta_content or ""
            loop.call_soon_threadsafe(q.put_nowait, {"type": "message", "content": delta})
        elif event_type == "assistant.message":
            loop.call_soon_threadsafe(q.put_nowait, {"type": "message", "block_end": True})
        elif event_type == "tool.execution_start":
            d = event.data
            tool = getattr(d, 'tool_name', None) or getattr(d, 'mcp_tool_name', None) or '?'
            args = getattr(d, 'arguments', None)
            args_str = str(args)[:300] if args else ""
            tool_call_id = getattr(d, 'tool_call_id', None) or tool
            loop.call_soon_threadsafe(q.put_nowait, {"type": "tool_start", "tool": tool, "args": args_str, "id": tool_call_id})
        elif event_type == "tool.execution_complete":
            d = event.data
            tool = getattr(d, 'tool_name', None) or getattr(d, 'mcp_tool_name', None) or '?'
            tool_call_id = getattr(d, 'tool_call_id', None) or tool
            result = getattr(d, 'result', None)
            result_str = str(result) if result is not None else None
            loop.call_soon_threadsafe(q.put_nowait, {"type": "tool_end", "tool": tool, "id": tool_call_id, "result": result_str})
        elif event_type == "session.idle":
            loop.call_soon_threadsafe(q.put_nowait, None)

    session.on(on_event)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.copilot_client = CopilotClient()
    app.state.custom_instructions = ""
    app.state.active_queue = None
    app.state.chat_lock = asyncio.Lock()
    await app.state.copilot_client.start()
    await create_session(app)

    yield

    # Shutdown
    await app.state.session.destroy()
    await app.state.copilot_client.stop()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return FileResponse(
        "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )

@app.get("/set-instructions")
async def set_instructions(instructions: str, request: Request):
    async with request.app.state.chat_lock:
        request.app.state.custom_instructions = instructions
        old_session = request.app.state.session
        request.app.state.active_queue = None
        try:
            await old_session.destroy()
        except Exception:
            pass
        await create_session(request.app)
    return {"status": "ok"}

@app.get("/stop")
async def stop_endpoint(request: Request):
    session = request.app.state.session
    await session.abort()
    q = request.app.state.active_queue
    if q:
        q.put_nowait(None)
    return {"status": "aborted"}

@app.get("/chat")
async def chat_endpoint(msg: str, request: Request):
    session = request.app.state.session
    queue: asyncio.Queue = asyncio.Queue()

    async def event_generator():
        async with request.app.state.chat_lock:
            request.app.state.active_queue = queue
            try:
                # Notify frontend that a message is starting
                yield f"data: {json.dumps({'type': 'message', 'start': True})}\n\n"

                send_args: dict = {"prompt": msg}
                await session.send(send_args)

                # Stream deltas as they arrive (None sentinel signals end)
                while True:
                    chunk = await queue.get()
                    if chunk is None:
                        break
                    yield f"data: {json.dumps(chunk)}\n\n"

                # Notify frontend that message ended
                yield f"data: {json.dumps({'type': 'message', 'end': True})}\n\n"

            finally:
                request.app.state.active_queue = None

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
