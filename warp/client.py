import subprocess
import requests
import json
import logging
import warnings
from datetime import datetime

logger = logging.getLogger(__name__)

class WarpAPI:
    API_BASE = "https://api.cloudflareclient.com/v0i1909051800"
    
    @staticmethod
    def _warn_deprecated():
        """Выводит предупреждение об устаревании модуля."""
        warnings.warn(
            "Модуль warp.client устарел. Используйте generators.get_generator() вместо этого. "
            "См. документацию: from generators import get_generator",
            DeprecationWarning,
            stacklevel=3
        )
    
    @staticmethod
    def generate_keys():
        """Генерирует приватный и публичный ключи WireGuard"""
        WarpAPI._warn_deprecated()
        try:
            # Генерируем приватный ключ
            private_key = subprocess.check_output(
                ["wg", "genkey"], 
                stderr=subprocess.DEVNULL
            ).decode('utf-8').strip()
            
            # Генерируем публичный ключ из приватного
            public_key = subprocess.check_output(
                ["wg", "pubkey"], 
                input=private_key.encode('utf-8'),
                stderr=subprocess.DEVNULL
            ).decode('utf-8').strip()
            
            return private_key, public_key
        except Exception as e:
            logger.error(f"Ошибка генерации ключей: {e}")
            raise Exception(f"Не удалось сгенерировать ключи WireGuard: {e}")
    
    @staticmethod
    def register_device(public_key):
        """Регистрирует устройство в Cloudflare"""
        WarpAPI._warn_deprecated()
        headers = {
            'User-Agent': 'okhttp/3.12.1',
            'Content-Type': 'application/json'
        }
        
        data = {
            "install_id": "",
            "tos": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "key": public_key,
            "fcm_token": "",
            "type": "ios",
            "locale": "en_US"
        }
        
        try:
            response = requests.post(
                f"{WarpAPI.API_BASE}/reg", 
                headers=headers, 
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            if 'result' not in result:
                raise Exception(f"Неверный формат ответа: {result}")
            
            device_id = result['result'].get('id')
            token = result['result'].get('token')
            
            if not device_id or not token:
                raise Exception(f"Не получены ID или токен: {result}")
            
            return device_id, token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка регистрации устройства: {e}")
            raise Exception(f"Не удалось зарегистрировать устройство: {e}")
        except Exception as e:
            logger.error(f"Общая ошибка регистрации: {e}")
            raise
    
    @staticmethod
    def enable_warp(device_id, token):
        """Включает WARP для устройства"""
        WarpAPI._warn_deprecated()
        headers = {
            'User-Agent': 'okhttp/3.12.1',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        data = {"warp_enabled": True}
        
        try:
            response = requests.patch(
                f"{WarpAPI.API_BASE}/reg/{device_id}", 
                headers=headers, 
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            if 'result' not in result or 'config' not in result['result']:
                raise Exception(f"Неверный формат ответа: {result}")
            
            config_data = result['result']['config']
            
            peer_public_key = config_data['peers'][0]['public_key']
            client_ipv4 = config_data['interface']['addresses']['v4']
            client_ipv6 = config_data['interface']['addresses']['v6']
            
            return peer_public_key, client_ipv4, client_ipv6
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка включения WARP: {e}")
            raise Exception(f"Не удалось включить WARP: {e}")
        except Exception as e:
            logger.error(f"Общая ошибка включения WARP: {e}")
            raise
    
    @staticmethod
    def create_config(endpoint_address, endpoint_port):
        """Создает полную конфигурацию WARP"""
        WarpAPI._warn_deprecated()
        try:
            # 1. Генерируем ключи
            private_key, public_key = WarpAPI.generate_keys()
            
            # 2. Регистрируем устройство
            device_id, token = WarpAPI.register_device(public_key)
            
            # 3. Включаем WARP
            peer_public_key, client_ipv4, client_ipv6 = WarpAPI.enable_warp(device_id, token)
            
            # 4. Формируем конфиг
            config_content = f"""[Interface]
PrivateKey = {private_key}
MTU = 1280
Address = {client_ipv4}, {client_ipv6}
DNS = 1.1.1.1, 2606:4700:4700::1111, 1.0.0.1, 2606:4700:4700::1001

[Peer]
PublicKey = {peer_public_key}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {endpoint_address}:{endpoint_port}"""
            
            return {
                'device_id': device_id,
                'token': token,
                'private_key': private_key,
                'public_key': public_key,
                'peer_public_key': peer_public_key,
                'client_ipv4': client_ipv4,
                'client_ipv6': client_ipv6,
                'config_content': config_content
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания конфига: {e}")
            raise
    
    @staticmethod
    def delete_config(device_id, token):
        """Удаляет устройство из Cloudflare"""
        WarpAPI._warn_deprecated()
        headers = {
            'User-Agent': 'okhttp/3.12.1',
            'Authorization': f'Bearer {token}'
        }
        
        try:
            response = requests.delete(
                f"{WarpAPI.API_BASE}/reg/{device_id}",
                headers=headers,
                timeout=30
            )
            
            # Считаем успешными коды 200 и 204 (как в оригинальном скрипте)
            if response.status_code not in [200, 204]:
                raise Exception(f"Cloudflare вернул код: {response.status_code}")
            
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка удаления конфига: {e}")
            raise Exception(f"Не удалось удалить устройство из Cloudflare: {e}")
        except Exception as e:
            logger.error(f"Общая ошибка удаления: {e}")
            raise