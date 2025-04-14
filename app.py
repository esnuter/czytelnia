from flask import Flask, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email, ValidationError
from extensions import db, login_manager, bcrypt
from models import *
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField
from sqlalchemy import and_

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tajny-klucz-123'  # 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///czytelnia.db'

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

# Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, password=hashed_password)
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
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('book_list'))
    return render_template('home.html')

@app.route('/add_book', methods=['GET', 'POST'])  
@login_required  
def add_book():  
    if not current_user.is_moderator: 
        flash('Brak uprawnień!', 'danger')  
        return redirect(url_for('home'))  

    form = BookForm()  
    if form.validate_on_submit():  
        book = Book(  
            title=form.title.data,  
            author=form.author.data,  
            description=form.description.data  
        )  
        db.session.add(book)  
        db.session.commit()  
        flash('Książka dodana!', 'success')  
        return redirect(url_for('book_list'))  
    return render_template('add_book.html', form=form)  

@app.route('/books')  
def book_list():  
    books = Book.query.all()  
    return render_template('books.html', books=books)  

@app.route('/my_library')
@login_required
def my_library():
    user_books = current_user.library_books
    return render_template('my_library.html', user_books=user_books)

@app.route('/add_to_library/<int:book_id>', methods=['POST'])
@login_required
def add_to_library(book_id):
    book = Book.query.get_or_404(book_id)
    
    existing_entry = UserLibrary.query.filter(
        and_(
            UserLibrary.user_id == current_user.id,
            UserLibrary.book_id == book_id
        )
    ).first()
    
    if existing_entry:
        flash('Ta książka jest już w Twojej bibliotece!', 'warning')
    else:
        new_entry = UserLibrary(
            user_id=current_user.id,
            book_id=book_id,
            status='reading'  # Deafult status
        )
        db.session.add(new_entry)
        db.session.commit()
        flash('Książka dodana do biblioteki!', 'success')
    
    return redirect(url_for('book_list'))

@app.route('/update_status/<int:entry_id>/<status>')
@login_required
def update_status(entry_id, status):
    entry = UserLibrary.query.get_or_404(entry_id)
    
    if entry.user_id != current_user.id:
        flash('Brak uprawnień!', 'danger')
        return redirect(url_for('my_library'))
    
    entry.status = status
    db.session.commit()
    flash('Status zaktualizowany!', 'success')
    return redirect(url_for('my_library'))

@app.route('/remove_from_library/<int:entry_id>', methods=['POST'])
@login_required
def remove_from_library(entry_id):
    entry = UserLibrary.query.get_or_404(entry_id)
    
    if entry.library_user.id != current_user.id:
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
    
    if form.validate_on_submit():
        review = Review(
            rating=form.rating.data,
            text=form.text.data,
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
    book = Book.query.get_or_404(book_id)
    reviews = Review.query.filter_by(book_id=book.id).order_by(Review.created_at.desc()).all()
    
    # avg rating
    avg_rating = db.session.query(db.func.avg(Review.rating)).filter_by(book_id=book.id).scalar() or 0
    
    return render_template(
        'book_details.html',
        book=book,
        reviews=reviews,
        avg_rating=round(avg_rating, 1)
    )

#

with app.app_context():
    # db.drop_all()
    db.create_all()

    if not User.query.filter_by(username='admin').first():
        hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
        admin = User(username='admin', password=hashed_password, is_moderator=True)
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)