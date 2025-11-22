from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SpellingWord(Base):
    __tablename__ = "spelling_words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String, nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    difficulty = Column(Integer, default=1)
    pattern_hint = Column(String, nullable=True)
    missing_letter_mask = Column(String, nullable=True)
    definition = Column(Text, nullable=True)
    sample_sentence = Column(Text, nullable=True)
