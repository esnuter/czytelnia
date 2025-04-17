from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory, jsonify, abort
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, SelectMultipleField
from wtforms.validators import DataRequired, Length, ValidationError, Optional
from extensions import db, login_manager, bcrypt
from models import *
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField
from sqlalchemy import and_, or_, func
import os
from werkzeug.utils import secure_filename
from PIL import Image
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tajny-klucz-123'  # 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///czytelnia.db'

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# files
app.config['UPLOAD_FOLDER'] = 'static/uploads/covers'
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png'}
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB limit

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Forms
class RegisterForm(FlaskForm):
    username = StringField('Nazwa użytkownika', validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField('Hasło', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Zarejestruj się')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Nazwa użytkownika zajęta!')

class LoginForm(FlaskForm):
    username = StringField('Nazwa użytkownika', validators=[DataRequired()])
    password = PasswordField('Hasło', validators=[DataRequired()])
    submit = SubmitField('Zaloguj się')

class BookForm(FlaskForm):
    title = StringField('Tytuł', validators=[DataRequired()])
    author = StringField('Autor', validators=[DataRequired()])
    description = TextAreaField('Opis')
    genres = SelectMultipleField(
        'Gatunki',
        coerce=int,
        choices=[],
        render_kw={"class": "select2-multiple", "data-placeholder": "Wybierz gatunki..."}
    )
    tags = StringField(
        'Tagi (oddziel przecinkami)',
        validators=[Optional()],
        render_kw={"placeholder": "np. klasyka, dystopia, nagroda nobla"}
    )
    isbn = StringField('ISBN')
    cover = FileField('Okładka książki', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Tylko obrazy JPG/PNG!')
    ])
    submit = SubmitField('Dodaj książkę')

class ReviewForm(FlaskForm):
    rating = SelectField(
      'Ocena', 
      choices=[(1, '1 ★'), (2, '2 ★'), (3, '3 ★'), (4, '4 ★'), (5, '5 ★')],
      coerce=int, 
      validators=[DataRequired(message="Wybierz ocenę")]
    )
    text = TextAreaField(
        'Recenzja',
        validators=[
            DataRequired(message="Recenzja nie może być pusta"),
            Length(min=10, max=1000, message="Recenzja powinna mieć od 10 do 1000 znaków")
        ]
    )
    submit = SubmitField('Dodaj recenzję')

class GenreForm(FlaskForm):
    name = StringField('Nazwa gatunku', validators=[DataRequired(), Length(max=50)])
    submit = SubmitField('Zapisz')

    def validate_name(self, field):
        if Genre.query.filter(func.lower(Genre.name) == func.lower(field.data)).first():
            raise ValidationError('Gatunek o tej nazwie już istnieje')

# Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, password=hashed_password)
        default_shelves = [
            ('Do przeczytania', True),
            ('W trakcie czytania', True),
            ('Przeczytane', True),
            ('Ulubione', False)
        ]

        for name, is_default in default_shelves:
            shelf = Shelf(
                user_id=user.id,
                name=name,
                is_default=is_default
            )
            db.session.add(shelf)

        db.session.add(user)
        db.session.commit()
        flash('Konto stworzone! Możesz się zalogować.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('home'))  #
        else:
            flash('Błędna nazwa użytkownika lub hasło!', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
def home():
    # newest books
    newest_books = Book.query.order_by(Book.date_added.desc()).limit(6).all()
    
    # top rated
    top_rated = db.session.query(
        Book,
        db.func.avg(Review.rating).label('average_rating'),
        db.func.count(Review.id).label('review_count')
    ).outerjoin(Review).group_by(Book.id).order_by(
        db.desc('average_rating')
    ).limit(6).all()
    
    top_rated_books = []
    for book, avg_rating, review_count in top_rated:
        book.average_rating = avg_rating or 0
        book.review_count = review_count
        top_rated_books.append(book)
    
    # recommended books
    recommended_books = []
    show_recommendations = False
    
    if current_user.is_authenticated:
        if current_user.library_books:
            # Corrected from library_book to book
            user_authors = {entry.book.author for entry in current_user.library_books}
            user_book_ids = {entry.book_id for entry in current_user.library_books}
            
            recommended_books = Book.query.filter(
                Book.author.in_(user_authors),
                ~Book.id.in_(user_book_ids)
            ).limit(5).all()
            show_recommendations = True
        else:
            recommended_books = db.session.query(
                Book,
                db.func.count(UserLibrary.id).label('user_count')
            ).join(UserLibrary).group_by(Book.id).order_by(
                db.desc('user_count')
            ).limit(5).all()
            show_recommendations = True
    
    return render_template(
        'home.html',
        newest_books=newest_books,
        top_rated_books=top_rated_books,
        recommended_books=recommended_books,
        show_recommendations=show_recommendations,
        has_library_books=current_user.is_authenticated and bool(current_user.library_books)
    )


@app.route('/add_book', methods=['GET', 'POST'])
@login_required
def add_book():
    if not current_user.is_moderator:
        flash('Brak uprawnień!', 'danger')
        return redirect(url_for('home'))

    form = BookForm()
    form.genres.choices = [(g.id, g.name) for g in Genre.query.order_by('name')]
    
    if form.validate_on_submit():
        cover_url = ''
        if form.cover.data:
            file = form.cover.data
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[1].lower()}")
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                img = Image.open(file_path)
                img.thumbnail((300, 300))
                img.save(file_path)
                cover_url = f"/uploads/covers/{filename}"

        book = Book(
            title=form.title.data,
            author=form.author.data,
            description=form.description.data,
            isbn=form.isbn.data,
            cover_url=cover_url
        )
        db.session.add(book)
        
        for genre_id in form.genres.data:
            genre = Genre.query.get(genre_id)
            if genre:
                book.genres.append(genre)
        
        if form.tags.data:
            for tag_name in [t.strip() for t in form.tags.data.split(',') if t.strip()]:
                tag = Tag.query.filter(func.lower(Tag.name) == func.lower(tag_name)).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                book.tags.append(tag)
        
        db.session.commit()
        flash('Książka dodana!', 'success')
        return redirect(url_for('book_details', book_id=book.id))
    
    return render_template('add_book.html', form=form)

@app.route('/books')
def book_list():
    genre_id = request.args.get('genre', type=int)
    tag_id = request.args.get('tag', type=int)
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'title_asc')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 6, type=int)

    query = Book.query

    if genre_id:
        query = query.join(Book.genres).filter(Genre.id == genre_id)

    if tag_id:
        query = query.join(Book.tags).filter(Tag.id == tag_id)

    if search_query:
        query = query.filter(
            db.or_(
                Book.title.ilike(f'%{search_query}%'),
                Book.author.ilike(f'%{search_query}%')
            )
        )

    if sort_by == 'title_asc':
        query = query.order_by(Book.title.asc())
    elif sort_by == 'title_desc':
        query = query.order_by(Book.title.desc())
    elif sort_by == 'author_asc':
        query = query.order_by(Book.author.asc())
    elif sort_by == 'author_desc':
        query = query.order_by(Book.author.desc())
    elif sort_by == 'newest':
        query = query.order_by(Book.date_added.desc())
    elif sort_by == 'oldest':
        query = query.order_by(Book.date_added.asc())
    elif sort_by == 'best_rated':
        query = query.outerjoin(Review).group_by(Book.id).order_by(db.func.avg(Review.rating).desc())

    books_pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    all_genres = Genre.query.order_by(Genre.name).all()
    
    popular_tags = db.session.query(
        Tag,
        db.func.count(Book.id).label('book_count')
    ).join(
        Tag.books
    ).group_by(
        Tag.id
    ).order_by(
        db.desc('book_count')
    ).limit(10).all()

    return render_template(
        'books.html',
        books=books_pagination.items,
        pagination=books_pagination,
        search_query=search_query,
        sort_by=sort_by,
        per_page=per_page,
        all_genres=all_genres,
        popular_tags=popular_tags,
        selected_genre=genre_id,
        selected_tag=tag_id
    )

@app.route('/my_library')
@login_required
def my_library():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    shelf_id = request.args.get('shelf', type=int)
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'added_desc')

    shelves = Shelf.query.filter_by(user_id=current_user.id)\
        .order_by(Shelf.is_default.desc(), Shelf.name)\
        .all()
    
    shelf_counts = {}
    for shelf in shelves:
        count = UserLibrary.query.filter_by(
            user_id=current_user.id,
            shelf_id=shelf.id
        ).count()
        shelf_counts[shelf.id] = count

    query = db.session.query(UserLibrary, Book)\
        .join(Book, UserLibrary.book_id == Book.id)\
        .filter(UserLibrary.user_id == current_user.id)
    
    if shelf_id:
        query = query.filter(UserLibrary.shelf_id == shelf_id)
        selected_shelf_name = Shelf.query.get(shelf_id).name
    else:
        selected_shelf_name = "Wszystkie książki"
    
    if search_query:
        query = query.filter(or_(
            Book.title.ilike(f'%{search_query}%'),
            Book.author.ilike(f'%{search_query}%')
        ))
    
    if sort_by == 'title_asc':
        query = query.order_by(Book.title.asc())
    elif sort_by == 'title_desc':
        query = query.order_by(Book.title.desc())
    elif sort_by == 'author_asc':
        query = query.order_by(Book.author.asc())
    elif sort_by == 'author_desc':
        query = query.order_by(Book.author.desc())
    elif sort_by == 'added_desc':
        query = query.order_by(UserLibrary.added_at.desc())
    elif sort_by == 'added_asc':
        query = query.order_by(UserLibrary.added_at.asc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    user_books = pagination.items
    
    total_books = UserLibrary.query.filter_by(user_id=current_user.id).count()
    
    reading_shelf = Shelf.query.filter_by(user_id=current_user.id, name='W trakcie czytania').first()
    finished_shelf = Shelf.query.filter_by(user_id=current_user.id, name='Przeczytane').first()
    finished_books = UserLibrary.query.filter_by(
        user_id=current_user.id, 
        shelf_id=finished_shelf.id
    ).count() if finished_shelf else 0
    
    return render_template(
        'my_library.html',
        shelves=shelves,
        shelf_counts=shelf_counts,
        total_books=total_books,
        user_books=user_books,
        pagination=pagination,
        selected_shelf=shelf_id,
        selected_shelf_name=selected_shelf_name,
        search_query=search_query,
        sort_by=sort_by,
        per_page=per_page,
        finished_books=finished_books,
        reading_shelf=reading_shelf,
        finished_shelf=finished_shelf
    )

def create_default_shelves(user):
    default_shelves = [
        ('Do przeczytania', True),
        ('W trakcie czytania', True),
        ('Przeczytane', True),
        ('Ulubione', False)
    ]
    
    for name, is_default in default_shelves:
        shelf = Shelf(
            user_id=user.id,
            name=name,
            is_default=is_default
        )
        db.session.add(shelf)
    db.session.commit()

@app.route('/add_to_library/<int:book_id>', methods=['POST'])
@login_required
def add_to_library(book_id):
    book = Book.query.get_or_404(book_id)
    
    existing_entry = UserLibrary.query.filter_by(
        user_id=current_user.id,
        book_id=book_id
    ).first()
    
    if existing_entry:
        flash('Ta książka jest już w Twojej bibliotece!', 'warning')
    else:
        new_entry = UserLibrary(
            user_id=current_user.id,
            book_id=book_id
        )
        db.session.add(new_entry)
        db.session.commit()
        flash('Książka dodana do biblioteki!', 'success')
    
    return redirect(url_for('book_list'))

@app.route('/move_to_shelf/<int:entry_id>/<int:shelf_id>', methods=['POST'])
@login_required
def move_to_shelf(entry_id, shelf_id):
    entry = UserLibrary.query.get_or_404(entry_id)
    shelf = Shelf.query.filter_by(id=shelf_id, user_id=current_user.id).first_or_404()
    
    if entry.user_id != current_user.id:
        abort(403)
    
    entry.shelf_id = shelf.id
    db.session.commit()
    
    flash(f'Przeniesiono "{entry.book.title}" do półki "{shelf.name}"', 'success')
    return redirect(url_for('my_library'))

@app.route('/remove_from_library/<int:entry_id>', methods=['POST'])
@login_required
def remove_from_library(entry_id):
    entry = UserLibrary.query.get_or_404(entry_id)
    
    if entry.user_id != current_user.id:
        flash('Brak uprawnień!', 'danger')
        return redirect(url_for('my_library'))
    
    db.session.delete(entry)
    db.session.commit()
    flash('Książka została usunięta z biblioteki', 'success')
    return redirect(url_for('my_library'))

@app.route('/add_review/<int:book_id>', methods=['GET', 'POST'])
@login_required
def add_review(book_id):
    book = Book.query.get_or_404(book_id)
    form = ReviewForm()
    
    existing_review = Review.query.filter_by(
        book_id=book.id,
        user_id=current_user.id
    ).first()
    
    if existing_review:
        flash('Możesz dodać tylko jedną recenzję per książka!', 'warning')
        return redirect(url_for('book_details', book_id=book.id))
    
    if form.validate_on_submit():
        review = Review(
            rating=form.rating.data,
            text=form.text.data or None, 
            user_id=current_user.id,
            book_id=book.id
        )
        db.session.add(review)
        db.session.commit()
        flash('Recenzja dodana!', 'success')
        return redirect(url_for('book_details', book_id=book.id))
    
    return render_template('add_review.html', form=form, book=book)

@app.route('/book/<int:book_id>')
def book_details(book_id):
    page = request.args.get('page', 1, type=int)
    book = Book.query.options(
        db.joinedload(Book.genres),
        db.joinedload(Book.tags)
    ).get_or_404(book_id)
    
    reviews_query = Review.query.filter_by(book_id=book.id).order_by(Review.created_at.desc())
    reviews_pagination = reviews_query.paginate(page=page, per_page=5, error_out=False)
    
    current_user_review = None
    if current_user.is_authenticated:
        current_user_review = Review.query.filter_by(
            book_id=book.id,
            user_id=current_user.id
        ).first()
    
    avg_rating = db.session.query(db.func.avg(Review.rating))\
        .filter_by(book_id=book.id).scalar() or 0
    
    return render_template(
        'book_details.html',
        book=book,
        reviews=reviews_pagination.items,
        reviews_pagination=reviews_pagination,
        avg_rating=round(avg_rating, 1),
        current_user_review=current_user_review
    )

@app.route('/uploads/covers/<filename>')
def uploaded_cover(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/manage/genres')
@login_required
def manage_genres():
    if not current_user.is_moderator:
        abort(403)
    genres = Genre.query.order_by(Genre.name).all()
    form = GenreForm()
    return render_template('manage_genres.html', genres=genres, form=form)

@app.route('/genre/add', methods=['POST'])
@login_required
def add_genre():
    if not current_user.is_moderator:
        abort(403)
    form = GenreForm()
    if form.validate_on_submit():
        genre = Genre(name=form.name.data)
        db.session.add(genre)
        db.session.commit()
        flash('Gatunek został dodany', 'success')
    else:
        flash('Błąd podczas dodawania gatunku', 'danger')
    return redirect(url_for('manage_genres'))

@app.route('/genre/delete/<int:genre_id>', methods=['POST'])
@login_required
def delete_genre(genre_id):
    if not current_user.is_moderator:
        abort(403)
    genre = Genre.query.get_or_404(genre_id)
    db.session.delete(genre)
    db.session.commit()
    flash('Gatunek został usunięty', 'success')
    return redirect(url_for('manage_genres'))

@app.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    if not current_user.is_moderator:
        flash('Brak uprawnień!', 'danger')
        return redirect(url_for('home'))

    book = Book.query.get_or_404(book_id)
    form = BookForm(obj=book)
    form.genres.choices = [(g.id, g.name) for g in Genre.query.order_by('name')]

    if request.method == 'GET':
        form.genres.data = [g.id for g in book.genres]
        form.tags.data = ', '.join([t.name for t in book.tags])

    if form.validate_on_submit():
        try:
            book.title = form.title.data
            book.author = form.author.data
            book.description = form.description.data
            book.isbn = form.isbn.data

            if form.cover.data:
                file = form.cover.data
                if file and allowed_file(file.filename):
                    if book.cover_url:
                        old_file_path = os.path.join('static', book.cover_url.lstrip('/'))
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    
                    filename = secure_filename(f"{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[1].lower()}")
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    img = Image.open(file_path)
                    img.thumbnail((300, 300))
                    img.save(file_path)
                    book.cover_url = f"/uploads/covers/{filename}"

            book.genres = []
            for genre_id in form.genres.data:
                genre = Genre.query.get(genre_id) 
                if genre:
                    book.genres.append(genre) 

            book.tags = []
            if form.tags.data:
                for tag_name in [t.strip() for t in form.tags.data.split(',') if t.strip()]:
                    tag = Tag.query.filter(func.lower(Tag.name) == func.lower(tag_name)).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.session.add(tag)
                    book.tags.append(tag)

            db.session.commit()
            flash('Książka została zaktualizowana!', 'success')
            return redirect(url_for('book_details', book_id=book.id))
        except Exception as e:
            db.session.rollback()
            flash('Wystąpił błąd podczas aktualizacji książki', 'danger')
            app.logger.error(f"Error updating book: {str(e)}")
            return redirect(url_for('edit_book', book_id=book.id))

    return render_template('edit_book.html', form=form, book=book)

@app.route('/my_shelves')
@login_required
def my_shelves():
    shelves = Shelf.query.filter_by(user_id=current_user.id)\
        .order_by(Shelf.is_default.desc(), Shelf.name)\
        .all()
    
    if not shelves:
        create_default_shelves(current_user)
        shelves = Shelf.query.filter_by(user_id=current_user.id)\
            .order_by(Shelf.is_default.desc(), Shelf.name)\
            .all()
    
    shelf_counts = {}
    for shelf in shelves:
        count = UserLibrary.query.filter_by(
            user_id=current_user.id,
            shelf_id=shelf.id
        ).count()
        shelf_counts[shelf.id] = count
    
    return render_template('shelves.html', shelves=shelves, shelf_counts=shelf_counts)

@app.route('/add_to_shelf/<int:book_id>/<int:shelf_id>', methods=['POST'])
@login_required
def add_to_shelf(book_id, shelf_id):
    shelf = Shelf.query.filter_by(id=shelf_id, user_id=current_user.id).first_or_404()
    book = Book.query.get_or_404(book_id)
    
    library_entry = UserLibrary.query.filter_by(
        user_id=current_user.id,
        book_id=book_id
    ).first()
    
    if library_entry:
        library_entry.shelf_id = shelf_id
    else:
        library_entry = UserLibrary(
            user_id=current_user.id,
            book_id=book_id,
            shelf_id=shelf_id
        )
        db.session.add(library_entry)
    
    db.session.commit()
    flash(f'Książka "{book.title}" dodana do półki "{shelf.name}"', 'success')
    return redirect(request.referrer or url_for('book_details', book_id=book_id))

@app.route('/create_shelf', methods=['POST'])
@login_required
def create_shelf():
    shelf_name = request.form.get('shelf_name')
    current_shelf = request.args.get('shelf', type=int)  
    
    if not shelf_name or len(shelf_name) > 50:
        flash('Nazwa półki musi mieć od 1 do 50 znaków', 'danger')
        return redirect(url_for('my_library', shelf=current_shelf) if current_shelf else redirect(url_for('my_library')))
    
    shelf = Shelf(
        user_id=current_user.id,
        name=shelf_name.strip()
    )
    db.session.add(shelf)
    db.session.commit()
    
    flash(f'Utworzono nową półkę: "{shelf.name}"', 'success')
    return redirect(url_for('my_library', shelf=current_shelf)) if current_shelf else redirect(url_for('my_library'))

@app.route('/shelf/<int:shelf_id>')
@login_required
def shelf_books(shelf_id):
    shelf = Shelf.query.filter_by(id=shelf_id, user_id=current_user.id).first_or_404()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    
    books_pagination = Book.query.join(
        UserLibrary
    ).filter(
        UserLibrary.user_id == current_user.id,
        UserLibrary.shelf_id == shelf_id
    ).order_by(
        UserLibrary.added_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template(
        'shelf_books.html',
        shelf=shelf,
        books=books_pagination.items,
        pagination=books_pagination
    )

@app.route('/api/shelves/<int:shelf_id>/books/<int:book_id>', methods=['POST', 'DELETE'])
@login_required
def manage_shelf_books(shelf_id, book_id):
    shelf = Shelf.query.filter_by(id=shelf_id, user_id=current_user.id).first_or_404()
    book = Book.query.get_or_404(book_id)
    
    if request.method == 'POST':
        existing = UserLibrary.query.filter_by(
            user_id=current_user.id,
            book_id=book_id,
            shelf_id=shelf_id
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Książka już jest na tej półce'}), 400
            
        new_entry = UserLibrary(
            user_id=current_user.id,
            book_id=book_id,
            shelf_id=shelf_id
        )
        db.session.add(new_entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Dodano "{book.title}" do półki "{shelf.name}"',
            'shelf_name': shelf.name
        })
    
    elif request.method == 'DELETE':
        entry = UserLibrary.query.filter_by(
            user_id=current_user.id,
            book_id=book_id,
            shelf_id=shelf_id
        ).first_or_404()
        
        db.session.delete(entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Usunięto "{book.title}" z półki "{shelf.name}"'
        })

@app.route('/delete_shelf/<int:shelf_id>', methods=['POST'])
@login_required
def delete_shelf(shelf_id):
    shelf = Shelf.query.filter_by(id=shelf_id, user_id=current_user.id).first_or_404()
    
    default_shelf = Shelf.query.filter_by(
        user_id=current_user.id,
        name='Do przeczytania'
    ).first()
    
    if default_shelf:
        UserLibrary.query.filter_by(shelf_id=shelf.id).update({'shelf_id': default_shelf.id})
    else:
        UserLibrary.query.filter_by(shelf_id=shelf.id).delete()
    
    db.session.delete(shelf)
    db.session.commit()
    
    flash(f'Usunięto półkę "{shelf.name}"', 'success')
    return redirect(url_for('my_library'))

@app.route('/remove_from_shelf/<int:entry_id>', methods=['POST'])
@login_required
def remove_from_shelf(entry_id):
    entry = UserLibrary.query.get_or_404(entry_id)
    
    if entry.user_id != current_user.id:
        abort(403)
    
    entry.shelf_id = None
    db.session.commit()
    
    flash(f'Usunięto książkę "{entry.book.title}" z bieżącej półki', 'success')
    return redirect(request.referrer or url_for('my_library'))

#

with app.app_context():
    db.create_all()

    admin = User.query.filter_by(username='admin').first()
    if not admin:
        hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
        admin = User(
            username='admin',
            password=hashed_password,
            is_moderator=True
        )
        db.session.add(admin)
        
        default_shelves = [
            ('Do przeczytania', True),
            ('W trakcie czytania', True),
            ('Przeczytane', True),
            ('Ulubione', False)
        ]
        
        for name, is_default in default_shelves:
            shelf = Shelf(
                user_id=admin.id,
                name=name,
                is_default=is_default
            )
            db.session.add(shelf)
        
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)