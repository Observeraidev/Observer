RISK_MATRIX = {
    "systemd.status": "LOW",
    "fs.read": "LOW",
    "db.query": "MEDIUM",
    "fs.write": "HIGH",
    "systemd.restart": "HIGH",
}

def get_risk(op_type: str) -> str:
    return RISK_MATRIX.get(op_type, "MEDIUM")
