from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import bcrypt

db = SQLAlchemy()

# Таблица связи many-to-many между Endpoint и ConfigType
endpoint_config_types = db.Table('endpoint_config_types',
    db.Column('endpoint_id', db.Integer, db.ForeignKey('endpoints.id'), primary_key=True),
    db.Column('config_type_id', db.Integer, db.ForeignKey('config_types.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    config_limit = db.Column(db.Integer, default=5)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    configs = db.relationship('Config', backref='owner', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        """Установить хешированный пароль"""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        """Проверить пароль"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def get_config_count(self):
        """Получить количество конфигов пользователя"""
        return len(self.configs)
    
    def can_create_config(self):
        """Проверить, может ли пользователь создать еще один конфиг"""
        return self.get_config_count() < self.config_limit

class ConfigType(db.Model):
    __tablename__ = 'config_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    config_template = db.Column(db.Text, nullable=False)
    usage_instructions = db.Column(db.Text, nullable=True)
    client_links = db.Column(db.Text, nullable=True)  # JSON ссылок на клиенты
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship с Config
    configs = db.relationship('Config', backref='config_type', lazy=True)
    
    def __repr__(self):
        return f'<ConfigType {self.name}>'

class Endpoint(db.Model):
    __tablename__ = 'endpoints'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    configs = db.relationship('Config', backref='endpoint_ref', lazy=True)
    
    # Relationship с ConfigType через таблицу связи
    config_types = db.relationship('ConfigType', secondary=endpoint_config_types,
                                   backref=db.backref('endpoints', lazy=True),
                                   lazy=True)
    
    @property
    def full_address(self):
        """Полный адрес endpoint'a"""
        return f"{self.address}:{self.port}"

class Config(db.Model):
    __tablename__ = 'configs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    endpoint_id = db.Column(db.Integer, db.ForeignKey('endpoints.id'), nullable=False)
    config_type_id = db.Column(db.Integer, db.ForeignKey('config_types.id'), nullable=True)
    cloudflare_id = db.Column(db.String(100), nullable=False)
    cloudflare_token = db.Column(db.String(255), nullable=False)
    private_key = db.Column(db.Text, nullable=False)
    public_key = db.Column(db.Text, nullable=False)
    peer_public_key = db.Column(db.Text, nullable=False)
    client_ipv4 = db.Column(db.String(50), nullable=False)
    client_ipv6 = db.Column(db.String(50), nullable=False)
    config_content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
