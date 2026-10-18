"""
Reference Pattern: Asynchronous Bulk Report Processing & LLM Remark Generation
Demonstrates how EduSleek offloads heavy I/O and Groq API calls to Celery/Redis
to prevent HTTP timeouts during peak end-of-term grading periods.
"""

import logging
import os
import requests
from typing import Dict, Any
from celery import shared_task
from django.db import transaction

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


@shared_task(
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def generate_ai_student_remark_task(self, student_summary: Dict[str, Any]) -> Dict[str, str]:
    """
    Asynchronously generates a personalized report-card remark using the Groq LLM API
    based on structured academic performance metrics.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY is missing in environment configuration.")
        return {"status": "skipped", "remark": ""}

    prompt = (
        f"Write a concise, encouraging 2-sentence termly report card remark for a student. "
        f"Average Score: {student_summary.get('average_score')}%. "
        f"Strongest Subject: {student_summary.get('best_subject')}. "
        f"Area for Growth: {student_summary.get('weakest_subject')}. "
        f"Attendance: {student_summary.get('attendance_rate')}%."
    )

    response = requests.post(
        GROQ_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are an experienced school principal writing official academic remarks."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 120,
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    remark_text = data["choices"][0]["message"]["content"].strip()

    # In production, persist atomically to the tenant's student report record
    with transaction.atomic():
        logger.info("Successfully generated AI remark for student ID %s", student_summary.get("student_id"))

    return {"status": "completed", "remark": remark_text}
