from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, BooleanField, PasswordField, SubmitField, SelectField, TextAreaField, SelectMultipleField
from wtforms.validators import DataRequired, Length, NumberRange, IPAddress, Optional
from models import db, User, Endpoint, Config, ConfigType, Group
from warp.client import WarpAPI
from functools import wraps

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Декоратор для проверки прав администратора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ запрещен. Требуются права администратора.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

class UserForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=3)])
    config_limit = IntegerField('Лимит конфигов', validators=[DataRequired(), NumberRange(min=1, max=100)], default=5)
    group_id = SelectField('Группа', coerce=int, validators=[Optional()])
    is_admin = BooleanField('Права администратора')
    submit = SubmitField('Создать пользователя')

class EditUserForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Новый пароль (оставьте пустым, чтобы не менять)', validators=[Optional(), Length(min=3)])
    config_limit = IntegerField('Лимит конфигов', validators=[DataRequired(), NumberRange(min=1, max=100)])
    group_id = SelectField('Группа', coerce=int, validators=[Optional()])
    is_admin = BooleanField('Права администратора')
    submit = SubmitField('Обновить пользователя')

class EndpointForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(min=3, max=100)])
    address = StringField('Адрес', validators=[DataRequired(), Length(min=5, max=255)])
    port = IntegerField('Порт', validators=[DataRequired(), NumberRange(min=1, max=65535)])
    config_types = SelectMultipleField('Поддерживаемые типы конфигураций', coerce=int)
    submit = SubmitField('Создать Endpoint')

class ConfigTypeForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Описание', validators=[Length(max=500)])
    config_template = TextAreaField('Шаблон конфигурации', validators=[DataRequired()])
    usage_instructions = TextAreaField('Инструкции по использованию')
    client_links = TextAreaField('Ссылки на клиенты (JSON)')
    is_active = BooleanField('Активен', default=True)
    submit = SubmitField('Создать тип конфигурации')

class EditConfigTypeForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Описание', validators=[Length(max=500)])
    config_template = TextAreaField('Шаблон конфигурации', validators=[DataRequired()])
    usage_instructions = TextAreaField('Инструкции по использованию')
    client_links = TextAreaField('Ссылки на клиенты (JSON)')
    is_active = BooleanField('Активен')
    submit = SubmitField('Обновить тип конфигурации')

class GroupForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Описание', validators=[Length(max=500)])
    submit = SubmitField('Создать группу')

class EditGroupForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Описание', validators=[Length(max=500)])
    submit = SubmitField('Обновить группу')

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Главная страница администратора"""
    total_users = User.query.count()
    total_configs = Config.query.count()
    total_endpoints = Endpoint.query.count()
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_configs = Config.query.order_by(Config.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', 
                         total_users=total_users,
                         total_configs=total_configs,
                         total_endpoints=total_endpoints,
                         recent_users=recent_users,
                         recent_configs=recent_configs)

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """Управление пользователями"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    users = User.query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    """Создание нового пользователя"""
    form = UserForm()
    
    # Заполняем choices для группы
    groups = Group.query.all()
    form.group_id.choices = [(0, '-- Без группы --')] + [(g.id, g.name) for g in groups]
    
    if form.validate_on_submit():
        # Проверяем, что пользователь с таким именем не существует
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Пользователь с таким логином уже существует.', 'danger')
            return render_template('admin/create_user.html', form=form, groups=groups)
        
        user = User(
            username=form.username.data,
            config_limit=form.config_limit.data,
            is_admin=form.is_admin.data
        )
        # Устанавливаем группу если выбрана
        if form.group_id.data and form.group_id.data != 0:
            user.group_id = form.group_id.data
        
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash(f'Пользователь {user.username} успешно создан.', 'success')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка создания пользователя: {e}', 'danger')
    
    return render_template('admin/create_user.html', form=form, groups=groups)

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Редактирование пользователя"""
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)
    
    # Заполняем choices для группы
    groups = Group.query.all()
    form.group_id.choices = [(0, '-- Без группы --')] + [(g.id, g.name) for g in groups]
    
    if request.method == 'GET':
        # Устанавливаем текущую группу
        if user.group_id:
            form.group_id.data = user.group_id
        else:
            form.group_id.data = 0
    
    if form.validate_on_submit():
        # Проверяем уникальность логина
        existing_user = User.query.filter(User.username == form.username.data, User.id != user_id).first()
        if existing_user:
            flash('Пользователь с таким логином уже существует.', 'danger')
            return render_template('admin/edit_user.html', form=form, user=user, groups=groups)
        
        user.username = form.username.data
        user.config_limit = form.config_limit.data
        user.is_admin = form.is_admin.data
        
        # Обновляем группу
        if form.group_id.data and form.group_id.data != 0:
            user.group_id = form.group_id.data
        else:
            user.group_id = None
        
        # Обновляем пароль только если он указан
        if form.password.data:
            user.set_password(form.password.data)
        
        try:
            db.session.commit()
            flash(f'Пользователь {user.username} успешно обновлен.', 'success')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка обновления пользователя: {e}', 'danger')
    
    return render_template('admin/edit_user.html', form=form, user=user, groups=groups)

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Удаление пользователя"""
    user = User.query.get_or_404(user_id)
    
    # Нельзя удалить самого себя
    if user.id == current_user.id:
        flash('Вы не можете удалить свой собственный аккаунт.', 'danger')
        return redirect(url_for('admin.users'))
    
    try:
        # Удаляем все конфигурации пользователя из Cloudflare
        for config in user.configs:
            try:
                WarpAPI.delete_config(config.cloudflare_id, config.cloudflare_token)
            except Exception as e:
                print(f"Ошибка удаления конфига {config.id} из Cloudflare: {e}")
        
        db.session.delete(user)
        db.session.commit()
        flash(f'Пользователь {user.username} успешно удален.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка удаления пользователя: {e}', 'danger')
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/endpoints')
@login_required
@admin_required
def endpoints():
    """Управление Endpoints"""
    endpoints = Endpoint.query.order_by(Endpoint.created_at.desc()).all()
    return render_template('admin/endpoints.html', endpoints=endpoints)

@admin_bp.route('/endpoints/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_endpoint():
    """Создание нового Endpoint"""
    form = EndpointForm()
    
    # Заполняем choices для config_types
    form.config_types.choices = [(ct.id, ct.name) for ct in ConfigType.query.filter_by(is_active=True).all()]
    
    # Получаем все группы
    groups = Group.query.all()
    
    if form.validate_on_submit():
        endpoint = Endpoint(
            name=form.name.data,
            address=form.address.data,
            port=form.port.data
        )
        
        # Добавляем выбранные типы конфигураций
        if form.config_types.data:
            selected_types = ConfigType.query.filter(ConfigType.id.in_(form.config_types.data)).all()
            for ct in selected_types:
                endpoint.config_types.append(ct)
        
        # Добавляем выбранные группы
        selected_groups = request.form.getlist('groups', type=int)
        if selected_groups:
            groups_to_add = Group.query.filter(Group.id.in_(selected_groups)).all()
            for group in groups_to_add:
                endpoint.groups.append(group)
        
        try:
            db.session.add(endpoint)
            db.session.commit()
            flash(f'Endpoint {endpoint.name} успешно создан.', 'success')
            return redirect(url_for('admin.endpoints'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка создания endpoint: {e}', 'danger')
    
    return render_template('admin/create_endpoint.html', form=form, groups=groups)

@admin_bp.route('/endpoints/<int:endpoint_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_endpoint(endpoint_id):
    """Редактирование Endpoint"""
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    form = EndpointForm(obj=endpoint)
    
    # Заполняем choices для config_types
    form.config_types.choices = [(ct.id, ct.name) for ct in ConfigType.query.all()]
    
    # Получаем все группы
    groups = Group.query.all()
    
    if request.method == 'GET':
        # Устанавливаем текущие выбранные типы
        form.config_types.data = [ct.id for ct in endpoint.config_types]
    
    if form.validate_on_submit():
        endpoint.name = form.name.data
        endpoint.address = form.address.data
        endpoint.port = form.port.data
        
        # Обновляем выбранные типы конфигураций
        # Очищаем текущие связи
        endpoint.config_types.clear()
        
        if form.config_types.data:
            selected_types = ConfigType.query.filter(ConfigType.id.in_(form.config_types.data)).all()
            for ct in selected_types:
                endpoint.config_types.append(ct)
        
        # Обновляем группы
        endpoint.groups = []
        selected_groups = request.form.getlist('groups', type=int)
        if selected_groups:
            groups_to_add = Group.query.filter(Group.id.in_(selected_groups)).all()
            for group in groups_to_add:
                endpoint.groups.append(group)
        
        try:
            db.session.commit()
            flash(f'Endpoint {endpoint.name} успешно обновлен.', 'success')
            return redirect(url_for('admin.endpoints'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка обновления endpoint: {e}', 'danger')
    
    selected_groups = [g.id for g in endpoint.groups]
    return render_template('admin/edit_endpoint.html', form=form, endpoint=endpoint,
                         groups=groups, selected_groups=selected_groups)

@admin_bp.route('/endpoints/<int:endpoint_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_endpoint(endpoint_id):
    """Удаление Endpoint"""
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    
    # Проверяем, есть ли конфигурации, использующие этот endpoint
    configs_count = Config.query.filter_by(endpoint_id=endpoint_id).count()
    if configs_count > 0:
        flash(f'Невозможно удалить endpoint. Он используется в {configs_count} конфигурациях.', 'danger')
        return redirect(url_for('admin.endpoints'))
    
    try:
        db.session.delete(endpoint)
        db.session.commit()
        flash(f'Endpoint {endpoint.name} успешно удален.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка удаления endpoint: {e}', 'danger')
    
    return redirect(url_for('admin.endpoints'))

@admin_bp.route('/configs')
@login_required
@admin_required
def configs():
    """Просмотр всех конфигураций"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    configs = Config.query.order_by(Config.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/configs.html', configs=configs)

@admin_bp.route('/endpoints/<int:endpoint_id>/configs')
@login_required
@admin_required
def endpoint_configs(endpoint_id):
    """Просмотр всех конфигураций на конкретном endpoint"""
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    configs = Config.query.filter_by(endpoint_id=endpoint_id)\
                    .order_by(Config.created_at.desc())\
                    .paginate(page=page, per_page=per_page, error_out=False)
    
    # Получаем все endpoints для возможности переноса
    all_endpoints = Endpoint.query.filter(Endpoint.id != endpoint_id).all()
    
    return render_template('admin/endpoint_configs.html',
                         endpoint=endpoint,
                         configs=configs,
                         all_endpoints=all_endpoints)

@admin_bp.route('/endpoints/<int:endpoint_id>/configs/bulk-delete', methods=['POST'])
@login_required
@admin_required
def bulk_delete_configs(endpoint_id):
    """Массовое удаление конфигураций с endpoint"""
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    config_ids = request.form.getlist('config_ids[]')
    
    if not config_ids:
        flash('Не выбрано ни одной конфигурации для удаления.', 'warning')
        return redirect(url_for('admin.endpoint_configs', endpoint_id=endpoint_id))
    
    deleted_count = 0
    errors = []
    
    for config_id in config_ids:
        config = Config.query.get(config_id)
        if config and config.endpoint_id == endpoint_id:
            try:
                WarpAPI.delete_config(config.cloudflare_id, config.cloudflare_token)
                db.session.delete(config)
                deleted_count += 1
            except Exception as e:
                errors.append(f"Конфиг {config.name}: {e}")
    
    try:
        db.session.commit()
        if deleted_count > 0:
            flash(f'Успешно удалено {deleted_count} конфигураций.', 'success')
        if errors:
            flash(f'Ошибки при удалении: {"; ".join(errors)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении конфигураций: {e}', 'danger')
    
    return redirect(url_for('admin.endpoint_configs', endpoint_id=endpoint_id))

@admin_bp.route('/endpoints/<int:endpoint_id>/configs/bulk-move', methods=['POST'])
@login_required
@admin_required
def bulk_move_configs(endpoint_id):
    """Массовый перенос конфигураций на другой endpoint"""
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    config_ids = request.form.getlist('config_ids[]')
    target_endpoint_id = request.form.get('target_endpoint_id', type=int)
    
    if not config_ids:
        flash('Не выбрано ни одной конфигурации для переноса.', 'warning')
        return redirect(url_for('admin.endpoint_configs', endpoint_id=endpoint_id))
    
    if not target_endpoint_id:
        flash('Не выбран целевой endpoint для переноса.', 'warning')
        return redirect(url_for('admin.endpoint_configs', endpoint_id=endpoint_id))
    
    target_endpoint = Endpoint.query.get_or_404(target_endpoint_id)
    
    # Нельзя перенести на тот же endpoint
    if target_endpoint_id == endpoint_id:
        flash('Нельзя перенести конфигурации на тот же endpoint.', 'warning')
        return redirect(url_for('admin.endpoint_configs', endpoint_id=endpoint_id))
    
    moved_count = 0
    errors = []
    
    for config_id in config_ids:
        config = Config.query.get(config_id)
        if config and config.endpoint_id == endpoint_id:
            try:
                # Перегенерируем конфигурацию из шаблона с новым endpoint
                # Cloudflare API не вызываем - ключи и IP остаются прежними
                from jinja2 import Template
                config_type = config.config_type
                if config_type and config_type.config_template:
                    template = Template(config_type.config_template)
                    config_content = template.render(
                        private_key=config.private_key,
                        public_key=config.public_key,
                        peer_public_key=config.peer_public_key,
                        client_ipv4=config.client_ipv4,
                        client_ipv6=config.client_ipv6,
                        endpoint=target_endpoint.address,
                        port=target_endpoint.port
                    )
                else:
                    # Если нет шаблона, используем стандартный формат WireGuard
                    config_content = f"""[Interface]
PrivateKey = {config.private_key}
MTU = 1280
Address = {config.client_ipv4}, {config.client_ipv6}
DNS = 1.1.1.1, 2606:4700:4700::1111, 1.0.0.1, 2606:4700:4700::1001

[Peer]
PublicKey = {config.peer_public_key}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {target_endpoint.address}:{target_endpoint.port}"""
                
                # Обновляем только endpoint_id и config_content
                config.endpoint_id = target_endpoint_id
                config.config_content = config_content
                
                moved_count += 1
            except Exception as e:
                errors.append(f"Конфиг {config.name}: {e}")
    
    try:
        db.session.commit()
        if moved_count > 0:
            flash(f'Успешно перенесено {moved_count} конфигураций на endpoint "{target_endpoint.name}".', 'success')
        if errors:
            flash(f'Ошибки при переносе: {"; ".join(errors)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при переносе конфигураций: {e}', 'danger')
    
    return redirect(url_for('admin.endpoint_configs', endpoint_id=endpoint_id))


# ==================== CRUD для ConfigType ====================

@admin_bp.route('/config-types')
@login_required
@admin_required
def config_types():
    """Список всех типов конфигураций"""
    config_types = ConfigType.query.order_by(ConfigType.created_at.desc()).all()
    return render_template('admin/config_types.html', config_types=config_types)

@admin_bp.route('/config-types/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_config_type():
    """Создание нового типа конфигурации"""
    form = ConfigTypeForm()
    
    if form.validate_on_submit():
        # Проверяем уникальность имени
        existing = ConfigType.query.filter_by(name=form.name.data).first()
        if existing:
            flash('Тип конфигурации с таким названием уже существует.', 'danger')
            return render_template('admin/create_config_type.html', form=form)
        
        config_type = ConfigType(
            name=form.name.data,
            description=form.description.data,
            config_template=form.config_template.data,
            usage_instructions=form.usage_instructions.data,
            client_links=form.client_links.data,
            is_active=form.is_active.data
        )
        
        try:
            db.session.add(config_type)
            db.session.commit()
            flash(f'Тип конфигурации "{config_type.name}" успешно создан.', 'success')
            return redirect(url_for('admin.config_types'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка создания типа конфигурации: {e}', 'danger')
    
    return render_template('admin/create_config_type.html', form=form)

@admin_bp.route('/config-types/<int:config_type_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_config_type(config_type_id):
    """Редактирование типа конфигурации"""
    config_type = ConfigType.query.get_or_404(config_type_id)
    form = EditConfigTypeForm(obj=config_type)
    
    if form.validate_on_submit():
        # Проверяем уникальность имени
        existing = ConfigType.query.filter(
            ConfigType.name == form.name.data,
            ConfigType.id != config_type_id
        ).first()
        if existing:
            flash('Тип конфигурации с таким названием уже существует.', 'danger')
            return render_template('admin/edit_config_type.html', form=form, config_type=config_type)
        
        config_type.name = form.name.data
        config_type.description = form.description.data
        config_type.config_template = form.config_template.data
        config_type.usage_instructions = form.usage_instructions.data
        config_type.client_links = form.client_links.data
        config_type.is_active = form.is_active.data
        
        try:
            db.session.commit()
            flash(f'Тип конфигурации "{config_type.name}" успешно обновлен.', 'success')
            return redirect(url_for('admin.config_types'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка обновления типа конфигурации: {e}', 'danger')
    
    return render_template('admin/edit_config_type.html', form=form, config_type=config_type)

@admin_bp.route('/config-types/<int:config_type_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_config_type(config_type_id):
    """Удаление типа конфигурации"""
    config_type = ConfigType.query.get_or_404(config_type_id)
    
    # Проверяем, есть ли связанные конфигурации
    configs_count = Config.query.filter_by(config_type_id=config_type_id).count()
    if configs_count > 0:
        flash(f'Невозможно удалить тип конфигурации. Он используется в {configs_count} конфигурациях.', 'danger')
        return redirect(url_for('admin.config_types'))
    
    # Проверяем, есть ли связанные endpoints
    endpoints_count = len(config_type.endpoints)
    if endpoints_count > 0:
        flash(f'Невозможно удалить тип конфигурации. Он связан с {endpoints_count} endpoint\'ами.', 'danger')
        return redirect(url_for('admin.config_types'))
    
    try:
        db.session.delete(config_type)
        db.session.commit()
        flash(f'Тип конфигурации "{config_type.name}" успешно удален.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка удаления типа конфигурации: {e}', 'danger')
    
    return redirect(url_for('admin.config_types'))

@admin_bp.route('/config-types/<int:config_type_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_config_type(config_type_id):
    """Включение/выключение типа конфигурации"""
    config_type = ConfigType.query.get_or_404(config_type_id)
    
    config_type.is_active = not config_type.is_active
    
    try:
        db.session.commit()
        status = 'включен' if config_type.is_active else 'выключен'
        flash(f'Тип конфигурации "{config_type.name}" {status}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка изменения статуса типа конфигурации: {e}', 'danger')
    
    return redirect(url_for('admin.config_types'))

# ==================== GROUPS MANAGEMENT ====================

@admin_bp.route('/groups')
@login_required
@admin_required
def groups():
    """Управление группами пользователей"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    groups = Group.query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/groups.html', groups=groups)

@admin_bp.route('/groups/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_group():
    """Создание новой группы"""
    form = GroupForm()
    endpoints = Endpoint.query.all()
    
    if form.validate_on_submit():
        # Проверяем, не существует ли группа с таким именем
        existing_group = Group.query.filter_by(name=form.name.data).first()
        if existing_group:
            flash(f'Группа с названием "{form.name.data}" уже существует.', 'danger')
            return render_template('admin/create_group.html', form=form, endpoints=endpoints)
        
        group = Group(
            name=form.name.data,
            description=form.description.data
        )
        
        # Добавляем выбранные endpoints
        selected_endpoints = request.form.getlist('endpoints', type=int)
        for endpoint_id in selected_endpoints:
            endpoint = Endpoint.query.get(endpoint_id)
            if endpoint:
                group.endpoints.append(endpoint)
        
        try:
            db.session.add(group)
            db.session.commit()
            flash(f'Группа "{group.name}" успешно создана.', 'success')
            return redirect(url_for('admin.groups'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка создания группы: {e}', 'danger')
    
    return render_template('admin/create_group.html', form=form, endpoints=endpoints)

@admin_bp.route('/groups/<int:group_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_group(group_id):
    """Редактирование группы"""
    group = Group.query.get_or_404(group_id)
    form = EditGroupForm(obj=group)
    endpoints = Endpoint.query.all()
    
    if form.validate_on_submit():
        # Проверяем, не существует ли другая группа с таким именем
        existing_group = Group.query.filter(
            Group.name == form.name.data,
            Group.id != group_id
        ).first()
        if existing_group:
            flash(f'Группа с названием "{form.name.data}" уже существует.', 'danger')
            selected_endpoints = [e.id for e in group.endpoints]
            return render_template('admin/edit_group.html', form=form, group=group,
                                 endpoints=endpoints, selected_endpoints=selected_endpoints)
        
        group.name = form.name.data
        group.description = form.description.data
        
        # Обновляем endpoints
        group.endpoints = []
        selected_endpoints = request.form.getlist('endpoints', type=int)
        for endpoint_id in selected_endpoints:
            endpoint = Endpoint.query.get(endpoint_id)
            if endpoint:
                group.endpoints.append(endpoint)
        
        try:
            db.session.commit()
            flash(f'Группа "{group.name}" успешно обновлена.', 'success')
            return redirect(url_for('admin.groups'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка обновления группы: {e}', 'danger')
    
    selected_endpoints = [e.id for e in group.endpoints]
    return render_template('admin/edit_group.html', form=form, group=group,
                         endpoints=endpoints, selected_endpoints=selected_endpoints)

@admin_bp.route('/groups/<int:group_id>/delete')
@login_required
@admin_required
def delete_group(group_id):
    """Удаление группы"""
    group = Group.query.get_or_404(group_id)
    
    # Нельзя удалить группу по умолчанию
    if group.name == 'Default':
        flash('Нельзя удалить группу по умолчанию.', 'danger')
        return redirect(url_for('admin.groups'))
    
    # Находим группу по умолчанию
    default_group = Group.query.filter_by(name='Default').first()
    if not default_group:
        flash('Группа по умолчанию не найдена. Сначала создайте группу "Default".', 'danger')
        return redirect(url_for('admin.groups'))
    
    # Перемещаем всех пользователей в группу по умолчанию
    users_in_group = User.query.filter_by(group_id=group_id).all()
    for user in users_in_group:
        user.group_id = default_group.id
    
    try:
        db.session.delete(group)
        db.session.commit()
        flash(f'Группа "{group.name}" успешно удалена. Пользователи перемещены в группу по умолчанию.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка удаления группы: {e}', 'danger')
    
    return redirect(url_for('admin.groups'))