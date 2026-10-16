"""
Seed script to populate initial speech therapy practice and assessment sentences into the database.
Usage: python scripts/seed_database.py
"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app
from extensions import db
from modules.sentences.models import Sentence

DEFAULT_SENTENCES = [
    {
        "text": "The red rabbit ran around the river.",
        "source_type": "assessment",
        "difficulty": "easy",
        "phonemes": ["DH", "AH", "R", "EH", "D", "R", "AE", "B", "AH", "T", "R", "AE", "N", "ER", "AW", "N", "D", "DH", "AH", "R", "IH", "V", "ER"]
    },
    {
        "text": "She sells thick shells on the seashore.",
        "source_type": "practice",
        "difficulty": "medium",
        "phonemes": ["SH", "IY", "S", "EH", "L", "Z", "TH", "IH", "K", "SH", "EH", "L", "Z", "AA", "N", "DH", "AH", "S", "IY", "SH", "AO", "R"]
    },
    {
        "text": "They think these things are easy to say.",
        "source_type": "practice",
        "difficulty": "medium",
        "phonemes": ["DH", "EY", "TH", "IH", "NG", "K", "DH", "IY", "Z", "TH", "IH", "NG", "Z", "AA", "R", "IY", "Z", "IY", "T", "UW", "S", "EY"]
    },
    {
        "text": "Please bring the blue glass bottle to the table.",
        "source_type": "assessment",
        "difficulty": "easy",
        "phonemes": ["P", "L", "IY", "Z", "B", "R", "IH", "NG", "DH", "AH", "B", "L", "UW", "G", "L", "AE", "S", "B", "AA", "T", "AH", "L", "T", "UW", "DH", "AH", "T", "EY", "B", "AH", "L"]
    },
    {
        "text": "The quick brown fox jumps over the lazy dog.",
        "source_type": "assessment",
        "difficulty": "easy",
        "phonemes": ["DH", "AH", "K", "W", "IH", "K", "B", "R", "AW", "N", "F", "AA", "K", "S", "JH", "AH", "M", "P", "S", "OW", "V", "ER", "DH", "AH", "L", "EY", "Z", "IY", "D", "AO", "G"]
    },
    {
        "text": "Peter Piper picked a peck of pickled peppers.",
        "source_type": "practice",
        "difficulty": "hard",
        "phonemes": ["P", "IY", "T", "ER", "P", "AY", "P", "ER", "P", "IH", "K", "T", "AH", "P", "EH", "K", "AH", "V", "P", "IH", "K", "AH", "L", "D", "P", "EH", "P", "ER", "Z"]
    },
    {
        "text": "We usually watch television every evening.",
        "source_type": "practice",
        "difficulty": "medium",
        "phonemes": ["W", "IY", "Y", "UW", "ZH", "AH", "L", "IY", "W", "AA", "CH", "T", "EH", "L", "AH", "V", "IH", "ZH", "AH", "N", "EH", "V", "R", "IY", "IY", "V", "N", "IH", "NG"]
    },
    {
        "text": "This zebra lives in a very large and busy zoo.",
        "source_type": "practice",
        "difficulty": "hard",
        "phonemes": ["DH", "IH", "S", "Z", "IY", "B", "R", "AH", "L", "IH", "V", "Z", "IH", "N", "AH", "V", "EH", "R", "IY", "L", "AA", "R", "JH", "AE", "N", "D", "B", "IH", "Z", "IY", "Z", "UW"]
    }
]


def seed():
    app = create_app()
    with app.app_context():
        db.create_all()
        print(f"Checking existing sentences in database...")
        existing_count = Sentence.query.count()
        print(f"Found {existing_count} existing sentences.")

        added = 0
        for item in DEFAULT_SENTENCES:
            exists = Sentence.query.filter_by(text=item["text"]).first()
            if not exists:
                sentence = Sentence(
                    text=item["text"],
                    source_type=item["source_type"],
                    difficulty=item["difficulty"],
                    phonemes=item["phonemes"]
                )
                db.session.add(sentence)
                added += 1

        if added > 0:
            db.session.commit()
            print(f"Successfully seeded {added} new sentences.")
        else:
            print("All default sentences already exist.")

        print(f"Total sentences in database: {Sentence.query.count()}")


if __name__ == "__main__":
    seed()
