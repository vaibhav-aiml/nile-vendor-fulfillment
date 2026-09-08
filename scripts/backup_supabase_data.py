import sys
import os
import json
from datetime import datetime, timezone
from decimal import Decimal
import uuid

sys.path.insert(0, os.getcwd())
from app.core.database import engine
from sqlalchemy import text

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime,)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)

def backup_data():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.getcwd(), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    with engine.connect() as conn:
        for table in ["fulfillment_requests", "vendors"]:
            rows = conn.execute(text(f"SELECT * FROM {table}")).mappings().all()
            data = [dict(r) for r in rows]
            
            json_file = os.path.join(backup_dir, f"{table}_{timestamp}.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, cls=CustomEncoder)
            
            print(f"Backed up {len(data)} rows from '{table}' to {json_file}")
            
    print("Backup complete!")

if __name__ == "__main__":
    backup_data()
