from fastapi import APIRouter, HTTPException, Query as FastAPIQuery
from pydantic import BaseModel
from typing import Optional
from tinydb import TinyDB, Query as TinyDBQuery
import time
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import io
from fastapi.responses import StreamingResponse, FileResponse
from datetime import datetime


router = APIRouter()

db = TinyDB('db.json')
ExamTable = db.table('exam')

class ExamSession(BaseModel):
    email: str
    exam_id: str
    timestamp: int
    session_id: str

class ExamResultRequest(BaseModel):
    email: str
    exam_id: str
    score: float
    cheat_score: float
    passed: bool
    details: Optional[dict] = None

class ExamInitRequest(BaseModel):
    email: str
    exam_id: str

@router.post("/init_exam")
def init_exam(request: ExamInitRequest):
    session_id = f"{request.email}-{request.exam_id}-{int(time.time())}"
    exam_session = ExamSession(
        email=request.email,
        exam_id=request.exam_id,
        timestamp=int(time.time()),
        session_id=session_id
    )
    ExamTable.insert(exam_session.dict())
    return {"session_id": session_id}

@router.post("/update_exam")
def update_exam(request: ExamResultRequest):
    Exam = TinyDBQuery()
    existing_exam = ExamTable.search((Exam.email == request.email) & (Exam.exam_id == request.exam_id))
    if not existing_exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    ExamTable.update(request.dict(), (Exam.email == request.email) & (Exam.exam_id == request.exam_id))
    return {"message": "Exam updated"}

@router.get("/get_last_exam/{email}")
def get_last_exam(email: str):
    Exam = TinyDBQuery()
    last_exam = sorted(ExamTable.search(Exam.email == email), key=lambda x: x['timestamp'], reverse=True)
    if not last_exam:
        raise HTTPException(status_code=404, detail="No exams found")
    return last_exam[0]

@router.get("/get_result")
def get_result(email: str = FastAPIQuery(None)):
    Exam = TinyDBQuery()
    result = ExamTable.search(Exam.email == email)
    # Return the result (even if empty) rather than raising an error
    return result


@router.get("/get_last_exam_global")
def get_last_exam_global():
    all_exams = ExamTable.all()
    if not all_exams:
        raise HTTPException(status_code=404, detail="No exams found")
    last_exam = max(all_exams, key=lambda x: x['timestamp'])
    return last_exam


@router.get("/last-exam-pdf", response_class=FileResponse)
async def get_last_exam_pdf():
    """Retrieve the last exam results as a professionally formatted PDF."""
    all_exams = ExamTable.all()
    if not all_exams:
        raise HTTPException(status_code=404, detail="No exams found")

    last_exam = max(all_exams, key=lambda x: x['timestamp'])
    timestamp = datetime.fromtimestamp(last_exam['timestamp']).strftime("%d/%m/%Y %H:%M")

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)

    # Styled title with rose color
    can.setFont("Helvetica-Bold", 22)
    can.setFillColorRGB(0.9, 0.4, 0.6)  # Rose color
    can.drawCentredString(4.25 * inch, 10 * inch, "🔬 Examination Results Report")
    can.setFillColor(colors.black)  # Reset to black for other text

    # Decorative separator line in rose color
    can.setStrokeColorRGB(0.9, 0.4, 0.6)
    can.setLineWidth(1.5)
    can.line(1 * inch, 9.7 * inch, 7.5 * inch, 9.7 * inch)

    # Exam information section
    can.setFont("Helvetica", 12)
    y_position = 9.4 * inch
    line_spacing = 0.35 * inch

    exam_details = [
        f"Email:          {last_exam['email']}",
        f"Exam ID:        {last_exam['exam_id']}",
        f"Session ID:     {last_exam['session_id']}",
        f"Date/Time:      {timestamp}",
        f"Score:          33 / 100"
    ]

    # Draw each line of information
    for detail in exam_details:
        can.drawString(1 * inch, y_position, detail)
        y_position -= line_spacing

    # Add a professional footer
    can.setFont("Helvetica-Oblique", 8)
    can.drawString(1 * inch, 0.5 * inch, "Confidential Report - Generated by ExamSystem Pro")

    can.save()
    packet.seek(0)
    return StreamingResponse(packet, media_type="application/pdf")