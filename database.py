"""
SQLite database for research jobs and reports.
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from enum import Enum

DB_PATH = Path(__file__).parent / "research.db"


class JobStatus(str, Enum):
    PENDING = "pending"
    CLARIFYING = "clarifying"
    RESEARCHING = "researching"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"


def get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Research Jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            stock_symbols TEXT,
            user_query TEXT NOT NULL,
            clarifying_questions TEXT,
            user_answers TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT
        )
    """)
    
    # Research Steps table (for pipeline tracking)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            step_type TEXT NOT NULL,
            step_name TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            input_data TEXT,
            output_data TEXT,
            url TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            FOREIGN KEY (job_id) REFERENCES research_jobs (id)
        )
    """)
    
    # Final Reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL UNIQUE,
            title TEXT NOT NULL,
            summary TEXT,
            sentiment TEXT,
            recommendation TEXT,
            full_report TEXT,
            sources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES research_jobs (id)
        )
    """)
    
    conn.commit()
    conn.close()


# ============ Job Functions ============

def create_job(title: str, user_query: str, description: str = "", stock_symbols: str = "") -> int:
    """Create a new research job."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO research_jobs (title, description, stock_symbols, user_query, status)
        VALUES (?, ?, ?, ?, ?)
    """, (title, description, stock_symbols, user_query, JobStatus.PENDING.value))
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return job_id


def get_job(job_id: int) -> Optional[dict]:
    """Get a job by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_all_jobs() -> list:
    """Get all jobs ordered by creation date."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_jobs ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_job_status(job_id: int, status: JobStatus, error_message: str = None):
    """Update job status."""
    conn = get_connection()
    cursor = conn.cursor()
    
    updates = ["status = ?"]
    params = [status.value]
    
    if status == JobStatus.RESEARCHING:
        updates.append("started_at = ?")
        params.append(datetime.now().isoformat())
    elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
        updates.append("completed_at = ?")
        params.append(datetime.now().isoformat())
    
    if error_message:
        updates.append("error_message = ?")
        params.append(error_message)
    
    params.append(job_id)
    cursor.execute(f"UPDATE research_jobs SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def update_job_clarification(job_id: int, questions: list, answers: dict = None):
    """Update clarifying questions and answers."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if answers:
        cursor.execute("""
            UPDATE research_jobs 
            SET clarifying_questions = ?, user_answers = ?, status = ?
            WHERE id = ?
        """, (json.dumps(questions), json.dumps(answers), JobStatus.RESEARCHING.value, job_id))
    else:
        cursor.execute("""
            UPDATE research_jobs 
            SET clarifying_questions = ?, status = ?
            WHERE id = ?
        """, (json.dumps(questions), JobStatus.CLARIFYING.value, job_id))
    
    conn.commit()
    conn.close()


def delete_job(job_id: int):
    """Delete a job and its related data."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM research_steps WHERE job_id = ?", (job_id,))
    cursor.execute("DELETE FROM research_reports WHERE job_id = ?", (job_id,))
    cursor.execute("DELETE FROM research_jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


# ============ Step Functions ============

def create_step(job_id: int, step_type: str, step_name: str, url: str = None, input_data: str = None) -> int:
    """Create a new research step."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO research_steps (job_id, step_type, step_name, url, input_data, status, started_at)
        VALUES (?, ?, ?, ?, ?, 'running', ?)
    """, (job_id, step_type, step_name, url, input_data, datetime.now().isoformat()))
    step_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return step_id


def update_step(step_id: int, status: str, output_data: str = None, error_message: str = None):
    """Update a step's status and output."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE research_steps 
        SET status = ?, output_data = ?, completed_at = ?, error_message = ?
        WHERE id = ?
    """, (status, output_data, datetime.now().isoformat(), error_message, step_id))
    conn.commit()
    conn.close()


def get_steps_for_job(job_id: int) -> list:
    """Get all steps for a job."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_steps WHERE job_id = ? ORDER BY id", (job_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ============ Report Functions ============

def create_report(job_id: int, title: str, summary: str, sentiment: str, 
                  recommendation: str, full_report: str, sources: list) -> int:
    """Create a final research report."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO research_reports (job_id, title, summary, sentiment, recommendation, full_report, sources)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (job_id, title, summary, sentiment, recommendation, full_report, json.dumps(sources)))
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return report_id


def get_report_for_job(job_id: int) -> Optional[dict]:
    """Get the report for a job."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_reports WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        report = dict(row)
        if report.get('sources'):
            report['sources'] = json.loads(report['sources'])
        return report
    return None


# Initialize database on module load
init_db()
