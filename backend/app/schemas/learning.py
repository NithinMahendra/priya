from pydantic import BaseModel, Field


class QuizGenerateRequest(BaseModel):
    concept: str | None = Field(default=None, min_length=2, max_length=120)
    submission_id: int | None = Field(default=None, ge=1)


class QuizQuestion(BaseModel):
    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: int = Field(ge=0, le=3)
    explanation: str


class QuizGenerateResponse(BaseModel):
    concept: str
    source: str
    questions: list[QuizQuestion] = Field(min_length=3, max_length=3)


class QuizSubmitRequest(BaseModel):
    score: int = Field(ge=0)
    total: int = Field(gt=0)


class QuizSubmitResponse(BaseModel):
    score: int
    total: int
    quiz_score: int
