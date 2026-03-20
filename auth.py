from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length
from models import db, User

auth_bp = Blueprint('auth', __name__)

class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=3)])
    submit = SubmitField('Войти')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Если пользователь уже авторизован, перенаправляем его на нужную страницу
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('user.dashboard'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data
        
        # Поиск пользователя
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            
            # Получаем URL для перенаправления после входа
            next_page = request.args.get('next')
            
            if next_page:
                return redirect(next_page)
            elif user.is_admin:
                flash(f'Добро пожаловать, {username}! Вы вошли как администратор.', 'success')
                return redirect(url_for('admin.dashboard'))
            else:
                flash(f'Добро пожаловать, {username}!', 'success')
                return redirect(url_for('user.dashboard'))
        else:
            flash('Неверный логин или пароль.', 'danger')
    
    return render_template('login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы.', 'info')
    return redirect(url_for('auth.login'))