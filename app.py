import os
import logging
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_required, logout_user
from dotenv import load_dotenv
from models import db, User, Endpoint, ConfigType, Group
from auth import auth_bp
from routes.admin import admin_bp
from routes.user import user_bp

# Загружаем переменные окружения
load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Конфигурация
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-me-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:////{os.path.abspath("/data/warp_manager.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Настройка логирования
    logging.basicConfig(level=logging.INFO)
    
    # Инициализация расширений
    db.init_app(app)
    
    # Настройка Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Необходимо войти в систему для доступа к этой странице.'
    login_manager.login_message_category = 'warning'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Регистрация маршрутов
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(user_bp, url_prefix='/user')
    
    # Главная страница
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))
    
    # Выход из системы
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Вы успешно вышли из системы.', 'info')
        return redirect(url_for('auth.login'))
    
    # Обработчики ошибок
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
    
    # Создание таблиц и администратора по умолчанию
    with app.app_context():
        # Создаем директорию для БД если её нет
        os.makedirs('/data', exist_ok=True)
        
        # Создаем таблицы
        db.create_all()
        
        try:
            # Создаем группу по умолчанию, если её нет
            default_group = Group.query.filter_by(name='Default').first()
            if not default_group:
                default_group = Group(
                    name='Default',
                    description='Группа по умолчанию для всех пользователей'
                )
                db.session.add(default_group)
                db.session.flush()  # Получаем ID группы до commit
            
            # Создаем администратора по умолчанию, если его нет
            admin = User.query.filter_by(username=os.getenv('ADMIN_LOGIN', 'admin')).first()
            if not admin:
                admin = User(
                    username=os.getenv('ADMIN_LOGIN', 'admin'),
                    is_admin=True,
                    config_limit=999,  # Неограниченно для админа
                    group_id=default_group.id
                )
                admin.set_password(os.getenv('ADMIN_PASSWORD', 'admin123'))
                db.session.add(admin)
                
                # Создаем несколько endpoints по умолчанию
                endpoints = [
                    Endpoint(name='Cloudflare WARP (Original)', address='engage.cloudflareclient.com', port=2408),
                    Endpoint(name='Cloudflare WARP (Alternative 1)', address='162.159.193.10', port=2408),
                    Endpoint(name='Cloudflare WARP (Alternative 2)', address='162.159.192.1', port=2408),
                    Endpoint(name='Custom Endpoint', address='1.1.1.1', port=2408)
                ]
                
                for endpoint in endpoints:
                    endpoint.groups.append(default_group)
                    db.session.add(endpoint)
                
                db.session.commit()
                app.logger.info("База данных инициализирована с администратором по умолчанию")
        except Exception as e:
            db.session.rollback()
            app.logger.warning(f"Инициализация БД пропущена (возможно, уже выполнена другим воркером): {e}")
        
        # Инициализация начальных типов конфигураций
        try:
            # Импортируем начальные типы конфигураций
            from data.initial_config_types import get_initial_config_types
            
            initial_types = get_initial_config_types()
            types_created = 0
            
            for type_data in initial_types:
                # Проверяем, существует ли уже такой тип
                existing_type = ConfigType.query.filter_by(name=type_data['name']).first()
                if not existing_type:
                    config_type = ConfigType(
                        name=type_data['name'],
                        description=type_data['description'],
                        config_template=type_data['config_template'],
                        usage_instructions=type_data['usage_instructions'],
                        client_links=type_data['client_links'],
                        is_active=type_data['is_active']
                    )
                    db.session.add(config_type)
                    types_created += 1
                    app.logger.info(f"Добавлен тип конфигурации: {type_data['name']}")
            
            if types_created > 0:
                db.session.commit()
                app.logger.info(f"Инициализировано {types_created} типов конфигураций")
            else:
                app.logger.info("Типы конфигураций уже существуют, пропускаем инициализацию")
            
            # Привязка endpoints к типу WireGuard по умолчанию (для совместимости)
            wireguard_type = ConfigType.query.filter_by(name='WireGuard').first()
            if wireguard_type:
                endpoints_without_types = Endpoint.query.filter(~Endpoint.config_types.any()).all()
                if endpoints_without_types:
                    for endpoint in endpoints_without_types:
                        endpoint.config_types.append(wireguard_type)
                        app.logger.info(f"Endpoint '{endpoint.name}' привязан к типу WireGuard по умолчанию")
                    db.session.commit()
                    app.logger.info(f"Привязано {len(endpoints_without_types)} endpoints к типу WireGuard")
                else:
                    app.logger.info("Все endpoints уже имеют привязанные типы конфигураций")
            else:
                app.logger.warning("Тип WireGuard не найден, пропускаем привязку endpoints")
                
        except ImportError as e:
            app.logger.warning(f"Не удалось импортировать начальные типы конфигураций: {e}")
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Ошибка инициализации типов конфигураций: {e}")
    
    return app

# Создание приложения
app = create_app()

# Контекстные процессоры для шаблонов
@app.context_processor
def inject_user_data():
    from flask_login import current_user
    return dict(current_user=current_user)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
