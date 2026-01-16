from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from interpreter import interpreter
import json
import time

interpreter.auto_run = True
interpreter.llm.model = "azure/gpt-4.1"

app = FastAPI()

@app.get("/")
def root():
    interpreter.messages = []
    return FileResponse("index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/set-instructions")
def set_instructions(instructions: str = ""):
    interpreter.custom_instructions = instructions
    return {"status": "success", "instructions": instructions}

@app.get("/chat")
def chat_endpoint(msg: str):
    def event_stream():
        for result in interpreter.chat(msg, stream=True):
            yield f"data: {json.dumps(result)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/history")
def history_endpoint():
    return interpreter.messages

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)