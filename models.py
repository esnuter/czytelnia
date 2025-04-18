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
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)

    library_books = db.relationship('UserLibrary', back_populates='user')
    shelves = db.relationship('Shelf', back_populates='user', lazy='dynamic')
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
    pages = db.Column(db.Integer, nullable=True)

    library_entries = db.relationship('UserLibrary', back_populates='book')
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
    __tablename__ = 'user_library'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'))
    shelf_id = db.Column(db.Integer, db.ForeignKey('shelves.id'))  
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    book = db.relationship('Book', back_populates='library_entries')
    shelf = db.relationship('Shelf', back_populates='books')
    user = db.relationship('User', back_populates='library_books')

class Genre(db.Model):
    __tablename__ = 'genres'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    books = db.relationship('Book', secondary='book_genres', backref=db.backref('genres', lazy=True))

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    books = db.relationship('Book', secondary='book_tags', backref=db.backref('tags', lazy=True))

class Shelf(db.Model):
    __tablename__ = 'shelves'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(50), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='shelves')
    books = db.relationship('UserLibrary', back_populates='shelf')

book_genres = db.Table('book_genres',
    db.Column('book_id', db.Integer, db.ForeignKey('books.id'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id'), primary_key=True)
)

book_tags = db.Table('book_tags',
    db.Column('book_id', db.Integer, db.ForeignKey('books.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)