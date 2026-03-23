#!/usr/bin/env python3
"""
Миграция для добавления поддержки групп пользователей.
Создает таблицы groups, group_endpoints и добавляет колонку group_id в users.
"""

import sqlite3
import os
import sys

def migrate_database(db_path):
    """Выполнить миграцию БД"""
    
    if not os.path.exists(db_path):
        print(f"База данных не найдена: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли уже колонка group_id
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'group_id' in columns:
            print("Миграция уже выполнена (колонка group_id существует)")
            return True
        
        print("Начинаем миграцию...")
        
        # 1. Создаем таблицу groups
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✓ Создана таблица groups")
        
        # 2. Добавляем колонку group_id в users
        cursor.execute('''
            ALTER TABLE users ADD COLUMN group_id INTEGER REFERENCES groups(id)
        ''')
        print("✓ Добавлена колонка group_id в таблицу users")
        
        # 3. Создаем таблицу связи group_endpoints
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_endpoints (
                group_id INTEGER NOT NULL,
                endpoint_id INTEGER NOT NULL,
                PRIMARY KEY (group_id, endpoint_id),
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (endpoint_id) REFERENCES endpoints(id)
            )
        ''')
        print("✓ Создана таблица group_endpoints")
        
        # 4. Создаем таблицу связи endpoint_config_types (если не существует)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS endpoint_config_types (
                endpoint_id INTEGER NOT NULL,
                config_type_id INTEGER NOT NULL,
                PRIMARY KEY (endpoint_id, config_type_id),
                FOREIGN KEY (endpoint_id) REFERENCES endpoints(id),
                FOREIGN KEY (config_type_id) REFERENCES config_types(id)
            )
        ''')
        print("✓ Создана таблица endpoint_config_types")
        
        conn.commit()
        print("\n✅ Миграция успешно завершена!")
        return True
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"\n❌ Ошибка миграции: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    # Путь к БД по умолчанию
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'warp_manager.db')
    
    # Можно передать путь как аргумент
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"Миграция БД: {db_path}")
    print("-" * 50)
    
    success = migrate_database(db_path)
    sys.exit(0 if success else 1)
