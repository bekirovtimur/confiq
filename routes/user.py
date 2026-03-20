from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Length, Optional, EqualTo
from models import db, User, Endpoint, Config, ConfigType
from warp.client import WarpAPI
import qrcode
import io
import base64
import json
from jinja2 import Template

user_bp = Blueprint('user', __name__)

class CreateConfigForm(FlaskForm):
    name = StringField('Название конфигурации', validators=[Optional(), Length(max=100)])
    endpoint_id = SelectField('Выберите Endpoint', validators=[DataRequired()], coerce=int)
    config_type_id = SelectField('Выберите тип конфигурации', validators=[DataRequired()], coerce=int)
    submit = SubmitField('Создать конфигурацию')

class EditConfigForm(FlaskForm):
    name = StringField('Название конфигурации', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Сохранить изменения')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Текущий пароль', validators=[DataRequired()])
    new_password = PasswordField('Новый пароль', validators=[DataRequired(), Length(min=3)])
    confirm_password = PasswordField('Подтвердите новый пароль',
                                   validators=[DataRequired(), EqualTo('new_password', 'Пароли не совпадают')])
    submit_password = SubmitField('Изменить пароль')

@user_bp.route('/dashboard')
@login_required
def dashboard():
    """Главная страница пользователя"""
    configs = Config.query.filter_by(user_id=current_user.id).order_by(Config.created_at.desc()).all()
    config_count = len(configs)
    config_limit = current_user.config_limit
    
    return render_template('user/dashboard.html', 
                         configs=configs,
                         config_count=config_count,
                         config_limit=config_limit)

@user_bp.route('/configs')
@login_required
def configs():
    """Список конфигураций пользователя"""
    page = request.args.get('page', 1, type=int)
    per_page = 6  # Показываем 6 карточек на страницу
    
    configs = Config.query.filter_by(user_id=current_user.id)\
                    .order_by(Config.created_at.desc())\
                    .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('user/configs.html', configs=configs)

@user_bp.route('/configs/create', methods=['GET', 'POST'])
@login_required
def create_config():
    """Создание новой конфигурации"""
    # Проверяем, может ли пользователь создать еще одну конфигурацию
    if not current_user.can_create_config():
        flash(f'Достигнут лимит конфигураций ({current_user.config_limit}). Удалите существующие конфиги для создания новых.', 'warning')
        return redirect(url_for('user.dashboard'))
    
    form = CreateConfigForm()
    
    # Заполняем список доступных endpoints
    endpoints = Endpoint.query.all()
    form.endpoint_id.choices = [(ep.id, f"{ep.name} ({ep.full_address})") for ep in endpoints]
    
    if not endpoints:
        flash('Нет доступных endpoints. Обратитесь к администратору.', 'danger')
        return redirect(url_for('user.dashboard'))
    
    # Получаем выбранный endpoint: сначала из POST-данных, затем из query params
    selected_endpoint_id = None
    if request.method == 'POST' and form.endpoint_id.data:
        selected_endpoint_id = form.endpoint_id.data
    else:
        selected_endpoint_id = request.args.get('endpoint_id', type=int)
    
    # Если endpoint выбран, фильтруем типы конфигураций
    if selected_endpoint_id:
        endpoint = Endpoint.query.get(selected_endpoint_id)
        if endpoint:
            form.endpoint_id.data = selected_endpoint_id
            # Показываем только поддерживаемые типы для этого endpoint
            config_types = endpoint.config_types
        else:
            config_types = ConfigType.query.filter_by(is_active=True).all()
    else:
        # По умолчанию показываем типы для первого endpoint
        first_endpoint = endpoints[0] if endpoints else None
        if first_endpoint:
            config_types = first_endpoint.config_types
        else:
            config_types = ConfigType.query.filter_by(is_active=True).all()
    
    form.config_type_id.choices = [(ct.id, ct.name) for ct in config_types if ct.is_active]
    
    if form.validate_on_submit():
        endpoint = Endpoint.query.get_or_404(form.endpoint_id.data)
        config_type = ConfigType.query.get_or_404(form.config_type_id.data)
        
        # Проверяем, поддерживает ли endpoint выбранный тип
        if config_type not in endpoint.config_types:
            flash('Выбранный тип конфигурации не поддерживается данным endpoint.', 'danger')
            return redirect(url_for('user.create_config'))
        
        try:
            # Создаем конфиг через Cloudflare API
            flash('Создание конфигурации... Это может занять несколько секунд.', 'info')
            warp_data = WarpAPI.create_config(endpoint.address, endpoint.port)
            
            # Генерируем конфигурацию из шаблона
            template = Template(config_type.config_template)
            config_content = template.render(
                private_key=warp_data['private_key'],
                public_key=warp_data['public_key'],
                peer_public_key=warp_data['peer_public_key'],
                client_ipv4=warp_data['client_ipv4'],
                client_ipv6=warp_data['client_ipv6'],
                endpoint=endpoint.address,
                port=endpoint.port,
                cloudflare_id=warp_data['device_id'],
                token=warp_data['token']
            )
            
            # Создаем запись в БД
            config = Config(
                name=form.name.data or f"{config_type.name} {current_user.get_config_count() + 1}",
                user_id=current_user.id,
                endpoint_id=endpoint.id,
                config_type_id=config_type.id,
                cloudflare_id=warp_data['device_id'],
                cloudflare_token=warp_data['token'],
                private_key=warp_data['private_key'],
                public_key=warp_data['public_key'],
                peer_public_key=warp_data['peer_public_key'],
                client_ipv4=warp_data['client_ipv4'],
                client_ipv6=warp_data['client_ipv6'],
                config_content=config_content
            )
            
            db.session.add(config)
            db.session.commit()
            
            flash(f'Конфигурация {config_type.name} успешно создана!', 'success')
            return redirect(url_for('user.view_config', config_id=config.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка создания конфигурации: {e}', 'danger')
    
    return render_template('user/create_config.html', form=form, endpoints=endpoints)

@user_bp.route('/api/endpoint/<int:endpoint_id>/config-types')
@login_required
def get_endpoint_config_types(endpoint_id):
    """API endpoint для получения типов конфигураций для выбранного endpoint"""
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    config_types = endpoint.config_types
    
    # Логирование для диагностики
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"API: Endpoint {endpoint_id} ({endpoint.name}) - {len(config_types)} types")
    for ct in config_types:
        logger.info(f"  Type: {ct.name} (id={ct.id}, active={ct.is_active})")
    
    return jsonify([{
        'id': ct.id,
        'name': ct.name,
        'description': ct.description
    } for ct in config_types if ct.is_active])

@user_bp.route('/configs/<int:config_id>')
@login_required
def view_config(config_id):
    """Просмотр конфигурации"""
    config = Config.query.filter_by(id=config_id, user_id=current_user.id).first_or_404()
    
    # Получаем тип конфигурации
    config_type = config.config_type
    
    # Парсим client_links из JSON
    client_links = {}
    if config_type and config_type.client_links:
        try:
            client_links = json.loads(config_type.client_links)
        except json.JSONDecodeError:
            client_links = {}
    
    # Генерируем QR-код
    qr_data = generate_qr_code(config.config_content)
    
    return render_template('user/view_config.html', 
                         config=config, 
                         config_type=config_type,
                         client_links=client_links,
                         qr_data=qr_data)

@user_bp.route('/configs/<int:config_id>/download')
@login_required
def download_config(config_id):
    """Скачивание конфиг-файла"""
    config = Config.query.filter_by(id=config_id, user_id=current_user.id).first_or_404()
    
    # Определяем расширение файла на основе типа конфигурации
    if config.config_type:
        # Clash использует YAML
        if 'clash' in config.config_type.name.lower():
            file_extension = 'yaml'
        else:
            file_extension = 'conf'
    else:
        file_extension = 'conf'
    
    filename = f"{config.name.replace(' ', '_')}.{file_extension}"
    
    response = make_response(config.config_content)
    response.headers['Content-Type'] = 'application/octet-stream'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@user_bp.route('/configs/<int:config_id>/qr')
@login_required
def config_qr(config_id):
    """Получение QR-кода конфигурации"""
    config = Config.query.filter_by(id=config_id, user_id=current_user.id).first_or_404()
    
    # Генерируем QR-код
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(config.config_content)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Конвертируем в base64 для возврата
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    response = make_response(img_buffer.getvalue())
    response.headers['Content-Type'] = 'image/png'
    response.headers['Cache-Control'] = 'max-age=3600'
    
    return response

@user_bp.route('/configs/<int:config_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_config(config_id):
    """Редактирование конфигурации (только название)"""
    config = Config.query.filter_by(id=config_id, user_id=current_user.id).first_or_404()
    form = EditConfigForm(obj=config)
    
    if form.validate_on_submit():
        config.name = form.name.data
        
        try:
            db.session.commit()
            flash('Название конфигурации успешно изменено.', 'success')
            return redirect(url_for('user.view_config', config_id=config.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка обновления конфигурации: {e}', 'danger')
    
    return render_template('user/edit_config.html', form=form, config=config)

@user_bp.route('/configs/<int:config_id>/delete', methods=['POST'])
@login_required
def delete_config(config_id):
    """Удаление конфигурации"""
    config = Config.query.filter_by(id=config_id, user_id=current_user.id).first_or_404()
    
    try:
        # Удаляем устройство из Cloudflare
        WarpAPI.delete_config(config.cloudflare_id, config.cloudflare_token)
        
        # Удаляем из БД
        db.session.delete(config)
        db.session.commit()
        
        flash('Конфигурация успешно удалена.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка удаления конфигурации: {e}', 'danger')
    
    return redirect(url_for('user.dashboard'))

@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Профиль пользователя с настройками"""
    config_count = current_user.get_config_count()
    
    # Форма смены пароля
    password_form = ChangePasswordForm()
    
    # Обработка смены пароля
    if 'submit_password' in request.form and password_form.validate():
        # Проверяем текущий пароль
        if not current_user.check_password(password_form.current_password.data):
            flash('Неверный текущий пароль.', 'danger')
        else:
            # Устанавливаем новый пароль
            current_user.set_password(password_form.new_password.data)
            try:
                db.session.commit()
                flash('Пароль успешно изменен. Рекомендуем перелогиниться.', 'success')
                return redirect(url_for('user.profile'))
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка смены пароля: {e}', 'danger')
    
    return render_template('user/profile.html',
                         config_count=config_count,
                         password_form=password_form)

def generate_qr_code(text):
    """Генерирует QR-код и возвращает как base64 строку"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"
