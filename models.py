from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from extensions import db
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_moderator = db.Column(db.Boolean, default=False)

    library_books = db.relationship(
        'UserLibrary',
        backref='library_user',
        lazy=True,
        cascade='all, delete-orphan'
    )
    reviews = db.relationship('Review', backref='review_user', lazy=True)

class Book(db.Model):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    cover_url = db.Column(db.String(255)) 
    isbn = db.Column(db.String(20)) 
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    library_entries = db.relationship(
        'UserLibrary',
        backref='library_book',
        lazy=True,
        cascade='all, delete-orphan'
    )
    book_reviews = db.relationship('Review', backref='review_book', lazy=True)


class Review(db.Model):
    __tablename__ = 'reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=True) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'))
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'book_id', name='_user_book_uc'),
    )

class UserLibrary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='reading')  # 'reading'/'finished'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'))