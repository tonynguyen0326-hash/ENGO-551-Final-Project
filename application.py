from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    __tablename__ = 'app_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))

        new_user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('homepage'))

    return render_template('register.html', hide_nav=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return render_template(
                'login.html',
                success_message='Login successful! Redirecting...',
                redirect_url=url_for('homepage'),
                hide_nav=True
            )

        return render_template(
            'login.html',
            error_message='Incorrect username or password',
            hide_nav=True
        )

    return render_template('login.html', hide_nav=True)

@app.route('/')
@login_required
def index():
    return redirect(url_for('homepage'))

@app.route('/homepage')
@login_required
def homepage():
    return render_template('homepage.html')

@app.route('/study-spot-suggestion')
@login_required
def study_spot_suggestion():
    return render_template('study_spot_suggestion.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('homepage'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = request.form.get('username')
        new_password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Password reset successful!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username not found.')

    return render_template('reset_password.html', hide_nav=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)