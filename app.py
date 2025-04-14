from flask import Flask, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email, ValidationError
from extensions import db, login_manager, bcrypt
from models import *
from wtforms import TextAreaField
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

# Register Form
class RegisterForm(FlaskForm):
    username = StringField('Nazwa użytkownika', validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField('Hasło', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Zarejestruj się')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Nazwa użytkownika zajęta!')

# Login Form
class LoginForm(FlaskForm):
    username = StringField('Nazwa użytkownika', validators=[DataRequired()])
    password = PasswordField('Hasło', validators=[DataRequired()])
    submit = SubmitField('Zaloguj się')

class BookForm(FlaskForm):  
    title = StringField('Tytuł', validators=[DataRequired()])  
    author = StringField('Autor', validators=[DataRequired()])  
    description = TextAreaField('Opis')  
    submit = SubmitField('Dodaj książkę')  

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
def home():
    return "Witaj w Czytelnia.pl!"  #

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