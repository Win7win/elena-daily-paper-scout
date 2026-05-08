from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
import os

import pdfplumber
import requests

from core.settings import HF_ENDPOINT, MINERU_TIMEOUT_SECONDS, TMP_DIR
from core.settings import MINERU_CUDA_VISIBLE_DEVICES


def download_pdf(url: str, paper_id: str) -> Path | None:
    """Download a PDF into a temporary workspace for parsing."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = TMP_DIR / f"{paper_id}.pdf"
    response = requests.get(url, headers={"User-Agent": "elena-arxiv-eater/0.1"}, timeout=60)
    response.raise_for_status()
    pdf_path.write_bytes(response.content)
    return pdf_path


def extract_text_with_pdfplumber(pdf_path: Path, max_pages: int = 8) -> str:
    """Extract raw text quickly for a lightweight PDF-assisted pass."""
    chunks: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages[:max_pages]:
            text = page.extract_text() or ""
            if text.strip():
                chunks.append(text)
    return "\n\n".join(chunks)


def parse_pdf_with_mineru(pdf_path: Path, paper_id: str, method: str = "txt") -> str | None:
    """Parse PDF with MinerU if available, otherwise return None."""
    mineru_path = shutil.which("mineru")
    if not mineru_path:
        return None

    out_dir = TMP_DIR / f"{paper_id}_mineru"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [mineru_path, "-p", str(pdf_path), "-o", str(out_dir), "-m", method, "-b", "pipeline"]
    env = os.environ.copy()
    env.setdefault("HF_ENDPOINT", HF_ENDPOINT)
    if MINERU_CUDA_VISIBLE_DEVICES:
        env["CUDA_VISIBLE_DEVICES"] = MINERU_CUDA_VISIBLE_DEVICES
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        timeout=MINERU_TIMEOUT_SECONDS,
        env=env,
    )

    md_files = sorted(out_dir.rglob("*.md"), key=lambda item: item.stat().st_size, reverse=True)
    if not md_files:
        return None
    return md_files[0].read_text(encoding="utf-8", errors="ignore")


def cleanup_temp_files(paper_id: str) -> None:
    """Remove temporary PDF and MinerU artifacts after archiving analysis."""
    pdf_path = TMP_DIR / f"{paper_id}.pdf"
    out_dir = TMP_DIR / f"{paper_id}_mineru"
    if pdf_path.exists():
        pdf_path.unlink()
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)


def run_mineru_warmup(input_path: Path, output_dir: Path, method: str = "txt") -> None:
    """Warm up MinerU models and runtime with an explicit sample input."""
    mineru_path = shutil.which("mineru")
    if not mineru_path:
        raise RuntimeError("mineru is not installed in the current environment")

    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [mineru_path, "-p", str(input_path), "-o", str(output_dir), "-m", method, "-b", "pipeline"]
    env = os.environ.copy()
    env.setdefault("HF_ENDPOINT", HF_ENDPOINT)
    if MINERU_CUDA_VISIBLE_DEVICES:
        env["CUDA_VISIBLE_DEVICES"] = MINERU_CUDA_VISIBLE_DEVICES
    subprocess.run(
        cmd,
        check=True,
        text=True,
        timeout=MINERU_TIMEOUT_SECONDS,
        env=env,
    )
