"""Optional real-browser checks: pip install playwright, then install Chromium.

Uses Flask's isolated test client, not app.py, a live server or the working DB.
"""
import shutil
import unittest
from urllib.parse import urlsplit

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
except ImportError:
    sync_playwright = None

import test_qr_routes


@unittest.skipUnless(sync_playwright, 'Optional dependency: playwright')
class ConfigMenuBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        executable = shutil.which('google-chrome') or shutil.which('chromium')
        try:
            cls.browser = cls.playwright.chromium.launch(executable_path=executable)
        except PlaywrightError as error:
            cls.playwright.stop()
            raise unittest.SkipTest('Chromium unavailable; install with python -m playwright install chromium') from error

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.fixture = test_qr_routes.QRRouteTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.page = self.browser.new_page(viewport={'width': 922, 'height': 705})
        self.addCleanup(self.page.close)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))

        def serve(route):
            url = urlsplit(route.request.url)
            if url.netloc != 'confiq.test':
                route.abort()
                return
            with self.fixture.client.get(url.path + ('?' + url.query if url.query else '')) as response:
                route.fulfill(status=response.status_code, body=response.data,
                              content_type=response.content_type)

        self.page.route('**/*', serve)

    def open_menu(self, config_id, top, left):
        trigger = self.page.locator(f'[data-config-menu="configMenu{config_id}"]')
        trigger.evaluate('(el, pos) => Object.assign(el.style, {position: "fixed", top: pos.top + "px", left: pos.left + "px", zIndex: "1100"})',
                         {'top': top, 'left': left})
        trigger.click()
        menu = self.page.locator(f'#configMenu{config_id}')
        self.assertTrue(menu.is_visible())
        self.assertEqual(trigger.get_attribute('aria-expanded'), 'true')
        self.assertTrue(menu.evaluate('el => el.parentNode === document.body'))
        rect = menu.bounding_box()
        viewport = self.page.viewport_size
        self.assertGreaterEqual(rect['x'], 7)
        self.assertGreaterEqual(rect['y'], 7)
        self.assertLessEqual(rect['x'] + rect['width'], viewport['width'] - 7)
        self.assertLessEqual(rect['y'] + rect['height'], viewport['height'] - 7)
        return trigger, menu, rect

    def test_both_pages_open_upward_at_bottom_and_downward_at_top(self):
        for path in ['/user/dashboard', '/user/configs']:
            for config_id in [self.fixture.small, self.fixture.large]:
                with self.subTest(path=path, config_id=config_id):
                    self.page.goto('http://confiq.test' + path)
                    trigger, menu, rect = self.open_menu(config_id, 620, 850)
                    self.assertLess(rect['y'] + rect['height'], 620)
                    # The last action is not clipped by the dashboard's outer card.
                    self.assertTrue(menu.locator('.md-menu-item').last.evaluate('el => { const r = el.getBoundingClientRect(); return el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)); }'))
                    self.page.keyboard.press('Escape')
                    self.assertFalse(menu.is_visible())
                    self.assertEqual(trigger.get_attribute('aria-expanded'), 'false')
                    self.assertTrue(trigger.evaluate('el => el === document.activeElement'))
                    _, menu, rect = self.open_menu(config_id, 80, 8)
                    self.assertGreater(rect['y'], 120)
                    self.page.mouse.click(500, 350)
                    self.assertFalse(menu.is_visible())
                    self.assertEqual(self.errors, [])

    def test_small_viewport_allows_menu_scrolling_and_delete_action(self):
        self.page.set_viewport_size({'width': 320, 'height': 240})
        self.page.goto('http://confiq.test/user/dashboard')
        _, menu, _ = self.open_menu(self.fixture.small, 100, 270)
        self.assertTrue(menu.evaluate('el => el.scrollHeight > el.clientHeight'))
        menu.evaluate('el => { el.scrollTop = el.scrollHeight; }')
        self.page.wait_for_timeout(100)
        self.assertTrue(menu.is_visible())
        menu.locator('.md-menu-item').last.click()
        self.assertFalse(menu.is_visible())
        self.assertTrue(self.page.locator('#deleteModal').is_visible())
        self.assertEqual(self.errors, [])

    def test_toggle_switch_scroll_and_resize_close_menu(self):
        self.page.goto('http://confiq.test/user/configs')
        trigger, menu, _ = self.open_menu(self.fixture.small, 100, 600)
        trigger.click()
        self.assertFalse(menu.is_visible())
        self.open_menu(self.fixture.small, 100, 600)
        self.open_menu(self.fixture.large, 200, 800)
        self.assertFalse(menu.is_visible())
        active = self.page.locator(f'#configMenu{self.fixture.large}')
        self.page.evaluate('window.scrollBy(0, 100)')
        self.page.wait_for_timeout(100)
        self.assertFalse(active.is_visible())
        self.open_menu(self.fixture.small, 100, 600)
        self.page.set_viewport_size({'width': 800, 'height': 600})
        self.page.wait_for_timeout(100)
        self.assertFalse(menu.is_visible())
        self.assertEqual(self.errors, [])


if __name__ == '__main__':
    unittest.main()
