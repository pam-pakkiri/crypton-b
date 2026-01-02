import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Algo Trade Bot API")

# Determine if we are running in production (set PRODUCTION=1 in env)
IS_PRODUCTION = os.getenv("PRODUCTION", "0") == "1"

# CORS origins – allow only the production domain when in prod, otherwise allow local dev URLs
if IS_PRODUCTION:
    origins = ["https://crypton0.com"]
else:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "online", "message": "Algo Trade Bot API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
