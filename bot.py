# -*- coding: utf-8 -*-
"""
====================================================================
 🌑 ربات سلف دارک (Self Dark) + تبچی هوشمند (نسخه مخصوص Render)
====================================================================

مشخصات و قابلیت‌های کلیدی سلف دارک:
  - اتصال واقعی به اکانت تلگرام کاربر با Telethon (دریافت شماره با دکمه تلگرام + کد ورود + رمز دو مرحله‌ای)
  - کسر ۳۰ الماس هنگام فعال‌سازی اولیه سلف دارک + کسر خودکار ۳ الماس در هر ساعت روشن بودن سلف
  - ارسال فوری مشخصات کامل، آیدی، نام و شماره تلفن هر کاربری که سلف دارک را فعال می‌کند به ادمین اصلی (8248647747)
  - دارای ۴۰ قابلیت کامل سلف دارک (۳۰ قابلیت درخواستی + ۱۰ قابلیت ویژه اضافه شده) قابل تنظیم از داخل ربات و دستورات خود اکانت
  - مجهز به تبچی هوشمند سلف دارک (ثبت گروه با دستور «تنظیم چت»، بنر اختصاصی، فاصله زمانی دقیق، روشن/خاموش و مدیریت کامل)
  - خرید الماس با ارز دیجیتال TON (هر الماس 0.0005 TON، حداقل خرید ۵۰ الماس) و کارت به کارت ریالی (@kanfingfreesup)
  - زیرمجموعه‌گیری هوشمند با شرط عضویت در کانال‌های جوین اجباری (هر زیرمجموعه = ۵ الماس، قابل تغییر و روشن/خاموش از پنل ادمین)
  - پنل مدیریت فوق‌پیشرفته با ۴۰ قابلیت کاربردی (شامل جستجوی کاربر با فوروارد پیام و افزایش/کاهش الماس، همگانی، مدیریت سلف‌ها و...)
  - تمام دکمه‌های ربات شیشه‌ای و رنگی (غالب آبی Primary + سبز Success + قرمز Danger) همراه با ایموجی‌های پریمیوم و متحرک تلگرام
  - مجهز به وب‌سرور Flask و ارسال سیگنال قوی ضد خواب هر ۵ دقیقه (۳۰۰ ثانیه) به Render

اجرا:
    python bot.py
====================================================================
"""

import logging
import sqlite3
import os
import re
import json
import time
import html
import asyncio
import threading
import requests
import io
import tempfile
from flask import Flask, jsonify
from datetime import datetime, timedelta, timezone
from contextlib import closing

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
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

from telethon import TelegramClient, events, functions, types
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    FloodWaitError,
)

# ====================================================================
#  تنظیمات اصلی ربات، توکن، API Hash و ادمین
# ====================================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8315326974:AAFYg6ygEYi7V3tZzUFBzciADoi1d_1UQLo")
ADMIN_ID = 8248647747
ADMIN_IDS = [8248647747]

API_ID = int(os.environ.get("API_ID", "32063619"))
API_HASH = os.environ.get("API_HASH", "9a80695b6e3fdfdae22ec69dc110b954")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_dark_bot.db")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# نگهداری کلاینت‌های فعال Telethon در حافظه
ACTIVE_SELF_CLIENTS: dict[int, TelegramClient] = {}
PENDING_LOGINS: dict[int, dict] = {}
LAST_CLOCK_MINUTE: dict[int, str] = {}
AUTOREPLY_COOLDOWN: dict[tuple[int, int], float] = {}
BOT_APP_REF: Application = None

# ====================================================================
#  وب‌سرور Flask و سیستم ضد خواب قوی (Keep-Alive هر ۵ دقیقه) مخصوص Render
# ====================================================================

web_app = Flask(__name__)
START_TIME = datetime.now()
PING_COUNTER = 0

@web_app.route("/")
def home():
    return "✅ ربات سلف دارک (Self Dark) با موفقیت روی Render فعال و در حال اجراست (24/7 Active).", 200

@web_app.route("/health")
def health():
    global PING_COUNTER
    PING_COUNTER += 1
    uptime_seconds = int((datetime.now() - START_TIME).total_seconds())
    return jsonify({
        "status": "online",
        "bot": "self_dark_bot",
        "active_selfs": len(ACTIVE_SELF_CLIENTS),
        "ping_count": PING_COUNTER,
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.now().isoformat()
    }), 200

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    logger.info(f"🌐 وب‌سرور Keep-Alive سلف دارک روی پورت {port} راه‌اندازی شد.")
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def keep_alive_pinger():
    """ارسال سیگنال قوی هر ۵ دقیقه (۳۰۰ ثانیه) به آدرس خارجی Render برای جلوگیری کامل از خاموشی"""
    time.sleep(15)
    port = int(os.environ.get("PORT", 10000))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SelfDarkKeepAlive/4.0",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive"
    }
    while True:
        try:
            render_external_url = os.environ.get("RENDER_EXTERNAL_URL")
            if render_external_url:
                target_url = f"{render_external_url.rstrip('/')}/health?ts={int(time.time())}"
                res = requests.get(target_url, headers=headers, timeout=15)
                logger.info(f"⚡ سیگنال ضد خواب ۵ دقیقه‌ای سلف دارک به Render ارسال شد ({target_url}) | وضعیت: {res.status_code}")
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
#  ایموجی‌های پریمیوم متحرک و دکمه‌های تمام‌شیشه‌ای رنگی
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
    "💳": f'<tg-emoji emoji-id="{EMOJI_IDS["money"]}">💳</tg-emoji>',
    "📢": f'<tg-emoji emoji-id="{EMOJI_IDS["megaphone"]}">📢</tg-emoji>',
    "📣": f'<tg-emoji emoji-id="{EMOJI_IDS["megaphone"]}">📣</tg-emoji>',
    "✨": f'<tg-emoji emoji-id="{EMOJI_IDS["sparkles"]}">✨</tg-emoji>',
    "💯": f'<tg-emoji emoji-id="{EMOJI_IDS["hundred"]}">💯</tg-emoji>',
    "🌑": f'<tg-emoji emoji-id="{EMOJI_IDS["sparkles"]}">🌑</tg-emoji>',
    "🔹": f'<tg-emoji emoji-id="{EMOJI_IDS["gem"]}">🔹</tg-emoji>',
    "🟢": f'<tg-emoji emoji-id="{EMOJI_IDS["check"]}">🟢</tg-emoji>',
    "🔴": f'<tg-emoji emoji-id="{EMOJI_IDS["fire"]}">🔴</tg-emoji>',
    "❌": f'<tg-emoji emoji-id="{EMOJI_IDS["fire"]}">❌</tg-emoji>',
    "⛔": f'<tg-emoji emoji-id="{EMOJI_IDS["fire"]}">⛔</tg-emoji>',
    "⚠️": f'<tg-emoji emoji-id="{EMOJI_IDS["zap"]}">⚠️</tg-emoji>',
}

PERSIAN_DIGITS_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def normalize_digits(text: str) -> str:
    if not text:
        return ""
    return text.translate(PERSIAN_DIGITS_MAP)

def p_text(text: str) -> str:
    if not text:
        return ""
    out = text
    for k, v in PREMIUM_EMOJI_MAP.items():
        if k in out:
            out = out.replace(k, v)
    return out

def p_btn(
    text: str,
    callback_data: str = None,
    url: str = None,
    style: str = "primary",
    emoji_key: str = None,
) -> InlineKeyboardButton:
    kwargs = {}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    if style in ("primary", "success", "danger"):
        kwargs["style"] = style
    if emoji_key and emoji_key in EMOJI_IDS:
        kwargs["icon_custom_emoji_id"] = EMOJI_IDS[emoji_key]
    try:
        return InlineKeyboardButton(text, **kwargs)
    except TypeError:
        kwargs.pop("style", None)
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(text, **kwargs)

# ====================================================================
#  فهرست کامل ۴۰ قابلیت سلف دارک (۳۰ قابلیت اصلی + ۱۰ قابلیت اضافه شده)
# ====================================================================

SELF_DARK_FEATURES = {
    "f1":  {"title": "۱. پاسخگویی خودکار هوشمند (فقط پیوی اکانت‌ها)", "type": "toggle_val", "val_key": "autoreply_text", "val_label": "متن پاسخ خودکار (فقط به اکانت‌های واقعی، نه ربات‌ها)", "default_val": "سلام، در حال حاضر آنلاین نیستم. به زودی پاسخ می‌دهم. 🌑"},
    "f2":  {"title": "۲. دستیار هوش مصنوعی", "type": "toggle", "desc": "پاسخ به سوالات با دستور .ai در چت‌ها"},
    "f3":  {"title": "۳. تغییر خودکار بیوگرافی با ساعت", "type": "toggle_val", "val_key": "bio_template", "val_label": "قالب بیوگرافی (با {time})", "default_val": "🌑 Self Dark | ⏰ {time}"},
    "f4":  {"title": "۴. ساعت زنده در نام و نام خانوادگی پروفایل (دقیق هر دقیقه)", "type": "toggle_val", "val_key": "name_clock_tpl", "val_label": "ساعت فعلی گوشی شما (مثلاً 14:30) یا قالب نام خانوادگی با {time}", "default_val": "| {time}"},
    "f5":  {"title": "۵. زمان‌بندی تغییر پروفایل", "type": "toggle", "desc": "بروزرسانی زمان‌بندی شده اطلاعات پروفایل"},
    "f6":  {"title": "۶. مدیریت وضعیت اکانت (آنلاین دائمی)", "type": "toggle", "desc": "نگه داشتن وضعیت اکانت در حالت Online"},
    "f7":  {"title": "۷. ترجمه خودکار پیام‌ها", "type": "toggle", "desc": "ترجمه سریع با ریپلای دستور .tr روی پیام"},
    "f8":  {"title": "۸. تبدیل ویس به متن", "type": "toggle", "desc": "تبدیل پیام صوتی به متن با دستور .v2t"},
    "f9":  {"title": "۹. خلاصه‌سازی پیام‌های طولانی", "type": "toggle", "desc": "خلاصه‌سازی متن‌های طولانی با ریپلای .sum"},
    "f10": {"title": "۱۰. دسته‌بندی هوشمند پیام‌ها", "type": "toggle", "desc": "دسته‌بندی گفتگوهای کاربر"},
    "f11": {"title": "۱۱. ذخیره پیام‌های حذف‌شده (بدون ارسال در Saved)", "type": "toggle", "desc": "ذخیره بی‌صدا در دیتابیس و مشاهده با دستور .حذفیات"},
    "f12": {"title": "۱۲. ذخیره تاریخچه ویرایش پیام‌ها (بدون ارسال در Saved)", "type": "toggle", "desc": "ذخیره بی‌صدا در دیتابیس و مشاهده با دستور .ویرایشها"},
    "f13": {"title": "۱۳. پشتیبان‌گیری از گفتگوها", "type": "toggle", "desc": "تهیه نسخه پشتیبان از پیام‌های چت با دستور .backup"},
    "f14": {"title": "۱۴. جستجوی پیشرفته پیام‌ها", "type": "toggle", "desc": "جستجوی سریع در کل چت با دستور .find"},
    "f15": {"title": "۱۵. بایگانی خودکار گفتگوها", "type": "toggle", "desc": "آرشیو کردن چت‌های بی‌صدا و غیرفعال"},
    "f16": {"title": "۱۶. یادداشت خصوصی برای هر گفتگو", "type": "toggle", "desc": "ذخیره یادداشت روی هر کاربر با دستور .note"},
    "f17": {"title": "۱۷. سنجاق خودکار پیام‌های مهم", "type": "toggle", "desc": "پین کردن خودکار پیام‌های حاوی کلمه «مهم»"},
    "f18": {"title": "۱۸. یادآوری پیام‌ها (Reminder)", "type": "toggle", "desc": "تنظیم یادآور در چت با دستور .rem"},
    "f19": {"title": "۱۹. دستورات سریع اختصاصی", "type": "toggle", "desc": "فعال‌سازی دستورات سریع .ping و .info و .id"},
    "f20": {"title": "۲۰. مدیریت چند اکانت", "type": "toggle", "desc": "پشتیبانی از اتصال همزمان در سلف دارک"},
    "f21": {"title": "۲۱. پاسخ با سبک دلخواه (فونت/بولد)", "type": "toggle_val", "val_key": "text_style", "val_label": "سبک نوشتار (bold / italic / mono / normal)", "default_val": "bold"},
    "f22": {"title": "۲۲. حافظه اختصاصی هوش مصنوعی", "type": "toggle", "desc": "نگهداری زمینه مکالمه در پاسخ‌های هوشمند"},
    "f23": {"title": "۲۳. پیشنهاد خودکار استیکر", "type": "toggle", "desc": "واکنش استیکری خودکار به کلمات خاص"},
    "f24": {"title": "۲۴. پیشنهاد هوشمند شکلک (ری‌اکشن خودکار پیوی)", "type": "toggle_val", "val_key": "auto_react_emoji", "val_label": "ایموجی ری‌اکشن خودکار", "default_val": "🔥"},
    "f25": {"title": "۲۵. ساخت دستورات شخصی", "type": "toggle_val", "val_key": "custom_cmd", "val_label": "دستور شخصی (فرمت کلید=پاسخ)", "default_val": ".salam=علیکم السلام عزیز 🌹"},
    "f26": {"title": "۲۶. دفترچه یادداشت خصوصی", "type": "toggle", "desc": "مدیریت دفترچه یادداشت با دستور .notebook"},
    "f27": {"title": "۲۷. گزارش فعالیت روزانه", "type": "toggle", "desc": "مشاهده گزارش عملکرد با دستور .report"},
    "f28": {"title": "۲۸. آمار گفتگوها و پیام‌ها", "type": "toggle", "desc": "دریافت آمار دقیق اکانت با دستور .stats"},
    "f29": {"title": "۲۹. ارسال زمان‌بندی‌شده پیام‌ها", "type": "toggle", "desc": "ارسال پیام تاخیری با دستور .later"},
    "f30": {"title": "۳۰. مدیریت هوشمند اعلان‌ها", "type": "toggle", "desc": "فیلتر کردن اعلان‌های مزاحم و تبلیغاتی"},
    # ۱۰ قابلیت اضافه شده اختصاصی سلف دارک
    "f31": {"title": "۳۱. حالت روح (سین بدون تیک دوم)", "type": "toggle", "desc": "عدم ارسال تیک دوم خوانده شدن در پیوی‌ها"},
    "f32": {"title": "۳۲. تایپینگ و اکشن دائمی (Auto Action)", "type": "toggle_val", "val_key": "chat_action", "val_label": "نوع اکشن (typing / game / voice)", "default_val": "typing"},
    "f33": {"title": "۳۳. دانلود مدیاهای تایمردار", "type": "toggle", "desc": "قابلیت مدیریت مدیاهای تایمردار"},
    "f34": {"title": "۳۴. ضد لینک و ضد اسپم پیوی", "type": "toggle", "desc": "حذف خودکار لینک‌های تبلیغاتی در پیوی"},
    "f35": {"title": "۳۵. قفل پیوی (منشی هوشمند)", "type": "toggle", "desc": "محدود کردن پیام‌های افراد ناشناس در زمان شلوغی"},
    "f36": {"title": "۳۶. خوش‌آمدگویی خودکار در گروه‌ها", "type": "toggle_val", "val_key": "welcome_text", "val_label": "متن خوش‌آمدگویی گروه", "default_val": "خوش آمدی عزیز به گروه! 🌺"},
    "f37": {"title": "۳۷. ماشین‌حساب سریع در چت", "type": "toggle", "desc": "محاسبه عبارات ریاضی با دستور .calc"},
    "f38": {"title": "۳۸. ساخت فونت انگلیسی و فارسی", "type": "toggle", "desc": "زیباسازی متن با دستور .font"},
    "f39": {"title": "۳۹. شکارچی تگ و منشن", "type": "toggle", "desc": "ثبت منشن‌های گروه بدون ارسال پیام مزاحم در Saved Messages"},
    "f40": {"title": "۴۰. پاکسازی سریع پیام‌ها (Purge)", "type": "toggle", "desc": "حذف سریع پیام‌های چت با دستور .del"},
}

def get_default_features_dict() -> dict:
    data = {
        "tabchi_enabled": True,
        "clock_offset_mins": 210,  # پیش‌فرض +03:30 به وقت ایران (قابل تنظیم دقیق با ساعت دستگاه هر کاربر)
        "name_clock_tpl": "| {time}",
    }
    for k, meta in SELF_DARK_FEATURES.items():
        data[k] = True if k in ("f19", "f28", "f37") else False
        if "val_key" in meta:
            data[meta["val_key"]] = meta["default_val"]
    return data

# ====================================================================
#  دیتابیس SQLite و جداول سلف دارک، الماس، تبچی و ادمین
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
                diamonds INTEGER DEFAULT 0,
                total_spent_diamonds INTEGER DEFAULT 0,
                invited_by INTEGER DEFAULT NULL,
                referral_verified INTEGER DEFAULT 0,
                referrals_count INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                last_daily_gift TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS self_accounts (
                user_id INTEGER PRIMARY KEY,
                phone TEXT NOT NULL,
                session_string TEXT NOT NULL,
                is_running INTEGER DEFAULT 1,
                activated_at TEXT NOT NULL,
                last_hourly_charge TEXT NOT NULL,
                features_json TEXT NOT NULL,
                msg_counter INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS tabchi_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                chat_title TEXT DEFAULT 'گروه تبچی',
                is_active INTEGER DEFAULT 1,
                interval_minutes INTEGER DEFAULT 10,
                delay_seconds INTEGER DEFAULT 3,
                banner_text TEXT DEFAULT '📣 پیام خودکار تبچی سلف دارک',
                last_sent_at TEXT DEFAULT NULL,
                UNIQUE(user_id, chat_id)
            );

            CREATE TABLE IF NOT EXISTS edited_cache (
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                msg_id INTEGER NOT NULL,
                sender_name TEXT,
                text_content TEXT,
                PRIMARY KEY (user_id, chat_id, msg_id)
            );

            CREATE TABLE IF NOT EXISTS private_notes (
                user_id INTEGER NOT NULL,
                target_id TEXT NOT NULL,
                note_text TEXT NOT NULL,
                PRIMARY KEY (user_id, target_id)
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

            CREATE TABLE IF NOT EXISTS ton_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                diamonds INTEGER NOT NULL,
                ton_amount TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS gift_codes (
                code TEXT PRIMARY KEY,
                diamonds INTEGER NOT NULL,
                max_uses INTEGER DEFAULT 1,
                used_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS gift_uses (
                code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (code, user_id)
            );
        """)

        default_settings = {
            "ton_wallet": "UQD_YOUR_TON_WALLET_ADDRESS_HERE",
            "ton_per_diamond": "0.0005",
            "min_buy_diamonds": "50",
            "activation_cost": "30",
            "hourly_cost": "3",
            "referral_enabled": "1",
            "referral_reward": "5",
            "welcome_bonus": "0",
            "daily_gift_diamonds": "2",
            "rial_support_id": "@kanfingfreesup",
            "bot_active": "1",
            "self_new_login_enabled": "1",
            "tabchi_global_enabled": "1",
            "transfer_enabled": "1",
            "min_transfer_diamonds": "50",
            "help_extra_note": "🌟 به راهنمای جامع سلف دارک خوش آمدید.",
        }
        for k, v in default_settings.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # حذف هرگونه کانال جوین اجباری قبلی یا پیش‌فرض که ادمین اضافه نکرده است
        fch_cleaned = conn.execute("SELECT value FROM settings WHERE key='force_channels_cleaned_v4'").fetchone()
        if not fch_cleaned:
            conn.execute("DELETE FROM force_channels")
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('force_channels_cleaned_v4', '1')")

def get_setting(key: str, default: str = "") -> str:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

def set_setting(key: str, value: str):
    with closing(get_conn()) as conn, conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_or_create_user(user_id: int, username: str = "", first_name: str = "", invited_by: int = None):
    with closing(get_conn()) as conn, conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            welcome_d = int(get_setting("welcome_bonus", "0"))
            valid_inv = invited_by if (invited_by and invited_by != user_id) else None
            conn.execute(
                """INSERT INTO users (user_id, username, first_name, joined_at, diamonds, invited_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username or "", first_name or "کاربر", datetime.now().isoformat(), welcome_d, valid_inv)
            )
            user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        else:
            conn.execute(
                "UPDATE users SET username=?, first_name=? WHERE user_id=?",
                (username or "", first_name or "کاربر", user_id)
            )
        return user

def add_user_diamonds(user_id: int, delta: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("UPDATE users SET diamonds = MAX(0, diamonds + ?) WHERE user_id=?", (delta, user_id))
        if delta < 0:
            conn.execute("UPDATE users SET total_spent_diamonds = total_spent_diamonds + ? WHERE user_id=?", (abs(delta), user_id))

def get_self_account(user_id: int):
    with closing(get_conn()) as conn:
        return conn.execute("SELECT * FROM self_accounts WHERE user_id=?", (user_id,)).fetchone()

def get_user_features(user_id: int) -> dict:
    acc = get_self_account(user_id)
    defaults = get_default_features_dict()
    if not acc or not acc["features_json"]:
        return defaults
    try:
        loaded = json.loads(acc["features_json"])
        defaults.update(loaded)
        return defaults
    except Exception:
        return defaults

def save_user_features(user_id: int, feats: dict):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "UPDATE self_accounts SET features_json=? WHERE user_id=?",
            (json.dumps(feats, ensure_ascii=False), user_id)
        )

# ====================================================================
#  جوین اجباری و تایید زیرمجموعه (هر زیرمجموعه = ۵ الماس)
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
    if get_setting("referral_enabled", "1") == "0":
        return
    with closing(get_conn()) as conn, conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user or not user["invited_by"] or user["referral_verified"] == 1:
            return
        inviter_id = user["invited_by"]
        reward = int(get_setting("referral_reward", "5"))
        conn.execute("UPDATE users SET referral_verified=1 WHERE user_id=?", (user_id,))
        conn.execute(
            "UPDATE users SET referrals_count = referrals_count + 1, diamonds = diamonds + ? WHERE user_id=?",
            (reward, inviter_id)
        )
        inviter = conn.execute("SELECT * FROM users WHERE user_id=?", (inviter_id,)).fetchone()

    if inviter:
        try:
            await bot.send_message(
                chat_id=inviter_id,
                text=p_text(
                    f"🎉 <b>زیرمجموعه جدید در سلف دارک تایید شد!</b>\n\n"
                    f"👤 کاربر <b>{html.escape(user['first_name'])}</b> در کانال‌های ربات عضو شد.\n"
                    f"💎 پاداش شما: <b>+{reward} الماس</b> به حساب شما اضافه شد!\n"
                    f"💰 موجودی فعلی شما: <b>{inviter['diamonds']} الماس</b>"
                ),
                parse_mode=ParseMode.HTML
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
#  موتور واقعی اجرای سلف دارک (Telethon Worker) + تبچی هوشمند
# ====================================================================

FONT_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
)

CLOCK_FANCY_MAP = str.maketrans("0123456789", "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵")

def compute_offset_mins_from_hhmm(hh: int, mm: int) -> int:
    """محاسبه اختلاف دقیق دقیقه ساعت دستگاه کاربر با ساعت جهانی UTC"""
    utc_now = datetime.now(timezone.utc)
    utc_total = utc_now.hour * 60 + utc_now.minute
    user_total = (hh % 24) * 60 + (mm % 60)
    diff = user_total - utc_total
    if diff < -720:
        diff += 1440
    elif diff > 840:
        diff -= 1440
    return diff

def get_user_device_time_str(feats: dict) -> tuple[str, str]:
    """برگرداندن ساعت دقیق فعلی بر اساس ساعت دستگاه کاربر (معمولی و فونت دارک)"""
    offset_mins = int(feats.get("clock_offset_mins", 210))
    user_dt = datetime.now(timezone.utc) + timedelta(minutes=offset_mins)
    normal_t = user_dt.strftime("%H:%M")
    fancy_t = normal_t.translate(CLOCK_FANCY_MAP)
    return normal_t, fancy_t

def strip_clock_from_text(name_str: str) -> str:
    """حذف ساعت‌های قبلی از انتهای نام یا نام خانوادگی برای جلوگیری از تکرار ساعت"""
    if not name_str:
        return ""
    cleaned = re.sub(r"[\s|•⏰⌚🌑\-]*([0-9𝟬-𝟵]{1,2}:[0-9𝟬-𝟵]{2})\s*$", "", name_str)
    return cleaned.strip()

async def update_user_profile_clock_now(uid: int, client: TelegramClient, force: bool = False):
    """بروزرسانی دقیق ساعت در نام/نام خانوادگی پروفایل و بیوگرافی کاربر"""
    feats = get_user_features(uid)
    want_name_clock = bool(feats.get("f4"))
    want_bio_clock = bool(feats.get("f3"))
    want_online = bool(feats.get("f6"))

    normal_t, fancy_t = get_user_device_time_str(feats)

    if not force and LAST_CLOCK_MINUTE.get(uid) == normal_t:
        return

    try:
        if want_online:
            await client(functions.account.UpdateStatusRequest(offline=False))

        profile_kwargs = {}

        if want_name_clock:
            me = await client.get_me()
            raw_first = getattr(me, "first_name", "") or "User"
            clean_first = strip_clock_from_text(raw_first) or raw_first
            tpl = str(feats.get("name_clock_tpl", "| {time}")).strip()
            if "{time}" not in tpl:
                tpl = "| {time}"
            clock_str = tpl.replace("{time}", fancy_t)
            # قرار دادن نام اصلی در بخش نام و ساعت زنده در بخش نام خانوادگی (Last Name) و کنار نام
            profile_kwargs["first_name"] = clean_first[:45]
            profile_kwargs["last_name"] = clock_str[:45]

        if want_bio_clock:
            bio_tpl = str(feats.get("bio_template", "🌑 Self Dark | ⏰ {time}"))
            profile_kwargs["about"] = bio_tpl.replace("{time}", normal_t)[:70]

        if profile_kwargs:
            await client(functions.account.UpdateProfileRequest(**profile_kwargs))
            LAST_CLOCK_MINUTE[uid] = normal_t
    except Exception as e:
        logger.debug(f"خطا در بروزرسانی ساعت پروفایل کاربر {uid}: {e}")

async def setup_telethon_handlers(user_id: int, client: TelegramClient):
    """ثبت تمام ۴۰ قابلیت سلف دارک و دستورات تبچی هوشمند روی کلاینت Telethon کاربر"""

    @client.on(events.NewMessage)
    async def on_any_new_message(event):
        feats = get_user_features(user_id)

        # شمارش پیام‌ها و کش کردن بی‌صدا برای Anti-Delete و Anti-Edit (بدون ارسال هیچ گزارشی به Saved Messages)
        with closing(get_conn()) as conn, conn:
            conn.execute("UPDATE self_accounts SET msg_counter = msg_counter + 1 WHERE user_id=?", (user_id,))
            if event.raw_text and (feats.get("f11") or feats.get("f12")) and not event.out:
                sender = await event.get_sender()
                sname = getattr(sender, "first_name", "کاربر") or "کاربر"
                conn.execute(
                    "INSERT OR REPLACE INTO edited_cache (user_id, chat_id, msg_id, sender_name, text_content) VALUES (?, ?, ?, ?, ?)",
                    (user_id, event.chat_id, event.id, sname, event.raw_text[:800])
                )

        # دستورات خروجی صاحب اکانت (Outgoing Self Dark Commands)
        if event.out and event.raw_text:
            txt = event.raw_text.strip()

            # دستور همگام‌سازی مستقیم ساعت پروفایل با ساعت گوشی کاربر: «.ساعت 14:30»
            if txt.startswith(".ساعت ") or txt.startswith(".clock "):
                arg_t = normalize_digits(txt.split(" ", 1)[1].strip())
                m_time = re.match(r"^(\d{1,2}):(\d{2})$", arg_t)
                if m_time:
                    hh, mm = int(m_time.group(1)), int(m_time.group(2))
                    offset_m = compute_offset_mins_from_hhmm(hh, mm)
                    feats["clock_offset_mins"] = offset_m
                    feats["f4"] = True
                    save_user_features(user_id, feats)
                    await update_user_profile_clock_now(user_id, client, force=True)
                    await event.edit(f"⏰ <b>ساعت پروفایل با ساعت دستگاه شما (<code>{hh:02d}:{mm:02d}</code>) تنظیم و فعال شد!</b>\nاز این پس هر دقیقه به‌صورت دقیق بروزرسانی می‌شود.", parse_mode="html")
                    return

            # دستور ثبت گروه در تبچی هوشمند سلف دارک: «تنظیم چت»
            if txt == "تنظیم چت" and (event.is_group or event.is_channel):
                chat = await event.get_chat()
                title = getattr(chat, "title", "گروه تبچی")
                with closing(get_conn()) as conn, conn:
                    conn.execute(
                        """INSERT OR REPLACE INTO tabchi_groups (user_id, chat_id, chat_title, is_active, interval_minutes, delay_seconds)
                           VALUES (?, ?, ?, 1, 10, 3)""",
                        (user_id, event.chat_id, title)
                    )
                await event.edit(f"✅ <b>گروه «{html.escape(title)}» با موفقیت در تبچی هوشمند سلف دارک ثبت شد!</b>\n⚙️ از داخل ربات سلف دارک می‌توانید بنر و زمان ارسال آن را مدیریت کنید.", parse_mode="html")
                return

            if txt == "حذف چت" and (event.is_group or event.is_channel):
                with closing(get_conn()) as conn, conn:
                    conn.execute("DELETE FROM tabchi_groups WHERE user_id=? AND chat_id=?", (user_id, event.chat_id))
                await event.edit("🗑 <b>این گروه از لیست تبچی سلف دارک حذف شد.</b>", parse_mode="html")
                return

            # ۱۹. دستورات سریع اختصاصی (.ping, .id, .info, .help)
            if feats.get("f19", True):
                if txt == ".ping":
                    t0 = time.time()
                    await event.edit("🌑 Pong...")
                    ms = int((time.time() - t0) * 1000)
                    await event.edit(f"🌑 <b>Self Dark Online!</b>\n⚡ سرعت پاسخ: <code>{ms}ms</code>", parse_mode="html")
                    return
                elif txt == ".id":
                    if event.is_reply:
                        rep = await event.get_reply_message()
                        await event.edit(f"🔢 آیدی کاربر: <code>{rep.sender_id}</code>\n💬 آیدی چت: <code>{event.chat_id}</code>", parse_mode="html")
                    else:
                        await event.edit(f"💬 آیدی چت: <code>{event.chat_id}</code>", parse_mode="html")
                    return

            # ۲۸. آمار گفتگوها و پیام‌ها (.stats)
            if feats.get("f28", True) and txt == ".stats":
                acc = get_self_account(user_id)
                cnt = acc["msg_counter"] if acc else 0
                with closing(get_conn()) as conn:
                    tc = conn.execute("SELECT COUNT(*) c FROM tabchi_groups WHERE user_id=?", (user_id,)).fetchone()["c"]
                await event.edit(
                    f"📊 <b>آمار زنده سلف دارک:</b>\n"
                    f"💬 پیام‌های پردازش شده: <code>{cnt}</code>\n"
                    f"📣 گروه‌های ثبت‌شده تبچی: <code>{tc} گروه</code>",
                    parse_mode="html"
                )
                return

            # ۳۷. ماشین‌حساب سریع (.calc)
            if feats.get("f37", True) and txt.startswith(".calc "):
                expr = txt[6:].strip()
                if re.match(r"^[0-9+\-*/().\s]+$", expr):
                    try:
                        res = eval(expr, {"__builtins__": None}, {})
                        await event.edit(f"🧮 <code>{expr}</code> = <b>{res}</b>", parse_mode="html")
                    except Exception:
                        await event.edit("❌ خطا در عبارت ریاضی.")
                return

            # ۳۸. ساخت فونت (.font)
            if feats.get("f38") and txt.startswith(".font "):
                raw_f = txt[6:].translate(FONT_MAP)
                await event.edit(raw_f)
                return

            # ۴۰. پاکسازی سریع پیام‌ها (.del)
            if feats.get("f40") and txt.startswith(".del"):
                parts = txt.split()
                count = int(parts[1]) if (len(parts) > 1 and parts[1].isdigit()) else 5
                count = min(count, 30)
                msgs = [m.id async for m in client.iter_messages(event.chat_id, limit=count + 1, from_user="me")]
                await client.delete_messages(event.chat_id, msgs)
                return

            # ۱۶. یادداشت خصوصی (.note) و ۲۶. دفترچه یادداشت (.notebook)
            if feats.get("f16") and txt.startswith(".note "):
                note_val = txt[6:].strip()
                with closing(get_conn()) as conn, conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO private_notes (user_id, target_id, note_text) VALUES (?, ?, ?)",
                        (user_id, str(event.chat_id), note_val)
                    )
                await event.edit("📝 یادداشت خصوصی برای این گفتگو ذخیره شد.")
                return

            if feats.get("f26") and txt == ".notebook":
                with closing(get_conn()) as conn:
                    notes = conn.execute("SELECT * FROM private_notes WHERE user_id=?", (user_id,)).fetchall()
                if not notes:
                    await event.edit("📒 دفترچه یادداشت سلف دارک خالی است.")
                else:
                    lines = ["📒 <b>دفترچه یادداشت خصوصی سلف دارک:</b>"]
                    for n in notes[:15]:
                        lines.append(f"• <code>{n['target_id']}</code>: {html.escape(n['note_text'])}")
                    await event.edit("\n".join(lines), parse_mode="html")
                return

            # ۹. خلاصه‌سازی پیام طولانی (.sum)
            if feats.get("f9") and txt == ".sum" and event.is_reply:
                rep = await event.get_reply_message()
                if rep and rep.raw_text:
                    words = rep.raw_text.split()
                    summary = " ".join(words[:35]) + ("..." if len(words) > 35 else "")
                    await event.edit(f"📝 <b>خلاصه پیام ({len(words)} کلمه):</b>\n{html.escape(summary)}", parse_mode="html")
                return

            # ۷. ترجمه سریع (.tr)
            if feats.get("f7") and txt.startswith(".tr") and event.is_reply:
                rep = await event.get_reply_message()
                if rep and rep.raw_text:
                    try:
                        r = requests.get(
                            "https://translate.googleapis.com/translate_a/single",
                            params={"client": "gtx", "sl": "auto", "tl": "fa", "dt": "t", "q": rep.raw_text[:500]},
                            timeout=8
                        ).json()
                        tr_text = "".join([part[0] for part in r[0] if part[0]])
                        await event.edit(f"🌐 <b>ترجمه سلف دارک:</b>\n{html.escape(tr_text)}", parse_mode="html")
                    except Exception:
                        await event.edit("⚠️ خطا در ارتباط با سرویس ترجمه.")
                return

            # ۲۵. ساخت دستورات شخصی
            if feats.get("f25"):
                custom_rule = feats.get("custom_cmd", "")
                if "=" in custom_rule:
                    k_cmd, v_resp = custom_rule.split("=", 1)
                    if txt == k_cmd.strip():
                        await event.edit(v_resp.strip())
                        return

            # ۲۱. پاسخ با سبک دلخواه (بولد/ایتالیک/مونو خودکار روی پیام‌های خروجی عادی)
            if feats.get("f21") and not txt.startswith(".") and len(txt) < 300:
                style_mode = feats.get("text_style", "bold")
                try:
                    if style_mode == "bold":
                        await event.edit(f"<b>{html.escape(txt)}</b>", parse_mode="html")
                    elif style_mode == "italic":
                        await event.edit(f"<i>{html.escape(txt)}</i>", parse_mode="html")
                    elif style_mode == "mono":
                        await event.edit(f"<code>{html.escape(txt)}</code>", parse_mode="html")
                except Exception:
                    pass

        # پردازش پیام‌های ورودی از دیگران (Incoming Messages)
        if not event.out:
            # ۱۷. سنجاق خودکار پیام‌های مهم
            if feats.get("f17") and event.raw_text and ("مهم" in event.raw_text or "#مهم" in event.raw_text):
                try:
                    await event.pin()
                except Exception:
                    pass

            # بررسی اینکه در پیوی، فرستنده حتماً یک اکانت واقعی انسان باشد (نه ربات و نه اکانت سرویس تلگرام)
            if event.is_private:
                sender = await event.get_sender()
                is_real_human_account = (
                    sender is not None
                    and isinstance(sender, types.User)
                    and not getattr(sender, "bot", False)
                    and not getattr(sender, "deleted", False)
                    and not getattr(sender, "support", False)
                    and sender.id not in (777000, user_id)
                )

                if is_real_human_account:
                    # ۲۴. پیشنهاد هوشمند شکلک / ری‌اکشن خودکار (فقط پیوی اکانت‌ها)
                    if feats.get("f24"):
                        emj = feats.get("auto_react_emoji", "🔥")
                        try:
                            await client(functions.messages.SendReactionRequest(
                                peer=event.chat_id,
                                msg_id=event.id,
                                reaction=[types.ReactionEmoji(emoticon=emj)]
                            ))
                        except Exception:
                            pass

                    # ۳۴. ضد لینک پیوی (فقط پیوی اکانت‌ها)
                    if feats.get("f34") and event.raw_text:
                        if "t.me/" in event.raw_text or "http://" in event.raw_text or "https://" in event.raw_text:
                            try:
                                await event.delete()
                                return
                            except Exception:
                                pass

                    # ۱. پاسخگویی خودکار هوشمند (فقط برای پیوی اکانت‌های واقعی، نه ربات‌ها!)
                    if feats.get("f1"):
                        now_ts = time.time()
                        last_rep = AUTOREPLY_COOLDOWN.get((user_id, sender.id), 0.0)
                        if (now_ts - last_rep) >= 60.0:
                            AUTOREPLY_COOLDOWN[(user_id, sender.id)] = now_ts
                            reply_txt = feats.get("autoreply_text", "سلام، در حال حاضر آنلاین نیستم. 🌑")
                            try:
                                await event.reply(reply_txt)
                            except Exception:
                                pass

                    # ۳۲. اکشن تایپینگ خودکار (فقط پیوی اکانت‌ها)
                    if feats.get("f32"):
                        act = feats.get("chat_action", "typing")
                        try:
                            async with client.action(event.chat_id, act):
                                await asyncio.sleep(2)
                        except Exception:
                            pass

    # توجه: طبق درخواست شما، هیچ گزارش لحظه‌ای (حذف، ویرایش یا منشن) به Saved Messages ("me") ارسال نمی‌شود.

async def start_single_self_client(user_id: int, session_str: str) -> bool:
    if user_id in ACTIVE_SELF_CLIENTS:
        try:
            await ACTIVE_SELF_CLIENTS[user_id].disconnect()
        except Exception:
            pass
        ACTIVE_SELF_CLIENTS.pop(user_id, None)

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning(f"سشن کاربر {user_id} دیگر معتبر نیست.")
            with closing(get_conn()) as conn, conn:
                conn.execute("UPDATE self_accounts SET is_running=0 WHERE user_id=?", (user_id,))
            return False

        await setup_telethon_handlers(user_id, client)
        ACTIVE_SELF_CLIENTS[user_id] = client
        await update_user_profile_clock_now(user_id, client, force=True)
        logger.info(f"🌑 سلف دارک برای کاربر {user_id} با موفقیت روشن شد.")
        return True
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی کلاینت سلف دارک {user_id}: {e}")
        return False

async def stop_single_self_client(user_id: int):
    client = ACTIVE_SELF_CLIENTS.pop(user_id, None)
    LAST_CLOCK_MINUTE.pop(user_id, None)
    if client:
        try:
            await client.disconnect()
        except Exception:
            pass
    with closing(get_conn()) as conn, conn:
        conn.execute("UPDATE self_accounts SET is_running=0 WHERE user_id=?", (user_id,))

# ====================================================================
#  تسک‌های پس‌زمینه: ۱. کسر ساعتی ۳ الماس | ۲. ساعت دقیق هر دقیقه در پروفایل | ۳. ارسال خودکار تبچی
# ====================================================================

async def accurate_profile_clock_loop():
    """حلقه بسیار دقیق که هر ۵ ثانیه بررسی می‌کند و دقیقاً در ثانیه تغییر هر دقیقه ساعت نام/نام خانوادگی و بیو را بروز می‌کند"""
    while True:
        try:
            for uid, client in list(ACTIVE_SELF_CLIENTS.items()):
                await update_user_profile_clock_now(uid, client, force=False)
        except Exception as e:
            logger.debug(f"Clock loop error: {e}")
        await asyncio.sleep(5)

async def hourly_diamond_billing_job(context: ContextTypes.DEFAULT_TYPE):
    """هر دقیقه چک می‌کند و به ازای هر ۱ ساعت روشن بودن سلف دارک، ۳ الماس از حساب کاربر کسر می‌کند"""
    hourly_cost = int(get_setting("hourly_cost", "3"))
    now = datetime.now()

    with closing(get_conn()) as conn:
        running_accs = conn.execute("SELECT * FROM self_accounts WHERE is_running=1").fetchall()

    for acc in running_accs:
        uid = acc["user_id"]
        if is_admin(uid):
            continue
        try:
            last_charge = datetime.fromisoformat(acc["last_hourly_charge"])
        except Exception:
            last_charge = now - timedelta(hours=1)

        if (now - last_charge) >= timedelta(hours=1):
            with closing(get_conn()) as conn, conn:
                u = conn.execute("SELECT diamonds FROM users WHERE user_id=?", (uid,)).fetchone()
                current_d = u["diamonds"] if u else 0

                if current_d >= hourly_cost:
                    conn.execute(
                        "UPDATE users SET diamonds = diamonds - ?, total_spent_diamonds = total_spent_diamonds + ? WHERE user_id=?",
                        (hourly_cost, hourly_cost, uid)
                    )
                    conn.execute(
                        "UPDATE self_accounts SET last_hourly_charge=? WHERE user_id=?",
                        (now.isoformat(), uid)
                    )
                else:
                    # خاموش کردن خودکار سلف در صورت اتمام الماس
                    await stop_single_self_client(uid)
                    try:
                        await context.bot.send_message(
                            chat_id=uid,
                            text=p_text(
                                f"⚠️ <b>سلف دارک شما به دلیل اتمام موجودی الماس متوقف شد!</b>\n\n"
                                f"💎 هزینه روشن بودن سلف ساعتی <b>{hourly_cost} الماس</b> است و موجودی شما به پایان رسید.\n"
                                f"👇 جهت روشن شدن مجدد سلف دارک، حساب خود را شارژ کنید:"
                            ),
                            parse_mode=ParseMode.HTML,
                            reply_markup=InlineKeyboardMarkup([
                                [p_btn("خرید الماس (TON / کارت به کارت)", callback_data="menu:buy_diamonds", style="success", emoji_key="gem")],
                                [p_btn("دریافت الماس رایگان (زیرمجموعه)", callback_data="menu:referral", style="primary", emoji_key="gift")]
                            ])
                        )
                    except Exception:
                        pass

async def profile_and_tabchi_worker_job(context: ContextTypes.DEFAULT_TYPE):
    """اجرای زمان‌بندی تغییر بیوگرافی/نام اکانت و ارسال خودکار بنرهای تبچی هوشمند"""
    now = datetime.now()

    for uid, client in list(ACTIVE_SELF_CLIENTS.items()):
        feats = get_user_features(uid)

        # بروزرسانی ساعت پروفایل و بیوگرافی
        await update_user_profile_clock_now(uid, client, force=False)

        # اجرای تبچی هوشمند برای گروه‌های ثبت شده کاربر
        if get_setting("tabchi_global_enabled", "1") == "1" and feats.get("tabchi_enabled", True):
            with closing(get_conn()) as conn:
                groups = conn.execute(
                    "SELECT * FROM tabchi_groups WHERE user_id=? AND is_active=1",
                    (uid,)
                ).fetchall()

            for grp in groups:
                interval_m = max(1, grp["interval_minutes"])
                should_send = False
                if not grp["last_sent_at"]:
                    should_send = True
                else:
                    try:
                        last_dt = datetime.fromisoformat(grp["last_sent_at"])
                        if (now - last_dt) >= timedelta(minutes=interval_m):
                            should_send = True
                    except Exception:
                        should_send = True

                if should_send:
                    try:
                        await client.send_message(grp["chat_id"], grp["banner_text"])
                        with closing(get_conn()) as conn, conn:
                            conn.execute(
                                "UPDATE tabchi_groups SET last_sent_at=? WHERE id=?",
                                (now.isoformat(), grp["id"])
                            )
                        await asyncio.sleep(max(1, grp["delay_seconds"]))
                    except Exception as e:
                        logger.warning(f"خطا در ارسال تبچی به گروه {grp['chat_id']}: {e}")

# ====================================================================
#  کیبوردهای تمام‌شیشه‌ای و رنگی سلف دارک (با تم غالب آبی Primary)
# ====================================================================

def main_inline_keyboard(user_id: int) -> InlineKeyboardMarkup:
    acc = get_self_account(user_id)
    self_status = "🟢 فعال" if (acc and acc["is_running"] == 1) else "🔴 غیرفعال"
    rows = [
        [
            p_btn(f"فعالسازی و اتصال سلف دارک ({self_status})", callback_data="menu:activate_self", style="primary", emoji_key="rocket"),
        ],
        [
            p_btn("مدیریت ۴۰ قابلیت سلف دارک", callback_data="self:features_page:0", style="primary", emoji_key="sparkles"),
            p_btn("تبچی هوشمند سلف دارک", callback_data="menu:tabchi", style="primary", emoji_key="megaphone"),
        ],
        [
            p_btn("خرید الماس (TON / ریالی)", callback_data="menu:buy_diamonds", style="success", emoji_key="gem"),
            p_btn("انتقال الماس به دیگران", callback_data="menu:transfer_diamonds", style="primary", emoji_key="sparkles"),
        ],
        [
            p_btn("زیرمجموعه‌گیری (۵ الماس رایگان)", callback_data="menu:referral", style="primary", emoji_key="gift"),
            p_btn("هدیه روزانه و کد هدیه", callback_data="menu:daily_gift", style="success", emoji_key="party"),
        ],
        [
            p_btn("حساب کاربری من", callback_data="menu:profile", style="primary", emoji_key="star"),
            p_btn("راهنمای کامل سلف دارک", callback_data="menu:help", style="primary", emoji_key="zap"),
        ],
    ]
    if is_admin(user_id):
        rows.append([
            p_btn("پنل مدیریت سلف دارک (۴۰ قابلیت)", callback_data="admin:page:0", style="danger", emoji_key="crown")
        ])
    return InlineKeyboardMarkup(rows)

def build_features_keyboard(user_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """صفحه‌بندی ۴۰ قابلیت سلف دارک (هر صفحه ۱۰ قابلیت با دکمه‌های آبی، سبز و قرمز)"""
    feats = get_user_features(user_id)
    keys = list(SELF_DARK_FEATURES.keys())
    per_page = 10
    total_pages = (len(keys) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    slice_keys = keys[page * per_page : (page + 1) * per_page]

    rows = []
    for k in slice_keys:
        meta = SELF_DARK_FEATURES[k]
        is_on = feats.get(k, False)
        status_str = "🟢 روشن" if is_on else "🔴 خاموش"
        btn_style = "success" if is_on else "primary"
        row = [p_btn(f"{meta['title']} ({status_str})", callback_data=f"ftoggle:{k}:{page}", style=btn_style)]
        if "val_key" in meta:
            row.append(p_btn("⚙️ تنظیم مقدار", callback_data=f"fsetval:{k}:{page}", style="primary"))
        rows.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(p_btn("⬅️ صفحه قبل", callback_data=f"self:features_page:{page - 1}", style="primary"))
    nav_row.append(p_btn(f"صفحه {page + 1} از {total_pages}", callback_data="noop", style="primary"))
    if page < total_pages - 1:
        nav_row.append(p_btn("صفحه بعد ➡️", callback_data=f"self:features_page:{page + 1}", style="primary"))
    rows.append(nav_row)

    rows.append([
        p_btn("روشن کردن همه قابلیت‌ها", callback_data=f"fbulk:on:{page}", style="success", emoji_key="check"),
        p_btn("خاموش کردن همه", callback_data=f"fbulk:off:{page}", style="danger", emoji_key="fire"),
    ])
    rows.append([p_btn("بازگشت به منوی اصلی سلف دارک", callback_data="menu:main", style="danger", emoji_key="glow")])
    return InlineKeyboardMarkup(rows)

# ====================================================================
#  پنل مدیریت ۴۰ قابلیته سلف دارک (مخصوص آیدی عددی 8248647747)
# ====================================================================

ADMIN_40_ITEMS = [
    ("adm:1",  "۱. آمار جامع سلف دارک", "primary"),
    ("adm:2",  "۲. پیام همگانی به کاربران", "primary"),
    ("adm:3",  "۳. فوروارد همگانی", "primary"),
    ("adm:4",  "۴. شناسایی کاربر با فوروارد پیام", "success"),
    ("adm:5",  "۵. افزایش الماس کاربر با آیدی", "success"),
    ("adm:6",  "۶. کسر الماس کاربر با آیدی", "danger"),
    ("adm:7",  "۷. تنظیم آدرس ولت TON", "primary"),
    ("adm:8",  "۸. تنظیم قیمت هر الماس به TON", "primary"),
    ("adm:9",  "۹. تنظیم حداقل خرید الماس", "primary"),
    ("adm:10", "۱۰. سفارشات TON در انتظار تایید", "success"),
    ("adm:11", "۱۱. تنظیم آیدی پشتیبانی ریالی", "primary"),
    ("adm:12", "۱۲. روشن/خاموش کردن زیرمجموعه‌گیری", "primary"),
    ("adm:13", "۱۳. تغییر پاداش الماس هر زیرمجموعه", "success"),
    ("adm:14", "۱۴. افزودن کانال جوین اجباری", "success"),
    ("adm:15", "۱۵. حذف کانال جوین اجباری", "danger"),
    ("adm:16", "۱۶. لیست کانال‌های جوین اجباری", "primary"),
    ("adm:17", "۱۷. تغییر هزینه فعال‌سازی سلف (۳۰ الماس)", "primary"),
    ("adm:18", "۱۸. تغییر هزینه ساعتی سلف (۳ الماس)", "primary"),
    ("adm:19", "۱۹. لیست اکانت‌های سلف روشن", "primary"),
    ("adm:20", "۲۰. قطع و توقف سلف کاربر", "danger"),
    ("adm:21", "۲۱. راه‌اندازی مجدد همه سلف‌ها", "success"),
    ("adm:22", "۲۲. مسدود کردن کاربر (Ban)", "danger"),
    ("adm:23", "۲۳. رفع مسدودیت کاربر (Unban)", "success"),
    ("adm:24", "۲۴. هدیه الماس همگانی به همه", "success"),
    ("adm:25", "۲۵. ساخت کد هدیه الماس", "success"),
    ("adm:26", "۲۶. حذف کدهای هدیه", "danger"),
    ("adm:27", "۲۷. لیست کدهای هدیه فعال", "primary"),
    ("adm:28", "۲۸. تنظیم الماس خوش‌آمدگویی", "primary"),
    ("adm:29", "۲۹. تنظیم الماس هدیه روزانه", "primary"),
    ("adm:30", "۳۰. لیست برترین زیرمجموعه‌گیرها", "primary"),
    ("adm:31", "۳۱. لیست ثروتمندترین کاربران (الماس)", "primary"),
    ("adm:32", "۳۲. لیست کل گروه‌های تبچی ثبت‌شده", "primary"),
    ("adm:33", "۳۳. روشن/خاموش کردن سراسری تبچی", "danger"),
    ("adm:34", "۳۴. ارسال پیام مستقیم به پیوی کاربر", "primary"),
    ("adm:35", "۳۵. تنظیم متن تکمیلی راهنما", "primary"),
    ("adm:36", "۳۶. روشن/خاموش کردن ثبت سلف جدید", "danger"),
    ("adm:37", "۳۷. بازگردانی فایل بکاپ (Restore)", "primary"),
    ("adm:38", "۳۸. بکاپ کامل اطلاعات ربات و کاربران", "success"),
    ("adm:39", "۳۹. وضعیت سلامت سرور و پینگر Render", "primary"),
    ("adm:40", "۴۰. روشن/خاموش کردن کل ربات", "danger"),
]

def build_admin_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    per_page = 10
    total_pages = (len(ADMIN_40_ITEMS) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    items = ADMIN_40_ITEMS[page * per_page : (page + 1) * per_page]

    transfer_on = get_setting("transfer_enabled", "1") == "1"
    tr_label = "🟢 انتقال الماس: روشن" if transfer_on else "🔴 انتقال الماس: خاموش"
    tr_style = "success" if transfer_on else "danger"
    min_tr = get_setting("min_transfer_diamonds", "50")

    rows = [
        [
            p_btn("📦 بکاپ کامل ربات و کاربران", callback_data="adm:backup_all", style="success", emoji_key="gem"),
            p_btn("♻️ بازگردانی بکاپ (Restore)", callback_data="adm:restore_backup", style="primary", emoji_key="rocket"),
        ],
        [
            p_btn(tr_label, callback_data="adm:toggle_transfer", style=tr_style, emoji_key="sparkles"),
            p_btn(f"🔢 حداقل انتقال الماس ({min_tr})", callback_data="adm:set_min_transfer", style="primary", emoji_key="gem"),
        ],
    ]
    for i in range(0, len(items), 2):
        row = [p_btn(items[i][1], callback_data=items[i][0], style=items[i][2])]
        if i + 1 < len(items):
            row.append(p_btn(items[i + 1][1], callback_data=items[i + 1][0], style=items[i + 1][2]))
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(p_btn("⬅️ صفحه قبل", callback_data=f"admin:page:{page - 1}", style="primary"))
    nav.append(p_btn(f"صفحه {page + 1} از {total_pages}", callback_data="noop", style="primary"))
    if page < total_pages - 1:
        nav.append(p_btn("صفحه بعد ➡️", callback_data=f"admin:page:{page + 1}", style="primary"))
    rows.append(nav)
    rows.append([p_btn("بازگشت به منوی اصلی سلف دارک", callback_data="menu:main", style="danger", emoji_key="glow")])
    return InlineKeyboardMarkup(rows)

def cancel_inline_keyboard(back_cb: str = "menu:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [p_btn("انصراف و بازگشت", callback_data=back_cb, style="danger", emoji_key="fire")]
    ])

# ====================================================================
#  وضعیت‌های ConversationHandler
# ====================================================================
(
    SELF_WAIT_PHONE,
    SELF_WAIT_CODE,
    SELF_WAIT_2FA,
    FEAT_WAIT_VAL,
    TABCHI_WAIT_BANNER,
    TABCHI_WAIT_INTERVAL,
    TABCHI_WAIT_DELAY,
    BUY_WAIT_DIAMOND_COUNT,
    GIFT_WAIT_CODE,
    ADM_WAIT_GENERIC,
    ADM_WAIT_FORWARD_USER,
    ADM_WAIT_FORWARD_AMOUNT,
    ADM_WAIT_FCH_ID,
    ADM_WAIT_FCH_LINK,
    ADM_WAIT_FCH_TITLE,
    ADM_WAIT_RESTORE_FILE,
    TRANSFER_WAIT_TARGET_ID,
    TRANSFER_WAIT_AMOUNT,
) = range(18)

# ====================================================================
#  هندلر شروع (/start) و منوهای اصلی سلف دارک
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
        await update.message.reply_text(p_text("🚫 حساب شما در ربات سلف دارک مسدود شده است."), parse_mode=ParseMode.HTML)
        return

    if get_setting("bot_active", "1") == "0" and not is_admin(user.id):
        await update.message.reply_text(p_text("⏳ ربات سلف دارک موقتاً در حال بروزرسانی است."), parse_mode=ParseMode.HTML)
        return

    not_joined = await check_user_joined_all(context.bot, user.id)
    if not_joined:
        await update.message.reply_text(
            p_text("👋 سلام! برای ورود به ربات <b>سلف دارک (Self Dark)</b> و ثبت زیرمجموعه، ابتدا در کانال‌های زیر عضو شوید و سپس دکمه <b>«✅ عضو شدم»</b> را بزنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=build_force_join_keyboard(not_joined)
        )
        return

    await verify_referral_if_eligible(context.bot, user.id)
    db_user = get_or_create_user(user.id, user.username, user.first_name)
    acc = get_self_account(user.id)
    self_state = "🟢 روشن و متصل" if (acc and acc["is_running"] == 1) else "🔴 خاموش / متصل نشده"

    welcome = p_text(
        f"🌑 <b>به ربات هوشمند «سلف دارک | Self Dark» خوش آمدید!</b>\n\n"
        f"👤 کاربر: <b>{html.escape(user.first_name)}</b>\n"
        f"💎 موجودی الماس شما: <b>{db_user['diamonds']} الماس</b>\n"
        f"⚡ وضعیت سلف دارک: <b>{self_state}</b>\n\n"
        f"🚀 با <b>سلف دارک</b>، اکانت تلگرام خود را به ۴۰ قابلیت پیشرفته (ضد حذف، ضد ویرایش، ساعت زنده، منشی هوشمند، هوش مصنوعی و...) و <b>تبچی هوشمند گروهی</b> مجهز کنید!\n\n"
        f"✨ از دکمه‌های شیشه‌ای رنگی زیر بخش مورد نظر خود را انتخاب کنید:"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.HTML, reply_markup=main_inline_keyboard(user.id))

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    not_joined = await check_user_joined_all(context.bot, user.id)
    if not_joined:
        await query.answer("⚠️ هنوز در تمام کانال‌ها عضو نشده‌اید!", show_alert=True)
        return
    await query.answer("✅ عضویت شما تایید شد!")
    await verify_referral_if_eligible(context.bot, user.id)
    await query.edit_message_text(
        p_text(f"✅ <b>عضویت شما تایید شد!</b>\n🌑 به ربات <b>سلف دارک</b> خوش آمدید:"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )

async def menu_router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    db_user = get_or_create_user(user.id, user.username, user.first_name)
    if db_user["is_banned"] == 1 and not is_admin(user.id):
        await query.answer("🚫 حساب شما مسدود است.", show_alert=True)
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
        acc = get_self_account(user.id)
        self_state = "🟢 روشن و متصل" if (acc and acc["is_running"] == 1) else "🔴 خاموش / متصل نشده"
        await query.edit_message_text(
            p_text(
                f"🌑 <b>منوی اصلی ربات سلف دارک (Self Dark)</b>\n\n"
                f"👤 کاربر: <b>{html.escape(user.first_name)}</b>\n"
                f"💎 موجودی الماس: <b>{db_user['diamonds']} الماس</b>\n"
                f"⚡ وضعیت سلف دارک: <b>{self_state}</b>\n\n"
                f"✨ بخش مورد نظر را انتخاب کنید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )

    elif data == "menu:profile":
        acc = get_self_account(user.id)
        with closing(get_conn()) as conn:
            t_groups = conn.execute("SELECT COUNT(*) c FROM tabchi_groups WHERE user_id=?", (user.id,)).fetchone()["c"]
        act_cost = get_setting("activation_cost", "30")
        hr_cost = get_setting("hourly_cost", "3")
        phone_str = acc["phone"] if acc else "ثبت نشده"
        self_st = "🟢 فعال و روشن" if (acc and acc["is_running"] == 1) else "🔴 غیرفعال"

        text = p_text(
            f"👤 <b>حساب کاربری شما در سلف دارک</b>\n\n"
            f"🔢 آیدی عددی: <code>{user.id}</code>\n"
            f" نام: <b>{html.escape(user.first_name)}</b> (@{user.username or 'ندارد'})\n"
            f"💎 موجودی فعلی الماس: <b>{db_user['diamonds']} الماس</b>\n"
            f"🔥 کل الماس مصرف‌شده: <b>{db_user['total_spent_diamonds']} الماس</b>\n"
            f"👥 زیرمجموعه‌های تاییدشده: <b>{db_user['referrals_count']} نفر</b>\n\n"
            f"🌑 <b>وضعیت سلف دارک:</b> <b>{self_st}</b>\n"
            f"📱 شماره متصل: <code>{phone_str}</code>\n"
            f"📣 گروه‌های ثبت‌شده در تبچی: <b>{t_groups} گروه</b>\n"
            f"💰 تعرفه مصرف: <b>{act_cost} الماس فعال‌سازی | ساعتی {hr_cost} الماس</b>"
        )
        kb = InlineKeyboardMarkup([
            [
                p_btn("خرید الماس", callback_data="menu:buy_diamonds", style="success", emoji_key="gem"),
                p_btn("انتقال الماس به دیگران", callback_data="menu:transfer_diamonds", style="primary", emoji_key="sparkles"),
            ],
            [
                p_btn("زیرمجموعه‌گیری رایگان", callback_data="menu:referral", style="primary", emoji_key="gift"),
            ],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "menu:buy_diamonds":
        ton_rate = float(get_setting("ton_per_diamond", "0.0005"))
        min_buy = int(get_setting("min_buy_diamonds", "50"))
        text = p_text(
            f"💎 <b>فروشگاه خرید الماس سلف دارک</b>\n\n"
            f"⚡ برای فعال‌سازی سلف دارک (<b>{get_setting('activation_cost', '30')} الماس</b>) و روشن ماندن ۲۴ ساعته آن (<b>ساعتی {get_setting('hourly_cost', '3')} الماس</b>) می‌توانید حساب خود را به یکی از ۲ روش زیر شارژ کنید:\n\n"
            f"1️⃣ <b>پرداخت با ارز دیجیتال TON (تون کوین):</b>\n"
            f"• قیمت هر ۱ الماس: <b>{ton_rate} TON</b>\n"
            f"• حداقل میزان خرید: <b>{min_buy} الماس</b> ({min_buy * ton_rate:.4f} TON)\n\n"
            f"2️⃣ <b>پرداخت ریالی (کارت به کارت):</b>\n"
            f"• خرید مستقیم از طریق پشتیبانی ریالی\n\n"
            f"✨ لطفاً روش پرداخت مورد نظر خود را انتخاب کنید:"
        )
        kb = InlineKeyboardMarkup([
            [p_btn("خرید با ارز دیجیتال TON (تون)", callback_data="buy:ton", style="primary", emoji_key="gem")],
            [p_btn("خرید با کارت به کارت (ریالی)", callback_data="buy:rial", style="success", emoji_key="money")],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "buy:rial":
        sup_id = get_setting("rial_support_id", "@kanfingfreesup")
        sup_url = f"https://t.me/{sup_id.lstrip('@')}"
        text = p_text(
            f"💳 <b>خرید الماس با کارت به کارت (پرداخت ریالی)</b>\n\n"
            f"✨ برای خرید الماس به صورت ریالی (کارت به کارت)، لطفاً به آیدی پشتیبانی زیر پیام دهید و تعداد الماس مورد نظر و آیدی عددی خود (<code>{user.id}</code>) را اعلام کنید:\n\n"
            f"👤 <b>آیدی پشتیبانی پرداخت ریالی:</b> {sup_id}"
        )
        kb = InlineKeyboardMarkup([
            [p_btn(f"پیام به پشتیبانی ({sup_id})", url=sup_url, style="success", emoji_key="rocket")],
            [p_btn("بازگشت به بخش خرید الماس", callback_data="menu:buy_diamonds", style="primary", emoji_key="gem")],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "menu:referral":
        ref_enabled = get_setting("referral_enabled", "1") == "1"
        reward = get_setting("referral_reward", "5")
        bot_me = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_me.username}?start=ref_{user.id}"
        status_txt = "🟢 فعال" if ref_enabled else "🔴 موقتاً غیرفعال توسط مدیریت"

        text = p_text(
            f"🎁 <b>کسب الماس رایگان (زیرمجموعه‌گیری سلف دارک)</b>\n\n"
            f"📊 وضعیت بخش زیرمجموعه‌گیری: <b>{status_txt}</b>\n"
            f"💎 پاداش هر زیرمجموعه: <b>{reward} الماس رایگان</b>\n"
            f"👥 زیرمجموعه‌های تاییدشده شما: <b>{db_user['referrals_count']} نفر</b>\n\n"
            f"🔥 با ارسال لینک اختصاصی زیر برای دوستان خود، به ازای هر نفری که وارد ربات شده و در <b>کانال‌های جوین اجباری</b> عضو شود، بلافاصله <b>{reward} الماس</b> دریافت می‌کنید!\n\n"
            f"🔗 <b>لینک دعوت اختصاصی شما:</b>\n"
            f"<code>{ref_link}</code>"
        )
        kb = InlineKeyboardMarkup([
            [p_btn("خرید مستقیم الماس", callback_data="menu:buy_diamonds", style="success", emoji_key="gem")],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "menu:daily_gift":
        today_str = datetime.now().strftime("%Y-%m-%d")
        daily_amt = int(get_setting("daily_gift_diamonds", "2"))
        msg_alert = ""
        if db_user["last_daily_gift"] != today_str:
            with closing(get_conn()) as conn, conn:
                conn.execute(
                    "UPDATE users SET diamonds = diamonds + ?, last_daily_gift = ? WHERE user_id=?",
                    (daily_amt, today_str, user.id)
                )
            msg_alert = f"🎉 تبریک! تعداد <b>{daily_amt} الماس هدیه روزانه</b> به حساب شما اضافه شد!\n\n"
        else:
            msg_alert = "⏳ شما هدیه روزانه امروز خود را قبلاً دریافت کرده‌اید. فردا دوباره سر بزنید!\n\n"

        await query.edit_message_text(
            p_text(
                f"🎁 <b>بخش هدیه روزانه و کد هدیه سلف دارک</b>\n\n"
                f"{msg_alert}"
                f"✨ اگر کد هدیه الماس دارید، روی دکمه زیر کلیک کنید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [p_btn("ثبت کد هدیه الماس", callback_data="enter_gift_code", style="success", emoji_key="gift")],
                [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
            ])
        )

    elif data == "menu:help":
        act_c = get_setting("activation_cost", "30")
        hr_c = get_setting("hourly_cost", "3")
        ref_r = get_setting("referral_reward", "5")
        ton_r = get_setting("ton_per_diamond", "0.0005")
        extra_note = get_setting("help_extra_note", "")

        help_text = p_text(
            f"📚 <b>راهنمای جامع ربات «سلف دارک | Self Dark»</b>\n\n"
            f"🌑 <b>۱. نحوه فعال‌سازی سلف دارک:</b>\n"
            f"• ابتدا از داشتن حداقل <b>{act_c} الماس</b> در حساب خود مطمئن شوید.\n"
            f"• وارد بخش <b>«🚀 فعالسازی و اتصال سلف دارک»</b> شوید.\n"
            f"• روی دکمه <b>«📱 ارسال شماره تلگرام من»</b> بزنید تا شماره اکانتتان ارسال شود.\n"
            f"• کد ۵ رقمی تلگرام را با فاصله یا خط تیره (مثلاً <code>1-2-3-4-5</code>) بفرستید تا تلگرام کد را مسدود نکند.\n"
            f"• اگر رمز دو مرحله‌ای (2FA) دارید، آن را نیز وارد کنید تا سلف دارک بلافاصله روی اکانت شما روشن شود!\n\n"
            f"💎 <b>۲. سیستم الماس و هزینه‌ها:</b>\n"
            f"• هزینه فعال‌سازی اولیه سلف دارک: <b>{act_c} الماس</b>\n"
            f"• هزینه روشن ماندن سلف دارک: <b>ساعتی {hr_c} الماس</b>\n"
            f"• خرید با ارز دیجیتال TON: هر الماس <b>{ton_r} TON</b> (حداقل ۵۰ الماس)\n"
            f"• خرید کارت به کارت ریالی: پیام به {get_setting('rial_support_id', '@kanfingfreesup')}\n"
            f"• زیرمجموعه‌گیری: هر زیرمجموعه که در کانال‌های اجباری عضو شود = <b>{ref_r} الماس رایگان</b>\n\n"
            f"📣 <b>۳. راهنمای تبچی هوشمند سلف دارک:</b>\n"
            f"• بعد از روشن شدن سلف دارک، در هر گروهی که می‌خواهید تبچی پیام بفرستد، عبارت <code>تنظیم چت</code> را با اکانت خود ارسال کنید تا گروه ثبت شود.\n"
            f"• برای حذف گروه، عبارت <code>حذف چت</code> را در گروه بفرستید.\n"
            f"• از منوی <b>«📣 تبچی هوشمند سلف دارک»</b> در همین ربات می‌توانید بنر اختصاصی، زمان ارسال برحسب دقیقه، فاصله بین پیام‌ها و روشن/خاموش بودن هر گروه را تنظیم کنید.\n\n"
            f"⚡ <b>۴. دستورات کاربردی داخل اکانت سلف دارک:</b>\n"
            f"• <code>.ping</code> (بررسی سرعت) | <code>.stats</code> (آمار سلف) | <code>.id</code> (آیدی عددی)\n"
            f"• <code>.tr</code> (ترجمه با ریپلای) | <code>.sum</code> (خلاصه‌سازی با ریپلای)\n"
            f"• <code>.calc 2+2</code> (ماشین حساب) | <code>.font text</code> (زیباسازی فونت)\n"
            f"• <code>.note متن</code> (ثبت یادداشت گفتگو) | <code>.notebook</code> (مشاهده دفترچه)\n"
            f"• <code>.del 5</code> (پاکسازی سریع پیام‌ها)\n\n"
            f"{html.escape(extra_note)}"
        )
        kb = InlineKeyboardMarkup([
            [
                p_btn("فعالسازی سلف دارک", callback_data="menu:activate_self", style="primary", emoji_key="rocket"),
                p_btn("خرید الماس", callback_data="menu:buy_diamonds", style="success", emoji_key="gem"),
            ],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(help_text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ====================================================================
#  مدیریت ۴۰ قابلیت سلف دارک (روشن/خاموش و تغییر مقادیر)
# ====================================================================

async def self_features_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    if data.startswith("self:features_page:"):
        page = int(data.split(":")[2])
        await query.answer()
        await query.edit_message_text(
            p_text(
                "🌑 <b>پنل تنظیمات ۴۰ قابلیت «سلف دارک | Self Dark»</b>\n\n"
                "✨ روی هر قابلیت کلیک کنید تا <b>🟢 روشن</b> یا <b>🔴 خاموش</b> شود.\n"
                "⚙️ قابلیت‌هایی که دکمه «تنظیم مقدار» دارند (مثل متن پاسخ خودکار، قالب بیو، ایموجی ری‌اکشن و...) قابل شخصی‌سازی کامل هستند:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=build_features_keyboard(user.id, page)
        )

    elif data.startswith("ftoggle:"):
        _, fkey, page_str = data.split(":")
        page = int(page_str)
        feats = get_user_features(user.id)
        feats[fkey] = not feats.get(fkey, False)
        save_user_features(user.id, feats)
        st = "🟢 روشن شد" if feats[fkey] else "🔴 خاموش شد"

        # اگر ساعت زنده نام/نام خانوادگی یا بیوگرافی روشن/خاموش شد، بلافاصله روی اکانت اعمال شود
        client = ACTIVE_SELF_CLIENTS.get(user.id)
        if client:
            if fkey in ("f4", "f3", "f6") and feats[fkey]:
                await update_user_profile_clock_now(user.id, client, force=True)
            elif fkey == "f4" and not feats[fkey]:
                try:
                    await client(functions.account.UpdateProfileRequest(last_name=""))
                except Exception:
                    pass

        await query.answer(f"{SELF_DARK_FEATURES[fkey]['title']} {st}!")
        await query.edit_message_reply_markup(reply_markup=build_features_keyboard(user.id, page))

    elif data.startswith("fbulk:"):
        _, mode, page_str = data.split(":")
        page = int(page_str)
        feats = get_user_features(user.id)
        for k in SELF_DARK_FEATURES:
            feats[k] = (mode == "on")
        save_user_features(user.id, feats)
        await query.answer("✅ وضعیت تمام ۴۰ قابلیت سلف دارک بروزرسانی شد!", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=build_features_keyboard(user.id, page))

async def feature_set_val_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, fkey, page_str = query.data.split(":")
    meta = SELF_DARK_FEATURES[fkey]
    feats = get_user_features(query.from_user.id)
    curr_val = feats.get(meta["val_key"], meta["default_val"])

    context.user_data["edit_feat_key"] = fkey
    context.user_data["edit_feat_page"] = int(page_str)

    extra_hint = ""
    if fkey == "f4":
        normal_t, fancy_t = get_user_device_time_str(feats)
        extra_hint = (
            f"\n⏰ <b>ساعت فعلی تنظیم شده برای دستگاه شما:</b> <code>{normal_t}</code> ({fancy_t})\n"
            f"💡 <b>راهنما:</b> اگر ساعت بالا با ساعت گوشی شما تفاوت دارد، کافی است <b>ساعت فعلی گوشی خود</b> را بفرستید (مثلاً <code>16:42</code>) تا دقیقاً با ساعت دستگاه شما هماهنگ شود و هر دقیقه در بخش نام/نام خانوادگی پروفایل بالا برود!\n"
            f"یا می‌توانید قالب دلخواه با <code>{{time}}</code> بفرستید (مثلاً <code>| {{time}}</code>)."
        )

    await query.edit_message_text(
        p_text(
            f"⚙️ <b>تنظیم مقدار برای «{meta['title']}»</b>\n\n"
            f"📌 عنوان تنظیم: <b>{meta['val_label']}</b>\n"
            f"🔹 مقدار فعلی:\n<code>{html.escape(str(curr_val))}</code>"
            f"{extra_hint}\n\n"
            f"✨ لطفاً مقدار جدید را ارسال کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard(f"self:features_page:{page_str}")
    )
    return FEAT_WAIT_VAL

async def feature_set_val_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    fkey = context.user_data.get("edit_feat_key")
    page = context.user_data.get("edit_feat_page", 0)
    if not fkey or fkey not in SELF_DARK_FEATURES:
        return ConversationHandler.END

    meta = SELF_DARK_FEATURES[fkey]
    new_val = update.message.text.strip()
    feats = get_user_features(user.id)

    # اگر قابلیت ۴ (ساعت زنده در نام و نام خانوادگی پروفایل) است و کاربر ساعت فعلی دستگاه خود را وارد کرده (مثلاً 14:35)
    if fkey == "f4":
        norm_v = normalize_digits(new_val)
        m_clock = re.search(r"(\d{1,2}):(\d{2})", norm_v)
        if m_clock:
            hh, mm = int(m_clock.group(1)), int(m_clock.group(2))
            feats["clock_offset_mins"] = compute_offset_mins_from_hhmm(hh, mm)
        if "{time}" in new_val:
            feats["name_clock_tpl"] = new_val
        elif not m_clock:
            feats["name_clock_tpl"] = f"{new_val} {{time}}"
    else:
        feats[meta["val_key"]] = new_val

    feats[fkey] = True
    save_user_features(user.id, feats)

    client = ACTIVE_SELF_CLIENTS.get(user.id)
    if client and fkey in ("f4", "f3"):
        await update_user_profile_clock_now(user.id, client, force=True)

    await update.message.reply_text(
        p_text(f"✅ تنظیمات <b>{meta['title']}</b> با موفقیت ذخیره شد و قابلیت روشن گردید!"),
        parse_mode=ParseMode.HTML,
        reply_markup=build_features_keyboard(user.id, page)
    )
    return ConversationHandler.END

# ====================================================================
#  بخش تبچی هوشمند سلف دارک (مدیریت گروه‌ها، بنر، زمان و فاصله)
# ====================================================================

async def tabchi_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    if data == "menu:tabchi":
        feats = get_user_features(user.id)
        tab_on = feats.get("tabchi_enabled", True)
        with closing(get_conn()) as conn:
            groups = conn.execute("SELECT * FROM tabchi_groups WHERE user_id=? ORDER BY id DESC", (user.id,)).fetchall()

        st_badge = "🟢 فعال" if tab_on else "🔴 غیرفعال"
        text = p_text(
            f"📣 <b>بخش تبچی هوشمند «سلف دارک | Self Dark»</b>\n\n"
            f"⚡ وضعیت کلی تبچی شما: <b>{st_badge}</b>\n"
            f"📊 تعداد گروه‌های ثبت‌شده: <b>{len(groups)} گروه</b>\n\n"
            f"🔹 <b>نحوه ثبت گروه جدید:</b>\n"
            f"کافی است با اکانت سلف خود در گروه مورد نظر دستور <code>تنظیم چت</code> را ارسال کنید تا گروه بلافاصله در لیست زیر ظاهر شود!\n\n"
            f"👇 برای تغییر بنر، تعیین زمان ارسال (دقیقه) یا روشن/خاموش کردن تبچی هر گروه، روی نام گروه کلیک کنید:"
        )
        rows = [
            [
                p_btn(
                    f"وضعیت کلی تبچی: {st_badge}",
                    callback_data="tabchi:toggle_master",
                    style="success" if tab_on else "danger",
                    emoji_key="megaphone"
                )
            ]
        ]
        for g in groups:
            g_st = "🟢" if g["is_active"] == 1 else "🔴"
            rows.append([
                p_btn(
                    f"{g_st} {g['chat_title']} (هر {g['interval_minutes']} دقیقه)",
                    callback_data=f"tabchi:grp:{g['id']}",
                    style="primary"
                )
            ])
        rows.append([p_btn("تنظیم بنر همگانی برای همه گروه‌ها", callback_data="tabchi:set_all_banner", style="success", emoji_key="sparkles")])
        rows.append([p_btn("بازگشت به منوی اصلی سلف دارک", callback_data="menu:main", style="danger", emoji_key="fire")])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))

    elif data == "tabchi:toggle_master":
        feats = get_user_features(user.id)
        feats["tabchi_enabled"] = not feats.get("tabchi_enabled", True)
        save_user_features(user.id, feats)
        await tabchi_menu_callback(update, context)

    elif data.startswith("tabchi:grp:"):
        gid = int(data.split(":")[2])
        await show_single_tabchi_group(query, user.id, gid)

    elif data.startswith("tabchi:gtoggle:"):
        gid = int(data.split(":")[2])
        with closing(get_conn()) as conn, conn:
            g = conn.execute("SELECT is_active FROM tabchi_groups WHERE id=? AND user_id=?", (gid, user.id)).fetchone()
            if g:
                new_st = 0 if g["is_active"] == 1 else 1
                conn.execute("UPDATE tabchi_groups SET is_active=? WHERE id=?", (new_st, gid))
        await show_single_tabchi_group(query, user.id, gid)

    elif data.startswith("tabchi:gdel:"):
        gid = int(data.split(":")[2])
        with closing(get_conn()) as conn, conn:
            conn.execute("DELETE FROM tabchi_groups WHERE id=? AND user_id=?", (gid, user.id))
        await query.answer("🗑 گروه از تبچی حذف شد.", show_alert=True)
        query.data = "menu:tabchi"
        await tabchi_menu_callback(update, context)

async def show_single_tabchi_group(query, user_id: int, gid: int):
    with closing(get_conn()) as conn:
        g = conn.execute("SELECT * FROM tabchi_groups WHERE id=? AND user_id=?", (gid, user_id)).fetchone()
    if not g:
        await query.edit_message_text("❌ گروه یافت نشد.", reply_markup=cancel_inline_keyboard("menu:tabchi"))
        return

    st = "🟢 فعال" if g["is_active"] == 1 else "🔴 غیرفعال"
    text = p_text(
        f"⚙️ <b>مدیریت گروه تبچی: {html.escape(g['chat_title'])}</b>\n\n"
        f"🔢 آیدی چت: <code>{g['chat_id']}</code>\n"
        f"📌 وضعیت تبچی این گروه: <b>{st}</b>\n"
        f"⏰ زمان ارسال پیام: <b>هر {g['interval_minutes']} دقیقه</b>\n"
        f"⏳ فاصله زمانی دقیق بین پیام‌ها: <b>{g['delay_seconds']} ثانیه</b>\n\n"
        f"📝 <b>متن/بنر اختصاصی فعلی:</b>\n"
        f"<code>{html.escape(g['banner_text'])}</code>"
    )
    kb = InlineKeyboardMarkup([
        [
            p_btn(
                f"تغییر وضعیت ({st})",
                callback_data=f"tabchi:gtoggle:{gid}",
                style="success" if g["is_active"] == 1 else "danger"
            )
        ],
        [
            p_btn("ثبت بنر/متن اختصاصی", callback_data=f"tabchi_edit:banner:{gid}", style="primary", emoji_key="sparkles"),
            p_btn("تعیین زمان ارسال (دقیقه)", callback_data=f"tabchi_edit:interval:{gid}", style="primary", emoji_key="zap"),
        ],
        [
            p_btn("تنظیم فاصله زمانی (ثانیه)", callback_data=f"tabchi_edit:delay:{gid}", style="primary"),
            p_btn("حذف این گروه از تبچی", callback_data=f"tabchi:gdel:{gid}", style="danger", emoji_key="fire"),
        ],
        [p_btn("بازگشت به لیست گروه‌های تبچی", callback_data="menu:tabchi", style="primary", emoji_key="megaphone")]
    ])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def tabchi_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "tabchi:set_all_banner":
        context.user_data["tabchi_edit_gid"] = "ALL"
        await query.edit_message_text(
            p_text("📣 <b>تنظیم بنر و متن همگانی برای تمام گروه‌های تبچی</b>\n\nلطفاً متن بنر جدید را ارسال کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:tabchi")
        )
        return TABCHI_WAIT_BANNER

    _, mode, gid_str = data.split(":")
    gid = int(gid_str)
    context.user_data["tabchi_edit_gid"] = gid

    if mode == "banner":
        await query.edit_message_text(
            p_text("📝 <b>لطفاً متن یا بنر اختصاصی جدید برای این گروه را ارسال کنید:</b>"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"tabchi:grp:{gid}")
        )
        return TABCHI_WAIT_BANNER
    elif mode == "interval":
        await query.edit_message_text(
            p_text("⏰ <b>فاصله زمانی ارسال پیام به این گروه را برحسب دقیقه وارد کنید (مثلاً 5 یا 15):</b>"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"tabchi:grp:{gid}")
        )
        return TABCHI_WAIT_INTERVAL
    elif mode == "delay":
        await query.edit_message_text(
            p_text("⏳ <b>فاصله تاخیر دقیق بین پیام‌ها را برحسب ثانیه وارد کنید (مثلاً 3):</b>"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"tabchi:grp:{gid}")
        )
        return TABCHI_WAIT_DELAY

async def tabchi_save_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    gid = context.user_data.get("tabchi_edit_gid")
    txt = update.message.text.strip()
    with closing(get_conn()) as conn, conn:
        if gid == "ALL":
            conn.execute("UPDATE tabchi_groups SET banner_text=? WHERE user_id=?", (txt, user.id))
        else:
            conn.execute("UPDATE tabchi_groups SET banner_text=? WHERE id=? AND user_id=?", (txt, int(gid), user.id))
    await update.message.reply_text(
        p_text("✅ <b>بنر تبچی سلف دارک با موفقیت ذخیره شد!</b>"),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[p_btn("بازگشت به مدیریت تبچی", callback_data="menu:tabchi", style="primary", emoji_key="megaphone")]])
    )
    return ConversationHandler.END

async def tabchi_save_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    gid = context.user_data.get("tabchi_edit_gid")
    txt = update.message.text.strip()
    if not txt.isdigit() or int(txt) < 1:
        await update.message.reply_text(p_text("⚠️ لطفاً یک عدد صحیح بزرگ‌تر از ۱ وارد کنید:"), parse_mode=ParseMode.HTML)
        return TABCHI_WAIT_INTERVAL
    with closing(get_conn()) as conn, conn:
        conn.execute("UPDATE tabchi_groups SET interval_minutes=? WHERE id=? AND user_id=?", (int(txt), int(gid), user.id))
    await update.message.reply_text(
        p_text(f"✅ زمان ارسال تبچی روی <b>هر {txt} دقیقه</b> تنظیم شد!"),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[p_btn("بازگشت به تنظیمات گروه", callback_data=f"tabchi:grp:{gid}", style="primary")]])
    )
    return ConversationHandler.END

async def tabchi_save_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    gid = context.user_data.get("tabchi_edit_gid")
    txt = update.message.text.strip()
    if not txt.isdigit() or int(txt) < 1:
        await update.message.reply_text(p_text("⚠️ لطفاً یک عدد صحیح وارد کنید:"), parse_mode=ParseMode.HTML)
        return TABCHI_WAIT_DELAY
    with closing(get_conn()) as conn, conn:
        conn.execute("UPDATE tabchi_groups SET delay_seconds=? WHERE id=? AND user_id=?", (int(txt), int(gid), user.id))
    await update.message.reply_text(
        p_text(f"✅ فاصله دقیق بین پیام‌ها روی <b>{txt} ثانیه</b> تنظیم شد!"),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[p_btn("بازگشت به تنظیمات گروه", callback_data=f"tabchi:grp:{gid}", style="primary")]])
    )
    return ConversationHandler.END

# ====================================================================
#  فرایند واقعی فعال‌سازی سلف دارک (دریافت شماره با دکمه تلگرام + کد + 2FA)
# ====================================================================

async def activate_self_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()

    if get_setting("self_new_login_enabled", "1") == "0" and not is_admin(user.id):
        await query.edit_message_text(
            p_text("⚠️ ثبت سلف جدید موقتاً توسط مدیریت غیرفعال شده است."),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:main")
        )
        return ConversationHandler.END

    db_user = get_or_create_user(user.id, user.username, user.first_name)
    act_cost = int(get_setting("activation_cost", "30"))
    hr_cost = int(get_setting("hourly_cost", "3"))

    # بررسی اینکه آیا قبلاً سلف داشته است یا خیر
    acc = get_self_account(user.id)
    if acc and acc["is_running"] == 1:
        await query.edit_message_text(
            p_text(
                f"✅ <b>سلف دارک شما هم‌اکنون روی شماره <code>{acc['phone']}</code> فعال و روشن است!</b>\n\n"
                f"می‌توانید قابلیت‌ها را تنظیم کنید یا سلف را موقتاً خاموش نمایید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [p_btn("مدیریت ۴۰ قابلیت سلف دارک", callback_data="self:features_page:0", style="primary", emoji_key="sparkles")],
                [p_btn("خاموش کردن سلف دارک", callback_data="self:stop_now", style="danger", emoji_key="fire")],
                [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="primary", emoji_key="glow")]
            ])
        )
        return ConversationHandler.END

    if db_user["diamonds"] < act_cost and not is_admin(user.id):
        await query.edit_message_text(
            p_text(
                f"⛔ <b>موجودی الماس شما برای فعال‌سازی سلف دارک کافی نیست!</b>\n\n"
                f"💎 هزینه فعال‌سازی سلف دارک: <b>{act_cost} الماس</b> (و ساعتی {hr_cost} الماس)\n"
                f"💰 موجودی فعلی شما: <b>{db_user['diamonds']} الماس</b>\n\n"
                f"👇 لطفاً ابتدا حساب خود را شارژ کنید یا با دعوت دوستان الماس رایگان بگیرید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [p_btn("خرید الماس (TON / کارت به کارت)", callback_data="menu:buy_diamonds", style="success", emoji_key="gem")],
                [p_btn("دریافت الماس رایگان (زیرمجموعه)", callback_data="menu:referral", style="primary", emoji_key="gift")],
                [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
            ])
        )
        return ConversationHandler.END

    try:
        btn_contact = KeyboardButton("📱 ارسال شماره تلگرام من برای فعالسازی سلف دارک", request_contact=True, style="success")
    except TypeError:
        btn_contact = KeyboardButton("📱 ارسال شماره تلگرام من برای فعالسازی سلف دارک", request_contact=True)

    contact_kb = ReplyKeyboardMarkup(
        [[btn_contact]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await query.message.reply_text(
        p_text(
            f"🌑 <b>مرحله ۱ از ۲: ارسال شماره تلگرام برای فعال‌سازی سلف دارک</b>\n\n"
            f"💎 هزینه فعال‌سازی: <b>{act_cost} الماس</b> | روشن ماندن: <b>ساعتی {hr_cost} الماس</b>\n\n"
            f"👇 لطفاً روی دکمه سبز رنگ <b>«📱 ارسال شماره تلگرام من برای فعالسازی سلف دارک»</b> در پایین صفحه ضربه بزنید تا شماره اکانت شما ارسال شود (یا شماره را با پیش‌شماره مثل <code>+98912...</code> بفرستید):"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=contact_kb
    )
    return SELF_WAIT_PHONE

def build_code_entry_message(phone: str, entered_code: str = "") -> str:
    slots = []
    for i in range(5):
        if i < len(entered_code):
            slots.append(f"<b>{entered_code[i]}</b>")
        else:
            slots.append("▫️")
    slots_display = "  ".join(slots)

    return p_text(
        f"✅ <b>کد ورود ۵ رقمی به تلگرام شما (<code>{html.escape(phone)}</code>) ارسال شد!</b>\n\n"
        f"🔢 <b>بخش وارد کردن کد ورود سلف دارک:</b>\n"
        f"┌──────────────────────┐\n"
        f"      {slots_display}\n"
        f"└──────────────────────┘\n\n"
        f"✨ <b>روش ۱ (پیشنهادی و ضد مسدودی کد):</b>\n"
        f"از دکمه‌های شیشه‌ای زیر، کد ۵ رقمی تلگرام را به ترتیب وارد کرده و دکمه <b>«✅ تایید کد و فعال‌سازی»</b> را بزنید.\n\n"
        f"✍️ <b>روش ۲ (تایپ در چت):</b>\n"
        f"می‌توانید کد ۵ رقمی را با خط تیره یا فاصله (مثلاً <code>1-2-3-4-5</code>) در همین چت تایپ و ارسال کنید:"
    )

def build_code_entry_keyboard(entered_code: str = "") -> InlineKeyboardMarkup:
    shown = " ".join(list(entered_code)) if entered_code else "هنوز رقمی وارد نشده"
    return InlineKeyboardMarkup([
        [p_btn(f"🔢 کد وارد شده: {shown}", callback_data="noop", style="primary", emoji_key="sparkles")],
        [
            p_btn("1", callback_data="codepad:d:1", style="primary"),
            p_btn("2", callback_data="codepad:d:2", style="primary"),
            p_btn("3", callback_data="codepad:d:3", style="primary"),
        ],
        [
            p_btn("4", callback_data="codepad:d:4", style="primary"),
            p_btn("5", callback_data="codepad:d:5", style="primary"),
            p_btn("6", callback_data="codepad:d:6", style="primary"),
        ],
        [
            p_btn("7", callback_data="codepad:d:7", style="primary"),
            p_btn("8", callback_data="codepad:d:8", style="primary"),
            p_btn("9", callback_data="codepad:d:9", style="primary"),
        ],
        [
            p_btn("⌫ حذف یکی", callback_data="codepad:back", style="danger"),
            p_btn("0", callback_data="codepad:d:0", style="primary"),
            p_btn("🗑 پاکسازی", callback_data="codepad:clear", style="danger"),
        ],
        [
            p_btn("تایید کد و فعال‌سازی سلف دارک", callback_data="codepad:submit", style="success", emoji_key="check"),
        ],
        [
            p_btn("ارسال مجدد کد ورود", callback_data="codepad:resend", style="primary", emoji_key="rocket"),
            p_btn("انصراف و بازگشت", callback_data="menu:main", style="danger", emoji_key="fire"),
        ],
    ])

async def activate_self_receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message
    phone = ""

    if msg.contact and msg.contact.phone_number:
        phone = msg.contact.phone_number
    elif msg.text:
        phone = msg.text.strip()
    else:
        await msg.reply_text(p_text("⚠️ لطفاً از دکمه ارسال شماره استفاده کنید:"), parse_mode=ParseMode.HTML)
        return SELF_WAIT_PHONE

    phone = normalize_digits(phone)
    phone = re.sub(r"[^\d+]", "", phone)
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    elif phone.startswith("09") and len(phone) == 11:
        phone = "+98" + phone[1:]
    elif not phone.startswith("+"):
        phone = "+" + phone

    # حذف کیبورد شماره با پیام جداگانه (توجه: پیام دارای ReplyKeyboardRemove نباید edit_text شود!)
    await msg.reply_text(
        p_text(f"⏳ در حال اتصال به سرور تلگرام و ارسال کد ورود به شماره <code>{html.escape(phone)}</code>..."),
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove()
    )

    # بستن کلاینت موقت قبلی در صورت وجود
    old_pending = PENDING_LOGINS.pop(user.id, None)
    if old_pending and old_pending.get("client"):
        try:
            await old_pending["client"].disconnect()
        except Exception:
            pass

    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        sent_code = await client.send_code_request(phone)
        PENDING_LOGINS[user.id] = {
            "client": client,
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash,
            "entered_code": "",
            "awaiting_2fa": False,
        }
        # ارسال پیام جدید حاوی پنل شیشه‌ای وارد کردن کد ورود
        await msg.reply_text(
            build_code_entry_message(phone, ""),
            parse_mode=ParseMode.HTML,
            reply_markup=build_code_entry_keyboard("")
        )
        return SELF_WAIT_CODE
    except FloodWaitError as fw:
        await msg.reply_text(
            p_text(f"⛔ محدودیت موقت تلگرام! لطفاً {fw.seconds} ثانیه دیگر تلاش کنید."),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )
        return ConversationHandler.END
    except Exception as e:
        await msg.reply_text(
            p_text(f"❌ خطا در ارسال کد به شماره <code>{html.escape(phone)}</code>:\n<code>{html.escape(str(e)[:150])}</code>"),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )
        return ConversationHandler.END

async def verify_and_sign_in_with_code(update: Update, context: ContextTypes.DEFAULT_TYPE, user, clean_code: str):
    target_msg = update.effective_message
    login_info = PENDING_LOGINS.get(user.id)
    if not login_info:
        await target_msg.reply_text(
            p_text("❌ نشست ورود منقضی شده است. لطفاً دوباره روی «فعالسازی سلف دارک» کلیک کنید."),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )
        return ConversationHandler.END

    client: TelegramClient = login_info["client"]
    phone = login_info["phone"]
    phone_code_hash = login_info["phone_code_hash"]

    try:
        await client.sign_in(phone=phone, code=clean_code, phone_code_hash=phone_code_hash)
        return await finalize_self_dark_login(update, context, user, client, phone)
    except SessionPasswordNeededError:
        login_info["awaiting_2fa"] = True
        await target_msg.reply_text(
            p_text(
                "🔐 <b>اکانت شما دارای رمز دو مرحله‌ای (Two-Step Verification) است!</b>\n\n"
                "👇 لطفاً رمز دو مرحله‌ای (گذرواژه ابری) اکانت تلگرام خود را در چت تایپ و ارسال کنید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:main")
        )
        return SELF_WAIT_2FA
    except PhoneCodeInvalidError:
        login_info["entered_code"] = ""
        await target_msg.reply_text(
            p_text("❌ <b>کد وارد شده اشتباه است!</b>\nلطفاً کد ۵ رقمی صحیح را از طریق کیبورد شیشه‌ای زیر یا با خط تیره (مثلاً <code>1-2-3-4-5</code>) وارد کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=build_code_entry_keyboard("")
        )
        return SELF_WAIT_CODE
    except PhoneCodeExpiredError:
        await client.disconnect()
        PENDING_LOGINS.pop(user.id, None)
        await target_msg.reply_text(
            p_text("⏰ کد ورود منقضی شده است. لطفاً مجدداً دکمه «فعالسازی سلف دارک» را بزنید."),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )
        return ConversationHandler.END
    except Exception as e:
        await client.disconnect()
        PENDING_LOGINS.pop(user.id, None)
        await target_msg.reply_text(
            p_text(f"❌ خطا در ورود به اکانت:\n<code>{html.escape(str(e)[:140])}</code>"),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )
        return ConversationHandler.END

async def activate_self_code_keypad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت دکمه‌های شیشه‌ای وارد کردن کد ۵ رقمی ورود سلف دارک"""
    query = update.callback_query
    user = query.from_user
    data = query.data

    login_info = PENDING_LOGINS.get(user.id)
    if not login_info:
        await query.answer("❌ نشست ورود منقضی شده است. مجدداً فعال‌سازی را شروع کنید.", show_alert=True)
        return ConversationHandler.END

    phone = login_info["phone"]
    entered = login_info.get("entered_code", "")

    if data.startswith("codepad:d:"):
        digit = data.split(":")[2]
        if len(entered) >= 5:
            await query.answer("کد ۵ رقمی کامل است! روی «تایید کد و فعال‌سازی» بزنید.", show_alert=False)
            return SELF_WAIT_CODE
        entered += digit
        login_info["entered_code"] = entered
        await query.answer(f"رقم {digit} ثبت شد ({entered})")
        try:
            await query.edit_message_text(
                build_code_entry_message(phone, entered),
                parse_mode=ParseMode.HTML,
                reply_markup=build_code_entry_keyboard(entered)
            )
        except Exception:
            pass
        # اگر ۵ رقم کامل شد، به صورت خودکار کد را بررسی و لاگین کن
        if len(entered) == 5:
            return await verify_and_sign_in_with_code(update, context, user, entered)
        return SELF_WAIT_CODE

    elif data == "codepad:back":
        entered = entered[:-1]
        login_info["entered_code"] = entered
        await query.answer("آخرین رقم پاک شد")
        try:
            await query.edit_message_text(
                build_code_entry_message(phone, entered),
                parse_mode=ParseMode.HTML,
                reply_markup=build_code_entry_keyboard(entered)
            )
        except Exception:
            pass
        return SELF_WAIT_CODE

    elif data == "codepad:clear":
        login_info["entered_code"] = ""
        await query.answer("کد پاکسازی شد")
        try:
            await query.edit_message_text(
                build_code_entry_message(phone, ""),
                parse_mode=ParseMode.HTML,
                reply_markup=build_code_entry_keyboard("")
            )
        except Exception:
            pass
        return SELF_WAIT_CODE

    elif data == "codepad:resend":
        client: TelegramClient = login_info["client"]
        try:
            sent_code = await client.send_code_request(phone)
            login_info["phone_code_hash"] = sent_code.phone_code_hash
            login_info["entered_code"] = ""
            await query.answer("✅ کد ورود جدید به تلگرام شما ارسال شد!", show_alert=True)
            await query.edit_message_text(
                build_code_entry_message(phone, ""),
                parse_mode=ParseMode.HTML,
                reply_markup=build_code_entry_keyboard("")
            )
        except Exception as e:
            await query.answer(f"⚠️ خطا در ارسال مجدد: {str(e)[:60]}", show_alert=True)
        return SELF_WAIT_CODE

    elif data == "codepad:submit":
        if len(entered) < 5:
            await query.answer("⚠️ لطفاً هر ۵ رقم کد ورود را وارد کنید!", show_alert=True)
            return SELF_WAIT_CODE
        await query.answer("⏳ در حال بررسی کد و فعال‌سازی سلف دارک...")
        return await verify_and_sign_in_with_code(update, context, user, entered)

    return SELF_WAIT_CODE

async def activate_self_receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    raw_code = normalize_digits(update.message.text.strip())
    clean_code = re.sub(r"[^0-9]", "", raw_code)

    if not clean_code:
        await update.message.reply_text(
            p_text("⚠️ لطفاً کد ۵ رقمی را از طریق کیبورد شیشه‌ای بالا یا با خط تیره (مثلاً <code>1-2-3-4-5</code>) وارد کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=build_code_entry_keyboard(PENDING_LOGINS.get(user.id, {}).get("entered_code", ""))
        )
        return SELF_WAIT_CODE

    return await verify_and_sign_in_with_code(update, context, user, clean_code)

async def activate_self_receive_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    password = update.message.text.strip()
    login_info = PENDING_LOGINS.get(user.id)
    if not login_info:
        await update.message.reply_text(p_text("❌ نشست ورود یافت نشد."), parse_mode=ParseMode.HTML, reply_markup=main_inline_keyboard(user.id))
        return ConversationHandler.END

    client: TelegramClient = login_info["client"]
    phone = login_info["phone"]

    try:
        await client.sign_in(password=password)
        return await finalize_self_dark_login(update, context, user, client, phone)
    except Exception as e:
        await update.message.reply_text(
            p_text(f"❌ رمز دو مرحله‌ای اشتباه است یا خطایی رخ داد:\n<code>{html.escape(str(e)[:100])}</code>\nلطفاً دوباره رمز را بفرستید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:main")
        )
        return SELF_WAIT_2FA

async def finalize_self_dark_login(update: Update, context: ContextTypes.DEFAULT_TYPE, user, client: TelegramClient, phone: str):
    PENDING_LOGINS.pop(user.id, None)
    session_str = client.session.save()
    await client.disconnect()

    act_cost = int(get_setting("activation_cost", "30"))
    hr_cost = int(get_setting("hourly_cost", "3"))

    if not is_admin(user.id):
        add_user_diamonds(user.id, -act_cost)

    now_iso = datetime.now().isoformat()
    default_feats = json.dumps(get_default_features_dict(), ensure_ascii=False)

    with closing(get_conn()) as conn, conn:
        conn.execute(
            """INSERT OR REPLACE INTO self_accounts
               (user_id, phone, session_string, is_running, activated_at, last_hourly_charge, features_json)
               VALUES (?, ?, ?, 1, ?, ?, COALESCE((SELECT features_json FROM self_accounts WHERE user_id=?), ?))""",
            (user.id, phone, session_str, now_iso, now_iso, user.id, default_feats)
        )

    await start_single_self_client(user.id, session_str)

    target_msg = update.effective_message
    # ارسال پیام تبریک به کاربر
    await target_msg.reply_text(
        p_text(
            f"🎉 <b>تبریک! «سلف دارک | Self Dark» با موفقیت روی اکانت شما فعال شد!</b>\n\n"
            f"📱 شماره متصل: <code>{phone}</code>\n"
            f"💎 هزینه کسر شده فعال‌سازی: <b>{act_cost} الماس</b> (ساعتی {hr_cost} الماس)\n\n"
            f"✨ هم‌اکنون می‌توانید از دکمه‌های زیر ۴۰ قابلیت سلف دارک و تبچی هوشمند را شخصی‌سازی کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [p_btn("مدیریت ۴۰ قابلیت سلف دارک", callback_data="self:features_page:0", style="primary", emoji_key="sparkles")],
            [p_btn("مدیریت تبچی هوشمند سلف دارک", callback_data="menu:tabchi", style="success", emoji_key="megaphone")],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="primary", emoji_key="glow")]
        ])
    )

    # اطلاع‌رسانی کامل به ادمین اصلی (8248647747) با مشخصات و شماره کاربر
    admin_report = p_text(
        f"🚨 <b>گزارش فعال‌سازی جدید «سلف دارک | Self Dark»</b>\n\n"
        f"👤 نام کاربر: <b>{html.escape(user.first_name)}</b>\n"
        f"🆔 یوزرنیم: @{user.username or 'ندارد'}\n"
        f"🔢 آیدی عددی: <code>{user.id}</code>\n"
        f"📱 شماره تلفن اکانت: <code>{phone}</code>\n"
        f"⏰ زمان فعال‌سازی: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"
    )
    for adm in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=adm, text=admin_report, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"خطا در ارسال گزارش فعال‌سازی سلف به ادمین: {e}")

    return ConversationHandler.END

async def stop_self_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await stop_single_self_client(user.id)
    await query.answer("🔴 سلف دارک شما متوقف شد.", show_alert=True)
    await query.edit_message_text(
        p_text("🔴 <b>سلف دارک شما با موفقیت خاموش شد و کسر ساعتی الماس متوقف گردید.</b>"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )

# ====================================================================
#  فرایند خرید الماس با ارز دیجیتال TON (محاسبه خودکار و تایید ادمین)
# ====================================================================

async def buy_ton_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ton_rate = float(get_setting("ton_per_diamond", "0.0005"))
    min_buy = int(get_setting("min_buy_diamonds", "50"))

    await query.edit_message_text(
        p_text(
            f"💎 <b>خرید الماس با ارز دیجیتال TON (تون کوین)</b>\n\n"
            f"✨ قیمت هر ۱ الماس: <b>{ton_rate} TON</b>\n"
            f"🔢 حداقل تعداد قابل خرید: <b>{min_buy} الماس</b>\n\n"
            f"👇 لطفاً <b>تعداد الماسی</b> که می‌خواهید خریداری کنید را به صورت عدد انگلیسی وارد کنید (مثلاً <code>100</code> یا <code>500</code>):"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:buy_diamonds")
    )
    return BUY_WAIT_DIAMOND_COUNT

async def buy_ton_receive_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    txt = update.message.text.strip()
    min_buy = int(get_setting("min_buy_diamonds", "50"))
    ton_rate = float(get_setting("ton_per_diamond", "0.0005"))
    wallet = get_setting("ton_wallet", "UQD_YOUR_TON_WALLET_ADDRESS_HERE")

    if not txt.isdigit() or int(txt) < min_buy:
        await update.message.reply_text(
            p_text(f"⚠️ لطفاً یک عدد صحیح حداقل برابر با <b>{min_buy} الماس</b> وارد کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:buy_diamonds")
        )
        return BUY_WAIT_DIAMOND_COUNT

    diamonds = int(txt)
    total_ton = round(diamonds * ton_rate, 6)
    ton_str = f"{total_ton:g}"

    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            """INSERT INTO ton_orders (user_id, diamonds, ton_amount, wallet_address, status, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (user.id, diamonds, ton_str, wallet, datetime.now().isoformat())
        )
        order_id = cur.lastrowid

    text = p_text(
        f"🧾 <b>فاکتور خرید الماس با ارز دیجیتال TON (#{order_id})</b>\n\n"
        f"💎 تعداد الماس درخواستی: <b>{diamonds:,} الماس</b>\n"
        f"💰 مبلغ دقیق قابل واریز: <code>{ton_str}</code> <b>TON</b>\n\n"
        f"🏦 <b>آدرس ولت TON جهت واریز:</b>\n"
        f"<code>{html.escape(wallet)}</code>\n\n"
        f"📌 لطفاً دقیقاً مبلغ <b>{ton_str} TON</b> را به آدرس ولت بالا واریز نمایید و سپس روی دکمه سبز <b>«✅ پرداخت کردم»</b> در زیر کلیک کنید تا درخواست تایید برای ادمین ارسال شود:"
    )
    kb = InlineKeyboardMarkup([
        [p_btn("پرداخت کردم (ارسال برای تایید ادمین)", callback_data=f"tonpaid:{order_id}", style="success", emoji_key="check")],
        [p_btn("انصراف و بازگشت", callback_data="menu:buy_diamonds", style="danger", emoji_key="fire")]
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    return ConversationHandler.END

async def ton_paid_user_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    order_id = int(query.data.split(":")[1])

    with closing(get_conn()) as conn, conn:
        order = conn.execute("SELECT * FROM ton_orders WHERE id=? AND user_id=?", (order_id, user.id)).fetchone()
        if not order:
            await query.answer("فاکتور یافت نشد.", show_alert=True)
            return
        if order["status"] != "pending":
            await query.answer("این سفارش قبلاً ثبت و ارسال شده است.", show_alert=True)
            return
        conn.execute("UPDATE ton_orders SET status='awaiting_admin' WHERE id=?", (order_id,))

    await query.answer("✅ درخواست تایید پرداخت برای مدیریت ارسال شد!", show_alert=True)
    await query.edit_message_text(
        p_text(
            f"✅ <b>درخواست تایید پرداخت فاکتور #{order_id} برای ادمین ارسال شد!</b>\n\n"
            f"💎 تعداد: <b>{order['diamonds']:,} الماس</b>\n"
            f"💰 مبلغ: <b>{order['ton_amount']} TON</b>\n\n"
            f"⏳ به‌محض بررسی تراکنش و تایید توسط ادمین، الماس‌ها بلافاصله به حساب شما اضافه خواهند شد."
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )

    # ارسال جزئیات کامل به ادمین برای تایید یا رد
    admin_msg = p_text(
        f"💎 <b>درخواست تایید پرداخت ارز دیجیتال TON (#{order_id})</b>\n\n"
        f"👤 نام کاربر: <b>{html.escape(user.first_name)}</b> (@{user.username or 'ندارد'})\n"
        f"🔢 آیدی عددی کاربر: <code>{user.id}</code>\n"
        f"💎 تعداد الماس خریداری شده: <b>{order['diamonds']:,} الماس</b>\n"
        f"💰 مبلغ پرداختی به تون: <code>{order['ton_amount']}</code> <b>TON</b>\n"
        f"🏦 ولت مقصد: <code>{html.escape(order['wallet_address'])}</code>\n"
        f"⏰ زمان ثبت: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"
    )
    adm_kb = InlineKeyboardMarkup([
        [
            p_btn(f"تایید و شارژ {order['diamonds']} الماس", callback_data=f"tonadm:approve:{order_id}", style="success", emoji_key="check"),
            p_btn("رد کردن پرداخت", callback_data=f"tonadm:reject:{order_id}", style="danger", emoji_key="fire"),
        ]
    ])
    for adm in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=adm, text=admin_msg, parse_mode=ParseMode.HTML, reply_markup=adm_kb)
        except Exception as e:
            logger.error(f"خطا در ارسال فاکتور TON به ادمین: {e}")

async def admin_ton_order_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ فقط ادمین اصلی دسترسی دارد!", show_alert=True)
        return

    _, action, order_id_str = query.data.split(":")
    order_id = int(order_id_str)

    with closing(get_conn()) as conn, conn:
        order = conn.execute("SELECT * FROM ton_orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            await query.answer("سفارش یافت نشد.", show_alert=True)
            return
        if order["status"] in ("approved", "rejected"):
            await query.answer("این سفارش قبلاً تعیین تکلیف شده است.", show_alert=True)
            return

        if action == "approve":
            conn.execute("UPDATE ton_orders SET status='approved' WHERE id=?", (order_id,))
            add_user_diamonds(order["user_id"], order["diamonds"])
            await query.answer(f"✅ تعداد {order['diamonds']} الماس به حساب کاربر اضافه شد!", show_alert=True)
            try:
                await context.bot.send_message(
                    chat_id=order["user_id"],
                    text=p_text(
                        f"🎉 <b>پرداخت TON شما تایید شد!</b>\n\n"
                        f"💎 تعداد <b>{order['diamonds']:,} الماس</b> با موفقیت به حساب کاربری شما در <b>سلف دارک</b> اضافه گردید!"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=main_inline_keyboard(order["user_id"])
                )
            except Exception:
                pass
            await query.edit_message_text(
                p_text(f"{query.message.text}\n\n✅ <b>وضعیت: تایید شد و {order['diamonds']} الماس شارژ گردید.</b>"),
                parse_mode=ParseMode.HTML
            )
        else:
            conn.execute("UPDATE ton_orders SET status='rejected' WHERE id=?", (order_id,))
            await query.answer("❌ سفارش رد شد.", show_alert=True)
            try:
                await context.bot.send_message(
                    chat_id=order["user_id"],
                    text=p_text(f"❌ پرداخت فاکتور #{order_id} ({order['ton_amount']} TON) توسط مدیریت تایید نشد."),
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass
            await query.edit_message_text(
                p_text(f"{query.message.text}\n\n❌ <b>وضعیت: رد شده توسط ادمین.</b>"),
                parse_mode=ParseMode.HTML
            )

# ====================================================================
#  استفاده از کد هدیه الماس توسط کاربر
# ====================================================================

async def gift_code_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        p_text("🎁 <b>لطفاً کد هدیه الماس خود را ارسال کنید:</b>"),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:main")
    )
    return GIFT_WAIT_CODE

async def gift_code_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    code = update.message.text.strip()
    with closing(get_conn()) as conn, conn:
        g = conn.execute("SELECT * FROM gift_codes WHERE code=?", (code,)).fetchone()
        if not g or g["used_count"] >= g["max_uses"]:
            await update.message.reply_text(p_text("❌ کد هدیه نامعتبر است یا ظرفیت آن تمام شده است."), parse_mode=ParseMode.HTML, reply_markup=main_inline_keyboard(user.id))
            return ConversationHandler.END
        already = conn.execute("SELECT 1 FROM gift_uses WHERE code=? AND user_id=?", (code, user.id)).fetchone()
        if already:
            await update.message.reply_text(p_text("⚠️ شما قبلاً از این کد هدیه استفاده کرده‌اید!"), parse_mode=ParseMode.HTML, reply_markup=main_inline_keyboard(user.id))
            return ConversationHandler.END

        conn.execute("INSERT INTO gift_uses (code, user_id) VALUES (?, ?)", (code, user.id))
        conn.execute("UPDATE gift_codes SET used_count = used_count + 1 WHERE code=?", (code,))
        conn.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id=?", (g["diamonds"], user.id))

    await update.message.reply_text(
        p_text(f"🎉 تبریک! کد هدیه اعمال شد و <b>{g['diamonds']} الماس</b> به حساب شما اضافه گردید! 💎"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )
    return ConversationHandler.END

# ====================================================================
#  بخش انتقال الماس بین کاربران با آیدی عددی (پشتیبانی از حداقل انتقال و قفل ادمین)
# ====================================================================

async def transfer_diamonds_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    if get_setting("transfer_enabled", "1") == "0" and not is_admin(user.id):
        await query.answer("⛔ بخش انتقال الماس در حال حاضر توسط مدیریت غیرفعال شده است.", show_alert=True)
        return ConversationHandler.END

    db_user = get_or_create_user(user.id, user.username, user.first_name)
    min_tr = int(get_setting("min_transfer_diamonds", "50"))

    if db_user["diamonds"] < min_tr and not is_admin(user.id):
        await query.answer(f"⚠️ موجودی شما ({db_user['diamonds']} الماس) کمتر از حداقل انتقال ({min_tr} الماس) است!", show_alert=True)
        await query.edit_message_text(
            p_text(
                f"💎 <b>انتقال الماس به سایر کاربران</b>\n\n"
                f"⚠️ موجودی فعلی شما: <b>{db_user['diamonds']} الماس</b>\n"
                f"🔢 حداقل الماس قابل انتقال: <b>{min_tr} الماس</b>\n\n"
                f"❌ موجودی شما برای انتقال الماس کافی نیست. ابتدا از طریق فروشگاه یا زیرمجموعه‌گیری موجودی خود را افزایش دهید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    p_btn("خرید الماس", callback_data="menu:buy_diamonds", style="success", emoji_key="gem"),
                    p_btn("زیرمجموعه‌گیری رایگان", callback_data="menu:referral", style="primary", emoji_key="gift"),
                ],
                [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
            ])
        )
        return ConversationHandler.END

    await query.answer()
    await query.edit_message_text(
        p_text(
            f"💎 <b>انتقال الماس به کاربر دیگر (مرحله ۱ از ۲)</b>\n\n"
            f"💰 موجودی فعلی شما: <b>{db_user['diamonds']} الماس</b>\n"
            f"🔢 حداقل تعداد قابل انتقال: <b>{min_tr} الماس</b>\n\n"
            f"👇 لطفاً <b>آیدی عددی (Numeric ID)</b> کاربری که می‌خواهید برای او الماس بفرستید را وارد کنید:\n"
            f"<i>(مثال: <code>123456789</code>)</i>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:main")
    )
    return TRANSFER_WAIT_TARGET_ID

async def transfer_receive_target_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    raw_txt = normalize_digits((update.message.text or "").strip())

    if get_setting("transfer_enabled", "1") == "0" and not is_admin(user.id):
        await update.message.reply_text(
            p_text("⛔ بخش انتقال الماس توسط مدیریت غیرفعال شده است."),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )
        return ConversationHandler.END

    if not raw_txt.isdigit():
        await update.message.reply_text(
            p_text("⚠️ آیدی وارد شده معتبر نیست! لطفاً فقط <b>آیدی عددی</b> کاربر مقصد را به صورت عدد وارد کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:main")
        )
        return TRANSFER_WAIT_TARGET_ID

    target_id = int(raw_txt)
    if target_id == user.id:
        await update.message.reply_text(
            p_text("⚠️ شما نمی‌توانید به حساب خودتان الماس انتقال دهید! لطفاً آیدی عددی کاربر دیگری را وارد کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:main")
        )
        return TRANSFER_WAIT_TARGET_ID

    context.user_data["transfer_target_id"] = target_id
    db_user = get_or_create_user(user.id, user.username, user.first_name)
    min_tr = int(get_setting("min_transfer_diamonds", "50"))

    with closing(get_conn()) as conn:
        target_row = conn.execute("SELECT first_name, username FROM users WHERE user_id=?", (target_id,)).fetchone()

    target_info = (
        f"<b>{html.escape(target_row['first_name'] or 'کاربر')}</b> (@{target_row['username'] or 'ندارد'})"
        if target_row else "کاربر تلگرام (ثبت با آیدی عددی)"
    )

    await update.message.reply_text(
        p_text(
            f"💎 <b>انتقال الماس به کاربر دیگر (مرحله ۲ از ۲)</b>\n\n"
            f"🎯 آیدی عددی گیرنده: <code>{target_id}</code> ({target_info})\n"
            f"💰 موجودی قابل انتقال شما: <b>{db_user['diamonds']} الماس</b>\n"
            f"🔢 حداقل انتقال مجاز: <b>{min_tr} الماس</b>\n\n"
            f"👇 لطفاً <b>تعداد الماسی</b> که می‌خواهید انتقال دهید را وارد کنید (حداقل <code>{min_tr}</code>):"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:main")
    )
    return TRANSFER_WAIT_AMOUNT

async def transfer_receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    raw_txt = normalize_digits((update.message.text or "").strip())
    target_id = context.user_data.get("transfer_target_id")

    if not target_id:
        await update.message.reply_text(
            p_text("⚠️ اطلاعات تراکنش منقضی شده است. لطفاً مجدداً از منوی اصلی اقدام کنید."),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )
        return ConversationHandler.END

    if get_setting("transfer_enabled", "1") == "0" and not is_admin(user.id):
        await update.message.reply_text(
            p_text("⛔ بخش انتقال الماس توسط مدیریت غیرفعال شده است."),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )
        return ConversationHandler.END

    min_tr = int(get_setting("min_transfer_diamonds", "50"))
    if not raw_txt.isdigit() or int(raw_txt) <= 0:
        await update.message.reply_text(
            p_text(f"⚠️ لطفاً یک عدد صحیح و معتبر (حداقل <b>{min_tr} الماس</b>) وارد کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:main")
        )
        return TRANSFER_WAIT_AMOUNT

    amount = int(raw_txt)
    if amount < min_tr:
        await update.message.reply_text(
            p_text(f"⚠️ حداقل تعداد مجاز برای انتقال <b>{min_tr} الماس</b> است! لطفاً عددی بزرگ‌تر یا مساوی <code>{min_tr}</code> وارد کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:main")
        )
        return TRANSFER_WAIT_AMOUNT

    db_user = get_or_create_user(user.id, user.username, user.first_name)
    if db_user["diamonds"] < amount:
        await update.message.reply_text(
            p_text(
                f"❌ موجودی شما کافی نیست!\n"
                f"💎 موجودی فعلی شما: <b>{db_user['diamonds']} الماس</b>\n"
                f"🔢 مقدار درخواستی: <b>{amount} الماس</b>\n\n"
                f"لطفاً مقدار کمتری وارد کنید یا ابتدا حساب خود را شارژ نمایید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:main")
        )
        return TRANSFER_WAIT_AMOUNT

    # تضمین وجود رکورد گیرنده در دیتابیس و انتقال آنی الماس
    get_or_create_user(target_id)
    add_user_diamonds(user.id, -amount)
    add_user_diamonds(target_id, amount)

    updated_sender = get_or_create_user(user.id)
    updated_receiver = get_or_create_user(target_id)
    context.user_data.pop("transfer_target_id", None)

    # اطلاع‌رسانی به گیرنده الماس
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=p_text(
                f"🎁 <b>دریافت الماس جدید!</b>\n\n"
                f"👤 کاربر <b>{html.escape(user.first_name)}</b> (آیدی عددی: <code>{user.id}</code>) تعداد <b>{amount:,} الماس</b> به حساب شما منتقل کرد!\n"
                f"💎 موجودی جدید شما: <b>{updated_receiver['diamonds']:,} الماس</b>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(target_id)
        )
    except Exception:
        pass

    await update.message.reply_text(
        p_text(
            f"✅ <b>انتقال الماس با موفقیت انجام شد!</b>\n\n"
            f"📤 فرستنده: <code>{user.id}</code>\n"
            f"📥 گیرنده: <code>{target_id}</code>\n"
            f"💎 مقدار منتقل‌شده: <b>{amount:,} الماس</b>\n"
            f"💰 موجودی جدید شما: <b>{updated_sender['diamonds']:,} الماس</b>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )
    return ConversationHandler.END

# ====================================================================
#  هندلرهای پنل مدیریت ۴۰ قابلیته (شامل فوروارد پیام کاربر و تغییر موجودی)
# ====================================================================

async def admin_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ فقط مدیر اصلی دسترسی دارد!", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    page = int(query.data.split(":")[2])
    context.user_data["adm_page"] = page

    ton_rate = get_setting("ton_per_diamond", "0.0005")
    ref_st = "🟢 روشن" if get_setting("referral_enabled", "1") == "1" else "🔴 خاموش"
    ref_rw = get_setting("referral_reward", "5")
    tr_st = "🟢 روشن" if get_setting("transfer_enabled", "1") == "1" else "🔴 خاموش"
    min_tr = get_setting("min_transfer_diamonds", "50")

    text = p_text(
        f"👑 <b>پنل مدیریت جامع «سلف دارک | Self Dark» (۴۰ قابلیت)</b>\n\n"
        f"💎 قیمت هر الماس: <b>{ton_rate} TON</b> | حداقل خرید: <b>{get_setting('min_buy_diamonds')} الماس</b>\n"
        f"🔄 انتقال الماس: <b>{tr_st}</b> | حداقل انتقال: <b>{min_tr} الماس</b>\n"
        f"🎁 زیرمجموعه‌گیری: <b>{ref_st}</b> (پاداش: <b>{ref_rw} الماس</b>)\n"
        f"🌑 سلف‌های روشن در لحظه: <b>{len(ACTIVE_SELF_CLIENTS)} اکانت</b>\n\n"
        f"✨ صفحه {page + 1} از ۴ — یکی از قابلیت‌های زیر را انتخاب کنید:"
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
    return ConversationHandler.END

async def admin_router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ عدم دسترسی!", show_alert=True)
        return ConversationHandler.END

    act = query.data
    page = context.user_data.get("adm_page", 0)
    back_kb = InlineKeyboardMarkup([[p_btn("بازگشت به پنل مدیریت", callback_data=f"admin:page:{page}", style="primary", emoji_key="crown")]])
    await query.answer()

    # ۱. آمار جامع
    if act == "adm:1":
        with closing(get_conn()) as conn:
            u_cnt = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            d_sum = conn.execute("SELECT COALESCE(SUM(diamonds),0) s FROM users").fetchone()["s"]
            s_cnt = conn.execute("SELECT COUNT(*) c FROM self_accounts WHERE is_running=1").fetchone()["c"]
            t_cnt = conn.execute("SELECT COUNT(*) c FROM tabchi_groups").fetchone()["c"]
            o_pend = conn.execute("SELECT COUNT(*) c FROM ton_orders WHERE status IN ('pending','awaiting_admin')").fetchone()["c"]
            o_app = conn.execute("SELECT COUNT(*) c FROM ton_orders WHERE status='approved'").fetchone()["c"]
        await query.edit_message_text(
            p_text(
                f"📊 <b>آمار جامع ربات سلف دارک</b>\n\n"
                f"👥 کل کاربران: <b>{u_cnt:,} نفر</b>\n"
                f"💎 مجموع الماس موجود کاربران: <b>{d_sum:,} الماس</b>\n"
                f"🌑 اکانت‌های سلف روشن در دیتابیس: <b>{s_cnt}</b> (متصل در حافظه: <b>{len(ACTIVE_SELF_CLIENTS)}</b>)\n"
                f"📣 گروه‌های تبچی ثبت‌شده: <b>{t_cnt} گروه</b>\n"
                f"🧾 فاکتورهای TON منتظر تایید: <b>{o_pend}</b> | تایید شده: <b>{o_app}</b>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=back_kb
        )
        return ConversationHandler.END

    # ۴. شناسایی کاربر با فوروارد پیام و کم/زیاد کردن الماس
    elif act == "adm:4":
        await query.edit_message_text(
            p_text(
                "🔍 <b>شناسایی کاربر با فوروارد پیام یا ارسال آیدی عددی</b>\n\n"
                "✨ لطفاً یک پیام از کاربر مورد نظر به اینجا <b>فوروارد (Forward)</b> کنید (یا آیدی عددی/یوزرنیم او را بفرستید) تا مشخصات کامل او باز شود و بتوانید موجودی الماس او را کم یا زیاد کنید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_FORWARD_USER

    # ۱۰. سفارشات TON منتظر تایید
    elif act == "adm:10":
        with closing(get_conn()) as conn:
            orders = conn.execute("SELECT * FROM ton_orders WHERE status IN ('pending','awaiting_admin') ORDER BY id DESC LIMIT 10").fetchall()
        if not orders:
            await query.edit_message_text(p_text("✅ هیچ سفارش TON در انتظار تاییدی وجود ندارد."), parse_mode=ParseMode.HTML, reply_markup=back_kb)
            return ConversationHandler.END
        for o in orders:
            kb = InlineKeyboardMarkup([
                [
                    p_btn(f"تایید ({o['diamonds']} الماس)", callback_data=f"tonadm:approve:{o['id']}", style="success", emoji_key="check"),
                    p_btn("رد سفارش", callback_data=f"tonadm:reject:{o['id']}", style="danger", emoji_key="fire"),
                ]
            ])
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=p_text(
                    f"🧾 <b>سفارش TON #{o['id']}</b>\n"
                    f"👤 کاربر: <code>{o['user_id']}</code>\n"
                    f"💎 الماس: <b>{o['diamonds']}</b> | مبلغ: <code>{o['ton_amount']}</code> TON"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
        return ConversationHandler.END

    # ۱۲. روشن/خاموش کردن زیرمجموعه‌گیری
    elif act == "adm:12":
        curr = get_setting("referral_enabled", "1")
        set_setting("referral_enabled", "0" if curr == "1" else "1")
        st = "🟢 روشن شد" if curr == "0" else "🔴 خاموش شد"
        await query.edit_message_text(p_text(f"✅ بخش زیرمجموعه‌گیری <b>{st}</b>."), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    # ۱۴. افزودن کانال جوین اجباری
    elif act == "adm:14":
        await query.edit_message_text(
            p_text("➕ <b>افزودن کانال جوین اجباری (مرحله ۱ از ۳)</b>\nآیدی کانال با @ (مثل <code>@MyChannel</code>) یا آیدی عددی کانال را بفرستید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_FCH_ID

    # ۱۵. حذف کانال جوین اجباری
    elif act == "adm:15":
        chs = get_force_channels()
        if not chs:
            await query.edit_message_text(p_text("⚠️ کانالی ثبت نشده است."), parse_mode=ParseMode.HTML, reply_markup=back_kb)
            return ConversationHandler.END
        rows = [[p_btn(f"حذف {c['title']} ({c['channel_id']})", callback_data=f"rmfch:{c['id']}", style="danger", emoji_key="fire")] for c in chs]
        rows.append([p_btn("بازگشت", callback_data=f"admin:page:{page}", style="primary")])
        await query.edit_message_text(p_text("🗑 روی کانال مورد نظر برای حذف کلیک کنید:"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
        return ConversationHandler.END

    # ۱۶. لیست کانال‌های اجباری
    elif act == "adm:16":
        chs = get_force_channels()
        if not chs:
            txt = "📢 هیچ کانال جوین اجباری ثبت نشده است."
        else:
            txt = "📋 <b>کانال‌های جوین اجباری:</b>\n\n" + "\n".join([f"• <b>{html.escape(c['title'])}</b> (<code>{c['channel_id']}</code>) -> {c['channel_link']}" for c in chs])
        await query.edit_message_text(p_text(txt), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    # ۱۹. لیست اکانت‌های سلف روشن
    elif act == "adm:19":
        with closing(get_conn()) as conn:
            accs = conn.execute("SELECT * FROM self_accounts WHERE is_running=1 LIMIT 30").fetchall()
        if not accs:
            txt = "🌑 هیچ اکانت سلفی در حال حاضر روشن نیست."
        else:
            lines = ["🌑 <b>لیست اکانت‌های سلف دارک فعال:</b>\n"]
            for a in accs:
                lines.append(f"• کاربر <code>{a['user_id']}</code> | شماره: <code>{a['phone']}</code> | پیام‌ها: {a['msg_counter']}")
            txt = "\n".join(lines)
        await query.edit_message_text(p_text(txt), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    # ۲۱. راه‌اندازی مجدد همه سلف‌ها
    elif act == "adm:21":
        with closing(get_conn()) as conn:
            accs = conn.execute("SELECT * FROM self_accounts WHERE is_running=1").fetchall()
        ok = 0
        for a in accs:
            if await start_single_self_client(a["user_id"], a["session_string"]):
                ok += 1
        await query.edit_message_text(p_text(f"✅ تعداد <b>{ok} سلف دارک</b> با موفقیت راه‌اندازی مجدد شدند."), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    # ۲۶ و ۲۷. کدهای هدیه
    elif act == "adm:26":
        with closing(get_conn()) as conn, conn:
            conn.execute("DELETE FROM gift_codes")
        await query.edit_message_text(p_text("🗑 تمام کدهای هدیه حذف شدند."), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    elif act == "adm:27":
        with closing(get_conn()) as conn:
            codes = conn.execute("SELECT * FROM gift_codes").fetchall()
        if not codes:
            txt = "🎁 هیچ کد هدیه‌ای وجود ندارد."
        else:
            txt = "🎁 <b>لیست کدهای هدیه:</b>\n\n" + "\n".join([f"• <code>{c['code']}</code> -> {c['diamonds']} الماس ({c['used_count']}/{c['max_uses']})" for c in codes])
        await query.edit_message_text(p_text(txt), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    # ۳۰. برترین زیرمجموعه‌گیرها
    elif act == "adm:30":
        with closing(get_conn()) as conn:
            top_u = conn.execute("SELECT * FROM users ORDER BY referrals_count DESC LIMIT 10").fetchall()
        lines = ["🏆 <b>۱۰ زیرمجموعه‌گیر برتر سلف دارک:</b>\n"]
        for idx, u in enumerate(top_u, 1):
            lines.append(f"{idx}. <code>{u['user_id']}</code> ({html.escape(u['first_name'] or '')}) -> <b>{u['referrals_count']} زیرمجموعه</b>")
        await query.edit_message_text(p_text("\n".join(lines)), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    # ۳۱. ثروتمندترین کاربران الماس
    elif act == "adm:31":
        with closing(get_conn()) as conn:
            top_d = conn.execute("SELECT * FROM users ORDER BY diamonds DESC LIMIT 10").fetchall()
        lines = ["💎 <b>۱۰ کاربر دارای بیشترین الماس:</b>\n"]
        for idx, u in enumerate(top_d, 1):
            lines.append(f"{idx}. <code>{u['user_id']}</code> ({html.escape(u['first_name'] or '')}) -> <b>{u['diamonds']} الماس</b>")
        await query.edit_message_text(p_text("\n".join(lines)), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    # ۳۲. لیست گروه‌های تبچی
    elif act == "adm:32":
        with closing(get_conn()) as conn:
            grps = conn.execute("SELECT * FROM tabchi_groups LIMIT 25").fetchall()
        if not grps:
            txt = "📣 هیچ گروه تبچی ثبت نشده است."
        else:
            txt = "📣 <b>لیست گروه‌های تبچی ثبت‌شده:</b>\n\n" + "\n".join([f"• {html.escape(g['chat_title'])} (<code>{g['chat_id']}</code>) | کاربر: <code>{g['user_id']}</code>" for g in grps])
        await query.edit_message_text(p_text(txt), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    # ۳۳. روشن/خاموش کردن سراسری تبچی
    elif act == "adm:33":
        curr = get_setting("tabchi_global_enabled", "1")
        set_setting("tabchi_global_enabled", "0" if curr == "1" else "1")
        st = "🟢 روشن" if curr == "0" else "🔴 خاموش"
        await query.edit_message_text(p_text(f"✅ وضعیت سراسری تبچی: <b>{st}</b>"), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    # ۳۶. روشن/خاموش کردن ثبت سلف جدید
    elif act == "adm:36":
        curr = get_setting("self_new_login_enabled", "1")
        set_setting("self_new_login_enabled", "0" if curr == "1" else "1")
        st = "🟢 مجاز" if curr == "0" else "🔴 غیرمجاز"
        await query.edit_message_text(p_text(f"✅ ثبت اکانت سلف جدید: <b>{st}</b>"), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    # ۳۷ یا دکمه بازگردانی بکاپ (Restore Backup)
    elif act in ("adm:37", "adm:restore_backup"):
        await query.edit_message_text(
            p_text(
                "♻️ <b>بازگردانی کامل اطلاعات ربات و کاربران (Restore Backup)</b>\n\n"
                "✨ لطفاً فایل بکاپی که قبلاً از ربات دریافت کرده‌اید (فایل <code>.json</code> یا فایل دیتابیس <code>.db</code>) را در همینجا <b>ارسال یا فوروارد کنید</b>:\n\n"
                "🔹 تمام اطلاعات کاربران، موجودی الماس‌ها، زیرمجموعه‌ها، اکانت‌های سلف متصل (Session)، گروه‌های تبچی، کدهای هدیه و تنظیمات ربات عیناً بازگردانی و فعال خواهند شد."
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_RESTORE_FILE

    # ۳۸ یا دکمه بکاپ کامل اطلاعات ربات و کاربران
    elif act in ("adm:38", "adm:backup_all"):
        await send_full_backup_to_admin(query.message.chat_id, context, page)
        return ConversationHandler.END

    # ۳۹. وضعیت سلامت سرور و پینگر Render
    elif act == "adm:39":
        up = int((datetime.now() - START_TIME).total_seconds())
        await query.edit_message_text(
            p_text(
                f"⚡ <b>وضعیت سرور Render و پینگر ۵ دقیقه‌ای</b>\n\n"
                f"🟢 وب‌سرور Flask: <b>فعال</b>\n"
                f"📡 تعداد سیگنال‌های ضد خواب ارسال شده: <b>{PING_COUNTER} بار</b>\n"
                f"⏱ آپتایم فعلی: <b>{up // 3600} ساعت و {(up % 3600) // 60} دقیقه</b>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=back_kb
        )
        return ConversationHandler.END

    # ۴۰. روشن/خاموش کردن کل ربات
    elif act == "adm:40":
        curr = get_setting("bot_active", "1")
        set_setting("bot_active", "0" if curr == "1" else "1")
        st = "🟢 روشن" if curr == "0" else "🔴 خاموش"
        await query.edit_message_text(p_text(f"✅ وضعیت کلی ربات سلف دارک: <b>{st}</b>"), parse_mode=ParseMode.HTML, reply_markup=back_kb)
        return ConversationHandler.END

    # روشن یا خاموش کردن بخش انتقال الماس
    elif act == "adm:toggle_transfer":
        curr = get_setting("transfer_enabled", "1")
        new_val = "0" if curr == "1" else "1"
        set_setting("transfer_enabled", new_val)
        st = "🟢 روشن و فعال شد" if new_val == "1" else "🔴 خاموش و غیرفعال شد"
        await query.edit_message_text(
            p_text(f"✅ وضعیت بخش <b>انتقال الماس بین کاربران</b> با موفقیت تغییر یافت:\n<b>{st}</b>"),
            parse_mode=ParseMode.HTML,
            reply_markup=build_admin_keyboard(page)
        )
        return ConversationHandler.END

    # سایر قابلیت‌هایی که ورودی متنی می‌گیرند
    prompts = {
        "adm:2":  "📣 <b>ارسال پیام همگانی</b>\nپیام خود را بفرستید:",
        "adm:3":  "🔄 <b>فوروارد همگانی</b>\nپیام خود را فوروارد کنید:",
        "adm:5":  "➕ <b>افزایش الماس کاربر با آیدی</b>\nبا فرمت <code>USER_ID:AMOUNT</code> بفرستید (مثال: <code>12345678:50</code>):",
        "adm:6":  "➖ <b>کسر الماس کاربر با آیدی</b>\nبا فرمت <code>USER_ID:AMOUNT</code> بفرستید (مثال: <code>12345678:20</code>):",
        "adm:7":  f"🏦 <b>تنظیم آدرس ولت TON</b>\nآدرس فعلی:\n<code>{html.escape(get_setting('ton_wallet'))}</code>\nآدرس ولت جدید را بفرستید:",
        "adm:8":  f"💎 <b>تنظیم قیمت هر ۱ الماس به TON</b>\nقیمت فعلی: <code>{get_setting('ton_per_diamond')}</code> TON\nمقدار اعشاری جدید را بفرستید (مثلاً <code>0.0005</code>):",
        "adm:9":  f"🔢 <b>تنظیم حداقل خرید الماس</b>\nمقدار فعلی: <b>{get_setting('min_buy_diamonds')} الماس</b>\nعدد جدید را بفرستید:",
        "adm:11": f"💳 <b>تنظیم آیدی پشتیبانی پرداخت ریالی</b>\nآیدی فعلی: {get_setting('rial_support_id')}\nآیدی جدید را با @ بفرستید:",
        "adm:13": f"🎁 <b>تغییر پاداش الماس هر زیرمجموعه</b>\nمقدار فعلی: <b>{get_setting('referral_reward')} الماس</b>\nعدد جدید را بفرستید:",
        "adm:17": f"⚡ <b>تغییر هزینه فعال‌سازی سلف دارک</b>\nمقدار فعلی: <b>{get_setting('activation_cost')} الماس</b>\nعدد جدید را بفرستید:",
        "adm:18": f"⏳ <b>تغییر هزینه ساعتی روشن بودن سلف دارک</b>\nمقدار فعلی: <b>{get_setting('hourly_cost')} الماس</b>\nعدد جدید را بفرستید:",
        "adm:20": "🔴 <b>قطع و توقف سلف کاربر</b>\nآیدی عددی کاربر را بفرستید:",
        "adm:22": "🚫 <b>مسدود کردن کاربر (Ban)</b>\nآیدی عددی کاربر را بفرستید:",
        "adm:23": "🟢 <b>رفع مسدودیت کاربر (Unban)</b>\nآیدی عددی کاربر را بفرستید:",
        "adm:24": "🎉 <b>هدیه الماس همگانی به تمام کاربران</b>\nتعداد الماسی که به همه اضافه شود را بفرستید:",
        "adm:25": "🎁 <b>ساخت کد هدیه الماس</b>\nبا فرمت <code>CODE:DIAMONDS:MAX_USES</code> بفرستید (مثال: <code>DARK50:50:10</code>):",
        "adm:28": f"🌟 <b>تنظیم الماس هدیه خوش‌آمدگویی</b>\nمقدار فعلی: <b>{get_setting('welcome_bonus')} الماس</b>\nعدد جدید را بفرستید:",
        "adm:29": f"📅 <b>تنظیم الماس هدیه روزانه</b>\nمقدار فعلی: <b>{get_setting('daily_gift_diamonds')} الماس</b>\nعدد جدید را بفرستید:",
        "adm:34": "✉️ <b>ارسال پیام مستقیم به کاربر</b>\nبا فرمت <code>USER_ID:MESSAGE</code> بفرستید:",
        "adm:35": "📚 <b>تنظیم متن تکمیلی انتهای راهنما</b>\nمتن جدید را بفرستید:",
        "adm:set_min_transfer": f"🔢 <b>تغییر حداقل انتقال الماس بین کاربران</b>\nحداقل فعلی: <b>{get_setting('min_transfer_diamonds', '50')} الماس</b>\nلطفاً عدد جدید حداقل انتقال الماس را وارد کنید (مثلاً <code>50</code> یا <code>20</code>):",
    }

    if act in prompts:
        context.user_data["adm_act"] = act
        await query.edit_message_text(
            p_text(prompts[act]),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_GENERIC

    return ConversationHandler.END

# ---- شناسایی کاربر با فوروارد پیام و افزایش/کاهش الماس ----
async def admin_receive_forwarded_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    page = context.user_data.get("adm_page", 0)
    target_uid = None

    # بررسی فوروارد در نسخه جدید PTB (forward_origin)
    if getattr(msg, "forward_origin", None):
        origin = msg.forward_origin
        if hasattr(origin, "sender_user") and origin.sender_user:
            target_uid = origin.sender_user.id

    if not target_uid and msg.text:
        t = msg.text.strip()
        if t.isdigit():
            target_uid = int(t)
        elif t.startswith("@"):
            with closing(get_conn()) as conn:
                row = conn.execute("SELECT user_id FROM users WHERE LOWER(username)=?", (t[1:].lower(),)).fetchone()
                if row:
                    target_uid = row["user_id"]

    if not target_uid:
        await msg.reply_text(
            p_text("⚠️ آیدی کاربر از پیام فوروارد شده قابل استخراج نبود (ممکن است فوروارد کاربر قفل باشد). لطفاً آیدی عددی یا @یوزرنیم او را بفرستید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_FORWARD_USER

    u = get_or_create_user(target_uid)
    acc = get_self_account(target_uid)
    context.user_data["adm_target_uid"] = target_uid

    info = p_text(
        f"👤 <b>کاربر شناسایی شد!</b>\n\n"
        f"🔢 آیدی عددی: <code>{target_uid}</code>\n"
        f"👤 نام: <b>{html.escape(u['first_name'] or 'کاربر')}</b> (@{u['username'] or 'ندارد'})\n"
        f"💎 موجودی فعلی الماس: <b>{u['diamonds']} الماس</b>\n"
        f"👥 زیرمجموعه‌ها: <b>{u['referrals_count']} نفر</b>\n"
        f"📱 شماره سلف دارک: <code>{acc['phone'] if acc else 'ندارد'}</code>\n\n"
        f"👇 حالا <b>مقدار الماسی که می‌خواهید اضافه یا کم کنید</b> را بفرستید:\n"
        f"• برای افزایش، عدد مثبت بفرستید (مثلاً <code>+50</code> یا <code>50</code>)\n"
        f"• برای کاهش، عدد منفی بفرستید (مثلاً <code>-30</code>)"
    )
    await msg.reply_text(info, parse_mode=ParseMode.HTML, reply_markup=cancel_inline_keyboard(f"admin:page:{page}"))
    return ADM_WAIT_FORWARD_AMOUNT

async def admin_receive_forward_diamond_delta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    page = context.user_data.get("adm_page", 0)
    target_uid = context.user_data.get("adm_target_uid")
    try:
        delta = int(txt)
    except ValueError:
        await update.message.reply_text(p_text("⚠️ لطفاً یک عدد صحیح (مثبت یا منفی) وارد کنید:"), parse_mode=ParseMode.HTML)
        return ADM_WAIT_FORWARD_AMOUNT

    add_user_diamonds(target_uid, delta)
    u = get_or_create_user(target_uid)
    action_word = f"+{delta} الماس اضافه شد" if delta >= 0 else f"{abs(delta)} الماس کسر شد"

    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text=p_text(f"💎 تغییر موجودی توسط مدیریت:\n<b>{action_word}</b>\n💰 موجودی جدید شما: <b>{u['diamonds']} الماس</b>"),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

    await update.message.reply_text(
        p_text(f"✅ تغییر موجودی روی کاربر <code>{target_uid}</code> اعمال شد ({action_word}).\n💎 موجودی جدید کاربر: <b>{u['diamonds']} الماس</b>"),
        parse_mode=ParseMode.HTML,
        reply_markup=build_admin_keyboard(page)
    )
    return ConversationHandler.END

# ---- مدیریت ورودی‌های متنی ادمین ----
async def admin_handle_generic_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    act = context.user_data.get("adm_act")
    page = context.user_data.get("adm_page", 0)
    msg = update.message
    txt = (msg.text or "").strip()

    if act in ("adm:2", "adm:3"):
        with closing(get_conn()) as conn:
            users = conn.execute("SELECT user_id FROM users").fetchall()
        sent, failed = 0, 0
        st_msg = await msg.reply_text(p_text(f"⏳ در حال ارسال به {len(users)} کاربر..."), parse_mode=ParseMode.HTML)
        for u in users:
            try:
                if act == "adm:3":
                    await msg.forward(chat_id=u["user_id"])
                else:
                    await msg.copy(chat_id=u["user_id"])
                sent += 1
            except Exception:
                failed += 1
        await st_msg.edit_text(
            p_text(f"✅ <b>ارسال همگانی کامل شد!</b>\n🟢 موفق: <b>{sent}</b> | 🔴 ناموفق: <b>{failed}</b>"),
            parse_mode=ParseMode.HTML,
            reply_markup=build_admin_keyboard(page)
        )
        return ConversationHandler.END

    elif act in ("adm:5", "adm:6") and ":" in txt:
        uid_s, amt_s = txt.split(":", 1)
        if uid_s.strip().isdigit() and amt_s.strip().isdigit():
            uid = int(uid_s.strip())
            amt = int(amt_s.strip())
            delta = amt if act == "adm:5" else -amt
            get_or_create_user(uid)
            add_user_diamonds(uid, delta)
            await msg.reply_text(p_text(f"✅ تغییر الماس ({delta:+d}) برای کاربر <code>{uid}</code> انجام شد."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
            return ConversationHandler.END

    elif act == "adm:7":
        set_setting("ton_wallet", txt)
        await msg.reply_text(p_text(f"✅ آدرس ولت TON ذخیره شد:\n<code>{html.escape(txt)}</code>"), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:8":
        try:
            float(txt)
            set_setting("ton_per_diamond", txt)
            await msg.reply_text(p_text(f"✅ قیمت هر ۱ الماس به <b>{txt} TON</b> تغییر یافت."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        except ValueError:
            await msg.reply_text(p_text("⚠️ عدد اعشاری معتبر وارد کنید."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:9" and txt.isdigit():
        set_setting("min_buy_diamonds", txt)
        await msg.reply_text(p_text(f"✅ حداقل خرید الماس روی <b>{txt}</b> تنظیم شد."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:11":
        set_setting("rial_support_id", txt)
        await msg.reply_text(p_text(f"✅ آیدی پشتیبانی ریالی به {html.escape(txt)} تغییر یافت."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:13" and txt.isdigit():
        set_setting("referral_reward", txt)
        await msg.reply_text(p_text(f"✅ پاداش هر زیرمجموعه به <b>{txt} الماس</b> تغییر یافت."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:17" and txt.isdigit():
        set_setting("activation_cost", txt)
        await msg.reply_text(p_text(f"✅ هزینه فعال‌سازی سلف روی <b>{txt} الماس</b> تنظیم شد."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:18" and txt.isdigit():
        set_setting("hourly_cost", txt)
        await msg.reply_text(p_text(f"✅ هزینه ساعتی سلف روی <b>{txt} الماس</b> تنظیم شد."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:20" and txt.isdigit():
        await stop_single_self_client(int(txt))
        await msg.reply_text(p_text(f"🔴 سلف دارک کاربر <code>{txt}</code> متوقف شد."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act in ("adm:22", "adm:23") and txt.isdigit():
        b_val = 1 if act == "adm:22" else 0
        with closing(get_conn()) as conn, conn:
            conn.execute("UPDATE users SET is_banned=? WHERE user_id=?", (b_val, int(txt)))
        await msg.reply_text(p_text(f"✅ وضعیت مسدودیت کاربر <code>{txt}</code> تغییر کرد."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:24" and txt.isdigit():
        amt = int(txt)
        with closing(get_conn()) as conn, conn:
            conn.execute("UPDATE users SET diamonds = diamonds + ?", (amt,))
        await msg.reply_text(p_text(f"🎉 تعداد <b>{amt} الماس همگانی</b> به تمام کاربران اضافه شد!"), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:25" and txt.count(":") == 2:
        c_code, c_dia, c_max = [x.strip() for x in txt.split(":")]
        if c_dia.isdigit() and c_max.isdigit():
            with closing(get_conn()) as conn, conn:
                conn.execute("INSERT OR REPLACE INTO gift_codes (code, diamonds, max_uses, used_count) VALUES (?, ?, ?, 0)", (c_code, int(c_dia), int(c_max)))
            await msg.reply_text(p_text(f"🎁 کد هدیه <code>{c_code}</code> ({c_dia} الماس - {c_max} بار مصرف) ساخته شد!"), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
            return ConversationHandler.END

    elif act == "adm:28" and txt.isdigit():
        set_setting("welcome_bonus", txt)
        await msg.reply_text(p_text(f"✅ هدیه خوش‌آمدگویی روی <b>{txt} الماس</b> تنظیم شد."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:29" and txt.isdigit():
        set_setting("daily_gift_diamonds", txt)
        await msg.reply_text(p_text(f"✅ هدیه روزانه روی <b>{txt} الماس</b> تنظیم شد."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:34" and ":" in txt:
        uid_s, m_body = txt.split(":", 1)
        if uid_s.strip().isdigit():
            try:
                await context.bot.send_message(chat_id=int(uid_s.strip()), text=p_text(f"✉️ <b>پیام از طرف مدیریت سلف دارک:</b>\n\n{html.escape(m_body.strip())}"), parse_mode=ParseMode.HTML)
                await msg.reply_text(p_text("✅ پیام ارسال شد."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
            except Exception as e:
                await msg.reply_text(p_text(f"❌ خطا در ارسال: {e}"), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
            return ConversationHandler.END

    elif act == "adm:35":
        set_setting("help_extra_note", txt)
        await msg.reply_text(p_text("✅ متن تکمیلی راهنما بروزرسانی شد."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
        return ConversationHandler.END

    elif act == "adm:set_min_transfer":
        norm_num = normalize_digits(txt)
        if norm_num.isdigit() and int(norm_num) >= 1:
            set_setting("min_transfer_diamonds", str(int(norm_num)))
            await msg.reply_text(
                p_text(f"✅ حداقل انتقال الماس بین کاربران با موفقیت روی <b>{int(norm_num)} الماس</b> تنظیم شد."),
                parse_mode=ParseMode.HTML,
                reply_markup=build_admin_keyboard(page)
            )
            return ConversationHandler.END

    await msg.reply_text(p_text("⚠️ فرمت ورودی نامعتبر بود. به پنل مدیریت بازگشتید."), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
    return ConversationHandler.END

async def admin_remove_fch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return
    fch_id = int(query.data.split(":")[1])
    with closing(get_conn()) as conn, conn:
        conn.execute("DELETE FROM force_channels WHERE id=?", (fch_id,))
    await query.answer("🗑 کانال از جوین اجباری حذف شد!", show_alert=True)
    page = context.user_data.get("adm_page", 0)
    query.data = f"admin:page:{page}"
    await admin_page_callback(update, context)

async def admin_add_fch_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_fch_id"] = update.message.text.strip()
    await update.message.reply_text(p_text("🔗 <b>مرحله ۲ از ۳: لینک عضویت کانال</b> را بفرستید:"), parse_mode=ParseMode.HTML)
    return ADM_WAIT_FCH_LINK

async def admin_add_fch_step2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_fch_link"] = update.message.text.strip()
    await update.message.reply_text(p_text("🏷 <b>مرحله ۳ از ۳: عنوان دکمه کانال</b> را بفرستید:"), parse_mode=ParseMode.HTML)
    return ADM_WAIT_FCH_TITLE

async def admin_add_fch_step3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    ch_id = context.user_data.get("new_fch_id")
    ch_link = context.user_data.get("new_fch_link")
    with closing(get_conn()) as conn, conn:
        conn.execute("INSERT OR REPLACE INTO force_channels (channel_id, channel_link, title) VALUES (?, ?, ?)", (ch_id, ch_link, title))
    page = context.user_data.get("adm_page", 0)
    await update.message.reply_text(p_text(f"✅ کانال <b>{html.escape(title)}</b> اضافه شد!"), parse_mode=ParseMode.HTML, reply_markup=build_admin_keyboard(page))
    return ConversationHandler.END

async def send_full_backup_to_admin(chat_id: int, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """تهیه بکاپ جامع از تمام اطلاعات ربات و کاربران (هم فایل JSON کامل و هم فایل DB)"""
    tables = [
        "users",
        "self_accounts",
        "tabchi_groups",
        "settings",
        "force_channels",
        "ton_orders",
        "gift_codes",
        "gift_uses",
        "private_notes",
    ]
    backup_payload = {
        "bot": "self_dark",
        "version": "4.0",
        "created_at": datetime.now().isoformat(),
        "tables": {},
    }
    with closing(get_conn()) as conn:
        for t in tables:
            try:
                rows = conn.execute(f"SELECT * FROM {t}").fetchall()
                backup_payload["tables"][t] = [dict(r) for r in rows]
            except Exception:
                backup_payload["tables"][t] = []

        u_cnt = len(backup_payload["tables"].get("users", []))
        d_sum = sum(int(x.get("diamonds", 0)) for x in backup_payload["tables"].get("users", []))
        s_cnt = len(backup_payload["tables"].get("self_accounts", []))
        t_cnt = len(backup_payload["tables"].get("tabchi_groups", []))

    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_bytes = json.dumps(backup_payload, ensure_ascii=False, indent=2).encode("utf-8")
    bio = io.BytesIO(json_bytes)
    bio.name = f"self_dark_full_backup_{ts_str}.json"

    caption = p_text(
        f"📦 <b>بکاپ کامل اطلاعات ربات و کاربران «سلف دارک»</b>\n\n"
        f"👥 کل کاربران ذخیره شده: <b>{u_cnt:,} نفر</b>\n"
        f"💎 مجموع الماس کاربران: <b>{d_sum:,} الماس</b>\n"
        f"🌑 اکانت‌های سلف و سشن‌ها: <b>{s_cnt} اکانت</b>\n"
        f"📣 گروه‌های تبچی ثبت‌شده: <b>{t_cnt} گروه</b>\n"
        f"⏰ تاریخ تهیه بکاپ: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n\n"
        f"♻️ برای بازگردانی، هر زمان کافی است دکمه <b>«♻️ بازگردانی بکاپ (Restore)»</b> را در پنل ادمین بزنید و همین فایل را ارسال کنید."
    )
    await context.bot.send_document(
        chat_id=chat_id,
        document=bio,
        caption=caption,
        parse_mode=ParseMode.HTML,
        reply_markup=build_admin_keyboard(page)
    )

async def admin_receive_restore_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت فایل بکاپ (.json یا .db) از ادمین و بازگردانی کامل تمام اطلاعات کاربران و ربات"""
    msg = update.message
    page = context.user_data.get("adm_page", 0)
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    if not msg.document:
        await msg.reply_text(
            p_text("⚠️ لطفاً <b>فایل بکاپ</b> (با پسوند <code>.json</code> یا <code>.db</code>) را ارسال یا فوروارد کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_RESTORE_FILE

    wait_m = await msg.reply_text(p_text("⏳ در حال بررسی فایل بکاپ و بازگردانی کل اطلاعات کاربران و ربات..."), parse_mode=ParseMode.HTML)

    try:
        tg_file = await context.bot.get_file(msg.document.file_id)
        raw_bytes = bytes(await tg_file.download_as_bytearray())

        restored_counts = {"users": 0, "self_accounts": 0, "tabchi_groups": 0, "settings": 0}

        # بررسی اینکه فایل SQLite (.db) است یا فایل JSON
        if raw_bytes.startswith(b"SQLite format 3"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                tmp.write(raw_bytes)
                tmp_path = tmp.name
            try:
                src_conn = sqlite3.connect(tmp_path)
                src_conn.row_factory = sqlite3.Row
                with closing(get_conn()) as dst_conn, dst_conn:
                    for t_name in ["users", "self_accounts", "tabchi_groups", "settings", "force_channels", "ton_orders", "gift_codes", "gift_uses", "private_notes"]:
                        try:
                            rows = src_conn.execute(f"SELECT * FROM {t_name}").fetchall()
                            if rows:
                                cols = rows[0].keys()
                                placeholders = ",".join(["?"] * len(cols))
                                col_names = ",".join(cols)
                                for r in rows:
                                    dst_conn.execute(
                                        f"INSERT OR REPLACE INTO {t_name} ({col_names}) VALUES ({placeholders})",
                                        tuple(r[c] for c in cols)
                                    )
                                if t_name in restored_counts:
                                    restored_counts[t_name] = len(rows)
                        except Exception:
                            pass
                src_conn.close()
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        else:
            data = json.loads(raw_bytes.decode("utf-8"))
            tables_data = data.get("tables", {})
            with closing(get_conn()) as dst_conn, dst_conn:
                for t_name, rows in tables_data.items():
                    if not isinstance(rows, list) or not rows:
                        continue
                    if t_name not in ("users", "self_accounts", "tabchi_groups", "settings", "force_channels", "ton_orders", "gift_codes", "gift_uses", "private_notes"):
                        continue
                    cols = list(rows[0].keys())
                    placeholders = ",".join(["?"] * len(cols))
                    col_names = ",".join(cols)
                    for r in rows:
                        dst_conn.execute(
                            f"INSERT OR REPLACE INTO {t_name} ({col_names}) VALUES ({placeholders})",
                            tuple(r.get(c) for c in cols)
                        )
                    if t_name in restored_counts:
                        restored_counts[t_name] = len(rows)

        # راه‌اندازی مجدد تمام اکانت‌های سلف بازگردانی شده
        with closing(get_conn()) as conn:
            running_accs = conn.execute("SELECT * FROM self_accounts WHERE is_running=1").fetchall()
        reconnected = 0
        for acc in running_accs:
            if await start_single_self_client(acc["user_id"], acc["session_string"]):
                reconnected += 1

        await wait_m.edit_text(
            p_text(
                f"✅ <b>بازگردانی بکاپ (Restore) با موفقیت کامل انجام شد!</b>\n\n"
                f"👥 کاربران بازگردانی شده: <b>{restored_counts['users']:,} نفر</b>\n"
                f"🌑 اکانت‌های سلف بازیابی شده: <b>{restored_counts['self_accounts']} اکانت</b> (متصل شده در لحظه: <b>{reconnected}</b>)\n"
                f"📣 گروه‌های تبچی بازیابی شده: <b>{restored_counts['tabchi_groups']} گروه</b>\n"
                f"⚙️ تنظیمات بازیابی شده: <b>{restored_counts['settings']} مورد</b>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=build_admin_keyboard(page)
        )
    except Exception as e:
        await wait_m.edit_text(
            p_text(f"❌ خطا در بازگردانی فایل بکاپ:\n<code>{html.escape(str(e)[:150])}</code>"),
            parse_mode=ParseMode.HTML,
            reply_markup=build_admin_keyboard(page)
        )

    return ConversationHandler.END

# ====================================================================
#  بازیابی خودکار سلف‌های روشن هنگام بالا آمدن سرور Render
# ====================================================================

async def post_init_startup(application: Application):
    global BOT_APP_REF
    BOT_APP_REF = application

    # راه‌اندازی مجدد تمام اکانت‌های سلف دارک که در دیتابیس روشن هستند
    with closing(get_conn()) as conn:
        running_accs = conn.execute("SELECT * FROM self_accounts WHERE is_running=1").fetchall()

    for acc in running_accs:
        await start_single_self_client(acc["user_id"], acc["session_string"])

    # اجرای حلقه بسیار دقیق ساعت پروفایل (هر دقیقه دقیق بر اساس ساعت دستگاه کاربر)
    asyncio.create_task(accurate_profile_clock_loop())

    # ثبت جاب‌های دوره‌ای در JobQueue
    if application.job_queue:
        application.job_queue.run_repeating(hourly_diamond_billing_job, interval=60, first=30)
        application.job_queue.run_repeating(profile_and_tabchi_worker_job, interval=60, first=20)
    else:
        # در صورتی که job_queue نصب نبود، با تسک asyncio اجرا شود
        async def fallback_loop():
            while True:
                await asyncio.sleep(60)
                try:
                    await hourly_diamond_billing_job(application)
                    await profile_and_tabchi_worker_job(application)
                except Exception as e:
                    logger.warning(f"Loop error: {e}")
        asyncio.create_task(fallback_loop())

# ====================================================================
#  تابع اصلی اجرا (Main)
# ====================================================================

async def fallback_pending_login_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پشتیبان هوشمند: اگر کاربر خارج از وضعیت مکالمه کد ورود یا رمز 2FA خود را فرستاد، آن را پردازش کند"""
    user = update.effective_user
    if not user or user.id not in PENDING_LOGINS:
        return
    info = PENDING_LOGINS[user.id]
    if info.get("awaiting_2fa"):
        await activate_self_receive_2fa(update, context)
    else:
        await activate_self_receive_code(update, context)

def main():
    init_db()
    start_render_keep_alive()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init_startup).build()

    # ۱. مکالمه فعال‌سازی سلف دارک (همراه با کیبورد شیشه‌ای کد ورود + پشتیبانی از ارسال متنی)
    self_login_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(activate_self_start, pattern="^menu:activate_self$"),
            MessageHandler(filters.CONTACT, activate_self_receive_phone),
        ],
        states={
            SELF_WAIT_PHONE: [
                MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, activate_self_receive_phone)
            ],
            SELF_WAIT_CODE: [
                CallbackQueryHandler(activate_self_code_keypad_callback, pattern="^codepad:"),
                MessageHandler(filters.CONTACT, activate_self_receive_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, activate_self_receive_code),
            ],
            SELF_WAIT_2FA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, activate_self_receive_2fa),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۲. مکالمه ویرایش مقدار قابلیت‌های سلف
    feat_val_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(feature_set_val_start, pattern="^fsetval:")],
        states={
            FEAT_WAIT_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, feature_set_val_save)],
        },
        fallbacks=[
            CallbackQueryHandler(self_features_callbacks, pattern="^self:features_page:"),
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۳. مکالمه تنظیمات تبچی هوشمند
    tabchi_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(tabchi_edit_start, pattern="^tabchi_edit:"),
            CallbackQueryHandler(tabchi_edit_start, pattern="^tabchi:set_all_banner$"),
        ],
        states={
            TABCHI_WAIT_BANNER: [MessageHandler(filters.TEXT & ~filters.COMMAND, tabchi_save_banner)],
            TABCHI_WAIT_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, tabchi_save_interval)],
            TABCHI_WAIT_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, tabchi_save_delay)],
        },
        fallbacks=[
            CallbackQueryHandler(tabchi_menu_callback, pattern="^menu:tabchi$|^tabchi:"),
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۴. مکالمه خرید الماس با TON
    buy_ton_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_ton_start, pattern="^buy:ton$")],
        states={
            BUY_WAIT_DIAMOND_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_ton_receive_count)],
        },
        fallbacks=[
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۵. مکالمه ثبت کد هدیه
    gift_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(gift_code_start, pattern="^enter_gift_code$")],
        states={
            GIFT_WAIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift_code_receive)],
        },
        fallbacks=[
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۵.۵ مکالمه انتقال الماس بین کاربران با آیدی عددی
    transfer_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(transfer_diamonds_start, pattern="^menu:transfer_diamonds$")],
        states={
            TRANSFER_WAIT_TARGET_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_receive_target_id)],
            TRANSFER_WAIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_receive_amount)],
        },
        fallbacks=[
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۶. مکالمه پنل مدیریت ۴۰ قابلیته (شامل بکاپ کامل، بازگردانی بکاپ و مدیریت انتقال الماس)
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_router_callback, pattern="^adm:")],
        states={
            ADM_WAIT_GENERIC: [MessageHandler(filters.ALL & ~filters.COMMAND, admin_handle_generic_input)],
            ADM_WAIT_FORWARD_USER: [MessageHandler(filters.ALL & ~filters.COMMAND, admin_receive_forwarded_user)],
            ADM_WAIT_FORWARD_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_forward_diamond_delta)],
            ADM_WAIT_FCH_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_fch_step1)],
            ADM_WAIT_FCH_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_fch_step2)],
            ADM_WAIT_FCH_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_fch_step3)],
            ADM_WAIT_RESTORE_FILE: [MessageHandler(filters.ALL & ~filters.COMMAND, admin_receive_restore_file)],
        },
        fallbacks=[
            CallbackQueryHandler(admin_page_callback, pattern="^admin:page:"),
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    app.add_handler(self_login_conv)
    app.add_handler(feat_val_conv)
    app.add_handler(tabchi_conv)
    app.add_handler(buy_ton_conv)
    app.add_handler(gift_conv)
    app.add_handler(transfer_conv)
    app.add_handler(admin_conv)
    app.add_handler(CommandHandler("start", start_cmd))

    app.add_handler(CallbackQueryHandler(activate_self_code_keypad_callback, pattern="^codepad:"))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(stop_self_now_callback, pattern="^self:stop_now$"))
    app.add_handler(CallbackQueryHandler(self_features_callbacks, pattern="^(self:features_page:|ftoggle:|fbulk:)"))
    app.add_handler(CallbackQueryHandler(tabchi_menu_callback, pattern="^(menu:tabchi|tabchi:)"))
    app.add_handler(CallbackQueryHandler(ton_paid_user_confirm_callback, pattern="^tonpaid:"))
    app.add_handler(CallbackQueryHandler(admin_ton_order_action_callback, pattern="^tonadm:"))
    app.add_handler(CallbackQueryHandler(admin_page_callback, pattern="^admin:page:"))
    app.add_handler(CallbackQueryHandler(admin_remove_fch_callback, pattern="^rmfch:"))
    app.add_handler(CallbackQueryHandler(menu_router_callback, pattern="^(menu:|buy:rial)"))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="^noop$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_pending_login_text_handler))

    logger.info("🌑 ربات سلف دارک (Self Dark) با ۴۰ قابلیت سلف، تبچی هوشمند و پینگر ۵ دقیقه‌ای Render آماده به کار است.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
