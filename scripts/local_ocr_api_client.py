#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import uuid
from http.client import RemoteDisconnected
from urllib import error, parse, request


def _http_json(url: str, payload: dict, timeout: float) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw_error": raw}
        return exc.code, parsed


def _build_multipart(image_path: str, top_k: int) -> tuple[bytes, str]:
    boundary = f"----ocr-client-{uuid.uuid4().hex}"
    ctype = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
    filename = os.path.basename(image_path)
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    parts: list[bytes] = []
    parts.append(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="top_k"\r\n\r\n'
            f"{top_k}\r\n"
        ).encode("utf-8")
    )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode("utf-8")
        + image_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    return body, boundary


def _http_ocr(url: str, token: str, image_path: str, top_k: int, timeout: float) -> tuple[int, str]:
    body, boundary = _build_multipart(image_path, top_k)
    req = request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (RemoteDisconnected, error.URLError, TimeoutError) as exc:
        return 0, f"Connection failure before response headers: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Local OCR API client for /api/uploads/ocr-search/")
    parser.add_argument("--base-url", default="http://46.101.108.29:8000", help="API host root URL")
    parser.add_argument("--username", default="seed_patient_1", help="JWT login username")
    parser.add_argument("--password", default="StrongPass123!", help="JWT login password")
    parser.add_argument("--image", default="sample_medicine.png", help="Path to image file")
    parser.add_argument("--top-k", type=int, default=5, help="OCR top_k value")
    parser.add_argument("--timeout", type=float, default=90.0, help="Request timeout in seconds")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Image not found: {args.image}", file=sys.stderr)
        return 2

    base = args.base_url.rstrip("/")
    token_url = parse.urljoin(base + "/", "api/auth/token/")
    ocr_url = parse.urljoin(base + "/", "api/uploads/ocr-search/")

    status, token_payload = _http_json(
        token_url,
        {"username": args.username, "password": args.password},
        timeout=args.timeout,
    )
    print(f"[auth] {status} {token_url}")
    if status != 200:
        print(json.dumps(token_payload, indent=2, ensure_ascii=False))
        return 1

    access = token_payload.get("access")
    if not access:
        print("Auth succeeded but no access token in response.", file=sys.stderr)
        print(json.dumps(token_payload, indent=2, ensure_ascii=False))
        return 1

    status, body = _http_ocr(
        ocr_url,
        token=access,
        image_path=args.image,
        top_k=args.top_k,
        timeout=args.timeout,
    )
    print(f"[ocr] {status} {ocr_url}")
    print(body)
    return 0 if status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
