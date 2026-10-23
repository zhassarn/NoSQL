import os
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = MongoClient(MONGO_URL)
db = client["users_db"]
users = db["users"]
users.create_index("email", unique=True)

app = FastAPI(title="Users CRUD API")

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    registered_at: datetime


def to_out(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


def parse_id(user_id: str) -> ObjectId:
    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID форматы дұрыс емес")


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    doc = user.model_dump()
    doc["registered_at"] = datetime.now(timezone.utc)
    try:
        result = users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Бұл email бұрыннан бар")
    return to_out(users.find_one({"_id": result.inserted_id}))

@app.get("/users", response_model=list[UserOut])
def list_users():
    return [to_out(d) for d in users.find()]



@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: str):
    doc = users.find_one({"_id": parse_id(user_id)})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пайдаланушы табылмады")
    return to_out(doc)


@app.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, data: UserUpdate):
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Жаңартатын өріс берілмеген")
    try:
        doc = users.find_one_and_update(
            {"_id": parse_id(user_id)},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Бұл email бұрыннан бар")
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пайдаланушы табылмады")
    return to_out(doc)


@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    result = users.delete_one({"_id": parse_id(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пайдаланушы табылмады")
    return {"message": "Пайдаланушы жойылды"}
