# -*- coding: utf-8 -*-
"""
====================================================================
 ربات سازنده دکمه شیشه‌ای رنگی + ایموجی پریمیوم تلگرام (نسخه مخصوص Render)
====================================================================

قابلیت‌های کلیدی:
  - تمام متن‌های ربات و تمام دکمه‌های شیشه‌ای منوها مجهز به ایموجی‌های پریمیوم و متحرک تلگرام (tg-emoji + icon_custom_emoji_id)
  - ساخت دکمه شیشه‌ای رنگی (آبی، سبز، قرمز، معمولی) روی متن، عکس، ویدیو، فایل و گیف
  - ارسال مستقیم پست به کانال انتخابی کاربر
  - سیستم اشتراک هوشمند:
      * اشتراک معمولی: روزانه حداکثر ۳ دکمه شیشه‌ای | ۳ روز اول بدون تبلیغ، پس از ۳ روز درج خودکار آیدی ربات زیر پست
      * اشتراک VIP (۳۰ روزه ۵۰,۰۰۰ تومان | ۳ ماهه ۱۹۹,۰۰۰ تومان): ساخت نامحدود روزانه + بدون تبلیغ + دسترسی به بخش ایموجی پریمیوم
  - بخش زیباسازی خودکار پست با ایموجی‌های پریمیوم تلگرام (مخصوص VIP) و ارسال به کانال
  - سیستم زیرمجموعه‌گیری (رفرال): شمارش زیرمجموعه فقط پس از عضویت در تمام کانال‌های جوین اجباری | هر ۶ زیرمجموعه = ۱۰ روز اشتراک VIP رایگان
  - تمام دکمه‌های ربات ۱۰۰٪ شیشه‌ای (Inline) و تمام‌رنگی با تم غالب آبی (primary)، سبز (success) و قرمز (danger)
  - پنل مدیریت حرفه‌ای با ۲۰ قابلیت کامل (فقط برای آیدی عددی 8248647747)
  - مجهز به وب‌سرور Flask و ارسال سیگنال قوی ضد خواب هر ۵ دقیقه (۳۰۰ ثانیه) به Render

اجرا:
    python bot.py
====================================================================
"""

import logging
import sqlite3
import os
import re
import time
import html
import threading
import requests
from flask import Flask, jsonify
from datetime import datetime, timedelta
from contextlib import closing

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ====================================================================
#  تنظیمات اصلی ربات و ادمین
# ====================================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8649807066:AAGZlazLVFr-jWDz8BURuFSP2K7WNRmRh-4")
ADMIN_ID = 8248647747
ADMIN_IDS = [8248647747]
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glass_button_bot.db")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ====================================================================
#  وب‌سرور Flask و سیستم ضد خواب قوی (Keep-Alive هر ۵ دقیقه) مخصوص Render
# ====================================================================

web_app = Flask(__name__)
START_TIME = datetime.now()
PING_COUNTER = 0

@web_app.route("/")
def home():
    return "✅ ربات دکمه شیشه‌ای رنگی و ایموجی پریمیوم با موفقیت روی Render فعال است (24/7 Active).", 200

@web_app.route("/health")
def health():
    global PING_COUNTER
    PING_COUNTER += 1
    uptime_seconds = int((datetime.now() - START_TIME).total_seconds())
    return jsonify({
        "status": "online",
        "bot": "glass_button_vip_bot",
        "ping_count": PING_COUNTER,
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.now().isoformat()
    }), 200

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    logger.info(f"🌐 وب‌سرور Keep-Alive روی پورت {port} راه‌اندازی شد.")
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def keep_alive_pinger():
    """ارسال سیگنال قوی هر ۵ دقیقه (۳۰۰ ثانیه) به آدرس خارجی Render برای جلوگیری کامل از خاموشی"""
    time.sleep(15)
    port = int(os.environ.get("PORT", 10000))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RenderKeepAlive/3.0",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive"
    }
    while True:
        try:
            render_external_url = os.environ.get("RENDER_EXTERNAL_URL")
            if render_external_url:
                target_url = f"{render_external_url.rstrip('/')}/health?ts={int(time.time())}"
                res = requests.get(target_url, headers=headers, timeout=15)
                logger.info(f"⚡ سیگنال ضد خواب ۵ دقیقه‌ای به Render ارسال شد ({target_url}) | وضعیت: {res.status_code}")
            else:
                local_url = f"http://127.0.0.1:{port}/health?ts={int(time.time())}"
                res = requests.get(local_url, headers=headers, timeout=10)
                logger.info(f"⚡ سیگنال ضد خواب داخلی ارسال شد | وضعیت: {res.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ خطا در ارسال سیگنال ضد خواب: {e}")

        time.sleep(300)  # دقیقاً ۵ دقیقه

def start_render_keep_alive():
    threading.Thread(target=run_flask_server, daemon=True).start()
    threading.Thread(target=keep_alive_pinger, daemon=True).start()

# ====================================================================
#  موتور ایموجی‌های پریمیوم و متحرک تلگرام (برای کل متن‌های ربات و دکمه‌ها)
# ====================================================================

EMOJI_IDS = {
    "fire": "5368324170671202286",      # 🔥
    "heart": "5334882760735598374",     # ❤️
    "gem": "5427009714745517609",       # 💎
    "check": "5206607081334906820",     # ✅
    "star": "5271604874419647061",      # ⭐
    "glow": "5350391536670567599",      # 🌟
    "party": "5461151367559141950",     # 🎉
    "rocket": "5445284980978621387",    # 🚀
    "zap": "5431449001532594346",       # ⚡
    "crown": "5409048419211682843",     # 👑
    "gift": "5472164874886846699",      # 🎁
    "money": "5375296873982604963",     # 💰
    "megaphone": "5424972470023104089", # 📢
    "sparkles": "5472055112702630502",  # ✨
    "hundred": "5386367538735104399",   # 💯
    "rose": "5440660757194744323",      # 🌹
    "love": "5373141891321699086",      # 😍
    "like": "5368324170671202286",      # 👍
}

PREMIUM_EMOJI_MAP = {
    "🔥": f'<tg-emoji emoji-id="{EMOJI_IDS["fire"]}">🔥</tg-emoji>',
    "❤️": f'<tg-emoji emoji-id="{EMOJI_IDS["heart"]}">❤️</tg-emoji>',
    "💎": f'<tg-emoji emoji-id="{EMOJI_IDS["gem"]}">💎</tg-emoji>',
    "✅": f'<tg-emoji emoji-id="{EMOJI_IDS["check"]}">✅</tg-emoji>',
    "⭐": f'<tg-emoji emoji-id="{EMOJI_IDS["star"]}">⭐</tg-emoji>',
    "🌟": f'<tg-emoji emoji-id="{EMOJI_IDS["glow"]}">🌟</tg-emoji>',
    "🎉": f'<tg-emoji emoji-id="{EMOJI_IDS["party"]}">🎉</tg-emoji>',
    "🚀": f'<tg-emoji emoji-id="{EMOJI_IDS["rocket"]}">🚀</tg-emoji>',
    "⚡": f'<tg-emoji emoji-id="{EMOJI_IDS["zap"]}">⚡</tg-emoji>',
    "👑": f'<tg-emoji emoji-id="{EMOJI_IDS["crown"]}">👑</tg-emoji>',
    "🎁": f'<tg-emoji emoji-id="{EMOJI_IDS["gift"]}">🎁</tg-emoji>',
    "💰": f'<tg-emoji emoji-id="{EMOJI_IDS["money"]}">💰</tg-emoji>',
    "💵": f'<tg-emoji emoji-id="{EMOJI_IDS["money"]}">💵</tg-emoji>',
    "💳": f'<tg-emoji emoji-id="{EMOJI_IDS["money"]}">💳</tg-emoji>',
    "📢": f'<tg-emoji emoji-id="{EMOJI_IDS["megaphone"]}">📢</tg-emoji>',
    "📣": f'<tg-emoji emoji-id="{EMOJI_IDS["megaphone"]}">📣</tg-emoji>',
    "✨": f'<tg-emoji emoji-id="{EMOJI_IDS["sparkles"]}">✨</tg-emoji>',
    "🎨": f'<tg-emoji emoji-id="{EMOJI_IDS["sparkles"]}">🎨</tg-emoji>',
    "💯": f'<tg-emoji emoji-id="{EMOJI_IDS["hundred"]}">💯</tg-emoji>',
    "🌹": f'<tg-emoji emoji-id="{EMOJI_IDS["rose"]}">🌹</tg-emoji>',
    "😍": f'<tg-emoji emoji-id="{EMOJI_IDS["love"]}">😍</tg-emoji>',
    "👍": f'<tg-emoji emoji-id="{EMOJI_IDS["like"]}">👍</tg-emoji>',
    "👋": f'<tg-emoji emoji-id="{EMOJI_IDS["sparkles"]}">👋</tg-emoji>',
    "🏆": f'<tg-emoji emoji-id="{EMOJI_IDS["crown"]}">🏆</tg-emoji>',
    "📊": f'<tg-emoji emoji-id="{EMOJI_IDS["zap"]}">📊</tg-emoji>',
    "👤": f'<tg-emoji emoji-id="{EMOJI_IDS["star"]}">👤</tg-emoji>',
    "👥": f'<tg-emoji emoji-id="{EMOJI_IDS["star"]}">👥</tg-emoji>',
    "📚": f'<tg-emoji emoji-id="{EMOJI_IDS["sparkles"]}">📚</tg-emoji>',
    "🏠": f'<tg-emoji emoji-id="{EMOJI_IDS["glow"]}">🏠</tg-emoji>',
    "🔗": f'<tg-emoji emoji-id="{EMOJI_IDS["zap"]}">🔗</tg-emoji>',
    "🏷": f'<tg-emoji emoji-id="{EMOJI_IDS["star"]}">🏷</tg-emoji>',
    "👁": f'<tg-emoji emoji-id="{EMOJI_IDS["sparkles"]}">👁</tg-emoji>',
    "🧾": f'<tg-emoji emoji-id="{EMOJI_IDS["check"]}">🧾</tg-emoji>',
    "⏳": f'<tg-emoji emoji-id="{EMOJI_IDS["zap"]}">⏳</tg-emoji>',
    "🔹": f'<tg-emoji emoji-id="{EMOJI_IDS["gem"]}">🔹</tg-emoji>',
    "🟢": f'<tg-emoji emoji-id="{EMOJI_IDS["check"]}">🟢</tg-emoji>',
    "🔵": f'<tg-emoji emoji-id="{EMOJI_IDS["gem"]}">🔵</tg-emoji>',
    "🔴": f'<tg-emoji emoji-id="{EMOJI_IDS["fire"]}">🔴</tg-emoji>',
    "❌": f'<tg-emoji emoji-id="{EMOJI_IDS["fire"]}">❌</tg-emoji>',
    "⛔": f'<tg-emoji emoji-id="{EMOJI_IDS["fire"]}">⛔</tg-emoji>',
    "🚫": f'<tg-emoji emoji-id="{EMOJI_IDS["fire"]}">🚫</tg-emoji>',
    "⚠️": f'<tg-emoji emoji-id="{EMOJI_IDS["zap"]}">⚠️</tg-emoji>',
}

def p_text(text: str) -> str:
    """تبدیل خودکار تمام ایموجی‌های موجود در متن‌های ربات به ایموجی‌های پریمیوم و متحرک تلگرام"""
    if not text:
        return ""
    out = text
    for normal_emoji, tg_tag in PREMIUM_EMOJI_MAP.items():
        if normal_emoji in out:
            out = out.replace(normal_emoji, tg_tag)
    return out

def p_btn(
    text: str,
    callback_data: str = None,
    url: str = None,
    style: str = None,
    emoji_key: str = None,
) -> InlineKeyboardButton:
    """ساخت دکمه شیشه‌ای رنگی مجهز به آیکون ایموجی پریمیوم متحرک تلگرام (icon_custom_emoji_id)"""
    kwargs = {}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    if style in ("primary", "success", "danger"):
        kwargs["style"] = style
    if emoji_key and emoji_key in EMOJI_IDS:
        kwargs["icon_custom_emoji_id"] = EMOJI_IDS[emoji_key]
    return InlineKeyboardButton(text, **kwargs)

def convert_to_premium_emoji_html(raw_text: str) -> str:
    """تبدیل ایموجی‌های معمولی متن کاربر به تگ‌های ایموجی پریمیوم تلگرام + قالب‌بندی لوکس"""
    escaped = html.escape(raw_text or "")
    converted = p_text(escaped)
    header_star = PREMIUM_EMOJI_MAP["✨"]
    footer_gem = PREMIUM_EMOJI_MAP["💎"]
    fire_tag = PREMIUM_EMOJI_MAP["🔥"]

    if converted == escaped:
        return f"{header_star} <b>{escaped}</b> {fire_tag}\n\n{footer_gem} <i>ویرایش شده با استایل پریمیوم</i>"
    return f"{header_star} {converted} {footer_gem}"

# ====================================================================
#  دیتابیس SQLite و تنظیمات پویا
# ====================================================================

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with closing(get_conn()) as conn, conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TEXT NOT NULL,
                vip_until TEXT DEFAULT NULL,
                daily_count INTEGER DEFAULT 0,
                last_usage_date TEXT DEFAULT NULL,
                total_posts INTEGER DEFAULT 0,
                invited_by INTEGER DEFAULT NULL,
                referral_verified INTEGER DEFAULT 0,
                referrals_count INTEGER DEFAULT 0,
                rewarded_referrals INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS force_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL UNIQUE,
                channel_link TEXT NOT NULL,
                title TEXT DEFAULT 'کانال اسپانسر'
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan_type TEXT NOT NULL,
                days INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                photo_file_id TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                post_type TEXT NOT NULL,
                target_channel TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        default_settings = {
            "card_number": "6037-9975-0000-0000",
            "card_holder": "مدیریت ربات",
            "price_30d": "50000",
            "price_90d": "199000",
            "free_daily_limit": "3",
            "free_no_ads_days": "3",
            "referral_target": "6",
            "referral_reward_days": "10",
            "ad_signature": "✨ ساخته شده با ربات سازنده دکمه شیشه‌ای: @{bot_username}",
            "support_id": "@Admin",
            "bot_active": "1",
        }
        for k, v in default_settings.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

def get_setting(key: str, default: str = "") -> str:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

def set_setting(key: str, value: str):
    with closing(get_conn()) as conn, conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))

# ====================================================================
#  توابع کاربری، بررسی اشتراک VIP و محدودیت روزانه
# ====================================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_or_create_user(user_id: int, username: str = "", first_name: str = "", invited_by: int = None):
    with closing(get_conn()) as conn, conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            now_iso = datetime.now().isoformat()
            today_str = datetime.now().strftime("%Y-%m-%d")
            valid_inviter = invited_by if (invited_by and invited_by != user_id) else None
            conn.execute(
                """INSERT INTO users (user_id, username, first_name, joined_at, last_usage_date, invited_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username or "", first_name or "کاربر", now_iso, today_str, valid_inviter)
            )
            user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        else:
            conn.execute(
                "UPDATE users SET username=?, first_name=? WHERE user_id=?",
                (username or "", first_name or "کاربر", user_id)
            )
        return user

def is_user_vip(user_id: int) -> bool:
    if is_admin(user_id):
        return True
    with closing(get_conn()) as conn:
        user = conn.execute("SELECT vip_until FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user or not user["vip_until"]:
            return False
        try:
            exp = datetime.fromisoformat(user["vip_until"])
            return exp > datetime.now()
        except Exception:
            return False

def get_vip_remaining_text(user_id: int) -> str:
    with closing(get_conn()) as conn:
        user = conn.execute("SELECT vip_until FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user or not user["vip_until"]:
            return "ندارد (اشتراک معمولی)"
        try:
            exp = datetime.fromisoformat(user["vip_until"])
            if exp <= datetime.now():
                return "منقضی شده (اشتراک معمولی)"
            diff = exp - datetime.now()
            days = diff.days
            hours = diff.seconds // 3600
            return f"💎 فعال ({days} روز و {hours} ساعت باقی‌مانده)"
        except Exception:
            return "ندارد (اشتراک معمولی)"

def add_vip_days(user_id: int, days: int):
    with closing(get_conn()) as conn, conn:
        user = conn.execute("SELECT vip_until FROM users WHERE user_id=?", (user_id,)).fetchone()
        now = datetime.now()
        base_time = now
        if user and user["vip_until"]:
            try:
                current_exp = datetime.fromisoformat(user["vip_until"])
                if current_exp > now:
                    base_time = current_exp
            except Exception:
                pass
        new_exp = (base_time + timedelta(days=days)).isoformat()
        conn.execute("UPDATE users SET vip_until=? WHERE user_id=?", (new_exp, user_id))
        return new_exp

def check_and_Reset_daily_usage(user_id: int) -> int:
    today_str = datetime.now().strftime("%Y-%m-%d")
    with closing(get_conn()) as conn, conn:
        user = conn.execute("SELECT daily_count, last_usage_date FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            return 0
        if user["last_usage_date"] != today_str:
            conn.execute("UPDATE users SET daily_count=0, last_usage_date=? WHERE user_id=?", (today_str, user_id))
            return 0
        return user["daily_count"]

def increment_user_usage(user_id: int, post_type: str, target_channel: str):
    today_str = datetime.now().strftime("%Y-%m-%d")
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """UPDATE users
               SET daily_count = daily_count + 1,
                   total_posts = total_posts + 1,
                   last_usage_date = ?
               WHERE user_id = ?""",
            (today_str, user_id)
        )
        conn.execute(
            "INSERT INTO posts_log (user_id, post_type, target_channel, created_at) VALUES (?, ?, ?, ?)",
            (user_id, post_type, target_channel, datetime.now().isoformat())
        )

def should_append_bot_ad(user_id: int) -> bool:
    """کاربر معمولی فقط تا ۳ روز اول بدون تبلیغ دکمه می‌سازد؛ بعد از ۳ روز آیدی ربات اضافه می‌شود. در VIP هیچ تبلیغی نیست."""
    if is_user_vip(user_id):
        return False
    no_ads_days = int(get_setting("free_no_ads_days", "3"))
    with closing(get_conn()) as conn:
        user = conn.execute("SELECT joined_at FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user or not user["joined_at"]:
            return True
        try:
            joined_dt = datetime.fromisoformat(user["joined_at"])
            return (datetime.now() - joined_dt) >= timedelta(days=no_ads_days)
        except Exception:
            return True

def can_user_create_glass_button(user_id: int) -> tuple[bool, int, int]:
    """بررسی محدودیت روزانه ساخت دکمه شیشه‌ای (معمولی: ۳ عدد در روز، VIP: نامحدود)"""
    daily_used = check_and_Reset_daily_usage(user_id)
    limit = int(get_setting("free_daily_limit", "3"))
    if is_user_vip(user_id):
        return True, daily_used, -1
    return (daily_used < limit), daily_used, limit

# ====================================================================
#  جوین اجباری و تایید خودکار زیرمجموعه (Referral Verification)
# ====================================================================

def get_force_channels():
    with closing(get_conn()) as conn:
        return conn.execute("SELECT * FROM force_channels ORDER BY id ASC").fetchall()

async def check_user_joined_all(bot, user_id: int) -> list:
    if is_admin(user_id):
        return []
    channels = get_force_channels()
    not_joined = []
    for ch in channels:
        ch_id = ch["channel_id"].strip()
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(ch)
        except Exception as e:
            logger.warning(f"خطا در بررسی عضویت کانال {ch_id}: {e}")
    return not_joined

async def verify_referral_if_eligible(bot, user_id: int):
    with closing(get_conn()) as conn, conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user or not user["invited_by"] or user["referral_verified"] == 1:
            return
        inviter_id = user["invited_by"]
        conn.execute("UPDATE users SET referral_verified=1 WHERE user_id=?", (user_id,))
        conn.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id=?", (inviter_id,))
        inviter = conn.execute("SELECT * FROM users WHERE user_id=?", (inviter_id,)).fetchone()

    if not inviter:
        return

    target = int(get_setting("referral_target", "6"))
    reward_days = int(get_setting("referral_reward_days", "10"))
    new_count = inviter["referrals_count"]
    rewarded_so_far = inviter["rewarded_referrals"]

    try:
        await bot.send_message(
            chat_id=inviter_id,
            text=p_text(
                f"🎉 <b>زیرمجموعه جدید تایید شد!</b>\n\n"
                f"👤 کاربر <b>{html.escape(user['first_name'])}</b> در کانال‌های ربات عضو شد و به زیرمجموعه‌های شما اضافه گردید.\n"
                f"👥 تعداد کل زیرمجموعه‌های شما: <b>{new_count} نفر</b>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [p_btn("مشاهده وضعیت زیرمجموعه‌گیری", callback_data="menu:referral", style="primary", emoji_key="gift")]
            ])
        )
    except Exception:
        pass

    if new_count - rewarded_so_far >= target:
        with closing(get_conn()) as conn, conn:
            conn.execute(
                "UPDATE users SET rewarded_referrals = rewarded_referrals + ? WHERE user_id=?",
                (target, inviter_id)
            )
        add_vip_days(inviter_id, reward_days)
        try:
            await bot.send_message(
                chat_id=inviter_id,
                text=p_text(
                    f"🏆 <b>تبریک! پاداش زیرمجموعه‌گیری فعال شد!</b>\n\n"
                    f"شما موفق به جذب <b>{target} زیرمجموعه تاییدشده</b> شدید و به صورت خودکار "
                    f"<b>{reward_days} روز اشتراک VIP رایگان</b> به حساب شما اضافه شد! 💎"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [p_btn("ورود به منوی اصلی", callback_data="menu:main", style="success", emoji_key="glow")]
                ])
            )
        except Exception:
            pass

def build_force_join_keyboard(not_joined_channels: list) -> InlineKeyboardMarkup:
    rows = []
    for idx, ch in enumerate(not_joined_channels, start=1):
        rows.append([
            p_btn(f"عضویت در {ch['title']} ({idx})", url=ch["channel_link"], style="primary", emoji_key="megaphone")
        ])
    rows.append([
        p_btn("عضو شدم / بررسی عضویت", callback_data="check_join", style="success", emoji_key="check")
    ])
    return InlineKeyboardMarkup(rows)

# ====================================================================
#  کیبوردهای تمام‌شیشه‌ای، رنگی و مجهز به ایموجی پریمیوم متحرک
# ====================================================================

def main_inline_keyboard(user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            p_btn("ساخت دکمه شیشه‌ای رنگی", callback_data="menu:create_btn", style="primary", emoji_key="sparkles"),
        ],
        [
            p_btn("ایموجی پریمیوم در کانال (VIP)", callback_data="menu:premium_emoji", style="primary", emoji_key="fire"),
        ],
        [
            p_btn("خرید اشتراک VIP", callback_data="menu:buy_vip", style="success", emoji_key="gem"),
            p_btn("زیرمجموعه‌گیری (VIP رایگان)", callback_data="menu:referral", style="primary", emoji_key="gift"),
        ],
        [
            p_btn("حساب کاربری و وضعیت من", callback_data="menu:profile", style="primary", emoji_key="star"),
            p_btn("راهنما و مقایسه پلن‌ها", callback_data="menu:help", style="primary", emoji_key="zap"),
        ],
    ]
    if is_admin(user_id):
        rows.append([
            p_btn("پنل مدیریت پیشرفته (۲۰ قابلیت)", callback_data="admin:home", style="danger", emoji_key="crown")
        ])
    return InlineKeyboardMarkup(rows)

def admin_inline_keyboard() -> InlineKeyboardMarkup:
    """پنل مدیریت ۲۰ قابلیته با دکمه‌های شیشه‌ای رنگی و ایموجی‌های پریمیوم متحرک"""
    bot_status_str = "روشن" if get_setting("bot_active", "1") == "1" else "خاموش"
    rows = [
        [
            p_btn("۱. آمار کامل ربات", callback_data="adm:stats", style="primary", emoji_key="zap"),
            p_btn("۲. پیام همگانی", callback_data="adm:broadcast", style="primary", emoji_key="megaphone"),
        ],
        [
            p_btn("۳. فوروارد همگانی", callback_data="adm:fwbroadcast", style="primary", emoji_key="rocket"),
            p_btn("۴. تنظیم شماره کارت", callback_data="adm:set_card", style="success", emoji_key="money"),
        ],
        [
            p_btn("۵. تنظیم نام صاحب کارت", callback_data="adm:set_holder", style="primary", emoji_key="star"),
            p_btn("۶. قیمت VIP یک‌ماهه", callback_data="adm:price_30", style="success", emoji_key="gem"),
        ],
        [
            p_btn("۷. قیمت VIP سه‌ماهه", callback_data="adm:price_90", style="success", emoji_key="crown"),
            p_btn("۸. رسیدهای در انتظار تایید", callback_data="adm:pending_pays", style="primary", emoji_key="check"),
        ],
        [
            p_btn("۹. افزودن کانال جوین اجباری", callback_data="adm:add_fch", style="success", emoji_key="sparkles"),
            p_btn("۱۰. حذف کانال جوین اجباری", callback_data="adm:del_fch", style="danger", emoji_key="fire"),
        ],
        [
            p_btn("۱۱. لیست کانال‌های اجباری", callback_data="adm:list_fch", style="primary", emoji_key="megaphone"),
            p_btn("۱۲. اهدای اشتراک VIP", callback_data="adm:gift_vip", style="success", emoji_key="gift"),
        ],
        [
            p_btn("۱۳. لغو اشتراک VIP کاربر", callback_data="adm:revoke_vip", style="danger", emoji_key="fire"),
            p_btn("۱۴. جستجو و اطلاعات کاربر", callback_data="adm:user_info", style="primary", emoji_key="star"),
        ],
        [
            p_btn("۱۵. مسدود/آزادسازی کاربر", callback_data="adm:ban_toggle", style="danger", emoji_key="fire"),
            p_btn("۱۶. سقف روزانه رایگان", callback_data="adm:set_limit", style="primary", emoji_key="hundred"),
        ],
        [
            p_btn("۱۷. روزهای بدون تبلیغ اولیه", callback_data="adm:set_noads", style="primary", emoji_key="glow"),
            p_btn("۱۸. تنظیمات پاداش رفرال", callback_data="adm:set_ref", style="primary", emoji_key="gift"),
        ],
        [
            p_btn("۱۹. متن تبلیغ زیر پست", callback_data="adm:set_adsig", style="primary", emoji_key="sparkles"),
            p_btn(f"۲۰. وضعیت ربات ({bot_status_str})", callback_data="adm:toggle_bot", style="danger", emoji_key="zap"),
        ],
        [
            p_btn("بازگشت به منوی اصلی ربات", callback_data="menu:main", style="primary", emoji_key="glow"),
        ]
    ]
    return InlineKeyboardMarkup(rows)

def cancel_inline_keyboard(back_cb: str = "menu:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [p_btn("انصراف و بازگشت", callback_data=back_cb, style="danger", emoji_key="fire")]
    ])

# ====================================================================
#  وضعیت‌های ConversationHandler
# ====================================================================
(
    BTN_WAIT_POST,
    BTN_WAIT_URL,
    BTN_WAIT_TEXT,
    BTN_WAIT_COLOR,
    BTN_WAIT_CHANNEL,
    BTN_WAIT_CONFIRM,
    EMOJI_WAIT_POST,
    EMOJI_WAIT_CHANNEL,
    EMOJI_WAIT_CONFIRM,
    PAY_WAIT_RECEIPT,
    ADM_WAIT_INPUT,
    ADM_WAIT_FCH_ID,
    ADM_WAIT_FCH_LINK,
    ADM_WAIT_FCH_TITLE,
    ADM_WAIT_GIFT_UID,
    ADM_WAIT_GIFT_DAYS,
) = range(16)

# ====================================================================
#  کمکی ارسال پست (متن یا مدیا) به کانال یا چت
# ====================================================================

async def send_stored_post(bot, chat_id, post_data: dict, reply_markup=None, custom_text: str = None):
    ptype = post_data.get("type", "text")
    caption_or_text = custom_text if custom_text is not None else post_data.get("text", "")
    file_id = post_data.get("file_id")

    if ptype == "text":
        return await bot.send_message(
            chat_id=chat_id,
            text=caption_or_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=False
        )
    elif ptype == "photo":
        return await bot.send_photo(
            chat_id=chat_id,
            photo=file_id,
            caption=caption_or_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    elif ptype == "video":
        return await bot.send_video(
            chat_id=chat_id,
            video=file_id,
            caption=caption_or_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    elif ptype == "animation":
        return await bot.send_animation(
            chat_id=chat_id,
            animation=file_id,
            caption=caption_or_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    elif ptype == "document":
        return await bot.send_document(
            chat_id=chat_id,
            document=file_id,
            caption=caption_or_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

def normalize_channel_identifier(raw_input: str) -> str:
    txt = raw_input.strip()
    if txt.startswith("-100") and txt[1:].isdigit():
        return txt
    m = re.search(r"(?:https?://)?(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{4,})", txt)
    if m:
        username = m.group(1)
        if not username.startswith("+") and username.lower() != "joinchat":
            return f"@{username}"
    if not txt.startswith("@") and re.match(r"^[a-zA-Z0-9_]{4,}$", txt):
        return f"@{txt}"
    return txt

# ====================================================================
#  هندلر شروع (/start) و بررسی جوین اجباری
# ====================================================================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    invited_by = None
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                invited_by = int(arg.replace("ref_", ""))
            except ValueError:
                invited_by = None

    db_user = get_or_create_user(user.id, user.username, user.first_name, invited_by)
    if db_user["is_banned"] == 1 and not is_admin(user.id):
        await update.message.reply_text(p_text("🚫 حساب کاربری شما توسط مدیریت مسدود شده است."), parse_mode=ParseMode.HTML)
        return

    if get_setting("bot_active", "1") == "0" and not is_admin(user.id):
        await update.message.reply_text(p_text("⏳ ربات موقتاً در حال بروزرسانی است. لطفاً کمی بعد مراجعه کنید."), parse_mode=ParseMode.HTML)
        return

    not_joined = await check_user_joined_all(context.bot, user.id)
    if not_joined:
        await update.message.reply_text(
            p_text("👋 سلام! برای استفاده از امکانات ربات و ثبت زیرمجموعه، ابتدا در کانال‌های زیر عضو شوید و سپس دکمه <b>«✅ عضو شدم»</b> را بزنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=build_force_join_keyboard(not_joined)
        )
        return

    await verify_referral_if_eligible(context.bot, user.id)

    vip_badge = "💎 اشتراک VIP فعال" if is_user_vip(user.id) else "🔹 اشتراک معمولی"
    welcome_text = p_text(
        f"🌟 <b>سلام {html.escape(user.first_name)} عزیز، به ربات سازنده دکمه شیشه‌ای رنگی خوش آمدی!</b>\n\n"
        f"📊 وضعیت حساب شما: <b>{vip_badge}</b>\n\n"
        f"🎨 با این ربات می‌تونی برای پست‌های متنی، عکس، ویدیو یا فایل خودت <b>دکمه‌های شیشه‌ای رنگی (آبی، سبز، قرمز و معمولی)</b> بسازی و مستقیم داخل کانالت پست کنی! 🚀\n\n"
        f"✨ از دکمه‌های شیشه‌ای زیر بخش مورد نظرت رو انتخاب کن:"
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    not_joined = await check_user_joined_all(context.bot, user.id)
    if not_joined:
        await query.answer("⚠️ شما هنوز در تمام کانال‌ها عضو نشده‌اید!", show_alert=True)
        return
    await query.answer("✅ عضویت شما با موفقیت تایید شد!")
    await verify_referral_if_eligible(context.bot, user.id)
    await query.edit_message_text(
        p_text(f"✅ <b>عضویت شما تایید شد!</b>\n🎉 خوش آمدید {html.escape(user.first_name)} عزیز.\n✨ از منوی شیشه‌ای زیر انتخاب کنید:"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )

# ====================================================================
#  منوهای عمومی (حساب کاربری، خرید اشتراک، زیرمجموعه‌گیری، راهنما)
# ====================================================================

async def menu_router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    db_user = get_or_create_user(user.id, user.username, user.first_name)
    if db_user["is_banned"] == 1 and not is_admin(user.id):
        await query.answer("🚫 شما مسدود هستید.", show_alert=True)
        return

    not_joined = await check_user_joined_all(context.bot, user.id)
    if not_joined:
        await query.answer("⚠️ ابتدا در کانال‌های اسپانسر عضو شوید.", show_alert=True)
        await query.edit_message_text(
            p_text("📢 لطفاً ابتدا در کانال‌های زیر عضو شوید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=build_force_join_keyboard(not_joined)
        )
        return

    await verify_referral_if_eligible(context.bot, user.id)
    await query.answer()

    if data == "menu:main":
        context.user_data.clear()
        vip_badge = "💎 اشتراک VIP فعال" if is_user_vip(user.id) else "🔹 اشتراک معمولی"
        await query.edit_message_text(
            p_text(
                f"🏠 <b>منوی اصلی ربات دکمه شیشه‌ای رنگی</b>\n\n"
                f"👤 کاربر: <b>{html.escape(user.first_name)}</b>\n"
                f"📊 نوع حساب: <b>{vip_badge}</b>\n\n"
                f"✨ یکی از گزینه‌های زیر را انتخاب کنید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )

    elif data == "menu:profile":
        daily_used = check_and_Reset_daily_usage(user.id)
        limit = get_setting("free_daily_limit", "3")
        vip_status = get_vip_remaining_text(user.id)
        ad_state = "بدون تبلیغ ✅" if not should_append_bot_ad(user.id) else "دارای آیدی ربات زیر پست (گذشت ۳ روز اول)"
        daily_str = f"{daily_used} از نامحدود (VIP)" if is_user_vip(user.id) else f"{daily_used} از {limit} دکمه"

        text = p_text(
            f"👤 <b>اطلاعات حساب کاربری شما</b>\n\n"
            f"⚡ آیدی عددی: <code>{user.id}</code>\n"
            f"💎 وضعیت اشتراک: <b>{vip_status}</b>\n"
            f"📊 مصرف امروز: <b>{daily_str}</b>\n"
            f"✨ کل پست‌های ساخته شده: <b>{db_user['total_posts']} پست</b>\n"
            f"👥 زیرمجموعه‌های تاییدشده: <b>{db_user['referrals_count']} نفر</b>\n"
            f"📣 وضعیت تبلیغ زیر پست: <b>{ad_state}</b>"
        )
        kb = InlineKeyboardMarkup([
            [
                p_btn("ارتقا به اشتراک VIP", callback_data="menu:buy_vip", style="success", emoji_key="gem"),
                p_btn("دریافت VIP رایگان", callback_data="menu:referral", style="primary", emoji_key="gift"),
            ],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "menu:buy_vip":
        p30 = int(get_setting("price_30d", "50000"))
        p90 = int(get_setting("price_90d", "199000"))
        text = p_text(
            f"💎 <b>خرید اشتراک ویژه (VIP)</b>\n\n"
            f"✨ <b>مزایای اشتراک VIP نسبت به اشتراک معمولی:</b>\n"
            f"🔥 ساخت <b>نامحدود</b> دکمه شیشه‌ای در روز (در حالت معمولی فقط ۳ عدد در روز)\n"
            f"✅ <b>حذف کامل تبلیغ و آیدی ربات</b> از زیر پست‌های کانال شما برای همیشه\n"
            f"🌟 باز شدن بخش ویژه <b>«✨ استفاده از ایموجی پریمیوم تلگرام در کانال»</b>\n\n"
            f"💳 <b>تعرفه پلن‌های اشتراک ویژه:</b>\n"
            f"🔹 اشتراک ۳۰ روزه (یک‌ماهه): <b>{p30:,} تومان</b>\n"
            f"👑 اشتراک ۹۰ روزه (سه‌ماهه): <b>{p90:,} تومان</b>\n\n"
            f"🚀 لطفاً پلن مورد نظر خود را برای پرداخت کارت به کارت انتخاب کنید:"
        )
        kb = InlineKeyboardMarkup([
            [p_btn(f"خرید اشتراک ۳۰ روزه ({p30:,} تومان)", callback_data="buyplan:30", style="primary", emoji_key="gem")],
            [p_btn(f"خرید اشتراک ۳ ماهه ({p90:,} تومان)", callback_data="buyplan:90", style="success", emoji_key="crown")],
            [p_btn("دریافت VIP رایگان با زیرمجموعه‌گیری", callback_data="menu:referral", style="primary", emoji_key="gift")],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "menu:referral":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user.id}"
        target = int(get_setting("referral_target", "6"))
        reward_days = int(get_setting("referral_reward_days", "10"))
        current_refs = db_user["referrals_count"]
        rewarded = db_user["rewarded_referrals"]
        progress = current_refs - rewarded
        rem = max(0, target - progress)

        text = p_text(
            f"🎁 <b>کسب اشتراک VIP رایگان (زیرمجموعه‌گیری)</b>\n\n"
            f"🔥 با دعوت از دوستان خود به ربات، به ازای هر <b>{target} زیرمجموعه</b> که وارد ربات شده و در کانال‌های جوین اجباری عضو شوند، "
            f"به‌صورت خودکار <b>{reward_days} روز اشتراک VIP رایگان</b> دریافت می‌کنید!\n\n"
            f"📊 <b>آمار زیرمجموعه‌های شما:</b>\n"
            f"👥 کل زیرمجموعه‌های تاییدشده: <b>{current_refs} نفر</b>\n"
            f"⏳ پیشرفت فعلی برای پاداش بعدی: <b>{progress} از {target} نفر</b> ({rem} نفر دیگر تا فعال‌سازی خودکار {reward_days} روز VIP)\n\n"
            f"🔗 <b>لینک اختصاصی دعوت شما:</b>\n"
            f"<code>{ref_link}</code>\n\n"
            f"✨ <i>توجه: زیرمجموعه زمانی شمارش می‌شود که کاربر جدید روی لینک شما کلیک کرده و در کانال‌های اسپانسر عضو شود.</i>"
        )
        kb = InlineKeyboardMarkup([
            [p_btn("خرید مستقیم اشتراک VIP", callback_data="menu:buy_vip", style="success", emoji_key="gem")],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "menu:help":
        limit = get_setting("free_daily_limit", "3")
        noads = get_setting("free_no_ads_days", "3")
        target = get_setting("referral_target", "6")
        reward = get_setting("referral_reward_days", "10")
        text = p_text(
            f"📚 <b>راهنمای کامل ربات و تفاوت اشتراک معمولی و VIP</b>\n\n"
            f"🔹 <b>اشتراک معمولی (رایگان):</b>\n"
            f"• هر کاربر تازه وارد، روزانه حداکثر <b>{limit} دکمه شیشه‌ای</b> می‌تواند بسازد.\n"
            f"• فقط تا <b>{noads} روز اول</b> عضویت، پست‌ها بدون تبلیغ در کانال ارسال می‌شوند.\n"
            f"• پس از گذشت {noads} روز، هنگام ساخت دکمه شیشه‌ای، آیدی ربات نیز در انتهای متن پست در کانال قرار می‌گیرد.\n\n"
            f"💎 <b>اشتراک ویژه (VIP):</b>\n"
            f"• ساخت دکمه شیشه‌ای رنگی به‌صورت <b>کاملاً نامحدود</b> در شبانه‌روز.\n"
            f"• <b>بدون هیچ‌گونه تبلیغ</b> یا نام ربات در زیر پست‌های شما.\n"
            f"• دسترسی کامل به بخش <b>«✨ ایموجی پریمیوم تلگرام»</b> برای زیباسازی خودکار پست‌ها.\n\n"
            f"🎁 <b>روش دریافت VIP رایگان:</b>\n"
            f"• با آوردن <b>{target} زیرمجموعه</b> (که در کانال‌های اجباری عضو شوند)، اشتراک VIP <b>{reward} روزه</b> رایگان برایتان فعال می‌شود.\n\n"
            f"⚠️ <b>نکته مهم برای ارسال به کانال:</b>\n"
            f"• ربات را در کانال خود <b>Admin (مدیر)</b> کنید تا بتواند پست را مستقیماً در کانالتان منتشر کند."
        )
        kb = InlineKeyboardMarkup([
            [
                p_btn("شروع ساخت دکمه شیشه‌ای", callback_data="menu:create_btn", style="primary", emoji_key="sparkles"),
                p_btn("خرید اشتراک VIP", callback_data="menu:buy_vip", style="success", emoji_key="gem"),
            ],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ====================================================================
#  فرایند ساخت دکمه شیشه‌ای رنگی (گام‌به‌گام طبق دستور کاربر)
# ====================================================================

async def create_btn_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    not_joined = await check_user_joined_all(context.bot, user.id)
    if not_joined:
        await query.answer("⚠️ ابتدا در کانال‌های اسپانسر عضو شوید.", show_alert=True)
        await query.edit_message_text(p_text("📢 ابتدا در کانال‌های زیر عضو شوید:"), parse_mode=ParseMode.HTML, reply_markup=build_force_join_keyboard(not_joined))
        return ConversationHandler.END

    allowed, used, limit = can_user_create_glass_button(user.id)
    if not allowed:
        await query.answer("⛔ سقف مجاز روزانه شما تمام شده است!", show_alert=True)
        await query.edit_message_text(
            p_text(
                f"⛔ <b>محدودیت روزانه اشتراک معمولی!</b>\n\n"
                f"شما امروز <b>{used} از {limit}</b> دکمه شیشه‌ای رایگان خود را ساخته‌اید.\n"
                f"برای ساخت دکمه شیشه‌ای <b>به‌صورت نامحدود و بدون تبلیغ</b>، اشتراک VIP تهیه کنید یا با دعوت ۶ دوست، ۱۰ روز VIP رایگان بگیرید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [p_btn("خرید اشتراک VIP نامحدود", callback_data="menu:buy_vip", style="success", emoji_key="gem")],
                [p_btn("دریافت VIP رایگان (زیرمجموعه)", callback_data="menu:referral", style="primary", emoji_key="gift")],
                [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
            ])
        )
        return ConversationHandler.END

    await query.answer()
    context.user_data["glass_builder"] = {}
    await query.edit_message_text(
        p_text(
            "🎨 <b>مرحله ۱ از ۵: ارسال محتوای پست</b>\n\n"
            "✨ لطفاً الان <b>متن پست</b> خود را بفرستید، یا <b>عکس / ویدیو / گیف / فایل</b> خود را به همراه کپشن ارسال کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:main")
    )
    return BTN_WAIT_POST

async def create_btn_receive_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    post_info = {"type": "text", "text": "", "file_id": None}

    if msg.photo:
        post_info["type"] = "photo"
        post_info["file_id"] = msg.photo[-1].file_id
        post_info["text"] = html.escape(msg.caption or "")
    elif msg.video:
        post_info["type"] = "video"
        post_info["file_id"] = msg.video.file_id
        post_info["text"] = html.escape(msg.caption or "")
    elif msg.animation:
        post_info["type"] = "animation"
        post_info["file_id"] = msg.animation.file_id
        post_info["text"] = html.escape(msg.caption or "")
    elif msg.document:
        post_info["type"] = "document"
        post_info["file_id"] = msg.document.file_id
        post_info["text"] = html.escape(msg.caption or "")
    elif msg.text:
        post_info["type"] = "text"
        post_info["text"] = html.escape(msg.text)
    else:
        await msg.reply_text(
            p_text("⚠️ لطفاً یک متن، عکس، ویدیو، گیف یا فایل معتبر ارسال کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:main")
        )
        return BTN_WAIT_POST

    context.user_data["glass_builder"]["post"] = post_info
    await msg.reply_text(
        p_text(
            "🔗 <b>مرحله ۲ از ۵: ارسال لینک دکمه شیشه‌ای</b>\n\n"
            "✨ لطفاً <b>لینکی</b> که می‌خواهید داخل دکمه شیشه‌ای قرار بگیرد را ارسال کنید\n"
            "<i>(مثال: https://t.me/YourChannel یا آدرس سایت)</i>:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:main")
    )
    return BTN_WAIT_URL

async def create_btn_receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_url = update.message.text.strip()
    if raw_url.startswith("@"):
        raw_url = f"https://t.me/{raw_url[1:]}"
    elif raw_url.startswith("t.me/"):
        raw_url = f"https://{raw_url}"
    elif not raw_url.startswith(("http://", "https://", "tg://")):
        raw_url = f"https://{raw_url}"

    context.user_data["glass_builder"]["btn_url"] = raw_url
    await update.message.reply_text(
        p_text(
            "🏷 <b>مرحله ۳ از ۵: نام روی دکمه شیشه‌ای</b>\n\n"
            "✨ حالا <b>اسم یا متنی</b> که می‌خواهید روی دکمه شیشه‌ای نمایش داده شود را بفرستید\n"
            "<i>(مثال: دانلود فایل | ورود به سایت | عضویت در کانال)</i>:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:main")
    )
    return BTN_WAIT_TEXT

async def create_btn_receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn_text = update.message.text.strip()
    context.user_data["glass_builder"]["btn_text"] = btn_text

    color_kb = InlineKeyboardMarkup([
        [
            p_btn("رنگ آبی (Primary)", callback_data="btncolor:primary", style="primary", emoji_key="gem"),
            p_btn("رنگ سبز (Success)", callback_data="btncolor:success", style="success", emoji_key="check"),
        ],
        [
            p_btn("رنگ قرمز (Danger)", callback_data="btncolor:danger", style="danger", emoji_key="fire"),
            p_btn("رنگ معمولی دکمه شیشه‌ای", callback_data="btncolor:normal", emoji_key="sparkles"),
        ],
        [
            p_btn("انصراف و بازگشت", callback_data="menu:main", style="danger", emoji_key="fire")
        ]
    ])
    await update.message.reply_text(
        p_text(
            "🎨 <b>مرحله ۴ از ۵: انتخاب رنگ دکمه شیشه‌ای</b>\n\n"
            "✨ لطفاً رنگ دکمه شیشه‌ای خود را از بین گزینه‌های زیر انتخاب کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=color_kb
    )
    return BTN_WAIT_COLOR

async def create_btn_receive_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chosen_color = query.data.split(":")[1]
    context.user_data["glass_builder"]["btn_color"] = chosen_color

    color_labels = {
        "primary": "🔵 آبی",
        "success": "🟢 سبز",
        "danger": "🔴 قرمز",
        "normal": "✨ معمولی شیشه‌ای"
    }
    await query.edit_message_text(
        p_text(
            f"✅ رنگ انتخاب شده: <b>{color_labels.get(chosen_color, 'معمولی')}</b>\n\n"
            f"📢 <b>مرحله ۵ از ۵: لینک یا آیدی کانال مقصد</b>\n\n"
            f"حالا <b>لینک یا یوزرنیم کانالی</b> که می‌خواهید این پست در آن قرار بگیرد را بفرستید\n"
            f"<i>(مثال: https://t.me/MyChannel یا @MyChannel)</i>\n\n"
            f"⚠️ <b>حتماً توجه کنید که ربات در کانال شما Admin (مدیر) باشد.</b>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:main")
    )
    return BTN_WAIT_CHANNEL

async def create_btn_receive_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    raw_ch = update.message.text.strip()
    channel_id = normalize_channel_identifier(raw_ch)
    context.user_data["glass_builder"]["target_channel"] = channel_id

    builder = context.user_data["glass_builder"]
    post_data = builder["post"]
    btn_text = builder["btn_text"]
    btn_url = builder["btn_url"]
    btn_color = builder["btn_color"]

    final_text = post_data.get("text", "")
    if should_append_bot_ad(user.id):
        bot_me = await context.bot.get_me()
        ad_sig = p_text(get_setting("ad_signature", "✨ ساخته شده با ربات: @{bot_username}").replace("{bot_username}", bot_me.username))
        final_text = f"{final_text}\n\n{ad_sig}".strip()
    builder["final_text"] = final_text

    if btn_color in ("primary", "success", "danger"):
        preview_btn = InlineKeyboardButton(btn_text, url=btn_url, style=btn_color)
    else:
        preview_btn = InlineKeyboardButton(btn_text, url=btn_url)

    confirm_kb = InlineKeyboardMarkup([
        [preview_btn],
        [p_btn("پست کردن در کانال", callback_data="publish_glass_post", style="success", emoji_key="rocket")],
        [p_btn("انصراف و لغو", callback_data="menu:main", style="danger", emoji_key="fire")]
    ])

    await update.message.reply_text(
        p_text(
            f"👁 <b>پیش‌نمایش پست شما (آماده ارسال به {html.escape(channel_id)}):</b>\n"
            f"✨ در صورت تایید، روی دکمه سبز <b>«🚀 پست کردن در کانال»</b> زیر پست بزنید:"
        ),
        parse_mode=ParseMode.HTML
    )
    await send_stored_post(context.bot, update.effective_chat.id, post_data, reply_markup=confirm_kb, custom_text=final_text)
    return BTN_WAIT_CONFIRM

async def create_btn_publish_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    builder = context.user_data.get("glass_builder")
    if not builder:
        await query.answer("اطلاعات پست یافت نشد. دوباره تلاش کنید.", show_alert=True)
        return ConversationHandler.END

    post_data = builder["post"]
    btn_text = builder["btn_text"]
    btn_url = builder["btn_url"]
    btn_color = builder["btn_color"]
    target_channel = builder["target_channel"]
    final_text = builder["final_text"]

    if btn_color in ("primary", "success", "danger"):
        channel_markup = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=btn_url, style=btn_color)]])
    else:
        channel_markup = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=btn_url)]])

    try:
        await send_stored_post(context.bot, target_channel, post_data, reply_markup=channel_markup, custom_text=final_text)
        increment_user_usage(user.id, "glass_button", target_channel)
        await query.answer("✅ با موفقیت در کانال پست شد!", show_alert=True)
        await context.bot.send_message(
            chat_id=user.id,
            text=p_text(
                f"✅ <b>پست شما با دکمه شیشه‌ای رنگی با موفقیت در کانال {html.escape(target_channel)} منتشر شد!</b> 🎉"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [p_btn("ساخت دکمه شیشه‌ای جدید", callback_data="menu:create_btn", style="primary", emoji_key="sparkles")],
                [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="success", emoji_key="glow")]
            ])
        )
    except Exception as e:
        await query.answer("❌ خطا در ارسال به کانال!", show_alert=True)
        await context.bot.send_message(
            chat_id=user.id,
            text=p_text(
                f"❌ <b>خطا در ارسال پست به کانال ({html.escape(target_channel)})!</b>\n\n"
                f"⚠️ لطفاً مطمئن شوید:\n"
                f"1️⃣ ربات را در کانال <b>Admin (مدیر)</b> کرده‌اید و دسترسی ارسال پست (Post Messages) دارد.\n"
                f"2️⃣ لینک یا آیدی کانال را به درستی وارد کرده‌اید.\n\n"
                f"جزئیات فنی: <code>{html.escape(str(e)[:120])}</code>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )

    context.user_data.pop("glass_builder", None)
    return ConversationHandler.END

# ====================================================================
#  بخش استفاده از ایموجی پریمیوم تلگرام در کانال (مخصوص VIP)
# ====================================================================

async def premium_emoji_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    not_joined = await check_user_joined_all(context.bot, user.id)
    if not_joined:
        await query.answer("⚠️ ابتدا در کانال‌های اسپانسر عضو شوید.", show_alert=True)
        await query.edit_message_text(p_text("📢 ابتدا در کانال‌های زیر عضو شوید:"), parse_mode=ParseMode.HTML, reply_markup=build_force_join_keyboard(not_joined))
        return ConversationHandler.END

    if not is_user_vip(user.id):
        await query.answer("💎 این بخش مخصوص کاربران VIP است!", show_alert=True)
        await query.edit_message_text(
            p_text(
                "✨ <b>بخش ایموجی پریمیوم تلگرام در کانال (ویژه VIP)</b>\n\n"
                "⛔ این قابلیت فقط با داشتن <b>اشتراک VIP</b> فعال می‌شود.\n"
                "🔥 در این بخش، شما پست خود را با ایموجی‌های معمولی می‌فرستید و ربات به‌صورت خودکار آن را با <b>ایموجی‌های پریمیوم و متحرک تلگرام</b> تزیین کرده و در کانال شما پست می‌کند!\n\n"
                "💎 همین حالا اشتراک VIP تهیه کنید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [p_btn("خرید اشتراک VIP", callback_data="menu:buy_vip", style="success", emoji_key="gem")],
                [p_btn("دریافت VIP رایگان با زیرمجموعه", callback_data="menu:referral", style="primary", emoji_key="gift")],
                [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
            ])
        )
        return ConversationHandler.END

    await query.answer()
    context.user_data["emoji_builder"] = {}
    await query.edit_message_text(
        p_text(
            "✨ <b>زیباسازی پست با ایموجی‌های پریمیوم تلگرام (مرحله ۱ از ۲)</b>\n\n"
            "لطفاً <b>پست خود (متن، عکس یا ویدیو)</b> را که حاوی ایموجی‌های معمولی است (مثل 🔥 ❤️ 💎 ✅ ⭐ 🚀 🎉 💰 ✨) برای ربات بفرستید تا ربات به صورت خودکار آن را با ایموجی‌های پریمیوم و متحرک زیبا کند:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:main")
    )
    return EMOJI_WAIT_POST

async def premium_emoji_receive_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    post_info = {"type": "text", "text": "", "file_id": None}
    raw_text = ""

    if msg.photo:
        post_info["type"] = "photo"
        post_info["file_id"] = msg.photo[-1].file_id
        raw_text = msg.caption or ""
    elif msg.video:
        post_info["type"] = "video"
        post_info["file_id"] = msg.video.file_id
        raw_text = msg.caption or ""
    elif msg.text:
        post_info["type"] = "text"
        raw_text = msg.text
    else:
        await msg.reply_text(p_text("⚠️ لطفاً متن، عکس یا ویدیو ارسال کنید:"), parse_mode=ParseMode.HTML, reply_markup=cancel_inline_keyboard("menu:main"))
        return EMOJI_WAIT_POST

    beautified_html = convert_to_premium_emoji_html(raw_text)
    post_info["text"] = beautified_html
    context.user_data["emoji_builder"]["post"] = post_info

    await msg.reply_text(
        p_text(
            "📢 <b>مرحله ۲ از ۲: ارسال لینک یا آیدی کانال</b>\n\n"
            "پست شما با ایموجی‌های پریمیوم آماده شد! ✨\n"
            "حالا <b>لینک یا یوزرنیم کانال</b> انتخابی خود را بفرستید تا در آن پست شود\n"
            "<i>(مثال: https://t.me/MyChannel یا @MyChannel)</i>:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:main")
    )
    return EMOJI_WAIT_CHANNEL

async def premium_emoji_receive_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_ch = update.message.text.strip()
    channel_id = normalize_channel_identifier(raw_ch)
    context.user_data["emoji_builder"]["target_channel"] = channel_id
    post_data = context.user_data["emoji_builder"]["post"]

    confirm_kb = InlineKeyboardMarkup([
        [p_btn("پست کردن در کانال با ایموجی پریمیوم", callback_data="publish_emoji_post", style="success", emoji_key="rocket")],
        [p_btn("انصراف و بازگشت", callback_data="menu:main", style="danger", emoji_key="fire")]
    ])

    await update.message.reply_text(
        p_text(f"✨ <b>پیش‌نمایش پست شما با ایموجی‌های پریمیوم (مقصد: {html.escape(channel_id)}):</b>"),
        parse_mode=ParseMode.HTML
    )
    await send_stored_post(context.bot, update.effective_chat.id, post_data, reply_markup=confirm_kb)
    return EMOJI_WAIT_CONFIRM

async def premium_emoji_publish_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    builder = context.user_data.get("emoji_builder")
    if not builder:
        await query.answer("اطلاعات یافت نشد.", show_alert=True)
        return ConversationHandler.END

    post_data = builder["post"]
    target_channel = builder["target_channel"]

    try:
        await send_stored_post(context.bot, target_channel, post_data)
        increment_user_usage(user.id, "premium_emoji", target_channel)
        await query.answer("✅ پست با ایموجی پریمیوم در کانال منتشر شد!", show_alert=True)
        await context.bot.send_message(
            chat_id=user.id,
            text=p_text(f"✅ <b>پست شما با ایموجی‌های پریمیوم با موفقیت در کانال {html.escape(target_channel)} منتشر شد!</b> 🎉"),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )
    except Exception as e:
        await query.answer("❌ خطا در ارسال به کانال!", show_alert=True)
        await context.bot.send_message(
            chat_id=user.id,
            text=p_text(
                f"❌ <b>خطا در ارسال به کانال {html.escape(target_channel)}!</b>\n"
                f"⚠️ مطمئن شوید ربات در کانال شما Admin است.\n"
                f"خطا: <code>{html.escape(str(e)[:100])}</code>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )

    context.user_data.pop("emoji_builder", None)
    return ConversationHandler.END

# ====================================================================
#  خرید اشتراک VIP و ارسال رسید کارت به کارت
# ====================================================================

async def buy_plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    days = int(query.data.split(":")[1])

    if days == 30:
        amount = int(get_setting("price_30d", "50000"))
        plan_title = "اشتراک VIP یک‌ماهه (۳۰ روزه)"
    else:
        amount = int(get_setting("price_90d", "199000"))
        plan_title = "اشتراک VIP سه‌ماهه (۹۰ روزه)"

    card_no = get_setting("card_number", "6037-9975-0000-0000")
    card_holder = get_setting("card_holder", "مدیریت ربات")

    context.user_data["pending_vip_plan"] = {
        "days": days,
        "amount": amount,
        "title": plan_title
    }

    text = p_text(
        f"💳 <b>پرداخت کارت به کارت — {plan_title}</b>\n\n"
        f"💰 مبلغ قابل پرداخت: <b>{amount:,} تومان</b>\n"
        f"💳 شماره کارت جهت واریز:\n"
        f"<code>{card_no}</code>\n"
        f"👤 به نام: <b>{html.escape(card_holder)}</b>\n\n"
        f"✨ <b>لطفاً پس از واریز، عکس رسید پرداخت خود را در همین صفحه ارسال کنید تا پس از تایید مدیر، اشتراک شما بلافاصله فعال شود:</b>"
    )
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:buy_vip")
    )
    return PAY_WAIT_RECEIPT

async def buy_plan_receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    plan = context.user_data.get("pending_vip_plan")
    if not plan:
        await update.message.reply_text(p_text("❌ خطا در اطلاعات پلن."), parse_mode=ParseMode.HTML, reply_markup=main_inline_keyboard(user.id))
        return ConversationHandler.END

    if not update.message.photo:
        await update.message.reply_text(
            p_text("⚠️ لطفاً تصویر (عکس) رسید پرداخت را ارسال کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:buy_vip")
        )
        return PAY_WAIT_RECEIPT

    photo_id = update.message.photo[-1].file_id
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            """INSERT INTO payments (user_id, plan_type, days, amount, photo_file_id, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (user.id, plan["title"], plan["days"], plan["amount"], photo_id, datetime.now().isoformat())
        )
        pay_id = cur.lastrowid

    await update.message.reply_text(
        p_text(
            f"✅ <b>رسید پرداخت شما با کد پیگیری #{pay_id} دریافت شد!</b>\n"
            f"✨ به‌محض بررسی و تایید توسط مدیریت، اشتراک <b>{plan['title']}</b> برای شما فعال شده و پیام تایید برایتان ارسال می‌گردد."
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )

    admin_caption = p_text(
        f"🧾 <b>رسید جدید خرید اشتراک VIP (#{pay_id})</b>\n\n"
        f"👤 کاربر: <b>{html.escape(user.first_name)}</b> (@{user.username or 'ندارد'})\n"
        f"⚡ آیدی عددی: <code>{user.id}</code>\n"
        f"💎 پلن درخواستی: <b>{plan['title']}</b> ({plan['days']} روز)\n"
        f"💰 مبلغ: <b>{plan['amount']:,} تومان</b>"
    )
    admin_kb = InlineKeyboardMarkup([
        [
            p_btn("تایید و فعال‌سازی VIP", callback_data=f"payact:approve:{pay_id}", style="success", emoji_key="check"),
            p_btn("رد کردن رسید", callback_data=f"payact:reject:{pay_id}", style="danger", emoji_key="fire"),
        ]
    ])
    for adm in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=adm,
                photo=photo_id,
                caption=admin_caption,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_kb
            )
        except Exception as e:
            logger.error(f"خطا در ارسال رسید به ادمین: {e}")

    context.user_data.pop("pending_vip_plan", None)
    return ConversationHandler.END

async def admin_payment_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ فقط مدیر اصلی دسترسی دارد.", show_alert=True)
        return

    _, action, pay_id_str = query.data.split(":")
    pay_id = int(pay_id_str)

    with closing(get_conn()) as conn, conn:
        pay = conn.execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()
        if not pay:
            await query.answer("رسید یافت نشد.", show_alert=True)
            return
        if pay["status"] != "pending":
            await query.answer("این رسید قبلاً بررسی شده است.", show_alert=True)
            return

        if action == "approve":
            conn.execute("UPDATE payments SET status='approved' WHERE id=?", (pay_id,))
            add_vip_days(pay["user_id"], pay["days"])
            await query.answer("✅ اشتراک VIP برای کاربر فعال شد!")
            try:
                await context.bot.send_message(
                    chat_id=pay["user_id"],
                    text=p_text(
                        f"🎉 <b>پرداخت شما تایید شد!</b>\n\n"
                        f"💎 اشتراک <b>{pay['plan_type']}</b> ({pay['days']} روز) با موفقیت برای حساب شما فعال گردید.\n"
                        f"🚀 اکنون می‌توانید به‌صورت نامحدود و بدون تبلیغ دکمه شیشه‌ای بسازید و از بخش ایموجی پریمیوم استفاده کنید!"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=main_inline_keyboard(pay["user_id"])
                )
            except Exception:
                pass
            await query.edit_message_caption(
                caption=p_text(f"{query.message.caption}\n\n✅ <b>وضعیت: تایید شده و اشتراک فعال شد.</b>"),
                parse_mode=ParseMode.HTML
            )
        else:
            conn.execute("UPDATE payments SET status='rejected' WHERE id=?", (pay_id,))
            await query.answer("❌ رسید رد شد.")
            try:
                await context.bot.send_message(
                    chat_id=pay["user_id"],
                    text=p_text(f"❌ رسید پرداخت شماره #{pay_id} شما مورد تایید قرار نگرفت. در صورت ابهام دوباره بررسی نمایید."),
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass
            await query.edit_message_caption(
                caption=p_text(f"{query.message.caption}\n\n❌ <b>وضعیت: رد شده توسط مدیر.</b>"),
                parse_mode=ParseMode.HTML
            )

# ====================================================================
#  پنل مدیریت پیشرفته با ۲۰ قابلیت کامل (مخصوص آیدی 8248647747)
# ====================================================================

async def admin_home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ این بخش فقط مخصوص ادمین اصلی ربات است!", show_alert=True)
        return
    await query.answer()
    context.user_data.pop("adm_mode", None)

    p30 = int(get_setting("price_30d", "50000"))
    p90 = int(get_setting("price_90d", "199000"))
    card = get_setting("card_number", "6037-9975-0000-0000")
    holder = get_setting("card_holder", "مدیریت ربات")

    text = p_text(
        f"👑 <b>پنل مدیریت پیشرفته ربات (۲۰ قابلیت فعال)</b>\n\n"
        f"💳 شماره کارت فعلی: <code>{card}</code> ({html.escape(holder)})\n"
        f"💎 قیمت ۳۰ روزه: <b>{p30:,} تومان</b> | ۳ ماهه: <b>{p90:,} تومان</b>\n"
        f"⚡ سقف روزانه عادی: <b>{get_setting('free_daily_limit')} پست</b> | بدون تبلیغ اولیه: <b>{get_setting('free_no_ads_days')} روز</b>\n\n"
        f"✨ از دکمه‌های شیشه‌ای رنگی زیر عملیات مورد نظر را انتخاب کنید:"
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())
    return ConversationHandler.END

async def admin_actions_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ دسترسی غیرمجاز!", show_alert=True)
        return ConversationHandler.END

    action = query.data
    await query.answer()

    if action == "adm:stats":
        with closing(get_conn()) as conn:
            total_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            now_iso = datetime.now().isoformat()
            vip_users = conn.execute("SELECT COUNT(*) c FROM users WHERE vip_until > ?", (now_iso,)).fetchone()["c"]
            banned_users = conn.execute("SELECT COUNT(*) c FROM users WHERE is_banned=1").fetchone()["c"]
            total_posts = conn.execute("SELECT COUNT(*) c FROM posts_log").fetchone()["c"]
            pending_pays = conn.execute("SELECT COUNT(*) c FROM payments WHERE status='pending'").fetchone()["c"]
            approved_sum = conn.execute("SELECT COALESCE(SUM(amount),0) s FROM payments WHERE status='approved'").fetchone()["s"]
            fch_count = conn.execute("SELECT COUNT(*) c FROM force_channels").fetchone()["c"]

        stats_text = p_text(
            f"📊 <b>آمار لحظه‌ای و جامع ربات</b>\n\n"
            f"👥 کل کاربران ثبت‌نامی: <b>{total_users:,} نفر</b>\n"
            f"💎 کاربران دارای اشتراک VIP فعال: <b>{vip_users:,} نفر</b>\n"
            f"🚫 کاربران مسدود شده: <b>{banned_users:,} نفر</b>\n"
            f"🎨 کل پست‌های ساخته شده: <b>{total_posts:,} پست</b>\n"
            f"📢 تعداد کانال‌های جوین اجباری: <b>{fch_count} کانال</b>\n"
            f"🧾 رسیدهای در انتظار تایید: <b>{pending_pays} رسید</b>\n"
            f"💰 مجموع فروش تایید شده: <b>{approved_sum:,} تومان</b>"
        )
        await query.edit_message_text(
            stats_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[p_btn("بازگشت به پنل مدیریت", callback_data="admin:home", style="primary", emoji_key="crown")]])
        )
        return ConversationHandler.END

    elif action == "adm:pending_pays":
        with closing(get_conn()) as conn:
            pays = conn.execute("SELECT * FROM payments WHERE status='pending' ORDER BY id DESC LIMIT 10").fetchall()
        if not pays:
            await query.edit_message_text(
                p_text("✅ هیچ رسید پرداختی در انتظار بررسی نیست."),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[p_btn("بازگشت به پنل مدیریت", callback_data="admin:home", style="primary", emoji_key="crown")]])
            )
            return ConversationHandler.END

        for p in pays:
            cap = p_text(
                f"🧾 <b>رسید #{p['id']}</b>\n"
                f"👤 کاربر: <code>{p['user_id']}</code>\n"
                f"💎 پلن: {p['plan_type']} ({p['days']} روز)\n"
                f"💰 مبلغ: {p['amount']:,} تومان"
            )
            kb = InlineKeyboardMarkup([
                [
                    p_btn("تایید و فعال‌سازی", callback_data=f"payact:approve:{p['id']}", style="success", emoji_key="check"),
                    p_btn("رد رسید", callback_data=f"payact:reject:{p['id']}", style="danger", emoji_key="fire"),
                ]
            ])
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=p["photo_file_id"], caption=cap, parse_mode=ParseMode.HTML, reply_markup=kb)
        return ConversationHandler.END

    elif action == "adm:list_fch":
        channels = get_force_channels()
        if not channels:
            text = p_text("📢 هیچ کانال جوین اجباری ثبت نشده است.")
        else:
            lines = [p_text("📢 <b>لیست کانال‌های جوین اجباری فعال:</b>\n")]
            for idx, ch in enumerate(channels, 1):
                lines.append(p_text(f"{idx}. <b>{html.escape(ch['title'])}</b> | شناسه: <code>{ch['channel_id']}</code>\n🔗 {ch['channel_link']}"))
            text = "\n\n".join(lines)
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    p_btn("افزودن کانال جدید", callback_data="adm:add_fch", style="success", emoji_key="sparkles"),
                    p_btn("حذف کانال", callback_data="adm:del_fch", style="danger", emoji_key="fire"),
                ],
                [p_btn("بازگشت به پنل مدیریت", callback_data="admin:home", style="primary", emoji_key="crown")]
            ])
        )
        return ConversationHandler.END

    elif action == "adm:del_fch":
        channels = get_force_channels()
        if not channels:
            await query.edit_message_text(
                p_text("⚠️ هیچ کانالی برای حذف وجود ندارد."),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[p_btn("بازگشت به پنل مدیریت", callback_data="admin:home", style="primary", emoji_key="crown")]])
            )
            return ConversationHandler.END
        rows = []
        for ch in channels:
            rows.append([p_btn(f"حذف {ch['title']} ({ch['channel_id']})", callback_data=f"rmfch:{ch['id']}", style="danger", emoji_key="fire")])
        rows.append([p_btn("بازگشت به پنل مدیریت", callback_data="admin:home", style="primary", emoji_key="crown")])
        await query.edit_message_text(p_text("🔥 روی کانالی که می‌خواهید از جوین اجباری حذف شود کلیک کنید:"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
        return ConversationHandler.END

    elif action == "adm:toggle_bot":
        curr = get_setting("bot_active", "1")
        new_val = "0" if curr == "1" else "1"
        set_setting("bot_active", new_val)
        await admin_home_callback(update, context)
        return ConversationHandler.END

    elif action == "adm:add_fch":
        await query.edit_message_text(
            p_text(
                "✨ <b>افزودن کانال جوین اجباری (مرحله ۱ از ۳)</b>\n\n"
                "لطفاً آیدی کانال با @ (مثل <code>@MyChannel</code>) یا آیدی عددی کانال (مثل <code>-100123456789</code>) را بفرستید.\n"
                "⚠️ <i>توجه: ربات حتماً باید در آن کانال ادمین باشد تا بتواند عضویت کاربران را بررسی کند.</i>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("admin:home")
        )
        return ADM_WAIT_FCH_ID

    elif action == "adm:gift_vip":
        await query.edit_message_text(
            p_text(
                "🎁 <b>اهدای اشتراک VIP به کاربر (مرحله ۱ از ۲)</b>\n\n"
                "لطفاً <b>آیدی عددی کاربر</b> مورد نظر را ارسال کنید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("admin:home")
        )
        return ADM_WAIT_GIFT_UID

    prompts = {
        "adm:broadcast": p_text("📣 <b>ارسال پیام همگانی</b>\nلطفاً پیام خود (متن، عکس یا ویدیو) را بفرستید تا برای تمام کاربران ارسال شود:"),
        "adm:fwbroadcast": p_text("🚀 <b>فوروارد همگانی</b>\nلطفاً پست مورد نظر خود را به اینجا فوروارد کنید تا با نام منبع برای همه کاربران فوروارد شود:"),
        "adm:set_card": p_text(f"💳 <b>تنظیم شماره کارت</b>\nشماره کارت فعلی: <code>{get_setting('card_number')}</code>\nشماره کارت جدید را ارسال کنید:"),
        "adm:set_holder": p_text(f"👤 <b>تنظیم نام صاحب کارت</b>\nنام فعلی: <b>{html.escape(get_setting('card_holder'))}</b>\nنام صاحب حساب جدید را بفرستید:"),
        "adm:price_30": p_text(f"💵 <b>تغییر قیمت اشتراک VIP ۳۰ روزه</b>\nقیمت فعلی: <b>{int(get_setting('price_30d')):,} تومان</b>\nقیمت جدید را به تومان (فقط عدد انگلیسی) وارد کنید:"),
        "adm:price_90": p_text(f"💰 <b>تغییر قیمت اشتراک VIP سه‌ماهه</b>\nقیمت فعلی: <b>{int(get_setting('price_90d')):,} تومان</b>\nقیمت جدید را به تومان (فقط عدد انگلیسی) وارد کنید:"),
        "adm:revoke_vip": p_text("❌ <b>لغو اشتراک VIP کاربر</b>\nلطفاً آیدی عددی کاربری که می‌خواهید اشتراک VIP او لغو شود را بفرستید:"),
        "adm:user_info": p_text("👤 <b>جستجوی اطلاعات کاربر</b>\nلطفاً آیدی عددی کاربر را ارسال کنید:"),
        "adm:ban_toggle": p_text("🚫 <b>مسدود یا آزادسازی کاربر</b>\nلطفاً آیدی عددی کاربر را ارسال کنید تا وضعیت مسدودیت او تغییر کند:"),
        "adm:set_limit": p_text(f"⚡ <b>تنظیم سقف روزانه اشتراک معمولی</b>\nمقدار فعلی: <b>{get_setting('free_daily_limit')} دکمه در روز</b>\nعدد جدید را وارد کنید:"),
        "adm:set_noads": p_text(f"⏳ <b>تنظیم تعداد روزهای بدون تبلیغ اولیه</b>\nمقدار فعلی: <b>{get_setting('free_no_ads_days')} روز اول</b>\nعدد جدید را وارد کنید:"),
        "adm:set_ref": p_text(f"👥 <b>تنظیم هدف زیرمجموعه‌گیری و روزهای پاداش</b>\nفرمت فعلی: <code>{get_setting('referral_target')}:{get_setting('referral_reward_days')}</code> (یعنی {get_setting('referral_target')} زیرمجموعه = {get_setting('referral_reward_days')} روز VIP)\nمقدار جدید را با فرمت <code>تعداد:روز</code> بفرستید (مثلاً <code>6:10</code>):"),
        "adm:set_adsig": p_text(f"✨ <b>تنظیم متن تبلیغ زیر پست‌های عادی</b>\nمتن فعلی:\n<code>{html.escape(get_setting('ad_signature'))}</code>\n\nمتن جدید را بفرستید (می‌توانید از <code>{{bot_username}}</code> استفاده کنید):"),
    }

    if action in prompts:
        context.user_data["adm_mode"] = action
        await query.edit_message_text(
            prompts[action],
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("admin:home")
        )
        return ADM_WAIT_INPUT

    return ConversationHandler.END

async def admin_remove_fch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return
    fch_id = int(query.data.split(":")[1])
    with closing(get_conn()) as conn, conn:
        conn.execute("DELETE FROM force_channels WHERE id=?", (fch_id,))
    await query.answer("✅ کانال از جوین اجباری حذف شد!", show_alert=True)
    await admin_home_callback(update, context)

async def admin_add_fch_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_fch_id"] = update.message.text.strip()
    await update.message.reply_text(
        p_text("🔗 <b>مرحله ۲ از ۳: لینک عضویت کانال</b>\nلطفاً لینک کانال (مثلاً <code>https://t.me/MyChannel</code>) را بفرستید:"),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("admin:home")
    )
    return ADM_WAIT_FCH_LINK

async def admin_add_fch_step2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_fch_link"] = update.message.text.strip()
    await update.message.reply_text(
        p_text("🏷 <b>مرحله ۳ از ۳: عنوان دکمه کانال</b>\nنامی که روی دکمه شیشه‌ای جوین اجباری نمایش داده شود را بفرستید (مثلاً: کانال رسمی ما):"),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("admin:home")
    )
    return ADM_WAIT_FCH_TITLE

async def admin_add_fch_step3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    ch_id = context.user_data.get("new_fch_id")
    ch_link = context.user_data.get("new_fch_link")
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "INSERT OR REPLACE INTO force_channels (channel_id, channel_link, title) VALUES (?, ?, ?)",
            (ch_id, ch_link, title)
        )
    await update.message.reply_text(
        p_text(f"✅ کانال <b>{html.escape(title)}</b> (<code>{ch_id}</code>) به لیست جوین اجباری اضافه شد!"),
        parse_mode=ParseMode.HTML,
        reply_markup=admin_inline_keyboard()
    )
    return ConversationHandler.END

async def admin_gift_vip_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
        context.user_data["gift_uid"] = uid
        await update.message.reply_text(
            p_text("⏳ <b>تعداد روز اشتراک VIP</b> که می‌خواهید به این کاربر اضافه شود را وارد کنید (مثلاً 30):"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("admin:home")
        )
        return ADM_WAIT_GIFT_DAYS
    except ValueError:
        await update.message.reply_text(p_text("⚠️ لطفاً فقط آیدی عددی معتبر وارد کنید:"), parse_mode=ParseMode.HTML, reply_markup=cancel_inline_keyboard("admin:home"))
        return ADM_WAIT_GIFT_UID

async def admin_gift_vip_step2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
        uid = context.user_data.get("gift_uid")
        get_or_create_user(uid)
        add_vip_days(uid, days)
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=p_text(f"🎁 <b>هدیه مدیریت!</b>\nتعداد <b>{days} روز اشتراک VIP</b> توسط مدیریت ربات برای حساب شما فعال شد! 💎"),
                parse_mode=ParseMode.HTML,
                reply_markup=main_inline_keyboard(uid)
            )
        except Exception:
            pass
        await update.message.reply_text(
            p_text(f"✅ تعداد <b>{days} روز اشتراک VIP</b> برای کاربر <code>{uid}</code> فعال شد."),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_inline_keyboard()
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(p_text("⚠️ عدد معتبر وارد کنید:"), parse_mode=ParseMode.HTML, reply_markup=cancel_inline_keyboard("admin:home"))
        return ADM_WAIT_GIFT_DAYS

async def admin_handle_single_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("adm_mode")
    msg = update.message
    txt = (msg.text or "").strip()

    if mode in ("adm:broadcast", "adm:fwbroadcast"):
        with closing(get_conn()) as conn:
            users = conn.execute("SELECT user_id FROM users").fetchall()
        sent = 0
        failed = 0
        status_msg = await msg.reply_text(p_text(f"⏳ در حال ارسال به {len(users)} کاربر..."), parse_mode=ParseMode.HTML)
        for u in users:
            try:
                if mode == "adm:fwbroadcast":
                    await msg.forward(chat_id=u["user_id"])
                else:
                    await msg.copy(chat_id=u["user_id"])
                sent += 1
            except Exception:
                failed += 1
        await status_msg.edit_text(
            p_text(
                f"✅ <b>عملیات همگانی به پایان رسید!</b>\n\n"
                f"🟢 ارسال موفق: <b>{sent} نفر</b>\n"
                f"🔴 ناموفق/بلاک: <b>{failed} نفر</b>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_inline_keyboard()
        )
        return ConversationHandler.END

    elif mode == "adm:set_card":
        set_setting("card_number", txt)
        await msg.reply_text(p_text(f"✅ شماره کارت به <code>{html.escape(txt)}</code> تغییر یافت."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())

    elif mode == "adm:set_holder":
        set_setting("card_holder", txt)
        await msg.reply_text(p_text(f"✅ نام صاحب کارت به <b>{html.escape(txt)}</b> تغییر یافت."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())

    elif mode == "adm:price_30":
        if txt.isdigit():
            set_setting("price_30d", txt)
            await msg.reply_text(p_text(f"✅ قیمت اشتراک ۳۰ روزه به <b>{int(txt):,} تومان</b> تغییر یافت."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())
        else:
            await msg.reply_text(p_text("⚠️ لطفاً فقط عدد انگلیسی وارد کنید."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())

    elif mode == "adm:price_90":
        if txt.isdigit():
            set_setting("price_90d", txt)
            await msg.reply_text(p_text(f"✅ قیمت اشتراک ۳ ماهه به <b>{int(txt):,} تومان</b> تغییر یافت."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())
        else:
            await msg.reply_text(p_text("⚠️ لطفاً فقط عدد انگلیسی وارد کنید."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())

    elif mode == "adm:revoke_vip":
        if txt.isdigit():
            with closing(get_conn()) as conn, conn:
                conn.execute("UPDATE users SET vip_until=NULL WHERE user_id=?", (int(txt),))
            await msg.reply_text(p_text(f"✅ اشتراک VIP کاربر <code>{txt}</code> لغو شد."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())
        else:
            await msg.reply_text(p_text("⚠️ آیدی عددی نامعتبر است."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())

    elif mode == "adm:user_info":
        if txt.isdigit():
            uid = int(txt)
            with closing(get_conn()) as conn:
                u = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
            if not u:
                await msg.reply_text(p_text("❌ کاربری با این آیدی یافت نشد."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())
            else:
                info = p_text(
                    f"👤 <b>مشخصات کاربر <code>{uid}</code>:</b>\n\n"
                    f"نام: <b>{html.escape(u['first_name'] or '')}</b> (@{u['username'] or 'ندارد'})\n"
                    f"وضعیت VIP: <b>{get_vip_remaining_text(uid)}</b>\n"
                    f"کل پست‌ها: <b>{u['total_posts']}</b> | زیرمجموعه: <b>{u['referrals_count']} نفر</b>\n"
                    f"وضعیت مسدودیت: <b>{'🚫 مسدود' if u['is_banned'] else '🟢 آزاد'}</b>"
                )
                await msg.reply_text(info, parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())
        else:
            await msg.reply_text(p_text("⚠️ آیدی عددی نامعتبر است."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())

    elif mode == "adm:ban_toggle":
        if txt.isdigit():
            uid = int(txt)
            with closing(get_conn()) as conn, conn:
                u = conn.execute("SELECT is_banned FROM users WHERE user_id=?", (uid,)).fetchone()
                if u:
                    new_state = 0 if u["is_banned"] == 1 else 1
                    conn.execute("UPDATE users SET is_banned=? WHERE user_id=?", (new_state, uid))
                    st_str = "🚫 مسدود شد" if new_state == 1 else "🟢 آزاد شد"
                    await msg.reply_text(p_text(f"✅ کاربر <code>{uid}</code> {st_str}."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())
                else:
                    await msg.reply_text(p_text("❌ کاربر یافت نشد."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())
        else:
            await msg.reply_text(p_text("⚠️ آیدی عددی نامعتبر است."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())

    elif mode == "adm:set_limit":
        if txt.isdigit():
            set_setting("free_daily_limit", txt)
            await msg.reply_text(p_text(f"✅ سقف روزانه اشتراک معمولی به <b>{txt} دکمه</b> تغییر یافت."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())
        else:
            await msg.reply_text(p_text("⚠️ عدد نامعتبر."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())

    elif mode == "adm:set_noads":
        if txt.isdigit():
            set_setting("free_no_ads_days", txt)
            await msg.reply_text(p_text(f"✅ مهلت بدون تبلیغ اولیه به <b>{txt} روز</b> تغییر یافت."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())
        else:
            await msg.reply_text(p_text("⚠️ عدد نامعتبر."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())

    elif mode == "adm:set_ref":
        if ":" in txt:
            parts = txt.split(":")
            if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                set_setting("referral_target", parts[0].strip())
                set_setting("referral_reward_days", parts[1].strip())
                await msg.reply_text(
                    p_text(f"✅ تنظیمات رفرال بروز شد: هر <b>{parts[0].strip()} زیرمجموعه = {parts[1].strip()} روز VIP</b>."),
                    parse_mode=ParseMode.HTML,
                    reply_markup=admin_inline_keyboard()
                )
            else:
                await msg.reply_text(p_text("⚠️ فرمت نادرست است (مثال: 6:10)."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())
        else:
            await msg.reply_text(p_text("⚠️ فرمت نادرست است (مثال: 6:10)."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())

    elif mode == "adm:set_adsig":
        set_setting("ad_signature", txt)
        await msg.reply_text(p_text("✅ متن تبلیغ زیر پست بروزرسانی شد."), parse_mode=ParseMode.HTML, reply_markup=admin_inline_keyboard())

    context.user_data.pop("adm_mode", None)
    return ConversationHandler.END

# ====================================================================
#  ثبت هندلرها و اجرای ربات + پینگر ضد خواب ۵ دقیقه‌ای Render
# ====================================================================

def main():
    init_db()
    start_render_keep_alive()

    app = Application.builder().token(BOT_TOKEN).build()

    glass_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_btn_start, pattern="^menu:create_btn$")],
        states={
            BTN_WAIT_POST: [MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL) & ~filters.COMMAND, create_btn_receive_post)],
            BTN_WAIT_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_btn_receive_url)],
            BTN_WAIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_btn_receive_text)],
            BTN_WAIT_COLOR: [CallbackQueryHandler(create_btn_receive_color, pattern="^btncolor:")],
            BTN_WAIT_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_btn_receive_channel)],
            BTN_WAIT_CONFIRM: [CallbackQueryHandler(create_btn_publish_now, pattern="^publish_glass_post$")],
        },
        fallbacks=[
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    emoji_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(premium_emoji_start, pattern="^menu:premium_emoji$")],
        states={
            EMOJI_WAIT_POST: [MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, premium_emoji_receive_post)],
            EMOJI_WAIT_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_emoji_receive_channel)],
            EMOJI_WAIT_CONFIRM: [CallbackQueryHandler(premium_emoji_publish_now, pattern="^publish_emoji_post$")],
        },
        fallbacks=[
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    buy_vip_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_plan_start, pattern="^buyplan:(30|90)$")],
        states={
            PAY_WAIT_RECEIPT: [MessageHandler(filters.PHOTO, buy_plan_receive_receipt)],
        },
        fallbacks=[
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_actions_router, pattern="^adm:")],
        states={
            ADM_WAIT_INPUT: [MessageHandler(filters.ALL & ~filters.COMMAND, admin_handle_single_input)],
            ADM_WAIT_FCH_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_fch_step1)],
            ADM_WAIT_FCH_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_fch_step2)],
            ADM_WAIT_FCH_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_fch_step3)],
            ADM_WAIT_GIFT_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gift_vip_step1)],
            ADM_WAIT_GIFT_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gift_vip_step2)],
        },
        fallbacks=[
            CallbackQueryHandler(admin_home_callback, pattern="^admin:home$"),
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(glass_conv)
    app.add_handler(emoji_conv)
    app.add_handler(buy_vip_conv)
    app.add_handler(admin_conv)

    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(admin_home_callback, pattern="^admin:home$"))
    app.add_handler(CallbackQueryHandler(admin_remove_fch_callback, pattern="^rmfch:"))
    app.add_handler(CallbackQueryHandler(admin_payment_action_callback, pattern="^payact:"))
    app.add_handler(CallbackQueryHandler(menu_router_callback, pattern="^menu:"))

    logger.info("🚀 ربات سازنده دکمه شیشه‌ای رنگی و ایموجی پریمیوم متحرک آماده به کار است.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
