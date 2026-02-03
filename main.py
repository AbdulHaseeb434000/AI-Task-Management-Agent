from fastapi import FastAPI

app = FastAPI(title="AI Task Management Agent")


@app.get("/")
def root():
    return {"message": "Hello from ai-task-management-agent!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
