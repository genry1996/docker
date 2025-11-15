import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
import requests
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from database import Database
from config import PROXY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PLAYWRIGHT, BETTING_SITES

RUN_INTERVAL_SEC = 5 * 60
MARKET_NAME = "1X2"


def tg_send(text: str):
    """Отправка уведомления в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=6)
    except Exception as e:
        logging.warning(f"⚠️ Telegram error: {e}")


async def parse_via_browser(db: Database, mirror_url: str):
    logging.info(f"🌍 Открываю зеркало: {mirror_url}")
    proxy_enabled = PROXY.get("enabled", False)
    proxy_server = PROXY.get("server", "")
    context_kwargs = {"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    if proxy_enabled and proxy_server:
        s = proxy_server.replace("http://", "").replace("https://", "")
        if "@" in s:
            creds, hostport = s.split("@", 1)
            user, password = creds.split(":")
            proxy_dict = {"server": f"http://{hostport}", "username": user, "password": password}
        else:
            proxy_dict = {"server": f"http://{s}"}
        context_kwargs["proxy"] = proxy_dict
        logging.info(f"🌍 Использую прокси: {proxy_server}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=PLAYWRIGHT["headless"], slow_mo=PLAYWRIGHT["slow_mo"])
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        try:
            await page.goto(mirror_url, timeout=PLAYWRIGHT["timeout"])
            await page.wait_for_timeout(3000)
            await page.wait_for_selector("div.c-events__item", timeout=20000)

            match_cards = await page.query_selector_all("div.c-events__item")
            logging.info(f"📊 Найдено матчей: {len(match_cards)}")

            for m in match_cards[:200]:
                try:
                    teams = await m.query_selector_all("span.c-events__team-name")
                    if len(teams) < 2:
                        continue
                    home = (await teams[0].inner_text()).strip()
                    away = (await teams[1].inner_text()).strip()
                    odds_elems = await m.query_selector_all("a.c-betting__item")
                    if len(odds_elems) < 3:
                        continue

                    def clean(o):
                        try:
                            return float(o.strip().replace(",", "."))
                        except Exception:
                            return None

                    odds = [clean(await e.inner_text()) for e in odds_elems[:3]]
                    if any(o is None for o in odds):
                        continue

                    match_id = abs(hash(f"{home}_{away}")) % (10 ** 10)
                    await db.insert_match(match_id, 1, home, away, datetime.now(), "live")
                    await db.insert_market(match_id, MARKET_NAME)

                    outcomes = [f"{home} win", "Draw", f"{away} win"]
                    for outcome, val in zip(outcomes, odds):
                        await db.insert_odd(1, outcome, val)
                        await db.insert_odds_history(match_id, outcome, val)

                    # === Проверка аномальных падений ===
                    last = await db.get_last_odd_change(match_id)
                    if last:
                        diffs = [abs(o - l) / l if l else 0 for o, l in zip(odds, last)]
                        if any(d > 0.15 for d in diffs):
                            await db.set_anomaly_flag(match_id, True)
                            tg_send(f"⚠️ Аномалия {home} vs {away}: {odds}")
                        elif any(d >= 0.05 for d in diffs):
                            tg_send(f"📈 {home} vs {away}: движение линии {odds}")

                except Exception as inner:
                    logging.warning(f"⚠️ Ошибка обработки матча: {inner}")

            await browser.close()
            return True

        except PlaywrightTimeout:
            logging.warning(f"⏳ Таймаут загрузки {mirror_url}")
        except Exception as e:
            logging.warning(f"⚠️ Ошибка при парсинге {mirror_url}: {e}")
        finally:
            await browser.close()
    return False


async def run_once():
    mirrors = BETTING_SITES["22bet"]["mirrors"]
    db = await Database.create()
    for mirror in mirrors:
        success = await parse_via_browser(db, mirror)
        if success:
            tg_send(f"✅ Парсинг завершён успешно ({mirror})")
            await db.close()
            return
    logging.info("❌ Все зеркала дали таймаут.")
    await db.close()


async def main_loop():
    logging.info(f"⏱️ Цикл парсинга каждые {RUN_INTERVAL_SEC} сек.")
    while True:
        try:
            await run_once()
        except Exception as e:
            logging.exception(f"❌ Критическая ошибка: {e}")
            tg_send(f"❌ Ошибка парсера: {e}")
        await asyncio.sleep(RUN_INTERVAL_SEC)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logging.info("🛑 Остановлено пользователем.")
