from app.main import app, init_db

if __name__ == "__main__":
    init_db()
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
