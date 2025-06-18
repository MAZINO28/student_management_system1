from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import logging

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client.student_management

# Logging
logging.basicConfig(level=logging.DEBUG)

# Pydantic models
class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    type: str = "student"

class Student(StudentCreate):
    id: str

class SubjectCreate(BaseModel):
    subject_name: str
    type: str = "subject"

class Subject(SubjectCreate):
    id: str

class GradeCreate(BaseModel):
    student_id: str
    subject_id: str
    activity_grade: float
    quiz_grade: float
    exam_grade: float
    type: str = "grade"

class Grade(GradeCreate):
    id: str
    subject: Subject

# Helper functions
def document_helper(doc) -> dict:
    return {
        "id": str(doc["_id"]),
        "first_name": doc.get("first_name"),
        "last_name": doc.get("last_name"),
        "email": doc.get("email"),
        "subject_name": doc.get("subject_name"),
        "student_id": doc.get("student_id"),
        "subject_id": doc.get("subject_id"),
        "activity_grade": doc.get("activity_grade"),
        "quiz_grade": doc.get("quiz_grade"),
        "exam_grade": doc.get("exam_grade"),
        "type": doc.get("type"),
    }

def grade_helper(grade, subject) -> dict:
    return {
        "id": str(grade["_id"]),
        "student_id": str(grade["student_id"]),
        "subject_id": str(grade["subject_id"]),
        "activity_grade": grade["activity_grade"],
        "quiz_grade": grade["quiz_grade"],
        "exam_grade": grade["exam_grade"],
        "subject": document_helper(subject) if subject else None,
    }

# Student CRUD
@app.post("/api/students", response_model=Student)
async def create_student(student: StudentCreate):
    try:
        student_dict = student.dict()
        result = await db.student_management.insert_one(student_dict)
        return {**student_dict, "id": str(result.inserted_id)}
    except Exception as e:
        logging.error(f"Error in create_student: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/api/students", response_model=List[Student])
async def get_students():
    try:
        students = []
        async for doc in db.student_management.find({"type": "student"}):
            students.append(document_helper(doc))
        logging.debug(f"Retrieved {len(students)} students")
        return students
    except Exception as e:
        logging.error(f"Error in get_students: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.put("/api/students/{id}", response_model=Student)
async def update_student(id: str, student: StudentCreate):
    try:
        result = await db.student_management.update_one(
            {"_id": ObjectId(id), "type": "student"},
            {"$set": student.dict()}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Student not found")
        updated_doc = await db.student_management.find_one({"_id": ObjectId(id)})
        return document_helper(updated_doc)
    except Exception as e:
        logging.error(f"Error in update_student: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.delete("/api/students/{id}")
async def delete_student(id: str):
    try:
        result = await db.student_management.delete_one({"_id": ObjectId(id), "type": "student"})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Student not found")
        await db.student_management.delete_many({"student_id": ObjectId(id), "type": "grade"})
        return {"message": "Student deleted"}
    except Exception as e:
        logging.error(f"Error in delete_student: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid student ID or server error: {str(e)}")

# Subject CRUD
@app.post("/api/subjects", response_model=Subject)
async def create_subject(subject: SubjectCreate):
    try:
        subject_dict = subject.dict()
        result = await db.student_management.insert_one(subject_dict)
        return {**subject_dict, "id": str(result.inserted_id)}
    except Exception as e:
        logging.error(f"Error in create_subject: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/api/subjects", response_model=List[Subject])
async def get_subjects():
    try:
        subjects = []
        async for doc in db.student_management.find({"type": "subject"}):
            subjects.append(document_helper(doc))
        logging.debug(f"Retrieved {len(subjects)} subjects")
        return subjects
    except Exception as e:
        logging.error(f"Error in get_subjects: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# Grade CRUD
@app.post("/api/grades", response_model=Grade)
async def create_grade(grade: GradeCreate):
    try:
        student = await db.student_management.find_one({"_id": ObjectId(grade.student_id), "type": "student"})
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        subject = await db.student_management.find_one({"_id": ObjectId(grade.subject_id), "type": "subject"})
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        
        existing_grade = await db.student_management.find_one({
            "student_id": ObjectId(grade.student_id),
            "subject_id": ObjectId(grade.subject_id),
            "type": "grade"
        })
        if existing_grade:
            raise HTTPException(status_code=400, detail="Grade already exists for this student and subject")

        grade_dict = grade.dict()
        grade_dict["student_id"] = ObjectId(grade.student_id)
        grade_dict["subject_id"] = ObjectId(grade.subject_id)
        result = await db.student_management.insert_one(grade_dict)
        return grade_helper({**grade_dict, "_id": result.inserted_id}, subject)
    except Exception as e:
        logging.error(f"Error in create_grade: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid ID or server error: {str(e)}")

@app.get("/api/grades", response_model=List[Grade])
async def get_grades(student_id: Optional[str] = None):
    try:
        grades = []
        query = {"type": "grade", "student_id": ObjectId(student_id)} if student_id else {"type": "grade"}
        async for grade in db.student_management.find(query):
            subject = await db.student_management.find_one({"_id": grade["subject_id"], "type": "subject"})
            if subject:
                grades.append(grade_helper(grade, subject))
        return grades
    except Exception as e:
        logging.error(f"Error in get_grades: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.put("/api/grades/{id}", response_model=Grade)
async def update_grade(id: str, grade: GradeCreate):
    try:
        existing_grade = await db.student_management.find_one({"_id": ObjectId(id), "type": "grade"})
        if not existing_grade:
            raise HTTPException(status_code=404, detail="Grade not found")
        
        student = await db.student_management.find_one({"_id": ObjectId(grade.student_id), "type": "student"})
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        subject = await db.student_management.find_one({"_id": existing_grade["subject_id"], "type": "subject"})
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        grade_dict = grade.dict()
        grade_dict["student_id"] = ObjectId(grade.student_id)
        grade_dict["subject_id"] = existing_grade["subject_id"]
        result = await db.student_management.update_one(
            {"_id": ObjectId(id)},
            {"$set": grade_dict}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update grade")
        updated_grade = await db.student_management.find_one({"_id": ObjectId(id)})
        return grade_helper(updated_grade, subject)
    except Exception as e:
        logging.error(f"Error in update_grade: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.delete("/api/grades/{id}")
async def delete_grade(id: str):
    try:
        result = await db.student_management.delete_one({"_id": ObjectId(id), "type": "grade"})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Grade not found")
        return {"message": "Grade deleted"}
    except Exception as e:
        logging.error(f"Error in delete_grade: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid grade ID or server error: {str(e)}")