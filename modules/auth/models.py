from extensions import db
from datetime import datetime

class users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    fullName = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def name(self):
        return self.fullName

    @name.setter
    def name(self, value):
        self.fullName = value

    def __repr__(self):
        return f"<User {self.fullName}>"