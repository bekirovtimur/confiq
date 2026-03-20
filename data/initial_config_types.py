"""
Начальные шаблоны типов конфигураций для Confiq.

Этот файл содержит базовые шаблоны для различных типов VPN клиентов:
- WireGuard: стандартный WireGuard конфиг
- AmneziaWG: WireGuard с обфускацией
- Clash: YAML конфиг для Clash клиента
"""

# Шаблон WireGuard конфигурации
WIREGUARD_TEMPLATE = """[Interface]
PrivateKey = {{ private_key }}
Address = {{ client_ipv4 }}/32, {{ client_ipv6 }}/128
DNS = 1.1.1.1, 1.0.0.1, 2606:4700:4700::1111, 2606:4700:4700::1001
MTU = 1280

[Peer]
PublicKey = {{ peer_public_key }}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {{ endpoint }}:{{ port }}
PersistentKeepalive = 25
"""

WIREGUARD_INSTRUCTIONS = """
<div class="usage-instructions">
    <h4>Инструкция по использованию WireGuard</h4>
    
    <h5>1. Установите клиент WireGuard:</h5>
    <ul>
        <li><strong>Windows/macOS:</strong> Скачайте с <a href="https://www.wireguard.com/install/" target="_blank">официального сайта</a></li>
        <li><strong>iOS:</strong> App Store - поиск "WireGuard"</li>
        <li><strong>Android:</strong> Google Play - поиск "WireGuard"</li>
        <li><strong>Linux:</strong> <code>sudo apt install wireguard</code> или <code>sudo yum install wireguard-tools</code></li>
    </ul>
    
    <h5>2. Импорт конфигурации:</h5>
    <ul>
        <li>Скачайте файл конфигурации (.conf)</li>
        <li>Откройте WireGuard клиент</li>
        <li>Нажмите "Import tunnel from file" или "Добавить туннель"</li>
        <li>Выберите скачанный файл</li>
    </ul>
    
    <h5>3. Подключение:</h5>
    <ul>
        <li>Нажмите "Activate" или "Подключить"</li>
        <li>Проверьте подключение на <a href="https://1.1.1.1/help" target="_blank">1.1.1.1/help</a></li>
    </ul>
    
        <strong>Совет:</strong> Для автоматического подключения при запуске, включите опцию "Activate on boot" в настройках туннеля.
</div>
"""

WIREGUARD_CLIENT_LINKS = """{
    "windows": "https://www.wireguard.com/install/",
    "macos": "https://www.wireguard.com/install/",
    "ios": "https://apps.apple.com/us/app/wireguard/id1441195209",
    "android": "https://play.google.com/store/apps/details?id=com.wireguard.android",
    "linux": "https://www.wireguard.com/install/"
}"""

# Шаблон AmneziaWG конфигурации
AMNEZIAWG_TEMPLATE = """[Interface]
PrivateKey = {{ private_key }}
Address = {{ client_ipv4 }}/32, {{ client_ipv6 }}/128
DNS = 1.1.1.1, 1.0.0.1, 2606:4700:4700::1111, 2606:4700:4700::1001
MTU = 1280
Jc = 120
Jmin = 23
Jmax = 911
S1 = 0
S2 = 0
H1 = 1
H2 = 2
H3 = 3
H4 = 4

[Peer]
PublicKey = {{ peer_public_key }}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {{ endpoint }}:{{ port }}
PersistentKeepalive = 25
"""

AMNEZIAWG_INSTRUCTIONS = """
<div class="usage-instructions">
    <h4>Инструкция по использованию AmneziaWG</h4>
    
    <h5>1. Установите клиент AmneziaWG:</h5>
    <ul>
        <li><strong>Windows:</strong> Скачайте с <a href="https://github.com/amnezia-vpn/amneziawg-windows-client/releases" target="_blank">GitHub Releases</a></li>
        <li><strong>macOS:</strong> Скачайте с <a href="https://github.com/amnezia-vpn/amneziawg-macos-client/releases" target="_blank">GitHub Releases</a></li>
        <li><strong>iOS:</strong> App Store - поиск "AmneziaWG"</li>
        <li><strong>Android:</strong> Google Play - поиск "AmneziaWG" или APK с <a href="https://github.com/amnezia-vpn/amneziawg-android/releases" target="_blank">GitHub</a></li>
        <li><strong>Linux:</strong> Следуйте инструкциям на <a href="https://github.com/amnezia-vpn/amneziawg-linux-kernel-module" target="_blank">GitHub</a></li>
    </ul>
    
    <h5>2. Что такое AmneziaWG?</h5>
    <p>AmneziaWG - это форк WireGuard с добавлением обфускации трафика. Параметры Jc, Jmin, Jmax добавляют "шум" в пакеты, что помогает обходить блокировки DPI (Deep Packet Inspection).</p>
    
    <h5>3. Импорт конфигурации:</h5>
    <ul>
        <li>Скачайте файл конфигурации (.conf)</li>
        <li>Откройте AmneziaWG клиент</li>
        <li>Нажмите "Import tunnel from file"</li>
        <li>Выберите скачанный файл</li>
    </ul>
    
    <h5>4. Подключение:</h5>
    <ul>
        <li>Нажмите "Activate" для подключения</li>
        <li>Значок туннеля станет зелёным при успешном подключении</li>
    </ul>
    
        <strong>Важно:</strong> AmneziaWG несовместим с обычным WireGuard. Убедитесь, что на всех устройствах используется AmneziaWG клиент.
</div>
"""

AMNEZIAWG_CLIENT_LINKS = """{
    "windows": "https://github.com/amnezia-vpn/amneziawg-windows-client/releases",
    "macos": "https://github.com/amnezia-vpn/amneziawg-macos-client/releases",
    "ios": "https://apps.apple.com/us/app/amneziawg/id1234567890",
    "android": "https://play.google.com/store/apps/details?id=org.amnezia.amneziawg",
    "linux": "https://github.com/amnezia-vpn/amneziawg-linux-kernel-module"
}"""

# Шаблон Clash конфигурации
CLASH_TEMPLATE = """mixed-port: 7890
allow-lan: false
bind-address: '*'
mode: rule
log-level: info
external-controller: 127.0.0.1:9090
unified-delay: true

profile:
  store-selected: true
  store-fake-ip: true

dns:
  enable: true
  listen: 0.0.0.0:1053
  default-nameserver:
    - 223.5.5.5
    - 8.8.8.8
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  use-hosts: true
  nameserver:
    - https://doh.pub/dns-query
    - https://dns.alidns.com/dns-query
  fallback:
    - https://1.1.1.1/dns-query
    - https://dns.cloudflare.com/dns-query
  fallback-filter:
    geoip: true
    geoip-code: CN
    ipcidr:
      - 240.0.0.0/4

proxies:
  - name: "WARP-{{ endpoint }}"
    type: wireguard
    server: {{ endpoint }}
    port: {{ port }}
    ip: {{ client_ipv4 }}
    ipv6: {{ client_ipv6 }}
    private-key: {{ private_key }}
    public-key: {{ peer_public_key }}
    udp: true
    reserved: []

proxy-groups:
  - name: "PROXY"
    type: select
    proxies:
      - "WARP-{{ endpoint }}"
      - "DIRECT"

rules:
  - GEOIP,CN,DIRECT
  - GEOSITE,cn,DIRECT
  - MATCH,PROXY
"""

CLASH_INSTRUCTIONS = """
<div class="usage-instructions">
    <h4>Инструкция по использованию Clash</h4>
    
    <h5>1. Установите клиент Clash:</h5>
    <ul>
        <li><strong>Windows:</strong> Clash Verge Rev, Clash for Windows, или Clash Verge</li>
        <li><strong>macOS:</strong> Clash Verge Rev, ClashX, ClashX Pro</li>
        <li><strong>iOS:</strong> Stash, Shadowrocket (платные)</li>
        <li><strong>Android:</strong> Clash for Android, Clash Meta for Android</li>
        <li><strong>Linux:</strong> Clash Verge Rev</li>
    </ul>
    
    <h5>2. Рекомендуемые клиенты:</h5>
    <table class="table table-sm">
        <tr>
            <td><strong>Windows/macOS/Linux:</strong></td>
            <td><a href="https://github.com/clash-verge-rev/clash-verge-rev/releases" target="_blank">Clash Verge Rev</a> (бесплатный, рекомендуется)</td>
        </tr>
        <tr>
            <td><strong>iOS:</strong></td>
            <td>Stash (App Store, ~$3.99)</td>
        </tr>
        <tr>
            <td><strong>Android:</strong></td>
            <td><a href="https://github.com/MetaCubeX/ClashMetaForAndroid/releases" target="_blank">Clash Meta for Android</a></td>
        </tr>
    </table>
    
    <h5>3. Импорт конфигурации:</h5>
    <ul>
        <li>Скачайте файл конфигурации (.yaml или .yml)</li>
        <li>В Clash клиенте нажмите "Profiles" → "Import"</li>
        <li>Выберите скачанный файл или перетащите его в окно</li>
        <li>Активируйте профиль кликом по нему</li>
    </ul>
    
    <h5>4. Настройка системного прокси:</h5>
    <ul>
        <li>Включите "System Proxy" в главном окне Clash</li>
        <li>Или настройте приложения на использование HTTP прокси 127.0.0.1:7890</li>
    </ul>
    
    <h5>5. Управление через веб-интерфейс:</h5>
    <ul>
        <li>Откройте http://127.0.0.1:9090/ui в браузере</li>
        <li>Или используйте встроенный интерфейс клиента</li>
    </ul>
    
        <strong>Преимущества Clash:</strong> Поддержка правил маршрутизации (rules), автоматическое переключение прокси, встроенный DNS с fake-ip.
</div>
"""

CLASH_CLIENT_LINKS = """{
    "windows": "https://github.com/clash-verge-rev/clash-verge-rev/releases",
    "macos": "https://github.com/clash-verge-rev/clash-verge-rev/releases",
    "ios": "https://apps.apple.com/us/app/stash/id1582679995",
    "android": "https://github.com/MetaCubeX/ClashMetaForAndroid/releases",
    "linux": "https://github.com/clash-verge-rev/clash-verge-rev/releases"
}"""

# Список всех начальных типов конфигураций
INITIAL_CONFIG_TYPES = [
    {
        "name": "WireGuard",
        "description": "Стандартный WireGuard клиент. Простой, быстрый, безопасный VPN протокол.",
        "config_template": WIREGUARD_TEMPLATE,
        "usage_instructions": WIREGUARD_INSTRUCTIONS,
        "client_links": WIREGUARD_CLIENT_LINKS,
        "is_active": True
    },
    {
        "name": "AmneziaWG",
        "description": "WireGuard с обфускацией трафика. Помогает обходить DPI блокировки.",
        "config_template": AMNEZIAWG_TEMPLATE,
        "usage_instructions": AMNEZIAWG_INSTRUCTIONS,
        "client_links": AMNEZIAWG_CLIENT_LINKS,
        "is_active": True
    },
    {
        "name": "Clash",
        "description": "Clash/Mihomo прокси-клиент с поддержкой правил маршрутизации и WireGuard.",
        "config_template": CLASH_TEMPLATE,
        "usage_instructions": CLASH_INSTRUCTIONS,
        "client_links": CLASH_CLIENT_LINKS,
        "is_active": True
    }
]


def get_initial_config_types():
    """
    Возвращает список начальных типов конфигураций для инициализации БД.
    
    Returns:
        list: Список словарей с данными типов конфигураций
    """
    return INITIAL_CONFIG_TYPES
