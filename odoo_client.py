import base64
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class OdooConfig:
    url: str
    db: str
    username: str
    password: str
    auth_token: Optional[str] = None
    folder_path: Optional[str] = None
    parent_id: Optional[int] = None
    verify_ssl: bool = True

    @classmethod
    def from_env(cls):
        url = os.getenv("ODOO_URL")
        db = os.getenv("ODOO_DB")
        username = os.getenv("ODOO_USERNAME")
        password = os.getenv("ODOO_PASSWORD")
        auth_token = os.getenv("ODOO_AUTH_TOKEN")
        folder_path = os.getenv("ODOO_FOLDER_PATH")
        parent_id_raw = os.getenv("ODOO_PARENT_ID")
        parent_id = int(parent_id_raw) if parent_id_raw else None
        verify_ssl = os.getenv("ODOO_VERIFY_SSL", "true").lower() != "false"

        missing = [k for k, v in {
            "ODOO_URL": url,
            "ODOO_DB": db,
            "ODOO_USERNAME": username,
            "ODOO_PASSWORD": password,
        }.items() if not v]
        if missing:
            raise ValueError(f"Missing required Odoo config env vars: {', '.join(missing)}")

        return cls(
            url=url.rstrip("/"),
            db=db,
            username=username,
            password=password,
            auth_token=auth_token,
            folder_path=folder_path,
            parent_id=parent_id,
            verify_ssl=verify_ssl,
        )


class OdooClient:
    def __init__(self, config: OdooConfig):
        self.config = config
        self.session = requests.Session()
        if config.auth_token:
            self.session.headers.update({"Authorization": f"Bearer {config.auth_token}"})

    def authenticate(self):
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": self.config.db,
                "login": self.config.username,
                "password": self.config.password,
            },
            "id": 1,
        }
        resp = self.session.post(f"{self.config.url}/web/session/authenticate", json=payload, verify=self.config.verify_ssl)
        resp.raise_for_status()
        data = resp.json()
        # Odoo returns session in result; mock service mirrors this
        return data.get("result", {})

    def upload_attachment(self, name: str, file_bytes: bytes, mimetype: str = "application/pdf") -> Any:
        b64 = base64.b64encode(file_bytes).decode("ascii")
        vals = {
            "name": name,
            "datas": b64,
            "mimetype": mimetype,
            "type": "binary",
        }
        if self.config.folder_path:
            vals["folder_path"] = self.config.folder_path
        if self.config.parent_id is not None:
            vals["parent_id"] = self.config.parent_id

        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "ir.attachment",
                "method": "create",
                "args": [vals],
                "kwargs": {},
                "context": {},
            },
            "id": 1,
        }
        resp = self.session.post(f"{self.config.url}/web/dataset/call_kw", json=payload, verify=self.config.verify_ssl)
        resp.raise_for_status()
        return resp.json().get("result")


def upload_pdfs_to_odoo(quantity_path: str, price_path: str):
    config = OdooConfig.from_env()
    client = OdooClient(config)

    print("Authenticating with Odoo...")
    client.authenticate()

    def _retry(func, attempts=3, delay=1.5):
        last_err = None
        for i in range(attempts):
            try:
                return func()
            except Exception as exc:  # noqa: BLE001 keep broad for retries
                last_err = exc
                print(f"Attempt {i + 1}/{attempts} failed: {exc}")
                time.sleep(delay)
        raise last_err

    with open(quantity_path, "rb") as f:
        qty_bytes = f.read()
    with open(price_path, "rb") as f:
        price_bytes = f.read()

    print("Uploading quantity PDF to Odoo...")
    qty_result = _retry(lambda: client.upload_attachment("roof_scope_quantity.pdf", qty_bytes))
    print(f"Quantity PDF upload result: {qty_result}")

    print("Uploading price PDF to Odoo...")
    price_result = _retry(lambda: client.upload_attachment("roof_scope_price.pdf", price_bytes))
    print(f"Price PDF upload result: {price_result}")

    return {"quantity": qty_result, "price": price_result}


def ping_odoo():
    config = OdooConfig.from_env()
    client = OdooClient(config)
    print("Pinging Odoo (auth only)...")
    return client.authenticate()
