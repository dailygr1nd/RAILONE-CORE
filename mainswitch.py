# mainswitch.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from zk_sd import onboard_user, USED_IDS

app = FastAPI(title="RailOne Prototype API")

# --------------------------
# Request Models
# --------------------------
class OnboardRequest(BaseModel):
    name: str
    nid: str
    role: str

# --------------------------
# Onboarding Endpoint
# --------------------------
@app.post("/onboard")
def onboard_user_api(req: OnboardRequest):
    if req.nid in USED_IDS:
        raise HTTPException(status_code=400, detail="ID already onboarded this session")

    user_data = onboard_user(req.role)
    if not user_data:
        raise HTTPException(status_code=400, detail="Failed to onboard user")

    # Truncate RailOneID for client display
    user_data["railone_id"] = user_data["identity_token"][:12]

    return {
        "username": user_data["username"],
        "railone_id": user_data["railone_id"],
        "kyc_level": user_data["attestation"]["kyc_level"],
        "zk_proof": user_data["zk_proof"],
        "accounts": user_data["accounts"]
    }

# --------------------------
# Health Check / Test
# --------------------------
@app.get("/ping")
def ping():
    return {"status": "alive"}