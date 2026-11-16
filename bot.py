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
import math
import random
import secrets
from flask import Flask, jsonify
from datetime import datetime, timedelta, timezone
from contextlib import closing

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
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

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8649807066:AAGZlazLVFr-jWDz8BURuFSP2K7WNRmRh-4")
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
    # قابلیت‌های پیشرفته اضافه شده به بخش قابلیت‌های سلف (با پنل مرکزی به عنوان آخرین قابلیت)
    "f41": {"title": "۴۱. کامنت اول خودکار کانال (با تنظیم کامنت اول)", "type": "toggle_val", "val_key": "first_comment_word", "val_label": "کلمه کامنت اول (زیر آن به انگلیسی Self Dark نوشته می‌شود)", "default_val": "کامنت اول"},
    "f42": {"title": "۴۲. عضویت اجباری پیوی (حداکثر ۳ کانال)", "type": "toggle_panel", "panel_cb": "pvforce:menu", "desc": "حذف سریع پیام پیوی افراد عضو نشده و ارسال دکمه‌های شیشه‌ای کانال‌ها"},
    "f43": {"title": "۴۳. ساخت قرعه‌کشی برای کانال", "type": "action_only", "action_cb": "lotto:start", "style": "success", "emoji_key": "gift"},
    "f44": {"title": "۴۴. ساخت دکمه شیشه‌ای برای کانال", "type": "action_only", "action_cb": "chbtn:start", "style": "primary", "emoji_key": "sparkles"},
    "f45": {"title": "۴۵. ساخت چالش لایکی برای کانال", "type": "action_only", "action_cb": "likechal:start", "style": "danger", "emoji_key": "heart"},
    "f46": {"title": "۴۶. پنل مرکزی (گزارش ۲۴ ساعت گذشته اکانت)", "type": "action_only", "action_cb": "self:central_panel", "style": "primary", "emoji_key": "crown"},
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
                last_daily_gift TEXT DEFAULT NULL,
                welcome_gift_claimed INTEGER DEFAULT 0
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

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                admin_reply TEXT DEFAULT NULL,
                created_at TEXT NOT NULL,
                answered_at TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS self_activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                target_title TEXT DEFAULT '',
                detail TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS first_comment_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                chat_title TEXT DEFAULT 'گروه متصل به کانال',
                created_at TEXT NOT NULL,
                UNIQUE(user_id, chat_id)
            );

            CREATE TABLE IF NOT EXISTS pv_force_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id TEXT NOT NULL,
                channel_link TEXT NOT NULL,
                title TEXT DEFAULT 'کانال عضویت اجباری پیوی',
                UNIQUE(user_id, channel_id)
            );

            CREATE TABLE IF NOT EXISTS group_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                creator_id INTEGER NOT NULL,
                creator_name TEXT DEFAULT 'کاربر',
                bet_amount INTEGER NOT NULL,
                status TEXT DEFAULT 'waiting',
                opponent_id INTEGER DEFAULT NULL,
                opponent_name TEXT DEFAULT NULL,
                winner_id INTEGER DEFAULT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS channel_lotteries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                min_participants INTEGER DEFAULT 0,
                max_participants INTEGER DEFAULT 0,
                force_channels_json TEXT DEFAULT '[]',
                description TEXT DEFAULT '',
                duration_minutes INTEGER NOT NULL,
                winners_count INTEGER DEFAULT 1,
                target_channel TEXT NOT NULL,
                channel_message_id INTEGER DEFAULT NULL,
                status TEXT DEFAULT 'draft',
                end_time TEXT DEFAULT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lottery_participants (
                lottery_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                joined_at TEXT NOT NULL,
                PRIMARY KEY (lottery_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS pv_force_history (
                owner_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                msg_count INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (owner_id, sender_id)
            );

            CREATE TABLE IF NOT EXISTS like_challenge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                channel_id TEXT NOT NULL,
                channel_title TEXT DEFAULT '',
                participant_name TEXT NOT NULL,
                message_id INTEGER DEFAULT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS like_challenge_votes (
                item_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (item_id, user_id)
            );
        """)

        # ارتقای بدون خطای جداول برای دیتابیس‌های قبلی
        for col_sql in [
            "ALTER TABLE edited_cache ADD COLUMN is_deleted INTEGER DEFAULT 0",
            "ALTER TABLE edited_cache ADD COLUMN edited_text TEXT DEFAULT NULL",
            "ALTER TABLE edited_cache ADD COLUMN created_at TEXT DEFAULT NULL",
            "ALTER TABLE users ADD COLUMN welcome_gift_claimed INTEGER DEFAULT 0",
        ]:
            try:
                conn.execute(col_sql)
            except Exception:
                pass

        default_settings = {
            "ton_wallet": "UQD_YOUR_TON_WALLET_ADDRESS_HERE",
            "ton_per_diamond": "0.0005",
            "min_buy_diamonds": "50",
            "activation_cost": "30",
            "hourly_cost": "3",
            "referral_enabled": "1",
            "referral_reward": "5",
            "welcome_bonus": "60",
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

        # تنظیم پیش‌فرض ۶۰ الماس هدیه ورود اولیه
        wb_init = conn.execute("SELECT value FROM settings WHERE key='welcome_bonus_60_v1'").fetchone()
        if not wb_init:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('welcome_bonus', '60')")
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('welcome_bonus_60_v1', '1')")

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

def calc_transfer_fee(amount: int) -> tuple[int, int]:
    """محاسبه کارمزد ۱۰ درصد انتقال الماس (در ربات و در گروه) که از انتقال‌دهنده کسر می‌شود"""
    fee = max(1, int(math.ceil(amount * 0.10)))
    total_deduct = amount + fee
    return fee, total_deduct

def log_self_activity(user_id: int, action_type: str, target_title: str = "", detail: str = ""):
    """ثبت لحظه‌ای فعالیت‌های ۲۴ ساعت گذشته اکانت کاربر برای نمایش در پنل مرکزی سلف دارک"""
    try:
        now_iso = datetime.now().isoformat()
        cutoff_iso = (datetime.now() - timedelta(hours=36)).isoformat()
        with closing(get_conn()) as conn, conn:
            conn.execute(
                "INSERT INTO self_activity_logs (user_id, action_type, target_title, detail, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, action_type, (target_title or "")[:120], (detail or "")[:200], now_iso)
            )
            if random.random() < 0.05:
                conn.execute("DELETE FROM self_activity_logs WHERE created_at < ?", (cutoff_iso,))
    except Exception as e:
        logger.debug(f"Activity log error: {e}")

def get_or_create_user(user_id: int, username: str = "", first_name: str = "", invited_by: int = None):
    with closing(get_conn()) as conn, conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            valid_inv = invited_by if (invited_by and invited_by != user_id) else None
            conn.execute(
                """INSERT INTO users (user_id, username, first_name, joined_at, diamonds, invited_by, welcome_gift_claimed)
                   VALUES (?, ?, ?, ?, 0, ?, 0)""",
                (user_id, username or "", first_name or "کاربر", datetime.now().isoformat(), valid_inv)
            )
            user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        else:
            conn.execute(
                "UPDATE users SET username=?, first_name=? WHERE user_id=?",
                (username or "", first_name or "کاربر", user_id)
            )
        return user

def grant_first_entry_gift_if_eligible(user_id: int) -> int:
    """
    اعطای ۶۰ الماس هدیه ورود اولیه به هر کاربر (فقط یک‌بار):
    - اگر کانال جوین اجباری وجود داشته باشد: بلافاصله پس از عضویت و تایید عضویت اعطا می‌شود.
    - اگر کانال جوین اجباری وجود نداشته باشد: بلافاصله در اولین استارت اعطا می‌شود.
    """
    try:
        gift_amount = int(get_setting("welcome_bonus", "60"))
        if gift_amount <= 0:
            gift_amount = 60
    except Exception:
        gift_amount = 60

    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            "UPDATE users SET diamonds = diamonds + ?, welcome_gift_claimed = 1 WHERE user_id = ? AND COALESCE(welcome_gift_claimed, 0) = 0",
            (gift_amount, user_id)
        )
        if cur.rowcount > 0:
            return gift_amount
    return 0

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

async def ensure_botfather_inline_enabled(client: TelegramClient):
    """در صورتی که اکانت ادمین ربات متصل شود، حالت Inline ربات را در BotFather خودکار فعال می‌کند تا دکمه‌های شیشه‌ای در پیوی ارسال شوند"""
    if get_setting("botfather_inline_ready", "0") == "1":
        return
    if not BOT_APP_REF:
        return
    try:
        bot_me = await BOT_APP_REF.bot.get_me()
        try:
            await client.inline_query(bot_me.username, "pvforce_check")
            set_setting("botfather_inline_ready", "1")
            return
        except Exception as e:
            err_s = str(e)
            if "BotInlineDisabled" not in err_s and "INLINE_BOT_REQUIRED" not in err_s:
                return
        # ارسال خودکار دستور فعال‌سازی Inline به BotFather در صورت مالک بودن اکانت
        await client.send_message("BotFather", "/setinline")
        await asyncio.sleep(1.2)
        await client.send_message("BotFather", f"@{bot_me.username}")
        await asyncio.sleep(1.2)
        await client.send_message("BotFather", "عضویت اجباری پیوی سلف دارک")
        await asyncio.sleep(1.2)
        set_setting("botfather_inline_ready", "1")
    except Exception as e:
        logger.debug(f"BotFather inline auto-enable skipped: {e}")

async def send_pv_force_glass_warning(
    client: TelegramClient,
    user_id: int,
    sender_id: int,
    chat_id: int,
    not_joined_pv: list,
    is_first_ever_msg: bool,
    reply_to_msg_id: int = None,
):
    """
    ارسال پیام عضویت اجباری پیوی به صورت دکمه شیشه‌ای واقعی:
    - اگر اولین پیام کاربر باشد: پیامش حذف نمی‌شود و روی پیامش ریپلای زده می‌شود.
    - اگر پیام دوم به بعد یا از قبل پیام داده باشد: پیامش حذف شده و دکمه شیشه‌ای ارسال می‌گردد.
    """
    if not BOT_APP_REF:
        return
    bot_me = await BOT_APP_REF.bot.get_me()
    first_flag = "1" if is_first_ever_msg else "0"
    query_str = f"pvforce:{user_id}:{sender_id}:{first_flag}"

    # ۱. تلاش برای ارسال مستقیم دکمه‌های شیشه‌ای رنگی در داخل پیوی از طریق Inline ربات
    sent_inline = False
    for attempt in range(2):
        try:
            q_res = await client.inline_query(bot_me.username, query_str)
            if q_res:
                if is_first_ever_msg and reply_to_msg_id:
                    await q_res[0].click(chat_id, reply_to=reply_to_msg_id)
                else:
                    await q_res[0].click(chat_id)
                sent_inline = True
                break
        except Exception as e:
            if attempt == 0 and ("BotInlineDisabled" in str(e) or "INLINE_BOT_REQUIRED" in str(e)):
                adm_client = ACTIVE_SELF_CLIENTS.get(ADMIN_ID)
                if adm_client:
                    await ensure_botfather_inline_enabled(adm_client)
                    continue
            sent_inline = False
            break

    # ۲. ساخت کیبورد شیشه‌ای رنگی برای ارسال از طریق ربات و پشتیبان
    pv_rows = [
        [p_btn(f"📢 عضویت در {c['title']}", url=c["channel_link"], style="primary", emoji_key="megaphone")]
        for c in not_joined_pv
    ]
    pv_rows.append([
        p_btn("✅ بررسی عضویت و باز کردن قفل پیوی", callback_data=f"pvcheck:{user_id}", style="success", emoji_key="check")
    ])

    if is_first_ever_msg:
        warn_html = p_text(
            "⚠️ <b>قفل عضویت اجباری پیوی فعال است!</b>\n\n"
            "👋 این اولین پیام شماست (پیام اول شما حذف نشد)؛ اما برای اینکه بتوانید ادامه دهید و پیام‌های بعدی شما پاک نشود، باید ابتدا از طریق <b>دکمه‌های شیشه‌ای زیر</b> در کانال‌ها عضو شوید و دکمه <b>«✅ بررسی عضویت»</b> را بزنید:"
        )
    else:
        warn_html = p_text(
            "🚫 <b>پیام شما حذف شد! (قفل عضویت اجباری پیوی)</b>\n\n"
            "⚠️ برای پیام دادن به این کاربر ابتدا باید در کانال‌های زیر عضو شوید و سپس روی دکمه شیشه‌ای <b>«✅ بررسی عضویت»</b> کلیک کنید:"
        )

    # ارسال دکمه‌های شیشه‌ای از طریق خود ربات به پیوی شخص (اگر ربات را استارت کرده باشد)
    if not sent_inline:
        try:
            await BOT_APP_REF.bot.send_message(
                chat_id=sender_id,
                text=warn_html,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(pv_rows)
            )
        except Exception:
            pass

        # ارسال در پیوی شخص (با ریپلای روی پیام اول، یا ارسال مستقیم پس از حذف پیام دوم)
        ch_lines = "\n".join([
            f"🔹 <a href=\"{html.escape(c['channel_link'])}\">📢 عضویت در کانال {html.escape(c['title'])}</a>"
            for c in not_joined_pv
        ])
        verify_url = f"https://t.me/{bot_me.username}?start=pvcheck_{user_id}"
        if is_first_ever_msg:
            fallback_txt = (
                f"⚠️ <b>برای پیام دادن به من ابتدا باید در کانال‌های زیر عضو شوی:</b>\n\n"
                f"{ch_lines}\n\n"
                f"👇 <b>سپس روی دکمه زیر کلیک کن تا دکمه‌های شیشه‌ای بررسی عضویت برایت باز شود:</b>\n"
                f"💎 <a href=\"{verify_url}\">【 ✅ بررسی عضویت و باز کردن قفل پیوی 】</a>"
            )
            await client.send_message(
                chat_id,
                fallback_txt,
                reply_to=reply_to_msg_id,
                parse_mode="html",
                link_preview=False
            )
        else:
            fallback_txt = (
                f"🚫 <b>پیام شما پاک شد! ابتدا باید در کانال‌های زیر عضو شوی:</b>\n\n"
                f"{ch_lines}\n\n"
                f"💎 <a href=\"{verify_url}\">【 ✅ بررسی عضویت با دکمه شیشه‌ای 】</a>"
            )
            await client.send_message(
                chat_id,
                fallback_txt,
                parse_mode="html",
                link_preview=False
            )

async def setup_telethon_handlers(user_id: int, client: TelegramClient):
    """ثبت کامل تمامی ۴۵ قابلیت سلف دارک و دستورات تبچی هوشمند روی کلاینت Telethon کاربر"""

    # رویداد حذف پیام (قابلیت ۱۱: ذخیره بی‌صدای پیام‌های حذف‌شده بدون ارسال در Saved Messages)
    @client.on(events.MessageDeleted)
    async def on_message_deleted(event):
        feats = get_user_features(user_id)
        if not feats.get("f11"):
            return
        deleted_ids = getattr(event, "deleted_ids", []) or []
        if not deleted_ids:
            return
        with closing(get_conn()) as conn, conn:
            for mid in deleted_ids:
                conn.execute(
                    "UPDATE edited_cache SET is_deleted=1 WHERE user_id=? AND msg_id=?",
                    (user_id, mid)
                )

    # رویداد ویرایش پیام (قابلیت ۱۲: ذخیره بی‌صدای تاریخچه ویرایش پیام‌ها بدون ارسال در Saved Messages)
    @client.on(events.MessageEdited)
    async def on_message_edited(event):
        if event.out or not event.raw_text:
            return
        feats = get_user_features(user_id)
        if not feats.get("f12"):
            return
        with closing(get_conn()) as conn, conn:
            conn.execute(
                "UPDATE edited_cache SET edited_text=? WHERE user_id=? AND chat_id=? AND msg_id=?",
                (event.raw_text[:800], user_id, event.chat_id, event.id)
            )

    # رویداد ورود عضو جدید به گروه (قابلیت ۳۶: خوش‌آمدگویی خودکار در گروه‌ها)
    @client.on(events.ChatAction)
    async def on_group_chat_action(event):
        if not (event.user_joined or event.user_added):
            return
        feats = get_user_features(user_id)
        if not feats.get("f36"):
            return
        welcome_msg = str(feats.get("welcome_text", "خوش آمدی عزیز به گروه! 🌺")).strip()
        if welcome_msg:
            try:
                await event.reply(welcome_msg)
            except Exception:
                pass

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
                    """INSERT OR REPLACE INTO edited_cache
                       (user_id, chat_id, msg_id, sender_name, text_content, is_deleted, edited_text, created_at)
                       VALUES (?, ?, ?, ?, ?, 0, NULL, ?)""",
                    (user_id, event.chat_id, event.id, sname, event.raw_text[:800], datetime.now().isoformat())
                )

        # دستورات خروجی صاحب اکانت (Outgoing Self Dark Commands)
        if event.out and event.raw_text:
            txt = event.raw_text.strip()

            # ثبت فعالیت‌های ۲۴ ساعت گذشته کاربر برای «پنل مرکزی»
            try:
                if event.is_group:
                    chat_obj = await event.get_chat()
                    g_title = getattr(chat_obj, "title", "گروه") or "گروه"
                    log_self_activity(user_id, "group_msg_out", g_title, txt[:80])
                elif event.is_private:
                    chat_obj = await event.get_chat()
                    if getattr(chat_obj, "bot", False):
                        b_name = getattr(chat_obj, "first_name", "") or "ربات"
                        b_user = getattr(chat_obj, "username", "")
                        b_label = f"{b_name} (@{b_user})" if b_user else b_name
                        if txt.startswith("/start"):
                            log_self_activity(user_id, "bot_start", b_label, txt[:80])
                        else:
                            log_self_activity(user_id, "bot_msg_out", b_label, txt[:80])
                    else:
                        p_name = getattr(chat_obj, "first_name", "") or "مخاطب"
                        log_self_activity(user_id, "pv_msg_out", p_name, txt[:80])
            except Exception:
                pass

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
                    log_self_activity(user_id, "self_cmd", "تنظیم ساعت زنده", f"{hh:02d}:{mm:02d}")
                    await event.edit(f"⏰ <b>ساعت پروفایل با ساعت دستگاه شما (<code>{hh:02d}:{mm:02d}</code>) تنظیم و فعال شد!</b>\nاز این پس هر دقیقه به‌صورت دقیق بروزرسانی می‌شود.", parse_mode="html")
                    return

            # دستور فعال‌سازی «کامنت اول» در گروه متصل به کانال: «تنظیم کامنت اول»
            if txt == "تنظیم کامنت اول" and (event.is_group or event.is_channel):
                chat = await event.get_chat()
                title = getattr(chat, "title", "گروه متصل به کانال")
                with closing(get_conn()) as conn, conn:
                    conn.execute(
                        """INSERT OR REPLACE INTO first_comment_groups (user_id, chat_id, chat_title, created_at)
                           VALUES (?, ?, ?, ?)""",
                        (user_id, event.chat_id, title, datetime.now().isoformat())
                    )
                feats["f41"] = True
                save_user_features(user_id, feats)
                fc_word = feats.get("first_comment_word", "کامنت اول")
                log_self_activity(user_id, "self_cmd", "تنظیم کامنت اول", title)
                await event.edit(
                    f"🥇 <b>گروه «{html.escape(title)}» با موفقیت برای قابلیت کامنت اول ثبت شد!</b>\n"
                    f"✨ متن کامنت اول فعلی: <b>{html.escape(fc_word)}</b> (با امضای <code>Self Dark</code>)\n"
                    f"📌 به محض ارسال پست جدید در کانال متصل به این گروه، کامنت اول به صورت خودکار ثبت می‌شود.",
                    parse_mode="html"
                )
                return

            if txt == "حذف کامنت اول" and (event.is_group or event.is_channel):
                with closing(get_conn()) as conn, conn:
                    conn.execute("DELETE FROM first_comment_groups WHERE user_id=? AND chat_id=?", (user_id, event.chat_id))
                await event.edit("🗑 <b>قابلیت کامنت اول برای این گروه غیرفعال و حذف شد.</b>", parse_mode="html")
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
                log_self_activity(user_id, "self_cmd", "ثبت گروه تبچی", title)
                await event.edit(f"✅ <b>گروه «{html.escape(title)}» با موفقیت در تبچی هوشمند سلف دارک ثبت شد!</b>\n⚙️ از داخل ربات سلف دارک می‌توانید بنر و زمان ارسال آن را مدیریت کنید.", parse_mode="html")
                return

            if txt == "حذف چت" and (event.is_group or event.is_channel):
                with closing(get_conn()) as conn, conn:
                    conn.execute("DELETE FROM tabchi_groups WHERE user_id=? AND chat_id=?", (user_id, event.chat_id))
                await event.edit("🗑 <b>این گروه از لیست تبچی سلف دارک حذف شد.</b>", parse_mode="html")
                return

            # ۲ و ۲۲. دستیار هوش مصنوعی (.ai) و حافظه اختصاصی هوش مصنوعی (.aiclear)
            if feats.get("f2"):
                if txt == ".aiclear":
                    feats["ai_history"] = []
                    save_user_features(user_id, feats)
                    await event.edit("🧠 <b>حافظه اختصاصی هوش مصنوعی سلف دارک پاکسازی شد.</b>", parse_mode="html")
                    return
                if txt.startswith(".ai"):
                    prompt = txt[3:].strip()
                    if not prompt and event.is_reply:
                        rep = await event.get_reply_message()
                        prompt = (rep.raw_text or "").strip() if rep else ""
                    if not prompt:
                        await event.edit("🤖 لطفاً سوال خود را بعد از <code>.ai</code> بنویسید (مثال: <code>.ai خلاصه هوش مصنوعی چیست؟</code>)", parse_mode="html")
                        return
                    await event.edit("🤖 <i>در حال پردازش پاسخ هوشمند سلف دارک...</i>", parse_mode="html")
                    history = feats.get("ai_history", []) if feats.get("f22") else []
                    context_prefix = ""
                    if feats.get("f22") and history:
                        context_prefix = "سابقه گفتگو:\n" + "\n".join(history[-3:]) + "\n\nسوال جدید: "
                    full_q = context_prefix + prompt
                    ai_ans = None
                    try:
                        resp = requests.get(
                            f"https://text.pollinations.ai/{requests.utils.quote(full_q)}",
                            timeout=12
                        )
                        if resp.status_code == 200 and resp.text.strip():
                            ai_ans = resp.text.strip()[:1200]
                    except Exception:
                        ai_ans = None
                    if not ai_ans:
                        ai_ans = f"پاسخ هوشمند به «{prompt[:60]}»: درخواست شما ثبت و بررسی شد."
                    if feats.get("f22"):
                        history.append(f"کاربر: {prompt[:80]} | پاسخ: {ai_ans[:120]}")
                        feats["ai_history"] = history[-6:]
                        save_user_features(user_id, feats)
                    log_self_activity(user_id, "self_cmd", ".ai", prompt[:50])
                    await event.edit(f"🤖 <b>پاسخ هوش مصنوعی سلف دارک:</b>\n\n{html.escape(ai_ans)}", parse_mode="html")
                    return

            # ۵. زمان‌بندی و مدیریت سریع عکس پروفایل (.setpic / .delpic)
            if feats.get("f5"):
                if txt == ".setpic" and event.is_reply:
                    rep = await event.get_reply_message()
                    if rep and rep.photo:
                        await event.edit("⏳ <i>در حال تنظیم عکس جدید روی پروفایل...</i>", parse_mode="html")
                        try:
                            path = await client.download_media(rep.photo)
                            uploaded = await client.upload_file(path)
                            await client(functions.photos.UploadProfilePhotoRequest(file=uploaded))
                            if path and os.path.exists(path):
                                os.remove(path)
                            await event.edit("✅ <b>عکس پروفایل شما با موفقیت بروزرسانی شد!</b>", parse_mode="html")
                        except Exception as e:
                            await event.edit(f"❌ خطا در تغییر عکس پروفایل: <code>{html.escape(str(e)[:80])}</code>", parse_mode="html")
                        return
                elif txt == ".delpic":
                    try:
                        photos = await client.get_profile_photos("me", limit=1)
                        if photos:
                            await client(functions.photos.DeletePhotosRequest(id=[types.InputPhoto(
                                id=photos[0].id,
                                access_hash=photos[0].access_hash,
                                file_reference=photos[0].file_reference
                            )]))
                            await event.edit("🗑 <b>آخرین عکس پروفایل شما حذف شد.</b>", parse_mode="html")
                        else:
                            await event.edit("⚠️ عکس پروفایلی برای حذف یافت نشد.")
                    except Exception:
                        await event.edit("⚠️ خطا در حذف عکس پروفایل.")
                    return

            # ۸. تبدیل ویس به متن (.v2t یا «تبدیل به متن» با ریپلای روی ویس/ویدیومسیج)
            if feats.get("f8") and (txt in (".v2t", "تبدیل به متن", ".متن") or txt.startswith(".v2t ")) and event.is_reply:
                rep = await event.get_reply_message()
                if not rep or not (rep.voice or rep.audio or rep.video_note):
                    await event.edit("⚠️ لطفاً روی یک <b>پیام صوتی (ویس)</b> یا <b>ویدیومسیج</b> ریپلای کنید و دستور <code>.v2t</code> یا <code>تبدیل به متن</code> را بفرستید!", parse_mode="html")
                    return
                await event.edit("🎙 <i>در حال تبدیل ویس به متن توسط سلف دارک...</i>", parse_mode="html")
                log_self_activity(user_id, "self_cmd", "تبدیل ویس به متن", ".v2t")
                transcribed_txt = None
                try:
                    res_tr = await client(functions.messages.TranscribeAudioRequest(
                        peer=event.chat_id,
                        msg_id=rep.id
                    ))
                    transcribed_txt = getattr(res_tr, "text", "") or ""
                    if getattr(res_tr, "pending", False) and not transcribed_txt:
                        await asyncio.sleep(2.5)
                        res_tr2 = await client(functions.messages.TranscribeAudioRequest(
                            peer=event.chat_id,
                            msg_id=rep.id
                        ))
                        transcribed_txt = getattr(res_tr2, "text", "") or ""
                except Exception as e:
                    logger.debug(f"Telegram native transcribe fallback: {e}")

                if transcribed_txt:
                    await event.edit(
                        f"🎙 <b>متن استخراج‌شده از ویس (سلف دارک):</b>\n\n"
                        f"<blockquote>{html.escape(transcribed_txt)}</blockquote>",
                        parse_mode="html"
                    )
                else:
                    dur = 0
                    try:
                        for attr in getattr(rep.media.document, "attributes", []):
                            if hasattr(attr, "duration"):
                                dur = int(attr.duration)
                    except Exception:
                        pass
                    await event.edit(
                        f"🎙 <b>پردازش پیام صوتی ({dur} ثانیه):</b>\n"
                        f"ℹ️ برای تبدیل مستقیم صوت به متن در سرور تلگرام، اکانت تلگرام یا سرور تشخیص گفتار پردازش را انجام داد (در صورت واضح نبودن صدا، دوباره <code>.v2t</code> بزنید).",
                        parse_mode="html"
                    )
                return

            # ۱۰. دسته‌بندی هوشمند پیام‌ها و گفتگوها (.cats یا .دسته بندی)
            if feats.get("f10") and txt in (".cats", ".دسته بندی", ".دسته‌بندی"):
                await event.edit("📂 <i>در حال آنالیز و دسته‌بندی هوشمند گفتگوهای اکانت...</i>", parse_mode="html")
                pvs, grps, chs, bots_c, unread_c = 0, 0, 0, 0, 0
                async for d in client.iter_dialogs(limit=200):
                    if d.unread_count > 0:
                        unread_c += 1
                    if d.is_user:
                        if getattr(d.entity, "bot", False):
                            bots_c += 1
                        else:
                            pvs += 1
                    elif d.is_group:
                        grps += 1
                    elif d.is_channel:
                        chs += 1
                await event.edit(
                    f"📂 <b>دسته‌بندی هوشمند گفتگوهای اکانت شما:</b>\n\n"
                    f"👤 گفتگوهای شخصی (پیوی): <b>{pvs} چت</b>\n"
                    f"👥 گروه‌ها و سوپرگروه‌ها: <b>{grps} گروه</b>\n"
                    f"📢 کانال‌ها: <b>{chs} کانال</b>\n"
                    f"🤖 ربات‌ها: <b>{bots_c} ربات</b>\n"
                    f"🔔 گفتگوهای دارای پیام خوانده‌نشده: <b>{unread_c} گفتگو</b>",
                    parse_mode="html"
                )
                return

            # ۱۱. مشاهده پیام‌های حذف‌شده (.حذفیات یا .deleted)
            if feats.get("f11") and txt in (".حذفیات", ".deleted"):
                with closing(get_conn()) as conn:
                    rows = conn.execute(
                        "SELECT * FROM edited_cache WHERE user_id=? AND is_deleted=1 ORDER BY rowid DESC LIMIT 10",
                        (user_id,)
                    ).fetchall()
                    if not rows:
                        rows = conn.execute(
                            "SELECT * FROM edited_cache WHERE user_id=? AND chat_id=? ORDER BY rowid DESC LIMIT 8",
                            (user_id, event.chat_id)
                        ).fetchall()
                if not rows:
                    await event.edit("🗑 <b>هنوز هیچ پیام حذف‌شده‌ای در دیتابیس ثبت نشده است.</b>", parse_mode="html")
                else:
                    lines = ["🗑 <b>آخرین پیام‌های ذخیره‌شده / حذف‌شده (سلف دارک):</b>\n"]
                    for r in rows:
                        st_tag = " [حذف‌شده]" if r["is_deleted"] else ""
                        lines.append(f"👤 <b>{html.escape(r['sender_name'] or 'کاربر')}</b>{st_tag}: <code>{html.escape(r['text_content'][:120])}</code>")
                    await event.edit("\n".join(lines), parse_mode="html")
                return

            # ۱۲. مشاهده تاریخچه ویرایش پیام‌ها (.ویرایشها یا .edits)
            if feats.get("f12") and txt in (".ویرایشها", ".edits"):
                with closing(get_conn()) as conn:
                    rows = conn.execute(
                        "SELECT * FROM edited_cache WHERE user_id=? AND edited_text IS NOT NULL ORDER BY rowid DESC LIMIT 10",
                        (user_id,)
                    ).fetchall()
                if not rows:
                    await event.edit("✏️ <b>هنوز پیام ویرایش‌شده‌ای در دیتابیس ثبت نشده است.</b>", parse_mode="html")
                else:
                    lines = ["✏️ <b>تاریخچه پیام‌های ویرایش‌شده (سلف دارک):</b>\n"]
                    for r in rows:
                        lines.append(
                            f"👤 <b>{html.escape(r['sender_name'] or 'کاربر')}</b>:\n"
                            f"   🔴 قبل: <code>{html.escape(r['text_content'][:100])}</code>\n"
                            f"   🟢 بعد: <code>{html.escape((r['edited_text'] or '')[:100])}</code>"
                        )
                    await event.edit("\n".join(lines), parse_mode="html")
                return

            # ۱۳. پشتیبان‌گیری از گفتگوها (.backup)
            if feats.get("f13") and txt.startswith(".backup"):
                parts = txt.split()
                lim = int(parts[1]) if (len(parts) > 1 and parts[1].isdigit()) else 100
                lim = min(max(10, lim), 500)
                await event.edit(f"📦 <i>در حال تهیه نسخه پشتیبان از {lim} پیام آخر این گفتگو...</i>", parse_mode="html")
                dump_lines = [f"=== نسخه پشتیبان گفتگوی {event.chat_id} | سلف دارک ===\n"]
                async for m in client.iter_messages(event.chat_id, limit=lim):
                    dt_s = m.date.strftime("%Y-%m-%d %H:%M:%S") if m.date else ""
                    txt_m = (m.raw_text or "[مدیا/فایل]").replace("\n", " ")
                    dump_lines.append(f"[{dt_s}] ({m.sender_id}): {txt_m}")
                bio_bytes = "\n".join(dump_lines).encode("utf-8")
                f_obj = io.BytesIO(bio_bytes)
                f_obj.name = f"chat_backup_{abs(event.chat_id)}.txt"
                await client.send_file(
                    event.chat_id,
                    f_obj,
                    caption=f"📦 <b>فایل پشتیبان این گفتگو ({len(dump_lines)-1} پیام) آماده شد.</b>",
                    parse_mode="html"
                )
                await event.delete()
                return

            # ۱۴. جستجوی پیشرفته پیام‌ها (.find)
            if feats.get("f14") and txt.startswith(".find "):
                q_word = txt[6:].strip()
                if not q_word:
                    await event.edit("🔍 لطفاً کلمه مورد نظر را بعد از <code>.find</code> بنویسید.", parse_mode="html")
                    return
                found = []
                async for m in client.iter_messages(event.chat_id, search=q_word, limit=10):
                    dt_s = m.date.strftime("%m-%d %H:%M") if m.date else ""
                    snippet = (m.raw_text or "")[:90].replace("\n", " ")
                    found.append(f"• <code>{dt_s}</code> (ID: <code>{m.id}</code>): {html.escape(snippet)}")
                if not found:
                    await event.edit(f"🔍 هیچ پیامی حاوی عبارت «<b>{html.escape(q_word)}</b>» در این چت یافت نشد.", parse_mode="html")
                else:
                    await event.edit(
                        f"🔍 <b>نتایج جستجو برای «{html.escape(q_word)}» ({len(found)} مورد):</b>\n\n" + "\n".join(found),
                        parse_mode="html"
                    )
                return

            # ۱۵. بایگانی خودکار گفتگوها (.archive / .unarchive)
            if feats.get("f15") and txt in (".archive", ".unarchive"):
                folder_id = 1 if txt == ".archive" else 0
                try:
                    await client.edit_folder(event.chat_id, folder_id)
                    msg_s = "📥 این گفتگو به پوشه <b>بایگانی (Archive)</b> منتقل شد." if folder_id == 1 else "📤 این گفتگو از پوشه بایگانی خارج شد."
                    await event.edit(msg_s, parse_mode="html")
                except Exception:
                    await event.edit("⚠️ خطا در تغییر وضعیت بایگانی گفتگو.")
                return

            # ۱۸. یادآوری پیام‌ها (.rem [دقیقه] [متن])
            if feats.get("f18") and txt.startswith(".rem "):
                parts = txt.split(" ", 2)
                if len(parts) < 3 or not normalize_digits(parts[1]).isdigit():
                    await event.edit("⏰ فرمت صحیح یادآور: <code>.rem 10 تماس با مشتری</code> (برحسب دقیقه)", parse_mode="html")
                    return
                mins = int(normalize_digits(parts[1]))
                rem_text = parts[2].strip()
                await event.edit(f"⏰ <b>یادآور ثبت شد!</b>\n🔔 تا <b>{mins} دقیقه دیگر</b> یادآوری می‌شود: <code>{html.escape(rem_text)}</code>", parse_mode="html")
                async def _remind_later(cid, r_txt, m_wait):
                    await asyncio.sleep(m_wait * 60)
                    try:
                        await client.send_message(cid, f"🔔 <b>یادآوری سلف دارک (پس از {m_wait} دقیقه):</b>\n\n📌 {html.escape(r_txt)}", parse_mode="html")
                    except Exception:
                        pass
                asyncio.create_task(_remind_later(event.chat_id, rem_text, mins))
                return

            # ۱۹. دستورات سریع اختصاصی (.ping, .id, .info)
            if feats.get("f19", True):
                if txt == ".ping":
                    t0 = time.time()
                    await event.edit("🌑 Pong...")
                    ms = int((time.time() - t0) * 1000)
                    log_self_activity(user_id, "self_cmd", ".ping", f"{ms}ms")
                    await event.edit(f"🌑 <b>Self Dark Online!</b>\n⚡ سرعت پاسخ: <code>{ms}ms</code>", parse_mode="html")
                    return
                elif txt == ".id":
                    if event.is_reply:
                        rep = await event.get_reply_message()
                        await event.edit(f"🔢 آیدی کاربر: <code>{rep.sender_id}</code>\n💬 آیدی چت: <code>{event.chat_id}</code>", parse_mode="html")
                    else:
                        await event.edit(f"💬 آیدی چت: <code>{event.chat_id}</code>", parse_mode="html")
                    return
                elif txt == ".info":
                    target_entity = None
                    if event.is_reply:
                        rep = await event.get_reply_message()
                        target_entity = await rep.get_sender()
                    else:
                        target_entity = await client.get_me()
                    if target_entity:
                        fn = getattr(target_entity, "first_name", "") or "کاربر"
                        ln = getattr(target_entity, "last_name", "") or ""
                        un = getattr(target_entity, "username", "") or "ندارد"
                        uid_t = getattr(target_entity, "id", 0)
                        await event.edit(
                            f"👤 <b>مشخصات کاربر (سلف دارک):</b>\n"
                            f"• نام: <b>{html.escape((fn + ' ' + ln).strip())}</b>\n"
                            f"• یوزرنیم: @{html.escape(un)}\n"
                            f"• آیدی عددی: <code>{uid_t}</code>",
                            parse_mode="html"
                        )
                    return

            # ۲۰. مدیریت اکانت و وضعیت نشست (.session / .اکانت)
            if feats.get("f20") and txt in (".session", ".اکانت"):
                acc = get_self_account(user_id)
                me = await client.get_me()
                await event.edit(
                    f"📱 <b>وضعیت نشست اکانت در سلف دارک:</b>\n\n"
                    f"👤 نام اکانت: <b>{html.escape(getattr(me, 'first_name', '') or '')}</b>\n"
                    f"🔢 آیدی عددی: <code>{user_id}</code>\n"
                    f"📞 شماره متصل: <code>{acc['phone'] if acc else 'نامشخص'}</code>\n"
                    f"🟢 وضعیت موتور سلف: <b>فعال و متصل (24/7)</b>",
                    parse_mode="html"
                )
                return

            # ۲۳. پیشنهاد خودکار استیکر و ایموجی متحرک (.تبریک / .عشق / .خنده / .اتش)
            if feats.get("f23"):
                emo_map = {
                    ".تبریک": "🎉🥳🎊✨",
                    ".عشق": "❤️🔥🌹💖",
                    ".خنده": "😂🤣😆✨",
                    ".اتش": "🔥⚡💥🌑",
                }
                if txt in emo_map:
                    await event.edit(emo_map[txt])
                    return

            # ۲۷ و ۴۵. گزارش فعالیت روزانه (.report / .گزارش) و پنل مرکزی ۲۴ ساعته (.پنل مرکزی)
            if (feats.get("f27") and txt in (".report", ".گزارش")) or txt == ".پنل مرکزی":
                cutoff_iso = (datetime.now() - timedelta(hours=24)).isoformat()
                with closing(get_conn()) as conn:
                    logs_24 = conn.execute(
                        "SELECT action_type, COUNT(*) c FROM self_activity_logs WHERE user_id=? AND created_at >= ? GROUP BY action_type",
                        (user_id, cutoff_iso)
                    ).fetchall()
                counts_map = {r["action_type"]: r["c"] for r in logs_24}
                await event.edit(
                    f"👑 <b>گزارش ۲۴ ساعت گذشته پنل مرکزی سلف دارک:</b>\n\n"
                    f"💬 پیام‌های ارسالی در گروه‌ها: <b>{counts_map.get('group_msg_out', 0)}</b>\n"
                    f"📤 پیام‌های ارسالی در پیوی: <b>{counts_map.get('pv_msg_out', 0)}</b>\n"
                    f"📥 پیام‌های دریافتی در پیوی: <b>{counts_map.get('pv_msg_in', 0)}</b>\n"
                    f"🤖 استارت کردن ربات‌ها: <b>{counts_map.get('bot_start', 0)}</b>\n"
                    f"🥇 کامنت‌های اول ثبت‌شده: <b>{counts_map.get('first_comment', 0)}</b>\n"
                    f"🛡 مسدودسازی عضویت اجباری پیوی: <b>{counts_map.get('pv_force_block', 0)}</b>",
                    parse_mode="html"
                )
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

            # ۲۹. ارسال زمان‌بندی‌شده پیام‌ها (.later [دقیقه] [متن])
            if feats.get("f29") and txt.startswith(".later "):
                parts = txt.split(" ", 2)
                if len(parts) < 3 or not normalize_digits(parts[1]).isdigit():
                    await event.edit("⏳ فرمت صحیح ارسال تاخیری: <code>.later 5 سلام وقت بخیر</code>", parse_mode="html")
                    return
                delay_m = int(normalize_digits(parts[1]))
                msg_body = parts[2].strip()
                await event.delete()
                async def _send_delayed(cid, text_to_send, wait_m):
                    await asyncio.sleep(wait_m * 60)
                    try:
                        await client.send_message(cid, text_to_send)
                    except Exception:
                        pass
                asyncio.create_task(_send_delayed(event.chat_id, msg_body, delay_m))
                return

            # ۳۰. مدیریت هوشمند اعلان‌ها (.mute / .unmute)
            if feats.get("f30") and txt in (".mute", ".unmute"):
                until_ts = 2147483647 if txt == ".mute" else 0
                try:
                    await client(functions.account.UpdateNotifySettingsRequest(
                        peer=types.InputNotifyPeer(peer=await client.get_input_entity(event.chat_id)),
                        settings=types.InputPeerNotifySettings(mute_until=until_ts)
                    ))
                    await event.edit("🔕 اعلان‌های این چت بی‌صدا (Mute) شد." if txt == ".mute" else "🔔 اعلان‌های این چت صدادار (Unmute) شد.")
                except Exception:
                    await event.edit("⚠️ خطا در تغییر وضعیت اعلان چت.")
                return

            # ۳۳. دانلود مدیاهای تایمردار و یک‌بار مصرف (.dl با ریپلای)
            if feats.get("f33") and txt == ".dl" and event.is_reply:
                rep = await event.get_reply_message()
                if rep and rep.media:
                    await event.edit("📥 <i>در حال دانلود و ذخیره مدیا...</i>", parse_mode="html")
                    try:
                        path = await client.download_media(rep.media)
                        if path:
                            await client.send_file("me", path, caption=f"📥 دانلود شده توسط سلف دارک از چت <code>{event.chat_id}</code>", parse_mode="html")
                            if os.path.exists(path):
                                os.remove(path)
                            await event.delete()
                            return
                    except Exception as e:
                        await event.edit(f"❌ خطا در دانلود مدیا: <code>{html.escape(str(e)[:60])}</code>", parse_mode="html")
                        return

            # ۳۵. قفل پیوی / منشی هوشمند (.lockpv / .unlockpv)
            if txt in (".lockpv", ".unlockpv"):
                feats["f35"] = (txt == ".lockpv")
                save_user_features(user_id, feats)
                await event.edit(
                    "🔒 <b>قفل پیوی (منشی هوشمند) فعال شد!</b>" if feats["f35"] else "🔓 <b>قفل پیوی باز شد.</b>",
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

            # ۳۹. مشاهده لیست تگ‌ها و منشن‌ها (.mentions)
            if feats.get("f39") and txt == ".mentions":
                with closing(get_conn()) as conn:
                    m_rows = conn.execute(
                        "SELECT * FROM self_activity_logs WHERE user_id=? AND action_type='mention_in' ORDER BY id DESC LIMIT 10",
                        (user_id,)
                    ).fetchall()
                if not m_rows:
                    await event.edit("🔔 <b>هنوز هیچ منشن یا تگی در گروه‌ها برای شما ثبت نشده است.</b>", parse_mode="html")
                else:
                    lines = ["🔔 <b>آخرین منشن‌ها و ریپلای‌های شما در گروه‌ها:</b>\n"]
                    for r in m_rows:
                        lines.append(f"• <b>{html.escape(r['target_title'])}</b>: <code>{html.escape(r['detail'][:90])}</code>")
                    await event.edit("\n".join(lines), parse_mode="html")
                return

            # ۴۰. پاکسازی سریع پیام‌ها (.del)
            if feats.get("f40") and txt.startswith(".del"):
                parts = txt.split()
                count = int(parts[1]) if (len(parts) > 1 and parts[1].isdigit()) else 5
                count = min(count, 30)
                msgs = [m.id async for m in client.iter_messages(event.chat_id, limit=count + 1, from_user="me")]
                await client.delete_messages(event.chat_id, msgs)
                return

            # ۱۶. یادداشت خصوصی (.note / .getnote) و ۲۶. دفترچه یادداشت (.notebook)
            if feats.get("f16"):
                if txt.startswith(".note "):
                    note_val = txt[6:].strip()
                    with closing(get_conn()) as conn, conn:
                        conn.execute(
                            "INSERT OR REPLACE INTO private_notes (user_id, target_id, note_text) VALUES (?, ?, ?)",
                            (user_id, str(event.chat_id), note_val)
                        )
                    await event.edit("📝 یادداشت خصوصی برای این گفتگو ذخیره شد.")
                    return
                elif txt == ".getnote":
                    with closing(get_conn()) as conn:
                        n_row = conn.execute("SELECT note_text FROM private_notes WHERE user_id=? AND target_id=?", (user_id, str(event.chat_id))).fetchone()
                    if n_row:
                        await event.edit(f"📝 <b>یادداشت این گفتگو:</b>\n<code>{html.escape(n_row['note_text'])}</code>", parse_mode="html")
                    else:
                        await event.edit("📝 یادداشتی برای این گفتگو ثبت نشده است.")
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

            # ۹. خلاصه‌سازی پیام طولانی (.sum / .خلاصه)
            if feats.get("f9") and txt in (".sum", ".خلاصه") and event.is_reply:
                rep = await event.get_reply_message()
                if rep and rep.raw_text:
                    words = rep.raw_text.split()
                    summary = " ".join(words[:35]) + ("..." if len(words) > 35 else "")
                    await event.edit(f"📝 <b>خلاصه پیام ({len(words)} کلمه):</b>\n{html.escape(summary)}", parse_mode="html")
                return

            # ۷. ترجمه سریع (.tr یا .tr en)
            if feats.get("f7") and txt.startswith(".tr") and event.is_reply:
                rep = await event.get_reply_message()
                if rep and rep.raw_text:
                    parts = txt.split()
                    target_lang = parts[1].strip() if len(parts) > 1 else "fa"
                    try:
                        r = requests.get(
                            "https://translate.googleapis.com/translate_a/single",
                            params={"client": "gtx", "sl": "auto", "tl": target_lang, "dt": "t", "q": rep.raw_text[:500]},
                            timeout=8
                        ).json()
                        tr_text = "".join([part[0] for part in r[0] if part[0]])
                        await event.edit(f"🌐 <b>ترجمه سلف دارک ({target_lang}):</b>\n{html.escape(tr_text)}", parse_mode="html")
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
            # ۳۹. شکارچی تگ و منشن در گروه‌ها (بدون ارسال پیام مزاحم در Saved Messages)
            if feats.get("f39") and event.is_group and getattr(event.message, "mentioned", False):
                try:
                    chat_obj = await event.get_chat()
                    g_title = getattr(chat_obj, "title", "گروه") or "گروه"
                    log_self_activity(user_id, "mention_in", g_title, (event.raw_text or "[مدیا]")[:100])
                except Exception:
                    pass

            # ۴۱. قابلیت «کامنت اول خودکار» در گروه‌های متصل به کانال
            if feats.get("f41") and (event.is_group or event.is_channel):
                fwd = getattr(event.message, "fwd_from", None)
                is_channel_auto_post = bool(
                    fwd and (getattr(fwd, "saved_from_peer", None) is not None or getattr(fwd, "channel_post", None) is not None)
                )
                if is_channel_auto_post:
                    with closing(get_conn()) as conn:
                        fc_row = conn.execute(
                            "SELECT * FROM first_comment_groups WHERE user_id=? AND chat_id=?",
                            (user_id, event.chat_id)
                        ).fetchone()
                    if fc_row:
                        fc_word = str(feats.get("first_comment_word", "کامنت اول")).strip() or "کامنت اول"
                        comment_body = f"{fc_word}\nSelf Dark"
                        try:
                            await event.reply(comment_body)
                            log_self_activity(user_id, "first_comment", fc_row["chat_title"], fc_word)
                        except Exception as e:
                            logger.debug(f"First comment error: {e}")

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
                    s_name = getattr(sender, "first_name", "کاربر") or "کاربر"
                    log_self_activity(user_id, "pv_msg_in", s_name, (event.raw_text or "[مدیا]")[:80])

                    # ۴۲. قابلیت «عضویت اجباری پیوی» (حداکثر ۳ کانال که ربات در آن‌ها ادمین است)
                    # رفتار دقیق طبق درخواست شما:
                    # - اگر اولین پیام کاربر باشد و قبلاً پیام نداده باشد: پیامش حذف نشود و فقط روی پیامش ریپلای شود و بگوید باید عضو شوی!
                    # - اگر دومین پیام باشد یا از قبل پیام داده باشد: پیام کاربر پاک شود و پیام عضویت اجباری با دکمه شیشه‌ای ارسال گردد!
                    if feats.get("f42") and BOT_APP_REF is not None:
                        with closing(get_conn()) as conn:
                            pv_chs = conn.execute(
                                "SELECT * FROM pv_force_channels WHERE user_id=? LIMIT 3",
                                (user_id,)
                            ).fetchall()
                        if pv_chs:
                            not_joined_pv = []
                            for pch in pv_chs:
                                try:
                                    m_info = await BOT_APP_REF.bot.get_chat_member(chat_id=pch["channel_id"], user_id=sender.id)
                                    if m_info.status in ("left", "kicked"):
                                        not_joined_pv.append(pch)
                                except Exception:
                                    not_joined_pv.append(pch)

                            if not_joined_pv:
                                # بررسی اینکه آیا این اولین پیام این شخص به کاربر است یا قبلاً هم پیام داده است
                                with closing(get_conn()) as conn:
                                    hist_row = conn.execute(
                                        "SELECT msg_count FROM pv_force_history WHERE owner_id=? AND sender_id=?",
                                        (user_id, sender.id)
                                    ).fetchone()
                                    prev_db_count = hist_row["msg_count"] if hist_row else 0

                                had_prior_messages = prev_db_count > 0
                                if not had_prior_messages:
                                    try:
                                        recent_msgs = await client.get_messages(event.chat_id, limit=6)
                                        # اگر قبل از این پیام، هر پیامی در تاریخچه این پیوی وجود داشته باشد یعنی از قبل پیام داده بود
                                        prior_msgs = [
                                            m for m in recent_msgs
                                            if getattr(m, "id", None) != event.id
                                        ]
                                        if len(prior_msgs) > 0:
                                            had_prior_messages = True
                                    except Exception:
                                        pass

                                is_first_ever_msg = not had_prior_messages

                                with closing(get_conn()) as conn, conn:
                                    conn.execute(
                                        """INSERT INTO pv_force_history (owner_id, sender_id, msg_count, updated_at)
                                           VALUES (?, ?, 1, ?)
                                           ON CONFLICT(owner_id, sender_id) DO UPDATE SET
                                           msg_count = msg_count + 1, updated_at = excluded.updated_at""",
                                        (user_id, sender.id, datetime.now().isoformat())
                                    )

                                if is_first_ever_msg:
                                    # اولین پیام کاربر است -> پیامش حذف نمی‌شود! فقط روی آن ریپلای زده می‌شود
                                    log_self_activity(user_id, "pv_force_block", s_name, "پیام اول (ریپلای بدون حذف)")
                                    await send_pv_force_glass_warning(
                                        client=client,
                                        user_id=user_id,
                                        sender_id=sender.id,
                                        chat_id=event.chat_id,
                                        not_joined_pv=not_joined_pv,
                                        is_first_ever_msg=True,
                                        reply_to_msg_id=event.id,
                                    )
                                else:
                                    # پیام دوم به بعد است یا از قبل پیام داده بود -> پیام کاربر بلافاصله حذف می‌شود!
                                    try:
                                        await client.delete_messages(event.chat_id, [event.id], revoke=True)
                                    except Exception:
                                        try:
                                            await event.delete()
                                        except Exception:
                                            pass
                                    log_self_activity(user_id, "pv_force_block", s_name, "حذف پیام (عضو نشده)")
                                    now_ts = time.time()
                                    last_pv_warn = AUTOREPLY_COOLDOWN.get((user_id, -sender.id), 0.0)
                                    if (now_ts - last_pv_warn) >= 3.0:
                                        AUTOREPLY_COOLDOWN[(user_id, -sender.id)] = now_ts
                                        await send_pv_force_glass_warning(
                                            client=client,
                                            user_id=user_id,
                                            sender_id=sender.id,
                                            chat_id=event.chat_id,
                                            not_joined_pv=not_joined_pv,
                                            is_first_ever_msg=False,
                                            reply_to_msg_id=None,
                                        )
                                return

                    # ۳۵. قفل پیوی (منشی هوشمند)
                    if feats.get("f35"):
                        try:
                            await client.delete_messages(event.chat_id, [event.id], revoke=True)
                        except Exception:
                            pass
                        now_ts = time.time()
                        if (now_ts - AUTOREPLY_COOLDOWN.get((user_id, sender.id), 0.0)) >= 30.0:
                            AUTOREPLY_COOLDOWN[(user_id, sender.id)] = now_ts
                            try:
                                await client.send_message(event.chat_id, "🔒 <b>پیوی در حال حاضر توسط منشی هوشمند سلف دارک قفل است. لطفاً بعداً پیام دهید.</b>", parse_mode="html")
                            except Exception:
                                pass
                        return

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
        if is_admin(user_id):
            asyncio.create_task(ensure_botfather_inline_enabled(client))
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
            p_btn("مدیریت ۴۶ قابلیت سلف دارک", callback_data="self:features_page:0", style="primary", emoji_key="sparkles"),
            p_btn("📖 توضیحات قابلیت‌ها (۴۶ قابلیت)", callback_data="self:features_guide:0", style="success", emoji_key="zap"),
        ],
        [
            p_btn("تبچی هوشمند سلف دارک", callback_data="menu:tabchi", style="primary", emoji_key="megaphone"),
            p_btn("📊 پنل مرکزی (گزارش ۲۴ ساعته)", callback_data="self:central_panel", style="primary", emoji_key="crown"),
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
            p_btn("🏆 لیدربورد (برترین‌های الماس)", callback_data="menu:leaderboard", style="danger", emoji_key="crown"),
        ],
        [
            p_btn("حساب کاربری من", callback_data="menu:profile", style="primary", emoji_key="star"),
            p_btn("راهنما و پشتیبانی", callback_data="menu:help", style="primary", emoji_key="zap"),
        ],
    ]
    if is_admin(user_id):
        rows.append([
            p_btn("پنل مدیریت سلف دارک (۴۰ قابلیت)", callback_data="admin:page:0", style="danger", emoji_key="crown")
        ])
    return InlineKeyboardMarkup(rows)

def build_features_keyboard(user_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """صفحه‌بندی قابلیت‌های سلف دارک (شامل دکمه توضیحات کامل ۴۶ قابلیت، چالش لایکی، قرعه‌کشی، دکمه شیشه‌ای، عضویت اجباری پیوی و پنل مرکزی)"""
    feats = get_user_features(user_id)
    keys = list(SELF_DARK_FEATURES.keys())
    per_page = 10
    total_pages = (len(keys) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    slice_keys = keys[page * per_page : (page + 1) * per_page]

    rows = [
        [
            p_btn("📖 توضیحات قابلیت‌ها (آموزش کامل هر ۴۶ قابلیت)", callback_data="self:features_guide:0", style="success", emoji_key="zap"),
        ],
        [
            p_btn("❤️ ساخت چالش لایکی کانال", callback_data="likechal:start", style="danger", emoji_key="heart"),
            p_btn("🎁 ساخت قرعه‌کشی کانال", callback_data="lotto:start", style="success", emoji_key="gift"),
        ],
        [
            p_btn("✨ ساخت دکمه شیشه‌ای کانال", callback_data="chbtn:start", style="primary", emoji_key="sparkles"),
            p_btn("🛡 عضویت اجباری پیوی", callback_data="pvforce:menu", style="primary", emoji_key="zap"),
        ],
        [
            p_btn("📊 پنل مرکزی (گزارش ۲۴ ساعته)", callback_data="self:central_panel", style="primary", emoji_key="crown"),
        ],
    ]
    for k in slice_keys:
        meta = SELF_DARK_FEATURES[k]
        ftype = meta.get("type", "toggle")
        if ftype == "action_only":
            row = [
                p_btn(
                    meta["title"],
                    callback_data=meta["action_cb"],
                    style=meta.get("style", "primary"),
                    emoji_key=meta.get("emoji_key", "sparkles")
                )
            ]
        elif ftype == "toggle_panel":
            is_on = feats.get(k, False)
            status_str = "🟢 روشن" if is_on else "🔴 خاموش"
            btn_style = "success" if is_on else "primary"
            row = [
                p_btn(f"{meta['title']} ({status_str})", callback_data=f"ftoggle:{k}:{page}", style=btn_style),
                p_btn("⚙️ مدیریت کانال‌ها", callback_data=meta["panel_cb"], style="primary"),
            ]
        else:
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
    ("adm:24", "۲۴. الماس همگانی با متن دلخواه", "success"),
    ("adm:25", "۲۵. ساخت کد هدیه الماس (مرحله‌ای)", "success"),
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
            p_btn("🎉 الماس همگانی با متن دلخواه", callback_data="adm:24", style="success", emoji_key="party"),
            p_btn("🎁 ساخت کد هدیه مرحله‌ای", callback_data="adm:25", style="primary", emoji_key="gift"),
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
    ADM_WAIT_PUBLIC_DIAMOND_AMOUNT,
    ADM_WAIT_PUBLIC_DIAMOND_TEXT,
    ADM_WAIT_GIFT_WORD,
    ADM_WAIT_GIFT_DIAMONDS,
    ADM_WAIT_GIFT_CAPACITY,
    TICKET_WAIT_MESSAGE,
    ADM_WAIT_TICKET_REPLY,
    PVFORCE_WAIT_CHANNEL,
    LOTTO_WAIT_TITLE,
    LOTTO_WAIT_MIN,
    LOTTO_WAIT_MAX,
    LOTTO_WAIT_FCH,
    LOTTO_WAIT_DESC,
    LOTTO_WAIT_DURATION,
    LOTTO_WAIT_WINNERS,
    LOTTO_WAIT_CHANNEL,
    LOTTO_WAIT_CONFIRM,
    CHBTN_WAIT_CONTENT,
    CHBTN_WAIT_LINK,
    CHBTN_WAIT_NAME,
    CHBTN_WAIT_COLOR,
    CHBTN_WAIT_CHANNEL,
    CHBTN_WAIT_CONFIRM,
    LIKECHAL_WAIT_CHANNEL,
    LIKECHAL_WAIT_NAMES,
) = range(43)

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

    # بررسی لینک‌های اختصاصی (شرکت در قرعه‌کشی کانال یا بررسی عضویت اجباری پیوی)
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("lotto_"):
            lotto_id_str = arg.replace("lotto_", "").strip()
            if lotto_id_str.isdigit():
                await handle_lottery_join_attempt(update, context, user, int(lotto_id_str), is_callback=False)
                return
        elif arg.startswith("pvcheck_"):
            owner_id_str = arg.replace("pvcheck_", "").strip()
            if owner_id_str.isdigit():
                await handle_pv_force_verify(update, context, user, int(owner_id_str), is_callback=False)
                return

    not_joined = await check_user_joined_all(context.bot, user.id)
    if not_joined:
        bonus_preview = int(get_setting("welcome_bonus", "60") or "60")
        gift_hint = (
            f"\n🎁 پس از عضویت در کانال‌ها و زدن دکمه تایید، <b>{bonus_preview} الماس هدیه ورود</b> به حساب شما اضافه خواهد شد!"
            if not db_user["welcome_gift_claimed"] else ""
        )
        await update.message.reply_text(
            p_text(
                f"👋 سلام! برای ورود به ربات <b>سلف دارک (Self Dark)</b>، ابتدا در کانال‌های زیر عضو شوید و سپس دکمه <b>«✅ عضو شدم»</b> را بزنید:{gift_hint}"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=build_force_join_keyboard(not_joined)
        )
        return

    await verify_referral_if_eligible(context.bot, user.id)
    gifted_amt = grant_first_entry_gift_if_eligible(user.id)
    db_user = get_or_create_user(user.id, user.username, user.first_name)
    acc = get_self_account(user.id)
    self_state = "🟢 روشن و متصل" if (acc and acc["is_running"] == 1) else "🔴 خاموش / متصل نشده"

    gift_banner = (
        f"🎁 <b>هدیه ورود اولیه:</b> تبریک! تعداد <b>+{gifted_amt} الماس رایگان</b> به حساب شما اضافه شد!\n\n"
        if gifted_amt > 0 else ""
    )

    welcome = p_text(
        f"🌑 <b>به ربات هوشمند «سلف دارک | Self Dark» خوش آمدید!</b>\n\n"
        f"{gift_banner}"
        f"👤 کاربر: <b>{html.escape(user.first_name)}</b>\n"
        f"💎 موجودی الماس شما: <b>{db_user['diamonds']} الماس</b>\n"
        f"⚡ وضعیت سلف دارک: <b>{self_state}</b>\n\n"
        f"🚀 با <b>سلف دارک</b>، اکانت تلگرام خود را به ۴۶ قابلیت پیشرفته (ضد حذف، ضد ویرایش، ساعت زنده، منشی هوشمند، هوش مصنوعی، چالش لایکی کانال و...) و <b>تبچی هوشمند گروهی</b> مجهز کنید!\n\n"
        f"✨ از دکمه‌های شیشه‌ای رنگی زیر بخش مورد نظر خود را انتخاب کنید:"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.HTML, reply_markup=main_inline_keyboard(user.id))

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    get_or_create_user(user.id, user.username, user.first_name)
    not_joined = await check_user_joined_all(context.bot, user.id)
    if not_joined:
        await query.answer("⚠️ هنوز در تمام کانال‌ها عضو نشده‌اید!", show_alert=True)
        return

    await verify_referral_if_eligible(context.bot, user.id)
    gifted_amt = grant_first_entry_gift_if_eligible(user.id)
    db_user = get_or_create_user(user.id, user.username, user.first_name)

    if gifted_amt > 0:
        await query.answer(f"🎉 عضویت شما تایید شد و +{gifted_amt} الماس هدیه ورود دریافت کردید!", show_alert=True)
        gift_line = f"\n🎁 <b>هدیه ورود اولیه: +{gifted_amt} الماس رایگان به حساب شما اضافه شد!</b>\n💎 موجودی فعلی شما: <b>{db_user['diamonds']} الماس</b>\n"
    else:
        await query.answer("✅ عضویت شما تایید شد!")
        gift_line = f"\n💎 موجودی فعلی شما: <b>{db_user['diamonds']} الماس</b>\n"

    await query.edit_message_text(
        p_text(f"✅ <b>عضویت شما تایید شد!</b>{gift_line}\n🌑 به ربات <b>سلف دارک</b> خوش آمدید:"),
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
    grant_first_entry_gift_if_eligible(user.id)
    db_user = get_or_create_user(user.id, user.username, user.first_name)
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

    elif data == "menu:leaderboard":
        with closing(get_conn()) as conn:
            top_50 = conn.execute(
                "SELECT first_name, diamonds FROM users ORDER BY diamonds DESC, user_id ASC LIMIT 50"
            ).fetchall()

        lines = [
            "🏆 <b>لیدربورد ۵۰ کاربر برتر سلف دارک (بیشترین الماس)</b>",
            "━━━━━━━━━━━━━━━━━━━━\n",
        ]
        if not top_50:
            lines.append("⚠️ هنوز کاربری در لیست برترین‌ها ثبت نشده است.")
        else:
            for idx, u_row in enumerate(top_50, start=1):
                u_name = html.escape((u_row["first_name"] or "کاربر").strip() or "کاربر")
                d_val = int(u_row["diamonds"] or 0)
                if idx == 1:
                    rank_badge = "🥇 ۱."
                elif idx == 2:
                    rank_badge = "🥈 ۲."
                elif idx == 3:
                    rank_badge = "🥉 ۳."
                else:
                    rank_badge = f"🔹 {idx}."
                lines.append(f"{rank_badge} <b>{u_name}</b> — <b>{d_val:,} الماس</b> 💎")

        kb = InlineKeyboardMarkup([
            [p_btn("🔄 بروزرسانی لیدربورد", callback_data="menu:leaderboard", style="danger", emoji_key="crown")],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="primary", emoji_key="glow")],
        ])
        await query.edit_message_text(
            p_text("\n".join(lines)),
            parse_mode=ParseMode.HTML,
            reply_markup=kb
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
        text = p_text(
            "📚 <b>بخش راهنما و پشتیبانی «سلف دارک | Self Dark»</b>\n\n"
            "✨ لطفاً یکی از دو بخش زیر را انتخاب کنید:\n\n"
            "🔹 <b>راهنمای کامل:</b> آموزش فعال‌سازی سلف، دستورات گروهی (موجودی، بازی، انتقال، کامنت اول) و قابلیت‌های سلف دارک\n"
            "🔹 <b>پشتیبانی:</b> ارتباط مستقیم با آیدی پشتیبانی یا ثبت تیکت در داخل ربات"
        )
        kb = InlineKeyboardMarkup([
            [
                p_btn("📚 راهنما (آموزش کامل ربات و گروه)", callback_data="menu:help_guide", style="primary", emoji_key="zap"),
            ],
            [
                p_btn("🎧 پشتیبانی (پیام مستقیم / ثبت تیکت)", callback_data="menu:support", style="success", emoji_key="rocket"),
            ],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "menu:support":
        sup_id = get_setting("rial_support_id", "@kanfingfreesup")
        sup_url = f"https://t.me/{sup_id.lstrip('@')}"
        with closing(get_conn()) as conn:
            open_t = conn.execute("SELECT id, created_at FROM tickets WHERE user_id=? AND status='open'", (user.id,)).fetchone()

        ticket_st = (
            f"🟡 شما یک تیکت باز (#{open_t['id']}) در انتظار پاسخ ادمین دارید."
            if open_t else "🟢 شما هیچ تیکت بی‌پاسخی ندارید و می‌توانید تیکت جدید ثبت کنید."
        )
        text = p_text(
            f"🎧 <b>مرکز پشتیبانی «سلف دارک | Self Dark»</b>\n\n"
            f"برای ارتباط با پشتیبانی ۲ روش در اختیار شماست:\n\n"
            f"1️⃣ <b>روش اول (ارتباط مستقیم با آیدی پشتیبانی):</b>\n"
            f"• می‌توانید مستقیماً به آیدی پشتیبانی پیام دهید: <b>{sup_id}</b>\n\n"
            f"2️⃣ <b>روش دوم (ثبت تیکت در داخل ربات):</b>\n"
            f"• مشکل یا سوال خود را به صورت تیکت ثبت کنید تا مستقیماً برای ادمین ارسال شود و در همین ربات پاسخ بگیرید.\n"
            f"📌 <i>توجه: تا زمانی که تیکت قبلی شما توسط ادمین پاسخ داده نشده باشد، امکان ثبت تیکت جدید وجود ندارد.</i>\n\n"
            f"📊 وضعیت تیکت شما: {ticket_st}"
        )
        kb = InlineKeyboardMarkup([
            [p_btn(f"💬 پیام مستقیم به پشتیبانی ({sup_id})", url=sup_url, style="primary", emoji_key="rocket")],
            [p_btn("📩 ثبت تیکت جدید در ربات", callback_data="support:new_ticket", style="success", emoji_key="sparkles")],
            [p_btn("⬅️ بازگشت به راهنما و پشتیبانی", callback_data="menu:help", style="primary", emoji_key="zap")],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "menu:help_guide":
        act_c = get_setting("activation_cost", "30")
        hr_c = get_setting("hourly_cost", "3")
        ref_r = get_setting("referral_reward", "5")
        ton_r = get_setting("ton_per_diamond", "0.0005")
        min_tr = get_setting("min_transfer_diamonds", "50")
        extra_note = get_setting("help_extra_note", "")

        help_text = p_text(
            f"📚 <b>راهنمای جامع ربات و قابلیت‌های گروهی «سلف دارک | Self Dark»</b>\n\n"
            f"🌑 <b>۱. نحوه فعال‌سازی سلف دارک:</b>\n"
            f"• ابتدا از داشتن حداقل <b>{act_c} الماس</b> در حساب خود مطمئن شوید.\n"
            f"• وارد بخش <b>«🚀 فعالسازی و اتصال سلف دارک»</b> شوید و شماره و کد ۵ رقمی تلگرام را وارد کنید.\n\n"
            f"💎 <b>۲. سیستم الماس، انتقال و کارمزد:</b>\n"
            f"• هزینه فعال‌سازی اولیه سلف: <b>{act_c} الماس</b> | هزینه ساعتی: <b>{hr_c} الماس</b>\n"
            f"• خرید با TON: هر الماس <b>{ton_r} TON</b> | کارت به کارت: {get_setting('rial_support_id', '@kanfingfreesup')}\n"
            f"• انتقال الماس: حداقل انتقال <b>{min_tr} الماس</b> با <b>۱۰٪ کارمزد</b> که از انتقال‌دهنده کسر می‌شود.\n\n"
            f"👥 <b>۳. راهنمای کامل قابلیت‌های گروهی (Group Features):</b>\n"
            f"• <b>مشاهده موجودی در گروه:</b> کافی است در گروه کلمه <code>موجودی</code> را بفرستید تا موجودی الماس شما داخل یک <b>دکمه شیشه‌ای آبی رنگ</b> نمایش داده شود.\n"
            f"• <b>ساخت بازی دو نفره شرطی:</b> در گروه بنویسید <code>بازی [مبلغ]</code> (مثال: <code>بازی 60</code>). حداقل مبلغ شرط <b>۱۵ الماس</b> است. یک بازی با دکمه شیشه‌ای رنگی ساخته می‌شود که فقط خود شما و ۱ نفر دیگر می‌توانید شرکت کنید؛ به محض ورود نفر دوم، ربات به صورت کاملاً تصادفی برنده را انتخاب کرده و <b>۲ برابر مبلغ شرط</b> را به برنده جایزه می‌دهد!\n"
            f"• <b>انتقال الماس با ریپلای در گروه:</b> روی پیام هر کاربری در گروه ریپلای کنید و بنویسید <code>انتقال [مبلغ]</code> (مثال: <code>انتقال 50</code>)؛ الماس بلافاصله با کسر ۱۰٪ کارمزد از حساب شما به حساب او منتقل شده و در پیوی ربات هم برایش نوتیفیکیشن ارسال می‌شود.\n\n"
            f"🥇 <b>۴. کامنت اول، عضویت اجباری پیوی، قرعه‌کشی و پنل مرکزی:</b>\n"
            f"• <b>کامنت اول خودکار:</b> در گروهی که به کانال متصل است عبارت <code>تنظیم کامنت اول</code> را بفرستید؛ به محض انتشار پست جدید در کانال، کلمه کامنت اول شما به همراه امضای <code>Self Dark</code> زیر پست ارسال می‌شود (قابل تغییر از بخش قابلیت‌های سلف).\n"
            f"• <b>عضویت اجباری پیوی:</b> از بخش قابلیت‌های سلف تا حداکثر ۳ کانال (که ربات در آن‌ها ادمین است) ثبت کنید تا هر کسی در پیوی پیام داد و عضو نبود، پیامش فوراً حذف شده و دکمه شیشه‌ای کانال‌ها و بررسی عضویت برایش ارسال شود.\n"
            f"• <b>ساخت قرعه‌کشی و دکمه شیشه‌ای کانال:</b> از بخش قابلیت‌های سلف می‌توانید قرعه‌کشی زمان‌دار با شمارنده زنده شرکت‌کنندگان و انتخاب خودکار برندگان یا پست شیشه‌ای رنگی در کانال منتشر کنید.\n"
            f"• <b>پنل مرکزی (آخرین قابلیت سلف):</b> نمایش گزارش کامل تمام فعالیت‌های ۲۴ ساعت گذشته اکانت شما (پیام‌های گروه، پیوی، استارت ربات‌ها و...).\n\n"
            f"📣 <b>۵. تبچی هوشمند و دستورات سلف:</b>\n"
            f"• ثبت گروه در تبچی با <code>تنظیم چت</code> و حذف با <code>حذف چت</code>\n"
            f"• دستورات سلف: <code>.ping</code> | <code>.stats</code> | <code>.id</code> | <code>.tr</code> | <code>.sum</code> | <code>.calc</code> | <code>.font</code> | <code>.del</code>\n\n"
            f"{html.escape(extra_note)}"
        )
        kb = InlineKeyboardMarkup([
            [
                p_btn("🎧 بخش پشتیبانی و ثبت تیکت", callback_data="menu:support", style="success", emoji_key="rocket"),
                p_btn("خرید الماس", callback_data="menu:buy_diamonds", style="primary", emoji_key="gem"),
            ],
            [p_btn("⬅️ بازگشت به راهنما و پشتیبانی", callback_data="menu:help", style="primary", emoji_key="zap")],
            [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
        ])
        await query.edit_message_text(help_text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ====================================================================
#  مدیریت قابلیت‌های سلف دارک (روشن/خاموش، تغییر مقادیر و پنل مرکزی)
# ====================================================================
#  کتابچه و دایرةالمعارف کامل «توضیحات قابلیت‌ها» (هر ۴۵ قابلیت در ۹ صفحه)
# ====================================================================

SELF_FEATURES_GUIDE_PAGES = [
    # صفحه ۱ (قابلیت‌های ۱ تا ۵)
    (
        "📖 <b>توضیحات کامل قابلیت‌های سلف دارک — صفحه ۱ از ۹ (قابلیت‌های ۱ تا ۵)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ <b>۱. پاسخگویی خودکار هوشمند (فقط پیوی اکانت‌ها):</b>\n"
        "• <b>کارکرد:</b> وقتی آنلاین نیستید، منشی هوشمند فقط به اکانت‌های واقعی اشخاص (نه ربات‌ها و نه کانال‌ها) پاسخ خودکار می‌دهد.\n"
        "• <b>نحوه استفاده دقیق:</b> در بخش مدیریت قابلیت‌ها، گزینه ۱ را <b>🟢 روشن</b> کنید. برای تغییر متن پاسخ، دکمه <b>«⚙️ تنظیم مقدار»</b> جلوی آن را بزنید و متن دلخواه خود را بفرستید (برای جلوگیری از اسپم، به هر شخص هر ۶۰ ثانیه یک بار پاسخ می‌دهد).\n\n"
        "2️⃣ <b>۲. دستیار هوش مصنوعی:</b>\n"
        "• <b>کارکرد:</b> پاسخگویی هوشمند به سوالات علمی، کدنویسی، انشا و ترجمه مستقیماً از داخل چت تلگرام.\n"
        "• <b>نحوه استفاده دقیق:</b> ابتدا قابلیت ۲ را روشن کنید. سپس در هر چت یا گروهی بنویسید:\n"
        "<code>.ai سوال شما</code> (مثال: <code>.ai خلاصه تاریخ ایران چیست؟</code>) و یا روی پیام شخص دیگری ریپلای کرده و فقط <code>.ai</code> بفرستید تا پاسخ کامل جایگزین پیام شما شود.\n\n"
        "3️⃣ <b>۳. تغییر خودکار بیوگرافی با ساعت:</b>\n"
        "• <b>کارکرد:</b> نمایش ساعت زنده و متن دلخواه در قسمت Bio پروفایل که راس هر دقیقه آپدیت می‌شود.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۳ را روشن کنید و از دکمه <b>«⚙️ تنظیم مقدار»</b> متن بیوگرافی خود را همراه با متغیر <code>{time}</code> بفرستید (مثال: <code>🌑 Self Dark | ⏰ {time}</code>).\n\n"
        "4️⃣ <b>۴. ساعت زنده در نام و نام خانوادگی پروفایل (دقیق هر دقیقه):</b>\n"
        "• <b>کارکرد:</b> قرار دادن ساعت فونت‌دار زنده در بخش نام خانوادگی پروفایل که دقیقاً طبق ساعت گوشی شما هر دقیقه بالا می‌رود.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۴ را روشن کنید. برای تنظیم دقیق با ساعت گوشی خود، در هر چتی دستور <code>.ساعت 16:45</code> (ساعت فعلی گوشی‌تان) را بفرستید یا در «⚙️ تنظیم مقدار» ساعت فعلی را وارد کنید.\n\n"
        "5️⃣ <b>۵. زمان‌بندی و مدیریت سریع عکس پروفایل:</b>\n"
        "• <b>کارکرد:</b> تغییر یا حذف آنی عکس پروفایل اکانت با یک دستور.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۵ را روشن کنید. در هر چتی روی یک عکس ریپلای کرده و دستور <code>.setpic</code> را بفرستید تا فوراً عکس پروفایل شما شود! برای حذف آخرین عکس پروفایل دستور <code>.delpic</code> را ارسال کنید."
    ),
    # صفحه ۲ (قابلیت‌های ۶ تا ۱۰)
    (
        "📖 <b>توضیحات کامل قابلیت‌های سلف دارک — صفحه ۲ از ۹ (قابلیت‌های ۶ تا ۱۰)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "6️⃣ <b>۶. مدیریت وضعیت اکانت (آنلاین دائمی ۲۴ ساعته):</b>\n"
        "• <b>کارکرد:</b> نگه داشتن وضعیت اکانت شما روی حالت <b>Online</b> به صورت ۲۴ ساعته حتی وقتی تلگرام شما بسته است.\n"
        "• <b>نحوه استفاده دقیق:</b> کافی است گزینه ۶ را در پنل قابلیت‌ها <b>🟢 روشن</b> کنید؛ نیازی به هیچ دستوری ندارد و خودکار هر دقیقه وضعیت آنلاین ارسال می‌کند.\n\n"
        "7️⃣ <b>۷. ترجمه خودکار پیام‌ها:</b>\n"
        "• <b>کارکرد:</b> ترجمه فوری پیام‌های انگلیسی، عربی، ترکی، روسی و... به فارسی یا هر زبان دلخواه.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۷ را روشن کنید. سپس در پیوی یا گروه روی پیام مورد نظر <b>ریپلای (Reply)</b> کرده و بنویسید:\n"
        "• <code>.tr</code> (برای ترجمه خودکار به فارسی)\n"
        "• <code>.tr en</code> (برای ترجمه به انگلیسی؛ یا <code>.tr ar</code> عربی، <code>.tr tr</code> ترکی).\n\n"
        "8️⃣ <b>۸. تبدیل ویس به متن (Voice to Text):</b>\n"
        "• <b>کارکرد:</b> تبدیل پیام‌های صوتی (Voice) و ویدیومسیج‌های دایره‌ای به متن قابل خواندن.\n"
        "• <b>نحوه استفاده دقیق:</b> ابتدا قابلیت ۸ را روشن کنید. سپس در هر چت یا گروهی روی <b>ویس یا ویدیومسیج</b> مورد نظر <b>ریپلای (Reply)</b> بزنید و دستور <code>.v2t</code> یا عبارت <code>تبدیل به متن</code> را بفرستید تا سلف دارک صدای داخل ویس را پردازش کرده و متن آن را بنویسد.\n\n"
        "9️⃣ <b>۹. خلاصه‌سازی پیام‌های طولانی:</b>\n"
        "• <b>کارکرد:</b> استخراج چکیده و تعداد کلمات پیام‌های بسیار بلند و مقاله‌ها.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۹ را روشن کنید، روی پیام متنی طولانی ریپلای کرده و دستور <code>.sum</code> یا <code>.خلاصه</code> را بفرستید.\n\n"
        "🔟 <b>۱۰. دسته‌بندی هوشمند پیام‌ها و گفتگوها:</b>\n"
        "• <b>کارکرد:</b> آنالیز کل چت‌های اکانت و تفکیک تعداد پیوی‌ها، گروه‌ها، کانال‌ها، ربات‌ها و چت‌های خوانده‌نشده.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۱۰ را روشن کرده و در هر چتی دستور <code>.cats</code> یا <code>.دسته بندی</code> را ارسال کنید."
    ),
    # صفحه ۳ (قابلیت‌های ۱۱ تا ۱۵)
    (
        "📖 <b>توضیحات کامل قابلیت‌های سلف دارک — صفحه ۳ از ۹ (قابلیت‌های ۱۱ تا ۱۵)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣1️⃣ <b>۱۱. ذخیره پیام‌های حذف‌شده (بدون ارسال گزارش مزاحم در Saved):</b>\n"
        "• <b>کارکرد:</b> کش کردن بی‌صدای پیام‌های دریافتی در دیتابیس تا اگر طرف مقابل پیامش را دوطرفه پاک کرد، بتوانید متن آن را ببینید (بدون شلوغ کردن Saved Messages).\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۱۱ را روشن بگذارید. هر زمان خواستید پیام‌های حذف‌شده را ببینید، در چت دستور <code>.حذفیات</code> یا <code>.deleted</code> را ارسال کنید.\n\n"
        "1️⃣2️⃣ <b>۱۲. ذخیره تاریخچه ویرایش پیام‌ها (Anti-Edit):</b>\n"
        "• <b>کارکرد:</b> ذخیره متن اصلی پیام‌ها قبل از اینکه طرف مقابل آن‌ها را ویرایش (Edit) کند.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۱۲ را روشن بگذارید. برای دیدن متن قبل و بعد از ویرایش پیام‌ها، دستور <code>.ویرایشها</code> یا <code>.edits</code> را ارسال نمایید.\n\n"
        "1️⃣3️⃣ <b>۱۳. پشتیبان‌گیری از گفتگوها (بکاپ چت):</b>\n"
        "• <b>کارکرد:</b> استخراج پیام‌های یک پیوی یا گروه در قالب فایل متنی <code>.txt</code>.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۱۳ را روشن کنید و داخل چت مورد نظر دستور <code>.backup</code> (برای ۱۰۰ پیام آخر) یا مثلاً <code>.backup 300</code> (برای ۳۰۰ پیام آخر) را بفرستید تا فایل بکاپ ساخته و ارسال شود.\n\n"
        "1️⃣4️⃣ <b>۱۴. جستجوی پیشرفته پیام‌ها:</b>\n"
        "• <b>کارکرد:</b> جستجوی سریع یک کلمه یا عدد در کل تاریخچه چت فعلی همراه با ساعت و آیدی پیام.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۱۴ را روشن کرده و بنویسید <code>.find کلمه</code> (مثال: <code>.find شماره کارت</code>).\n\n"
        "1️⃣5️⃣ <b>۱۵. بایگانی خودکار گفتگوها (Archive):</b>\n"
        "• <b>کارکرد:</b> انتقال سریع چت به پوشه بایگانی تلگرام یا خارج کردن آن.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۱۵ را روشن کنید؛ در داخل چت دستور <code>.archive</code> را برای بایگانی کردن و دستور <code>.unarchive</code> را برای خروج از بایگانی بفرستید."
    ),
    # صفحه ۴ (قابلیت‌های ۱۶ تا ۲۰)
    (
        "📖 <b>توضیحات کامل قابلیت‌های سلف دارک — صفحه ۴ از ۹ (قابلیت‌های ۱۶ تا ۲۰)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣6️⃣ <b>۱۶. یادداشت خصوصی برای هر گفتگو:</b>\n"
        "• <b>کارکرد:</b> ثبت یک نکته یا یادداشت مخفی درباره هر شخص یا گروه در دیتابیس سلف دارک.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۱۶ را روشن کنید. در چت مورد نظر بنویسید <code>.note متن یادداشت</code> (مثال: <code>.note مشتری ثابت - بدهی تسویه شد</code>). برای مشاهده یادداشت همان چت دستور <code>.getnote</code> را بفرستید.\n\n"
        "1️⃣7️⃣ <b>۱۷. سنجاق خودکار پیام‌های مهم (Auto-Pin):</b>\n"
        "• <b>کارکرد:</b> پین شدن خودکار پیام‌هایی که حاوی کلمه کلیدی مهم هستند.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۱۷ را روشن کنید. هر پیامی که در چت بیاید و داخل آن کلمه <code>مهم</code> یا هشتگ <code>#مهم</code> باشد، سلف دارک خودکار آن را Pin می‌کند.\n\n"
        "1️⃣8️⃣ <b>۱۸. یادآوری پیام‌ها و کارها (Reminder):</b>\n"
        "• <b>کارکرد:</b> تنظیم آلارم و یادآور دقیق در تلگرام.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۱۸ را روشن کنید و بنویسید:\n"
        "<code>.rem [دقیقه] [متن یادآوری]</code> (مثال: <code>.rem 15 چک کردن سرور</code>). دقیقاً ۱۵ دقیقه بعد سلف دارک در همان چت به شما پیام یادآوری می‌دهد.\n\n"
        "1️⃣9️⃣ <b>۱۹. دستورات سریع اختصاصی:</b>\n"
        "• <b>کارکرد:</b> ابزارهای فوری بررسی سرعت و استخراج مشخصات هر کاربر.\n"
        "• <b>نحوه استفاده دقیق:</b>\n"
        "  • <code>.ping</code> : تست آنلاین بودن و سرعت پینگ سلف دارک به میلی‌ثانیه\n"
        "  • <code>.id</code> : دریافت آیدی عددی چت (و آیدی عددی شخص در صورت ریپلای)\n"
        "  • <code>.info</code> : دریافت نام کامل، یوزرنیم و آیدی عددی شخص با ریپلای روی پیام او.\n\n"
        "2️⃣0️⃣ <b>۲۰. مدیریت اکانت و بررسی وضعیت نشست:</b>\n"
        "• <b>کارکرد:</b> مشاهده اطلاعات اتصال اکانت و نشست فعال در سلف دارک.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۲۰ را روشن کرده و دستور <code>.session</code> یا <code>.اکانت</code> را در چت بفرستید."
    ),
    # صفحه ۵ (قابلیت‌های ۲۱ تا ۲۵)
    (
        "📖 <b>توضیحات کامل قابلیت‌های سلف دارک — صفحه ۵ از ۹ (قابلیت‌های ۲۱ تا ۲۵)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "2️⃣1️⃣ <b>۲۱. پاسخ با سبک دلخواه خودکار (فونت/بولد/ایتالیک/مونو):</b>\n"
        "• <b>کارکرد:</b> تغییر خودکار استایل تمام پیام‌های معمولی که در تلگرام تایپ و ارسال می‌کنید.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۲۱ را روشن کنید و روی <b>«⚙️ تنظیم مقدار»</b> بزنید:\n"
        "  • ارسال <code>bold</code> برای ضخیم شدن خودکار همه پیام‌ها\n"
        "  • ارسال <code>italic</code> برای کج شدن خودکار پیام‌ها\n"
        "  • ارسال <code>mono</code> برای استایل کد/تک‌فاصله.\n\n"
        "2️⃣2️⃣ <b>۲۲. حافظه اختصاصی هوش مصنوعی:</b>\n"
        "• <b>کارکرد:</b> حفظ سابقه مکالمات شما با دستیار هوش مصنوعی (<code>.ai</code>) تا سوالات بعدی را در ادامه بحث قبلی پاسخ دهد.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۲۲ را روشن کنید. برای پاک کردن حافظه هوش مصنوعی هر زمان خواستید دستور <code>.aiclear</code> را بفرستید.\n\n"
        "2️⃣3️⃣ <b>۲۳. پیشنهاد خودکار استیکر و ایموجی متحرک:</b>\n"
        "• <b>کارکرد:</b> تبدیل سریع کلمات احساسی به ترکیب ایموجی‌های متحرک.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۲۳ را روشن کنید و یکی از دستورات <code>.تبریک</code>، <code>.عشق</code>، <code>.خنده</code> یا <code>.اتش</code> را در چت بنویسید.\n\n"
        "2️⃣4️⃣ <b>۲۴. پیشنهاد هوشمند شکلک (ری‌اکشن خودکار پیوی):</b>\n"
        "• <b>کارکرد:</b> ثبت خودکار ری‌اکشن (Reaction) روی تمام پیام‌هایی که اشخاص واقعی در پیوی برای شما می‌فرستند.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۲۴ را روشن کنید و از «⚙️ تنظیم مقدار» ایموجی دلخواه خود (مثلاً <code>🔥</code> یا <code>❤️</code>) را وارد نمایید.\n\n"
        "2️⃣5️⃣ <b>۲۵. ساخت دستورات شخصی (میانبر متنی):</b>\n"
        "• <b>کارکرد:</b> تعریف کلمه کوتاه که با تایپ آن، یک متن کامل جایگزینش شود (مناسب شماره کارت، آدرس کانال، قوانین و...).\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۲۵ را روشن کنید و در «⚙️ تنظیم مقدار» با فرمت <code>کلید=پاسخ</code> بنویسید (مثال: <code>.کارت=6037991122334455 به نام امیر</code>). حالا هر جا <code>.کارت</code> بنویسید خودکار تبدیل می‌شود!"
    ),
    # صفحه ۶ (قابلیت‌های ۲۶ تا ۳۰)
    (
        "📖 <b>توضیحات کامل قابلیت‌های سلف دارک — صفحه ۶ از ۹ (قابلیت‌های ۲۶ تا ۳۰)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "2️⃣6️⃣ <b>۲۶. دفترچه یادداشت خصوصی کل اکانت:</b>\n"
        "• <b>کارکرد:</b> مشاهده یکجای تمام یادداشت‌هایی که در پیوی‌ها و گروه‌های مختلف با <code>.note</code> ذخیره کرده‌اید.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۲۶ را روشن کنید و در هر چتی دستور <code>.notebook</code> را ارسال نمایید.\n\n"
        "2️⃣7️⃣ <b>۲۷. گزارش فعالیت روزانه اکانت:</b>\n"
        "• <b>کارکرد:</b> دریافت خلاصه عملکرد ۲۴ ساعت اخیر اکانت به صورت متنی در داخل چت.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۲۷ را روشن کرده و دستور <code>.report</code> یا <code>.گزارش</code> را بفرستید.\n\n"
        "2️⃣8️⃣ <b>۲۸. آمار گفتگوها و پیام‌های سلف دارک:</b>\n"
        "• <b>کارکرد:</b> نمایش تعداد کل پیام‌های پردازش‌شده توسط موتور سلف دارک و تعداد گروه‌های فعال در تبچی.\n"
        "• <b>نحوه استفاده دقیق:</b> در هر چتی دستور <code>.stats</code> را ارسال کنید.\n\n"
        "2️⃣9️⃣ <b>۲۹. ارسال زمان‌بندی‌شده و تاخیری پیام‌ها:</b>\n"
        "• <b>کارکرد:</b> تنظیم پیامی که چند دقیقه یا ساعت دیگر به صورت خودکار در همان چت ارسال شود.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۲۹ را روشن کنید و بنویسید:\n"
        "<code>.later [دقیقه] [متن پیام]</code> (مثال: <code>.later 30 سلام وقت بخیر، فایل آماده شد</code>). دستور شما فوراً پاک شده و ۳۰ دقیقه بعد پیام ارسال می‌گردد.\n\n"
        "3️⃣0️⃣ <b>۳۰. مدیریت هوشمند اعلان‌ها (Mute / Unmute):</b>\n"
        "• <b>کارکرد:</b> بی‌صدا یا صدادار کردن سریع نوتیفیکیشن‌های هر چت یا گروه با یک دستور.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۳۰ را روشن کنید؛ دستور <code>.mute</code> برای بی‌صدا کردن دائمی چت و دستور <code>.unmute</code> برای باز کردن صدای اعلان چت."
    ),
    # صفحه ۷ (قابلیت‌های ۳۱ تا ۳۵)
    (
        "📖 <b>توضیحات کامل قابلیت‌های سلف دارک — صفحه ۷ از ۹ (قابلیت‌های ۳۱ تا ۳۵)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "3️⃣1️⃣ <b>۳۱. حالت روح (سین بدون تیک دوم در پیوی):</b>\n"
        "• <b>کارکرد:</b> پردازش پیام‌های دریافتی توسط سلف بدون اینکه تیک دوم خوانده شدن (Seen) به صورت خودکار برای فرستنده بخورد.\n"
        "• <b>نحوه استفاده دقیق:</b> کافی است قابلیت ۳۱ را در پنل <b>🟢 روشن</b> نگه دارید.\n\n"
        "3️⃣2️⃣ <b>۳۲. تایپینگ و اکشن دائمی (Auto Action):</b>\n"
        "• <b>کارکرد:</b> نمایش حالت «در حال نوشتن...»، «در حال ضبط صدا...» یا «در حال بازی...» بالای صفحه پیوی وقتی کسی به شما پیام می‌دهد.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۳۲ را روشن کنید و در «⚙️ تنظیم مقدار» یکی از کلمات <code>typing</code> (تایپینگ)، <code>voice</code> (ضبط ویس) یا <code>game</code> (بازی) را وارد کنید.\n\n"
        "3️⃣3️⃣ <b>۳۳. دانلود مدیاهای تایمردار و یک‌بار مصرف:</b>\n"
        "• <b>کارکرد:</b> ذخیره عکس‌ها و ویدیوهای تایمردار (Self-Destructing) در پیام‌های ذخیره‌شده (Saved Messages) شما.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۳۳ را روشن کنید، روی عکس یا ویدیوی مورد نظر ریپلای کرده و دستور <code>.dl</code> را بفرستید تا فایل بلافاصله در Saved Messages شما ذخیره شود.\n\n"
        "3️⃣4️⃣ <b>۳۴. ضد لینک و ضد اسپم پیوی:</b>\n"
        "• <b>کارکرد:</b> حذف فوری و دوطرفه هرگونه لینک تلگرام (<code>t.me/</code>) یا لینک وب‌سایت که افراد در پیوی برای شما می‌فرستند.\n"
        "• <b>نحوه استفاده دقیق:</b> کافی است قابلیت ۳۴ را در منوی قابلیت‌ها <b>🟢 روشن</b> کنید.\n\n"
        "3️⃣5️⃣ <b>۳۵. قفل پیوی (منشی هوشمند موقع شلوغی):</b>\n"
        "• <b>کارکرد:</b> وقتی جلسه‌ای دارید یا نمی‌خواهید کسی پیام بدهد، پیام‌های ورودی پیوی را پاک کرده و اعلام می‌کند پیوی قفل است.\n"
        "• <b>نحوه استفاده دقیق:</b> از منوی قابلیت‌ها روشن کنید یا در هر چتی دستور <code>.lockpv</code> (برای قفل کردن) و <code>.unlockpv</code> (برای باز کردن قفل پیوی) را بفرستید."
    ),
    # صفحه ۸ (قابلیت‌های ۳۶ تا ۴۰)
    (
        "📖 <b>توضیحات کامل قابلیت‌های سلف دارک — صفحه ۸ از ۹ (قابلیت‌های ۳۶ تا ۴۰)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "3️⃣6️⃣ <b>۳۶. خوش‌آمدگویی خودکار در گروه‌ها:</b>\n"
        "• <b>کارکرد:</b> ارسال خودکار پیام خوش‌آمدگویی به محض عضو شدن یا اد شدن نفر جدید در گروه.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۳۶ را روشن کنید و از «⚙️ تنظیم مقدار» متن خوش‌آمدگویی دلخواه خود را وارد نمایید.\n\n"
        "3️⃣7️⃣ <b>۳۷. ماشین‌حساب سریع در چت:</b>\n"
        "• <b>کارکرد:</b> محاسبه آنی عبارات ریاضی مستقیماً داخل پیام تلگرام.\n"
        "• <b>نحوه استفاده دقیق:</b> در هر چتی بنویسید <code>.calc عبارت</code> (مثال: <code>.calc (450*12)+800</code>) تا نتیجه دقیق جایگزین پیام شود.\n\n"
        "3️⃣8️⃣ <b>۳۸. ساخت فونت انگلیسی و زیباسازی متن:</b>\n"
        "• <b>کارکرد:</b> تبدیل متن انگلیسی و اعداد به فونت خاص و ضخیم دارک (<code>𝗦𝗲𝗹𝗳 𝗗𝗮𝗿𝗸 𝟮𝟬𝟮۶</code>).\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۳۸ را روشن کرده و بنویسید <code>.font متن شما</code> (مثال: <code>.font Self Dark VIP</code>).\n\n"
        "3️⃣9️⃣ <b>۳۹. شکارچی تگ و منشن در گروه‌ها:</b>\n"
        "• <b>کارکرد:</b> ذخیره تمام پیام‌هایی که در گروه‌ها شما را تگ یا ریپلای کرده‌اند (بدون ارسال پیام مزاحم در Saved Messages).\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۳۹ را روشن بگذارید و هر زمان خواستید لیست تگ‌ها را ببینید دستور <code>.mentions</code> را ارسال کنید.\n\n"
        "4️⃣0️⃣ <b>۴۰. پاکسازی سریع پیام‌ها (Purge):</b>\n"
        "• <b>کارکرد:</b> حذف گروهی و سریع پیام‌های ارسالی خودتان در هر پیوی یا گروه.\n"
        "• <b>نحوه استفاده دقیق:</b> قابلیت ۴۰ را روشن کنید و بنویسید <code>.del [تعداد]</code> (مثال: <code>.del 20</code> برای پاک کردن ۲۰ پیام آخر خودتان در یک ثانیه)."
    ),
    # صفحه ۹ (قابلیت‌های ۴۱ تا ۴۶)
    (
        "📖 <b>توضیحات کامل قابلیت‌های سلف دارک — صفحه ۹ از ۹ (قابلیت‌های ۴۱ تا ۴۶)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "4️⃣1️⃣ <b>۴۱. کامنت اول خودکار کانال (با امضای Self Dark):</b>\n"
        "• <b>کارکرد:</b> به محض اینکه پست جدیدی در کانال گذاشته شود، اکانت شما در کسری از ثانیه اولین کامنت را زیر پست ثبت می‌کند!\n"
        "• <b>نحوه استفاده دقیق:</b> از «⚙️ تنظیم مقدار» جلوی قابلیت ۴۱ می‌توانید کلمه کامنت اول را تغییر دهید (پیش‌فرض: <code>کامنت اول</code>). سپس وارد <b>گروه چت متصل به آن کانال</b> شوید و عبارت <code>تنظیم کامنت اول</code> را بفرستید (برای لغو در آن گروه: <code>حذف کامنت اول</code>).\n\n"
        "4️⃣2️⃣ <b>۴۲. عضویت اجباری پیوی با دکمه شیشه‌ای (حداکثر ۳ کانال):</b>\n"
        "• <b>کارکرد:</b> قفل کردن پیوی روی حداکثر ۳ کانال شما به صورت دکمه شیشه‌ای:\n"
        "  🔹 <b>پیام اول شخص:</b> اگر کسی تا حالا به شما پیام نداده باشد و اولین پیامش را بفرستد، پیام اولش حذف نمی‌شود بلکه سلف دارک <b>روی پیامش ریپلای می‌زند</b> و با دکمه‌های شیشه‌ای می‌گوید باید عضو کانال‌ها شوی.\n"
        "  🔹 <b>پیام دوم به بعد (یا اگر از قبل پیام داده بود):</b> پیام شخص را <b>بلافاصله پاک می‌کند</b> و دکمه‌های شیشه‌ای عضویت و بررسی عضویت را می‌فرستد!\n"
        "• <b>نحوه استفاده دقیق:</b> روی «🛡 عضویت اجباری پیوی» بزنید، ربات را در کانال خود ادمین کنید و آیدی کانال را ثبت نمایید.\n\n"
        "4️⃣3️⃣ <b>۴۳. ساخت قرعه‌کشی هوشمند برای کانال:</b>\n"
        "• <b>کارکرد و استفاده:</b> روی گزینه ۴۳ کلیک کنید؛ نام قرعه‌کشی، حداقل/حداکثر نفرات، کانال‌های جوین اجباری (تا ۱۰ کانال)، توضیحات، زمان پایان (به ساعت یا دقیقه)، تعداد برنده‌ها و کانال مقصد را بدهید و <b>«🚀 پست کردن در کانال»</b> را بزنید. بنر با دکمه شیشه‌ای سبز (شمارنده زنده نفرات) و دکمه آبی («🎁 شرکت در قرعه‌کشی») پست شده و سر ساعت خودکار قرعه‌کشی و اعلام برنده می‌شود!\n\n"
        "4️⃣4️⃣ <b>۴۴. ساخت دکمه شیشه‌ای رنگی برای کانال:</b>\n"
        "• <b>کارکرد و استفاده:</b> روی گزینه ۴۴ کلیک کنید؛ پست (عکس/ویدیو/گیف/فایل/متن)، لینک دکمه، نام دکمه، رنگ دکمه (<b>آبی، سبز، قرمز یا معمولی شیشه‌ای</b>) و کانال مقصد را بدهید تا در کانال پست شود.\n\n"
        "4️⃣5️⃣ <b>۴۵. ساخت چالش لایکی برای کانال (با شرط عضویت در کانال):</b>\n"
        "• <b>کارکرد:</b> ارسال اسم شرکت‌کنندگان در کانال به همراه دکمه شیشه‌ای لایک (<code>❤️</code>) و شمارنده زنده لایک‌ها.\n"
        "• <b>نحوه استفاده دقیق:</b> در بخش قابلیت‌های سلف روی <b>«❤️ ساخت چالش لایکی کانال»</b> (گزینه ۴۵) بزنید؛ ابتدا لینک یا آیدی کانالی که می‌خواهید چالش در آن ارسال شود را بفرستید (ربات باید در کانال ادمین باشد). سپس هر چند تا اسم که می‌خواهید بفرستید تا هر اسم با دکمه شیشه‌ای لایک در کانال پست شود! کاربران برای لایک کردن <b>حتماً باید عضو همان کانال باشند</b> وگرنه لایک آن‌ها حساب نمی‌شود؛ همچنین با یک بار زدن لایک ثبت شده و اگر دوباره روی دکمه بزنند لایکشان پس گرفته می‌شود.\n\n"
        "4️⃣6️⃣ <b>۴۶. پنل مرکزی (گزارش ۲۴ ساعت گذشته اکانت):</b>\n"
        "• <b>کارکرد و استفاده:</b> آخرین قابلیت سلف دارک؛ با کلیک روی آن در ربات (یا ارسال دستور <code>.پنل مرکزی</code> در چت)، آمار دقیق تمام پیام‌های شما در گروه‌ها، پیوی‌ها، ربات‌های استارت‌شده، کامنت‌های اول و فعالیت‌های ۲۴ ساعت اخیر نمایش داده می‌شود."
    ),
]

def build_features_guide_keyboard(current_page: int = 0) -> InlineKeyboardMarkup:
    total_pages = len(SELF_FEATURES_GUIDE_PAGES)
    current_page = max(0, min(current_page, total_pages - 1))

    rows = []
    # ردیف دکمه‌های قبل و بعد
    nav_row = []
    if current_page > 0:
        nav_row.append(p_btn("⬅️ صفحه قبل", callback_data=f"self:features_guide:{current_page - 1}", style="primary"))
    nav_row.append(p_btn(f"📄 صفحه {current_page + 1} از {total_pages}", callback_data="noop", style="success", emoji_key="sparkles"))
    if current_page < total_pages - 1:
        nav_row.append(p_btn("صفحه بعد ➡️", callback_data=f"self:features_guide:{current_page + 1}", style="primary"))
    rows.append(nav_row)

    # دکمه‌های دسترسی سریع به هر ۹ صفحه
    page_labels = [
        (0, "۱ تا ۵"),
        (1, "۶ تا ۱۰"),
        (2, "۱۱ تا ۱۵"),
        (3, "۱۶ تا ۲۰"),
        (4, "۲۱ تا ۲۵"),
        (5, "۲۶ تا ۳۰"),
        (6, "۳۱ تا ۳۵"),
        (7, "۳۶ تا ۴۰"),
        (8, "۴۱ تا ۴۶"),
    ]
    for i in range(0, len(page_labels), 3):
        chunk = page_labels[i : i + 3]
        r = []
        for p_idx, lbl in chunk:
            st = "success" if p_idx == current_page else "primary"
            prefix = "🟢 " if p_idx == current_page else "📖 "
            r.append(p_btn(f"{prefix}قابلیت {lbl}", callback_data=f"self:features_guide:{p_idx}", style=st))
        rows.append(r)

    rows.append([
        p_btn("⚙️ ورود به مدیریت ۴۶ قابلیت سلف", callback_data="self:features_page:0", style="success", emoji_key="sparkles"),
    ])
    rows.append([
        p_btn("🚀 بخش فعال‌سازی و وضعیت سلف", callback_data="menu:activate_self", style="primary", emoji_key="rocket"),
        p_btn("🏠 منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire"),
    ])
    return InlineKeyboardMarkup(rows)

async def self_features_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    if data.startswith("self:features_guide:"):
        page = int(data.split(":")[2])
        page = max(0, min(page, len(SELF_FEATURES_GUIDE_PAGES) - 1))
        await query.answer(f"📖 صفحه {page + 1} از {len(SELF_FEATURES_GUIDE_PAGES)} توضیحات قابلیت‌ها")
        await query.edit_message_text(
            p_text(SELF_FEATURES_GUIDE_PAGES[page]),
            parse_mode=ParseMode.HTML,
            reply_markup=build_features_guide_keyboard(page)
        )
        return

    if data.startswith("self:features_page:"):
        page = int(data.split(":")[2])
        await query.answer()
        await query.edit_message_text(
            p_text(
                "🌑 <b>پنل تنظیمات ۴۵ قابلیت «سلف دارک | Self Dark»</b>\n\n"
                "✨ روی هر قابلیت کلیک کنید تا <b>🟢 روشن</b> یا <b>🔴 خاموش</b> شود.\n"
                "📖 برای مشاهده آموزش کامل و دقیق نحوه استفاده از تک‌تک ۴۵ قابلیت (مثل تبدیل ویس به متن، کامنت اول، عضویت اجباری پیوی و...) روی دکمه سبز <b>«📖 توضیحات قابلیت‌ها»</b> در بالا کلیک کنید:"
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
            if SELF_DARK_FEATURES[k].get("type") != "action_only":
                feats[k] = (mode == "on")
        save_user_features(user.id, feats)
        await query.answer("✅ وضعیت تمام قابلیت‌های سلف دارک بروزرسانی شد!", show_alert=True)
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
                f"📖 از دکمه <b>«توضیحات قابلیت‌ها»</b> می‌توانید آموزش کامل و دقیق نحوه استفاده از تمامی <b>۴۵ قابلیت سلف دارک</b> را در ۹ صفحه مطالعه کنید یا قابلیت‌ها را مدیریت نمایید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [p_btn("⚙️ مدیریت ۴۵ قابلیت سلف دارک", callback_data="self:features_page:0", style="primary", emoji_key="sparkles")],
                [p_btn("📖 توضیحات قابلیت‌ها (آموزش کامل ۴۵ قابلیت)", callback_data="self:features_guide:0", style="success", emoji_key="zap")],
                [
                    p_btn("📣 تبچی هوشمند", callback_data="menu:tabchi", style="primary", emoji_key="megaphone"),
                    p_btn("📊 پنل مرکزی ۲۴ ساعته", callback_data="self:central_panel", style="primary", emoji_key="crown"),
                ],
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
    # ارسال پیام تبریک به کاربر همراه با دکمه توضیحات کامل ۴۵ قابلیت
    await target_msg.reply_text(
        p_text(
            f"🎉 <b>تبریک! «سلف دارک | Self Dark» با موفقیت روی اکانت شما فعال شد!</b>\n\n"
            f"📱 شماره متصل: <code>{phone}</code>\n"
            f"💎 هزینه کسر شده فعال‌سازی: <b>{act_cost} الماس</b> (ساعتی {hr_cost} الماس)\n\n"
            f"✨ هم‌اکنون می‌توانید از دکمه‌های زیر <b>۴۵ قابلیت سلف دارک</b> را شخصی‌سازی کنید و در بخش <b>«📖 توضیحات قابلیت‌ها»</b> نحوه استفاده دقیق از تک‌تک ۴۵ قابلیت را مشاهده نمایید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [p_btn("⚙️ مدیریت ۴۵ قابلیت سلف دارک", callback_data="self:features_page:0", style="primary", emoji_key="sparkles")],
            [p_btn("📖 توضیحات قابلیت‌ها (آموزش کامل ۴۵ قابلیت)", callback_data="self:features_guide:0", style="success", emoji_key="zap")],
            [p_btn("📣 مدیریت تبچی هوشمند سلف دارک", callback_data="menu:tabchi", style="success", emoji_key="megaphone")],
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
    code_input = (update.message.text or "").strip()
    with closing(get_conn()) as conn, conn:
        g = conn.execute("SELECT * FROM gift_codes WHERE LOWER(code)=LOWER(?)", (code_input,)).fetchone()
        if not g:
            await update.message.reply_text(
                p_text("❌ کد هدیه وارد شده وجود ندارد یا پس از تکمیل ظرفیت منقضی شده است."),
                parse_mode=ParseMode.HTML,
                reply_markup=main_inline_keyboard(user.id)
            )
            return ConversationHandler.END

        actual_code = g["code"]
        if g["used_count"] >= g["max_uses"]:
            conn.execute("DELETE FROM gift_codes WHERE code=?", (actual_code,))
            await update.message.reply_text(
                p_text("❌ ظرفیت استفاده از این کد هدیه تکمیل شده و کد به صورت خودکار منقضی گردیده است."),
                parse_mode=ParseMode.HTML,
                reply_markup=main_inline_keyboard(user.id)
            )
            return ConversationHandler.END

        already = conn.execute("SELECT 1 FROM gift_uses WHERE LOWER(code)=LOWER(?) AND user_id=?", (actual_code, user.id)).fetchone()
        if already:
            await update.message.reply_text(
                p_text("⚠️ شما قبلاً از این کد هدیه استفاده کرده‌اید!"),
                parse_mode=ParseMode.HTML,
                reply_markup=main_inline_keyboard(user.id)
            )
            return ConversationHandler.END

        new_used = g["used_count"] + 1
        max_cap = g["max_uses"]
        reward_diamonds = g["diamonds"]

        conn.execute("INSERT INTO gift_uses (code, user_id) VALUES (?, ?)", (actual_code, user.id))
        conn.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id=?", (reward_diamonds, user.id))

        if new_used >= max_cap:
            # به محض رسیدن به سقف ظرفیت (مثلاً ۵ یا ۱۰ نفر)، کد هدیه خودکار منقضی و حذف می‌شود
            conn.execute("DELETE FROM gift_codes WHERE code=?", (actual_code,))
            cap_note = f"🔒 ظرفیت این کد هدیه (<b>{max_cap} از {max_cap} نفر</b>) تکمیل شد و کد منقضی گردید."
        else:
            conn.execute("UPDATE gift_codes SET used_count = ? WHERE code=?", (new_used, actual_code))
            cap_note = f"👥 ظرفیت باقی‌مانده کد: <b>{max_cap - new_used} نفر</b> (استفاده شده: {new_used}/{max_cap})"

    updated_u = get_or_create_user(user.id)
    await update.message.reply_text(
        p_text(
            f"🎉 <b>تبریک! کد هدیه <code>{html.escape(actual_code)}</code> با موفقیت اعمال شد!</b>\n\n"
            f"💎 مقدار هدیه: <b>+{reward_diamonds:,} الماس</b>\n"
            f"💰 موجودی جدید شما: <b>{updated_u['diamonds']:,} الماس</b>\n"
            f"{cap_note}"
        ),
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
    min_fee, min_total_needed = calc_transfer_fee(min_tr)

    if db_user["diamonds"] < min_total_needed and not is_admin(user.id):
        await query.answer(f"⚠️ با احتساب ۱۰٪ کارمزد، حداقل به {min_total_needed} الماس نیاز دارید!", show_alert=True)
        await query.edit_message_text(
            p_text(
                f"💎 <b>انتقال الماس به سایر کاربران (با ۱۰٪ کارمزد)</b>\n\n"
                f"⚠️ موجودی فعلی شما: <b>{db_user['diamonds']} الماس</b>\n"
                f"🔢 حداقل الماس قابل انتقال: <b>{min_tr} الماس</b> (+{min_fee} الماس کارمزد ۱۰٪ = <b>{min_total_needed} الماس</b>)\n\n"
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
            f"🔢 حداقل تعداد قابل انتقال: <b>{min_tr} الماس</b>\n"
            f"💸 کارمزد انتقال: <b>۱۰ درصد</b> (از حساب انتقال‌دهنده کسر می‌شود)\n\n"
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
            f"💰 موجودی شما: <b>{db_user['diamonds']} الماس</b>\n"
            f"🔢 حداقل انتقال مجاز: <b>{min_tr} الماس</b> (کارمزد: <b>۱۰٪</b>)\n\n"
            f"👇 لطفاً <b>تعداد الماسی</b> که می‌خواهید به گیرنده برسد را وارد کنید (حداقل <code>{min_tr}</code>):"
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

    fee, total_deduct = calc_transfer_fee(amount)
    db_user = get_or_create_user(user.id, user.username, user.first_name)
    if db_user["diamonds"] < total_deduct:
        await update.message.reply_text(
            p_text(
                f"❌ موجودی شما با احتساب ۱۰٪ کارمزد کافی نیست!\n\n"
                f"💎 مبلغ انتقال به گیرنده: <b>{amount:,} الماس</b>\n"
                f"💸 کارمزد انتقال (۱۰٪): <b>{fee:,} الماس</b>\n"
                f"🔢 مجموع قابل کسر از شما: <b>{total_deduct:,} الماس</b>\n"
                f"💰 موجودی فعلی شما: <b>{db_user['diamonds']:,} الماس</b>\n\n"
                f"لطفاً مقدار کمتری وارد کنید یا ابتدا حساب خود را شارژ نمایید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:main")
        )
        return TRANSFER_WAIT_AMOUNT

    # تضمین وجود رکورد گیرنده در دیتابیس و انتقال آنی الماس با کسر ۱۰٪ کارمزد از فرستنده
    get_or_create_user(target_id)
    add_user_diamonds(user.id, -total_deduct)
    add_user_diamonds(target_id, amount)

    updated_sender = get_or_create_user(user.id)
    updated_receiver = get_or_create_user(target_id)
    context.user_data.pop("transfer_target_id", None)

    # اطلاع‌رسانی به گیرنده الماس در ربات
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
            f"💎 مقدار واریزشده به گیرنده: <b>{amount:,} الماس</b>\n"
            f"💸 کارمزد انتقال (۱۰٪): <b>{fee:,} الماس</b>\n"
            f"➖ مجموع کسر شده از شما: <b>{total_deduct:,} الماس</b>\n"
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

    # ۲۴. هدیه الماس همگانی با متن دلخواه (مرحله ۱ از ۲)
    elif act == "adm:24":
        await query.edit_message_text(
            p_text(
                "🎉 <b>هدیه الماس همگانی با متن دلخواه (مرحله ۱ از ۲: تعداد الماس)</b>\n\n"
                "💎 لطفاً <b>تعداد الماسی</b> که می‌خواهید به حساب <b>تمام اعضای ربات</b> اضافه شود را به صورت عدد وارد کنید:\n"
                "<i>(مثال: <code>20</code> یا <code>50</code>)</i>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_PUBLIC_DIAMOND_AMOUNT

    # ۲۵. ساخت کد هدیه مرحله‌ای (مرحله ۱ از ۳: کلمه کد به انگلیسی)
    elif act == "adm:25":
        await query.edit_message_text(
            p_text(
                "🎁 <b>ساخت کد هدیه الماس (مرحله ۱ از ۳: کلمه کد هدیه)</b>\n\n"
                "🔤 لطفاً <b>کلمه کد هدیه را به انگلیسی</b> وارد کنید:\n"
                "<i>(مثال: <code>DARK50</code> یا <code>VIPGIFT</code>)</i>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_GIFT_WORD

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
            txt = "🎁 هیچ کد هدیه فعالی وجود ندارد."
        else:
            txt = "🎁 <b>لیست کدهای هدیه فعال:</b>\n\n" + "\n".join(
                [f"• کد: <code>{html.escape(c['code'])}</code> | هدیه: <b>{c['diamonds']} الماس</b> | ظرفیت: <b>{c['used_count']}/{c['max_uses']} نفر</b> (باقی‌مانده: {max(0, c['max_uses'] - c['used_count'])} نفر)" for c in codes]
            )
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

# ---- مراحل الماس همگانی با متن دلخواه (۲ مرحله‌ای) ----
async def admin_public_diamond_step1_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = context.user_data.get("adm_page", 0)
    raw_num = normalize_digits((update.message.text or "").strip())
    if not raw_num.isdigit() or int(raw_num) <= 0:
        await update.message.reply_text(
            p_text("⚠️ لطفاً یک عدد صحیح بزرگ‌تر از صفر برای تعداد الماس همگانی وارد کنید (مثلاً <code>25</code>):"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_PUBLIC_DIAMOND_AMOUNT

    amt = int(raw_num)
    context.user_data["pub_diamond_amt"] = amt
    await update.message.reply_text(
        p_text(
            f"📝 <b>هدیه الماس همگانی با متن دلخواه (مرحله ۲ از ۲: متن پیام)</b>\n\n"
            f"💎 تعداد الماس انتخابی برای هر نفر: <b>{amt:,} الماس</b>\n\n"
            f"👇 حالا <b>متن دلخواه خود</b> را بفرستید تا به همراه اطلاعیه دریافت <b>{amt:,} الماس</b> برای تمام اعضای ربات ارسال شود:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
    )
    return ADM_WAIT_PUBLIC_DIAMOND_TEXT

async def admin_public_diamond_step2_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = context.user_data.get("adm_page", 0)
    amt = int(context.user_data.get("pub_diamond_amt", 0))
    custom_text = (update.message.text or update.message.caption or "").strip()

    if amt <= 0 or not custom_text:
        await update.message.reply_text(
            p_text("⚠️ لطفاً متن پیام دلخواه را ارسال کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_PUBLIC_DIAMOND_TEXT

    with closing(get_conn()) as conn, conn:
        conn.execute("UPDATE users SET diamonds = diamonds + ?", (amt,))
        users = conn.execute("SELECT user_id, diamonds FROM users").fetchall()

    st_msg = await update.message.reply_text(
        p_text(f"⏳ در حال اهدای <b>{amt:,} الماس</b> و ارسال متن دلخواه شما به <b>{len(users):,} کاربر</b>..."),
        parse_mode=ParseMode.HTML
    )

    sent, failed = 0, 0
    for u in users:
        try:
            notify_txt = p_text(
                f"🎉 <b>هدیه الماس همگانی از طرف مدیریت سلف دارک!</b>\n\n"
                f"💬 <b>پیام مدیریت:</b>\n{html.escape(custom_text)}\n\n"
                f"💎 مقدار هدیه اضافه شده: <b>+{amt:,} الماس</b>\n"
                f"💰 موجودی جدید شما: <b>{u['diamonds']:,} الماس</b>"
            )
            await context.bot.send_message(
                chat_id=u["user_id"],
                text=notify_txt,
                parse_mode=ParseMode.HTML,
                reply_markup=main_inline_keyboard(u["user_id"])
            )
            sent += 1
        except Exception:
            failed += 1

    context.user_data.pop("pub_diamond_amt", None)
    await st_msg.edit_text(
        p_text(
            f"✅ <b>الماس همگانی با متن دلخواه با موفقیت به کل اعضای ربات اهدا شد!</b>\n\n"
            f"💎 مقدار اضافه شده به هر کاربر: <b>+{amt:,} الماس</b>\n"
            f"👥 کل کاربران شارژ شده در دیتابیس: <b>{len(users):,} نفر</b>\n"
            f"🟢 پیام ارسال‌شده موفق: <b>{sent:,} نفر</b> | 🔴 مسدود/ناموفق: <b>{failed:,} نفر</b>\n\n"
            f"📝 <b>متن ارسال شده:</b>\n{html.escape(custom_text)}"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=build_admin_keyboard(page)
    )
    return ConversationHandler.END

# ---- مراحل ساخت کد هدیه الماس (۳ مرحله‌ای: کلمه انگلیسی -> تعداد الماس -> ظرفیت استفاده) ----
async def admin_gift_code_step1_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = context.user_data.get("adm_page", 0)
    word = (update.message.text or "").strip()

    if not re.match(r"^[A-Za-z0-9_-]{2,40}$", word):
        await update.message.reply_text(
            p_text(
                "⚠️ <b>کلمه کد هدیه باید به انگلیسی باشد!</b>\n"
                "لطفاً فقط از حروف انگلیسی و اعداد (بدون فاصله) استفاده کنید (مثال: <code>DARK50</code> یا <code>GIFT100</code>):"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_GIFT_WORD

    context.user_data["new_gift_word"] = word
    await update.message.reply_text(
        p_text(
            f"💎 <b>ساخت کد هدیه الماس (مرحله ۲ از ۳: تعداد الماس هدیه)</b>\n\n"
            f"🔤 کد انتخابی: <code>{html.escape(word)}</code>\n\n"
            f"👇 حالا <b>تعداد الماس هدیه</b> که با زدن این کد به هر کاربر داده شود را به صورت عدد وارد کنید:\n"
            f"<i>(مثال: <code>30</code> یا <code>100</code>)</i>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
    )
    return ADM_WAIT_GIFT_DIAMONDS

async def admin_gift_code_step2_diamonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = context.user_data.get("adm_page", 0)
    raw_dia = normalize_digits((update.message.text or "").strip())

    if not raw_dia.isdigit() or int(raw_dia) <= 0:
        await update.message.reply_text(
            p_text("⚠️ لطفاً یک عدد صحیح بزرگ‌تر از صفر برای تعداد الماس هدیه وارد کنید (مثلاً <code>50</code>):"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_GIFT_DIAMONDS

    diamonds = int(raw_dia)
    context.user_data["new_gift_diamonds"] = diamonds
    word = context.user_data.get("new_gift_word", "")

    await update.message.reply_text(
        p_text(
            f"👥 <b>ساخت کد هدیه الماس (مرحله ۳ از ۳: ظرفیت کد هدیه)</b>\n\n"
            f"🔤 کد هدیه: <code>{html.escape(word)}</code>\n"
            f"💎 تعداد الماس هر نفر: <b>{diamonds:,} الماس</b>\n\n"
            f"👇 حالا <b>ظرفیت کد هدیه</b> (تعداد نفراتی که می‌توانند از این کد استفاده کنند، مثلاً <code>5</code> یا <code>10</code> نفر) را وارد کنید تا پس از تکمیل ظرفیت، کد به صورت خودکار منقضی شود:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
    )
    return ADM_WAIT_GIFT_CAPACITY

async def admin_gift_code_step3_capacity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = context.user_data.get("adm_page", 0)
    raw_cap = normalize_digits((update.message.text or "").strip())

    if not raw_cap.isdigit() or int(raw_cap) <= 0:
        await update.message.reply_text(
            p_text("⚠️ لطفاً یک عدد صحیح بزرگ‌تر از صفر برای ظرفیت نفرات وارد کنید (مثلاً <code>5</code> یا <code>10</code>):"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard(f"admin:page:{page}")
        )
        return ADM_WAIT_GIFT_CAPACITY

    capacity = int(raw_cap)
    word = context.user_data.pop("new_gift_word", "")
    diamonds = int(context.user_data.pop("new_gift_diamonds", 0))

    with closing(get_conn()) as conn, conn:
        conn.execute("DELETE FROM gift_uses WHERE LOWER(code)=LOWER(?)", (word,))
        conn.execute("DELETE FROM gift_codes WHERE LOWER(code)=LOWER(?)", (word,))
        conn.execute(
            "INSERT INTO gift_codes (code, diamonds, max_uses, used_count) VALUES (?, ?, ?, 0)",
            (word, diamonds, capacity)
        )

    await update.message.reply_text(
        p_text(
            f"🎁 <b>کد هدیه جدید با موفقیت ساخته و فعال شد!</b>\n\n"
            f"🔤 کد هدیه: <code>{html.escape(word)}</code>\n"
            f"💎 مقدار هدیه به هر نفر: <b>{diamonds:,} الماس</b>\n"
            f"👥 ظرفیت کل استفاده: <b>{capacity} نفر</b>\n"
            f"⏳ وضعیت انقضا: <b>به محض استفاده {capacity} نفر، به صورت خودکار منقضی و غیرفعال می‌شود.</b>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=build_admin_keyboard(page)
    )
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
#  ۱. سیستم تیکتینگ پشتیبانی (ثبت تیکت توسط کاربر و پاسخ توسط ادمین)
# ====================================================================

async def support_ticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    with closing(get_conn()) as conn:
        open_t = conn.execute(
            "SELECT id, created_at FROM tickets WHERE user_id=? AND status='open'",
            (user.id,)
        ).fetchone()

    if open_t:
        await query.answer(
            f"⚠️ شما یک تیکت باز (#{open_t['id']}) دارید! تا زمانی که ادمین به تیکت قبلی شما پاسخ ندهد نمی‌توانید تیکت جدید ثبت کنید.",
            show_alert=True
        )
        return ConversationHandler.END

    await query.answer()
    await query.edit_message_text(
        p_text(
            "📩 <b>ثبت تیکت جدید در پشتیبانی سلف دارک</b>\n\n"
            "✍️ لطفاً مشکل، سوال یا درخواست خود را به صورت کامل در یک پیام بنویسید و ارسال کنید:\n"
            "<i>(تیکت شما مستقیماً برای مدیریت ربات ارسال می‌شود و به محض پاسخگویی، در همینجا به شما اطلاع داده خواهد شد)</i>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("menu:support")
    )
    return TICKET_WAIT_MESSAGE

async def support_ticket_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg_text = (update.message.text or update.message.caption or "").strip()

    if not msg_text:
        await update.message.reply_text(
            p_text("⚠️ لطفاً متن پیام تیکت خود را ارسال کنید:"),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("menu:support")
        )
        return TICKET_WAIT_MESSAGE

    with closing(get_conn()) as conn, conn:
        open_t = conn.execute(
            "SELECT id FROM tickets WHERE user_id=? AND status='open'",
            (user.id,)
        ).fetchone()
        if open_t:
            await update.message.reply_text(
                p_text(f"⚠️ شما یک تیکت باز (#{open_t['id']}) در انتظار پاسخ دارید و تا زمان پاسخ ادمین نمی‌توانید تیکت دیگری ثبت کنید."),
                parse_mode=ParseMode.HTML,
                reply_markup=main_inline_keyboard(user.id)
            )
            return ConversationHandler.END

        cur = conn.execute(
            "INSERT INTO tickets (user_id, message_text, status, created_at) VALUES (?, ?, 'open', ?)",
            (user.id, msg_text, datetime.now().isoformat())
        )
        ticket_id = cur.lastrowid

    # ارسال تیکت برای ادمین ربات با دکمه پاسخگویی مستقیم
    adm_text = p_text(
        f"📩 <b>تیکت پشتیبانی جدید (#{ticket_id})</b>\n\n"
        f"👤 کاربر: <b>{html.escape(user.first_name)}</b> (@{user.username or 'ندارد'})\n"
        f"🔢 آیدی عددی: <code>{user.id}</code>\n"
        f"⏰ زمان ثبت: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n\n"
        f"💬 <b>متن تیکت کاربر:</b>\n{html.escape(msg_text)}"
    )
    adm_kb = InlineKeyboardMarkup([
        [p_btn(f"✍️ پاسخ به تیکت #{ticket_id}", callback_data=f"ticket_reply:{ticket_id}", style="success", emoji_key="sparkles")]
    ])
    for adm in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=adm, text=adm_text, parse_mode=ParseMode.HTML, reply_markup=adm_kb)
        except Exception as e:
            logger.warning(f"Ticket notify admin error: {e}")

    await update.message.reply_text(
        p_text(
            f"✅ <b>تیکت شما با شماره <code>#{ticket_id}</code> با موفقیت ثبت و برای مدیریت ارسال شد!</b>\n\n"
            f"⏳ لطفاً منتظر پاسخ مدیریت بمانید؛ تا زمان دریافت پاسخ این تیکت، امکان ثبت تیکت جدید وجود ندارد."
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )
    return ConversationHandler.END

async def admin_ticket_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ فقط ادمین اصلی دسترسی دارد!", show_alert=True)
        return ConversationHandler.END

    ticket_id = int(query.data.split(":")[1])
    with closing(get_conn()) as conn:
        t = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()

    if not t:
        await query.answer("❌ تیکت یافت نشد!", show_alert=True)
        return ConversationHandler.END

    context.user_data["reply_ticket_id"] = ticket_id
    await query.answer()
    await query.message.reply_text(
        p_text(
            f"✍️ <b>پاسخ به تیکت #{ticket_id} (کاربر <code>{t['user_id']}</code>)</b>\n\n"
            f"💬 متن تیکت کاربر:\n<i>{html.escape(t['message_text'][:300])}</i>\n\n"
            f"👇 لطفاً متن پاسخ خود را ارسال کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("admin:page:0")
    )
    return ADM_WAIT_TICKET_REPLY

async def admin_ticket_reply_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    ticket_id = context.user_data.get("reply_ticket_id")
    reply_txt = (update.message.text or update.message.caption or "").strip()
    if not ticket_id or not reply_txt:
        await update.message.reply_text(p_text("⚠️ لطفاً متن پاسخ را وارد کنید:"), parse_mode=ParseMode.HTML)
        return ADM_WAIT_TICKET_REPLY

    with closing(get_conn()) as conn, conn:
        t = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not t:
            await update.message.reply_text(p_text("❌ تیکت یافت نشد."), parse_mode=ParseMode.HTML)
            return ConversationHandler.END
        conn.execute(
            "UPDATE tickets SET status='answered', admin_reply=?, answered_at=? WHERE id=?",
            (reply_txt, datetime.now().isoformat(), ticket_id)
        )

    try:
        await context.bot.send_message(
            chat_id=t["user_id"],
            text=p_text(
                f"🎧 <b>پاسخ پشتیبانی به تیکت شما (#{ticket_id})</b>\n\n"
                f"❓ <b>تیکت شما:</b>\n<i>{html.escape(t['message_text'][:250])}</i>\n\n"
                f"✅ <b>پاسخ مدیریت:</b>\n{html.escape(reply_txt)}"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(t["user_id"])
        )
    except Exception:
        pass

    context.user_data.pop("reply_ticket_id", None)
    await update.message.reply_text(
        p_text(f"✅ پاسخ تیکت <b>#{ticket_id}</b> با موفقیت برای کاربر <code>{t['user_id']}</code> ارسال شد و وضعیت تیکت بسته شد."),
        parse_mode=ParseMode.HTML,
        reply_markup=build_admin_keyboard(0)
    )
    return ConversationHandler.END

# ====================================================================
#  ۲. پنل مرکزی (آخرین قابلیت سلف: گزارش کامل فعالیت ۲۴ ساعت گذشته اکانت)
# ====================================================================

async def central_panel_24h_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer("📊 در حال استخراج گزارش ۲۴ ساعت گذشته اکانت شما...")

    cutoff_iso = (datetime.now() - timedelta(hours=24)).isoformat()
    with closing(get_conn()) as conn:
        logs = conn.execute(
            "SELECT * FROM self_activity_logs WHERE user_id=? AND created_at >= ? ORDER BY id DESC",
            (user.id, cutoff_iso)
        ).fetchall()
        fc_cnt = conn.execute("SELECT COUNT(*) c FROM first_comment_groups WHERE user_id=?", (user.id,)).fetchone()["c"]
        pv_cnt = conn.execute("SELECT COUNT(*) c FROM pv_force_channels WHERE user_id=?", (user.id,)).fetchone()["c"]
        tb_cnt = conn.execute("SELECT COUNT(*) c FROM tabchi_groups WHERE user_id=?", (user.id,)).fetchone()["c"]

    group_out = [r for r in logs if r["action_type"] == "group_msg_out"]
    pv_out = [r for r in logs if r["action_type"] == "pv_msg_out"]
    pv_in = [r for r in logs if r["action_type"] == "pv_msg_in"]
    bot_starts = [r for r in logs if r["action_type"] == "bot_start"]
    bot_msgs = [r for r in logs if r["action_type"] == "bot_msg_out"]
    first_comms = [r for r in logs if r["action_type"] == "first_comment"]
    pv_blocks = [r for r in logs if r["action_type"] == "pv_force_block"]
    self_cmds = [r for r in logs if r["action_type"] == "self_cmd"]

    # لیست گروه‌هایی که کاربر در ۲۴ ساعت گذشته در آن‌ها پیام فرستاده
    unique_groups = []
    for r in group_out:
        if r["target_title"] and r["target_title"] not in unique_groups:
            unique_groups.append(r["target_title"])

    # لیست اشخاصی که کاربر در ۲۴ ساعت گذشته به آن‌ها پیام داده
    unique_pvs = []
    for r in pv_out:
        if r["target_title"] and r["target_title"] not in unique_pvs:
            unique_pvs.append(r["target_title"])

    # لیست ربات‌هایی که کاربر در ۲۴ ساعت گذشته استارت کرده یا تعامل داشته
    unique_bots = []
    for r in (bot_starts + bot_msgs):
        if r["target_title"] and r["target_title"] not in unique_bots:
            unique_bots.append(r["target_title"])

    grp_names_str = "، ".join([html.escape(x) for x in unique_groups[:5]]) if unique_groups else "ثبت نشده"
    pv_names_str = "، ".join([html.escape(x) for x in unique_pvs[:5]]) if unique_pvs else "ثبت نشده"
    bot_names_str = "، ".join([html.escape(x) for x in unique_bots[:6]]) if unique_bots else "هیچ رباتی استارت نشده"

    recent_lines = []
    for r in logs[:8]:
        try:
            t_str = datetime.fromisoformat(r["created_at"]).strftime("%H:%M")
        except Exception:
            t_str = "--:--"
        act_map = {
            "group_msg_out": "💬 پیام در گروه",
            "pv_msg_out": "📤 پیام به شخص",
            "pv_msg_in": "📥 دریافت پیام پیوی",
            "bot_start": "🤖 استارت ربات",
            "bot_msg_out": "🤖 پیام به ربات",
            "first_comment": "🥇 ثبت کامنت اول",
            "pv_force_block": "🛡 حذف پیام پیوی (جوین اجباری)",
            "self_cmd": "⚡ دستور سلف دارک",
        }
        lbl = act_map.get(r["action_type"], r["action_type"])
        recent_lines.append(f"• <code>{t_str}</code> | {lbl}: <b>{html.escape(r['target_title'] or '-')}</b>")

    recent_block = "\n".join(recent_lines) if recent_lines else "• هنوز فعالیتی در ۲۴ ساعت اخیر ثبت نشده است."

    text = p_text(
        f"👑 <b>پنل مرکزی سلف دارک (گزارش کامل ۲۴ ساعت گذشته اکانت)</b>\n\n"
        f"📊 <b>خلاصه تمام فعالیت‌های اکانت شما در ۲۴ ساعت اخیر:</b>\n"
        f"• 💬 پیام‌های ارسالی در گروه‌ها: <b>{len(group_out):,} پیام</b>\n"
        f"   └ گروه‌های فعال: <i>{grp_names_str}</i>\n"
        f"• 📤 پیام‌های ارسالی به اشخاص (پیوی): <b>{len(pv_out):,} پیام</b>\n"
        f"   └ مخاطبین: <i>{pv_names_str}</i>\n"
        f"• 📥 پیام‌های دریافتی از اشخاص در پیوی: <b>{len(pv_in):,} پیام</b>\n"
        f"• 🤖 استارت کردن ربات‌ها: <b>{len(bot_starts):,} بار</b> (کل پیام به ربات‌ها: <b>{len(bot_starts) + len(bot_msgs):,}</b>)\n"
        f"   └ ربات‌های تعامل‌شده: <i>{bot_names_str}</i>\n"
        f"• 🥇 کامنت‌های اول ارسال شده: <b>{len(first_comms):,} مورد</b> (گروه‌های ثبت‌شده: {fc_cnt})\n"
        f"• 🛡 پیام‌های مسدودشده عضویت اجباری پیوی: <b>{len(pv_blocks):,} مورد</b> (کانال‌های پیوی: {pv_cnt}/3)\n"
        f"• ⚡ دستورات اجراشده سلف دارک: <b>{len(self_cmds):,} دستور</b> | گروه‌های تبچی: <b>{tb_cnt}</b>\n\n"
        f"🕒 <b>آخرین فعالیت‌های ثبت‌شده در اکانت:</b>\n"
        f"{recent_block}"
    )
    kb = InlineKeyboardMarkup([
        [p_btn("🔄 بروزرسانی زنده گزارش ۲۴ ساعته", callback_data="self:central_panel", style="success", emoji_key="zap")],
        [p_btn("⬅️ بازگشت به قابلیت‌های سلف دارک", callback_data="self:features_page:4", style="primary", emoji_key="sparkles")],
        [p_btn("بازگشت به منوی اصلی", callback_data="menu:main", style="danger", emoji_key="fire")]
    ])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ====================================================================
#  ۳. عضویت اجباری پیوی (حداکثر تا ۳ کانال که ربات در آن‌ها ادمین است)
# ====================================================================

async def pv_force_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    if data.startswith("pvforce:del:"):
        del_id = int(data.split(":")[2])
        with closing(get_conn()) as conn, conn:
            conn.execute("DELETE FROM pv_force_channels WHERE id=? AND user_id=?", (del_id, user.id))
        await query.answer("🗑 کانال از عضویت اجباری پیوی شما حذف شد.", show_alert=True)
    elif data == "pvforce:toggle":
        feats = get_user_features(user.id)
        feats["f42"] = not feats.get("f42", False)
        save_user_features(user.id, feats)
        await query.answer("✅ وضعیت عضویت اجباری پیوی تغییر کرد.")
    else:
        await query.answer()

    feats = get_user_features(user.id)
    is_on = feats.get("f42", False)
    st_txt = "🟢 فعال و روشن" if is_on else "🔴 غیرفعال"

    with closing(get_conn()) as conn:
        chs = conn.execute("SELECT * FROM pv_force_channels WHERE user_id=? ORDER BY id ASC", (user.id,)).fetchall()

    ch_list_txt = (
        "\n".join([f"{i+1}. <b>{html.escape(c['title'])}</b> (<code>{c['channel_id']}</code>)" for i, c in enumerate(chs)])
        if chs else "⚠️ هنوز هیچ کانالی ثبت نکرده‌اید."
    )

    text = p_text(
        f"🛡 <b>مدیریت قابلیت «عضویت اجباری پیوی» (حداکثر ۳ کانال)</b>\n\n"
        f"⚡ وضعیت فعلی قابلیت: <b>{st_txt}</b>\n"
        f"📊 کانال‌های ثبت‌شده شما: <b>{len(chs)} از ۳ کانال</b>\n\n"
        f"📋 <b>لیست کانال‌های عضویت اجباری پیوی شما:</b>\n{ch_list_txt}\n\n"
        f"📌 <b>نحوه کارکرد هوشمند:</b>\n"
        f"1️⃣ <b>پیام اول شخص:</b> اگر کسی تا حالا به شما پیام نداده باشد و اولین پیامش را بفرستد، پیام اولش حذف نمی‌شود و سلف دارک <b>روی پیامش ریپلای می‌زند</b> و دکمه‌های شیشه‌ای عضویت در کانال‌ها را می‌فرستد.\n"
        f"2️⃣ <b>پیام دوم به بعد (یا اگر از قبل پیام داده بود):</b> پیام شخص را <b>بلافاصله پاک می‌کند</b> و دکمه‌های شیشه‌ای عضویت اجباری و بررسی عضویت را برایش ارسال می‌نماید!"
    )

    rows = [
        [
            p_btn(
                f"وضعیت عضویت اجباری پیوی: {st_txt}",
                callback_data="pvforce:toggle",
                style="success" if is_on else "danger",
                emoji_key="zap"
            )
        ]
    ]
    if len(chs) < 3:
        rows.append([p_btn("➕ افزودن کانال جدید (حداکثر ۳ کانال)", callback_data="pvforce:add", style="success", emoji_key="megaphone")])
    for c in chs:
        rows.append([p_btn(f"🗑 حذف کانال {c['title']}", callback_data=f"pvforce:del:{c['id']}", style="danger", emoji_key="fire")])

    rows.append([p_btn("⬅️ بازگشت به قابلیت‌های سلف دارک", callback_data="self:features_page:4", style="primary", emoji_key="sparkles")])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))

async def pv_force_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    with closing(get_conn()) as conn:
        cnt = conn.execute("SELECT COUNT(*) c FROM pv_force_channels WHERE user_id=?", (user.id,)).fetchone()["c"]

    if cnt >= 3:
        await query.answer("⚠️ شما حداکثر ۳ کانال مجاز خود را ثبت کرده‌اید! ابتدا یکی را حذف کنید.", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    await query.edit_message_text(
        p_text(
            "➕ <b>افزودن کانال به عضویت اجباری پیوی</b>\n\n"
            "⚠️ <b>نکته مهم:</b> ابتدا این ربات را در کانال مورد نظر خود <b>ادمین (Administrator)</b> کنید.\n"
            "👇 سپس یوزرنیم کانال با @ (مثلاً <code>@MyChannel</code>) یا لینک `https://t.me/...` یا آیدی عددی کانال را ارسال کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("pvforce:menu")
    )
    return PVFORCE_WAIT_CHANNEL

def normalize_channel_identifier(raw_input: str) -> str:
    s = (raw_input or "").strip()
    s = re.sub(r"^https?://t\.me/", "@", s)
    s = re.sub(r"^t\.me/", "@", s)
    if not s.startswith("@") and not s.startswith("-100") and not s.lstrip("-").isdigit():
        s = "@" + s
    return s

async def pv_force_add_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ch_identifier = normalize_channel_identifier(update.message.text or "")

    with closing(get_conn()) as conn:
        cnt = conn.execute("SELECT COUNT(*) c FROM pv_force_channels WHERE user_id=?", (user.id,)).fetchone()["c"]
    if cnt >= 3:
        await update.message.reply_text(p_text("⚠️ حداکثر ۳ کانال قابل ثبت است."), parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    try:
        bot_me = await context.bot.get_me()
        chat = await context.bot.get_chat(chat_id=ch_identifier)
        bot_member = await context.bot.get_chat_member(chat_id=chat.id, user_id=bot_me.id)
        if bot_member.status not in ("administrator", "creator"):
            await update.message.reply_text(
                p_text("❌ ربات در این کانال <b>ادمین</b> نیست! لطفاً ابتدا ربات را در کانال ادمین کنید و مجدداً آیدی کانال را بفرستید:"),
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_inline_keyboard("pvforce:menu")
            )
            return PVFORCE_WAIT_CHANNEL

        ch_title = chat.title or ch_identifier
        if chat.username:
            ch_link = f"https://t.me/{chat.username}"
            ch_id_store = f"@{chat.username}"
        else:
            ch_id_store = str(chat.id)
            ch_link = chat.invite_link or (await context.bot.export_chat_invite_link(chat.id))
    except Exception as e:
        await update.message.reply_text(
            p_text(
                f"❌ خطا در بررسی کانال! مطمئن شوید ربات در کانال <b>ادمین</b> است و آیدی را صحیح وارد کرده‌اید:\n"
                f"<code>{html.escape(str(e)[:100])}</code>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("pvforce:menu")
        )
        return PVFORCE_WAIT_CHANNEL

    with closing(get_conn()) as conn, conn:
        conn.execute(
            "INSERT OR REPLACE INTO pv_force_channels (user_id, channel_id, channel_link, title) VALUES (?, ?, ?, ?)",
            (user.id, ch_id_store, ch_link, ch_title)
        )

    feats = get_user_features(user.id)
    feats["f42"] = True
    save_user_features(user.id, feats)

    await update.message.reply_text(
        p_text(
            f"✅ <b>کانال «{html.escape(ch_title)}» با موفقیت به عضویت اجباری پیوی شما اضافه شد و قابلیت روشن گردید!</b>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [p_btn("🛡 بازگشت به مدیریت عضویت اجباری پیوی", callback_data="pvforce:menu", style="primary", emoji_key="zap")]
        ])
    )
    return ConversationHandler.END

async def inline_pv_force_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ به درخواست Inline سلف دارک برای ارسال مستقیم دکمه شیشه‌ای رنگی عضویت اجباری در پیوی"""
    iq = update.inline_query
    if not iq:
        return
    q_data = (iq.query or "").strip()
    if not q_data.startswith("pvforce:"):
        await iq.answer([], cache_time=0, is_personal=True)
        return

    parts = q_data.split(":")
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await iq.answer([], cache_time=0, is_personal=True)
        return

    owner_id = int(parts[1])
    sender_id = int(parts[2])
    is_first = (parts[3] == "1") if len(parts) >= 4 else False

    with closing(get_conn()) as conn:
        pv_chs = conn.execute("SELECT * FROM pv_force_channels WHERE user_id=? LIMIT 3", (owner_id,)).fetchall()

    if not pv_chs:
        await iq.answer([], cache_time=0, is_personal=True)
        return

    not_joined = []
    for pch in pv_chs:
        try:
            m = await context.bot.get_chat_member(chat_id=pch["channel_id"], user_id=sender_id)
            if m.status in ("left", "kicked"):
                not_joined.append(pch)
        except Exception:
            not_joined.append(pch)

    target_chs = not_joined if not_joined else pv_chs
    pv_rows = [
        [p_btn(f"📢 عضویت در {c['title']}", url=c["channel_link"], style="primary", emoji_key="megaphone")]
        for c in target_chs
    ]
    pv_rows.append([
        p_btn("✅ بررسی عضویت و باز کردن قفل پیوی", callback_data=f"pvcheck:{owner_id}", style="success", emoji_key="check")
    ])

    if is_first:
        msg_txt = p_text(
            "⚠️ <b>قفل عضویت اجباری پیوی فعال است!</b>\n\n"
            "👋 این اولین پیام شماست؛ برای اینکه بتوانید ادامه دهید و پیام‌های بعدی شما پاک نشود، ابتدا از طریق <b>دکمه‌های شیشه‌ای زیر</b> در کانال‌ها عضو شوید و سپس دکمه <b>«✅ بررسی عضویت»</b> را بزنید:"
        )
    else:
        msg_txt = p_text(
            "🚫 <b>پیام شما حذف شد! (قفل عضویت اجباری پیوی)</b>\n\n"
            "⚠️ برای پیام دادن به این کاربر ابتدا باید از طریق <b>دکمه‌های شیشه‌ای زیر</b> در کانال‌ها عضو شوید و سپس روی <b>«✅ بررسی عضویت»</b> کلیک کنید:"
        )

    article = InlineQueryResultArticle(
        id=f"pvforce_{owner_id}_{sender_id}_{int(time.time())}",
        title="🛡 قفل عضویت اجباری پیوی سلف دارک",
        description="ارسال دکمه‌های شیشه‌ای عضویت اجباری در پیوی",
        input_message_content=InputTextMessageContent(
            message_text=msg_txt,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        ),
        reply_markup=InlineKeyboardMarkup(pv_rows),
    )
    await iq.answer([article], cache_time=0, is_personal=True)

async def handle_pv_force_verify(update: Update, context: ContextTypes.DEFAULT_TYPE, user, owner_id: int, is_callback: bool = False):
    if is_callback and user.id == owner_id:
        await update.callback_query.answer("ℹ️ شما صاحب این پیوی هستید! این دکمه برای بررسی عضویت مخاطب شماست.", show_alert=True)
        return

    with closing(get_conn()) as conn:
        pv_chs = conn.execute("SELECT * FROM pv_force_channels WHERE user_id=? LIMIT 3", (owner_id,)).fetchall()

    not_joined = []
    for pch in pv_chs:
        try:
            m = await context.bot.get_chat_member(chat_id=pch["channel_id"], user_id=user.id)
            if m.status in ("left", "kicked"):
                not_joined.append(pch)
        except Exception:
            not_joined.append(pch)

    if not_joined:
        rows = [
            [p_btn(f"📢 عضویت در {c['title']}", url=c["channel_link"], style="primary", emoji_key="megaphone")]
            for c in not_joined
        ]
        rows.append([p_btn("✅ بررسی عضویت و باز کردن قفل پیوی", callback_data=f"pvcheck:{owner_id}", style="success", emoji_key="check")])
        msg_txt = p_text(
            "⚠️ <b>برای پیام دادن به این کاربر ابتدا باید در کانال‌های زیر عضو شوید و سپس دکمه «✅ بررسی عضویت» را بزنید:</b>"
        )
        if is_callback:
            await update.callback_query.answer("⚠️ هنوز در تمام کانال‌های مشخص‌شده عضو نشده‌اید!", show_alert=True)
            try:
                await update.callback_query.edit_message_text(msg_txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
            except Exception:
                pass
        else:
            await update.message.reply_text(msg_txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
    else:
        ok_txt = p_text(
            "✅ <b>عضویت شما در تمام کانال‌ها تایید شد!</b>\n"
            "🎉 اکنون قفل پیوی برای شما باز است و می‌توانید در پیوی به کاربر پیام دهید."
        )
        ok_kb = InlineKeyboardMarkup([
            [p_btn("🔓 عضویت تایید شد (قفل پیوی باز است)", callback_data="noop", style="success", emoji_key="check")]
        ])
        if is_callback:
            await update.callback_query.answer("✅ عضویت شما تایید شد! اکنون می‌توانید پیام دهید.", show_alert=True)
            try:
                await update.callback_query.edit_message_text(ok_txt, parse_mode=ParseMode.HTML, reply_markup=ok_kb)
            except Exception:
                pass
        else:
            await update.message.reply_text(ok_txt, parse_mode=ParseMode.HTML, reply_markup=main_inline_keyboard(user.id))

async def pv_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    owner_id = int(query.data.split(":")[1])
    await handle_pv_force_verify(update, context, query.from_user, owner_id, is_callback=True)

# ====================================================================
#  ۴. ساخت قرعه‌کشی هوشمند برای کانال (در بخش قابلیت‌های سلف)
# ====================================================================

def build_channel_lottery_post_text(lotto_data: dict, status_badge: str = "🟢 در حال برگزاری") -> str:
    min_p = lotto_data.get("min_participants", 0)
    max_p = lotto_data.get("max_participants", 0)
    min_str = f"{min_p} نفر" if min_p > 0 else "بدون حداقل"
    max_str = f"{max_p} نفر" if max_p > 0 else "بدون محدودیت"
    desc = lotto_data.get("description", "").strip()
    desc_block = f"\n📝 <b>توضیحات قرعه‌کشی:</b>\n{html.escape(desc)}\n" if desc else "\n"

    return p_text(
        f"🎁 <b>قرعه‌کشی بزرگ: {html.escape(lotto_data['title'])}</b>\n"
        f"{desc_block}\n"
        f"🏆 تعداد برندگان: <b>{lotto_data['winners_count']} نفر</b> (انتخاب کاملاً تصادفی)\n"
        f"👥 حداقل شرکت‌کننده: <b>{min_str}</b> | حداکثر ظرفیت: <b>{max_str}</b>\n"
        f"⏰ زمان پایان قرعه‌کشی: <code>{lotto_data.get('end_time_display', '')}</code>\n"
        f"📌 وضعیت: <b>{status_badge}</b>\n\n"
        f"👇 جهت شرکت در قرعه‌کشی روی دکمه شیشه‌ای آبی <b>«🎁 شرکت در قرعه‌کشی»</b> در زیر کلیک کنید:"
    )

def build_channel_lottery_keyboard(bot_username: str, lotto_id: int, participants_count: int) -> InlineKeyboardMarkup:
    join_url = f"https://t.me/{bot_username}?start=lotto_{lotto_id}"
    return InlineKeyboardMarkup([
        [
            p_btn(f"👥 تعداد شرکت‌کنندگان: {participants_count} نفر", callback_data=f"lottocnt:{lotto_id}", style="success", emoji_key="check")
        ],
        [
            p_btn("🎁 شرکت در قرعه‌کشی", url=join_url, style="primary", emoji_key="gift")
        ]
    ])

async def lotto_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["lotto_draft"] = {"force_channels": []}
    await query.edit_message_text(
        p_text(
            "🎁 <b>ساخت قرعه‌کشی هوشمند برای کانال (مرحله ۱ از ۸: نام قرعه‌کشی)</b>\n\n"
            "✨ لطفاً <b>نام قرعه‌کشی</b> را وارد کنید:\n"
            "<i>(مثال: <code>گیفت تلگرام</code> یا <code>قرعه‌کشی ۵۰۰ الماس</code>)</i>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("self:features_page:4")
    )
    return LOTTO_WAIT_TITLE

async def lotto_step1_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = (update.message.text or "").strip()
    if not title:
        await update.message.reply_text(p_text("⚠️ لطفاً نام قرعه‌کشی را وارد کنید:"), parse_mode=ParseMode.HTML)
        return LOTTO_WAIT_TITLE

    context.user_data.setdefault("lotto_draft", {})["title"] = title
    kb = InlineKeyboardMarkup([
        [p_btn("⏭ بدون حداقل شرکت‌کننده", callback_data="lotto:nomin", style="success", emoji_key="check")],
        [p_btn("انصراف و بازگشت", callback_data="self:features_page:4", style="danger", emoji_key="fire")]
    ])
    await update.message.reply_text(
        p_text(
            f"👥 <b>مرحله ۲ از ۸: حداقل تعداد شرکت‌کننده</b>\n\n"
            f"🎁 نام قرعه‌کشی: <b>{html.escape(title)}</b>\n\n"
            f"👇 لطفاً <b>حداقل تعداد شرکت‌کننده</b> را به صورت عدد وارد کنید (اگر به این تعداد نرسد قرعه‌کشی خودکار لغو می‌شود) یا روی دکمه <b>«بدون حداقل شرکت‌کننده»</b> بزنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    return LOTTO_WAIT_MIN

async def lotto_step2_min(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        min_p = 0
        send_fn = update.callback_query.edit_message_text
    else:
        raw_t = normalize_digits((update.message.text or "").strip())
        if not raw_t.isdigit():
            await update.message.reply_text(p_text("⚠️ لطفاً یک عدد صحیح وارد کنید یا دکمه «بدون حداقل» را بزنید:"), parse_mode=ParseMode.HTML)
            return LOTTO_WAIT_MIN
        min_p = int(raw_t)
        send_fn = update.message.reply_text

    context.user_data["lotto_draft"]["min_participants"] = min_p
    kb = InlineKeyboardMarkup([
        [p_btn("⏭ بدون حداکثر شرکت‌کننده", callback_data="lotto:nomax", style="success", emoji_key="check")],
        [p_btn("انصراف و بازگشت", callback_data="self:features_page:4", style="danger", emoji_key="fire")]
    ])
    await send_fn(
        p_text(
            "👥 <b>مرحله ۳ از ۸: حداکثر تعداد شرکت‌کننده</b>\n\n"
            "👇 لطفاً <b>حداکثر تعداد شرکت‌کننده</b> را به صورت عدد وارد کنید یا روی دکمه <b>«بدون حداکثر شرکت‌کننده»</b> کلیک کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    return LOTTO_WAIT_MAX

async def lotto_step3_max(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        max_p = 0
        send_fn = update.callback_query.edit_message_text
    else:
        raw_t = normalize_digits((update.message.text or "").strip())
        if not raw_t.isdigit():
            await update.message.reply_text(p_text("⚠️ لطفاً یک عدد صحیح وارد کنید یا دکمه «بدون حداکثر» را بزنید:"), parse_mode=ParseMode.HTML)
            return LOTTO_WAIT_MAX
        max_p = int(raw_t)
        send_fn = update.message.reply_text

    context.user_data["lotto_draft"]["max_participants"] = max_p
    context.user_data["lotto_draft"]["force_channels"] = []
    kb = InlineKeyboardMarkup([
        [p_btn("⏭ بدون کانال جوین اجباری", callback_data="lotto:fch_done", style="success", emoji_key="check")],
        [p_btn("انصراف و بازگشت", callback_data="self:features_page:4", style="danger", emoji_key="fire")]
    ])
    await send_fn(
        p_text(
            "📢 <b>مرحله ۴ از ۸: کانال‌های جوین اجباری قرعه‌کشی (حداکثر ۱۰ کانال)</b>\n\n"
            "👇 یوزرنیم کانال‌هایی که کاربران برای شرکت در قرعه‌کشی باید عضو آن‌ها شوند را بفرستید (مثلاً <code>@MyChannel</code>).\n"
            "• می‌توانید تا <b>۱۰ کانال</b> (یکی‌یکی یا در چند خط زیر هم) ارسال کنید (ربات باید در کانال‌ها ادمین باشد تا عضویت را چک کند).\n"
            "• یا اگر کانال جوین اجباری ندارید روی دکمه زیر کلیک کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    return LOTTO_WAIT_FCH

async def lotto_step4_fch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.setdefault("lotto_draft", {})
    fch_list = draft.setdefault("force_channels", [])

    if update.callback_query:
        await update.callback_query.answer()
        kb = InlineKeyboardMarkup([
            [p_btn("⏭ بدون توضیحات", callback_data="lotto:nodesc", style="success", emoji_key="check")],
            [p_btn("انصراف و بازگشت", callback_data="self:features_page:4", style="danger", emoji_key="fire")]
        ])
        await update.callback_query.edit_message_text(
            p_text(
                f"📝 <b>مرحله ۵ از ۸: توضیحات قرعه‌کشی</b>\n\n"
                f"📢 کانال‌های جوین اجباری ثبت‌شده: <b>{len(fch_list)} کانال</b>\n\n"
                f"👇 لطفاً <b>توضیحات قرعه‌کشی</b> را بفرستید یا روی دکمه <b>«بدون توضیحات»</b> کلیک کنید:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
        return LOTTO_WAIT_DESC

    lines = [x.strip() for x in (update.message.text or "").splitlines() if x.strip()]
    added_now = []
    for raw_ch in lines:
        if len(fch_list) >= 10:
            break
        ch_id = normalize_channel_identifier(raw_ch)
        try:
            chat = await context.bot.get_chat(ch_id)
            title = chat.title or ch_id
            link = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or await context.bot.export_chat_invite_link(chat.id))
            cid = f"@{chat.username}" if chat.username else str(chat.id)
            fch_list.append({"channel_id": cid, "channel_link": link, "title": title})
            added_now.append(title)
        except Exception:
            # حتی اگر خصوصی بود یا لینک مستقیم بود با همان آیدی ذخیره شود
            link = f"https://t.me/{ch_id.lstrip('@')}"
            fch_list.append({"channel_id": ch_id, "channel_link": link, "title": ch_id})
            added_now.append(ch_id)

    kb = InlineKeyboardMarkup([
        [p_btn(f"✅ اتمام ثبت کانال‌ها ({len(fch_list)}/10) و مرحله بعد", callback_data="lotto:fch_done", style="success", emoji_key="check")],
        [p_btn("انصراف و بازگشت", callback_data="self:features_page:4", style="danger", emoji_key="fire")]
    ])
    await update.message.reply_text(
        p_text(
            f"✅ کانال اضافه شد! (تعداد کل کانال‌های ثبت‌شده: <b>{len(fch_list)} از ۱۰ کانال</b>)\n\n"
            f"👇 اگر کانال دیگری دارید بفرستید، یا روی دکمه سبز <b>«✅ اتمام ثبت کانال‌ها و مرحله بعد»</b> کلیک کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    return LOTTO_WAIT_FCH

async def lotto_step5_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        desc = ""
        send_fn = update.callback_query.edit_message_text
    else:
        desc = (update.message.text or "").strip()
        send_fn = update.message.reply_text

    context.user_data["lotto_draft"]["description"] = desc
    await send_fn(
        p_text(
            "⏰ <b>مرحله ۶ از ۸: زمان پایان قرعه‌کشی (به ساعت یا دقیقه)</b>\n\n"
            "👇 مشخص کنید قرعه‌کشی تا <b>چند ساعت یا چند دقیقه دیگر</b> تمام شود:\n"
            "• برای دقیقه: مثلاً <code>30 دقیقه</code> یا <code>30m</code> یا فقط عدد <code>30</code>\n"
            "• برای ساعت: مثلاً <code>2 ساعت</code> یا <code>2h</code>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("self:features_page:4")
    )
    return LOTTO_WAIT_DURATION

def parse_duration_to_minutes(raw_text: str) -> int:
    t = normalize_digits((raw_text or "").strip().lower())
    m_hr = re.search(r"(\d+)\s*(ساعت|h|hour|hours)", t)
    m_min = re.search(r"(\d+)\s*(دقیقه|دقيقه|m|min|mins|minute)", t)
    if m_hr and m_min:
        return int(m_hr.group(1)) * 60 + int(m_min.group(1))
    if m_hr:
        return int(m_hr.group(1)) * 60
    if m_min:
        return int(m_min.group(1))
    if t.isdigit():
        return int(t)
    return 0

async def lotto_step6_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins = parse_duration_to_minutes(update.message.text or "")
    if mins <= 0:
        await update.message.reply_text(
            p_text("⚠️ زمان وارد شده نامعتبر است! لطفاً زمان را به ساعت یا دقیقه وارد کنید (مثلاً <code>30 دقیقه</code> یا <code>2 ساعت</code>):"),
            parse_mode=ParseMode.HTML
        )
        return LOTTO_WAIT_DURATION

    context.user_data["lotto_draft"]["duration_minutes"] = mins
    await update.message.reply_text(
        p_text(
            f"🏆 <b>مرحله ۷ از ۸: تعداد برندگان قرعه‌کشی</b>\n\n"
            f"⏰ مدت زمان قرعه‌کشی: <b>{mins} دقیقه</b>\n\n"
            f"👇 لطفاً مشخص کنید این قرعه‌کشی <b>چند برنده</b> داشته باشد؟ (مثلاً <code>1</code> یا <code>3</code> نفر):"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("self:features_page:4")
    )
    return LOTTO_WAIT_WINNERS

async def lotto_step7_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_w = normalize_digits((update.message.text or "").strip())
    if not raw_w.isdigit() or int(raw_w) <= 0:
        await update.message.reply_text(p_text("⚠️ لطفاً تعداد برندگان را به صورت عدد صحیح بزرگ‌تر از صفر وارد کنید (مثلاً <code>1</code>):"), parse_mode=ParseMode.HTML)
        return LOTTO_WAIT_WINNERS

    context.user_data["lotto_draft"]["winners_count"] = int(raw_w)
    await update.message.reply_text(
        p_text(
            "📢 <b>مرحله ۸ از ۸: کانال مقصد جهت پست شدن قرعه‌کشی</b>\n\n"
            "⚠️ <i>توجه: ربات باید در کانال مقصد ادمین باشد تا بتواند پست قرعه‌کشی را منتشر و شمارنده شرکت‌کنندگان را بروزرسانی کند.</i>\n\n"
            "👇 لطفاً <b>لینک یا یوزرنیم کانالی</b> که می‌خواهید قرعه‌کشی در آن پست شود را بفرستید (مثلاً <code>@MyChannel</code> یا <code>https://t.me/MyChannel</code>):"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("self:features_page:4")
    )
    return LOTTO_WAIT_CHANNEL

async def lotto_step8_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_ch = normalize_channel_identifier(update.message.text or "")
    draft = context.user_data.get("lotto_draft", {})
    draft["target_channel"] = target_ch

    mins = draft.get("duration_minutes", 30)
    kb = InlineKeyboardMarkup([
        [p_btn("🚀 پست کردن در کانال", callback_data="lotto:publish", style="success", emoji_key="rocket")],
        [p_btn("انصراف و بازگشت", callback_data="self:features_page:4", style="danger", emoji_key="fire")]
    ])

    await update.message.reply_text(
        p_text(
            f"🎁 <b>پیش‌نمایش نهایی قرعه‌کشی آماده انتشار در کانال</b>\n\n"
            f"🏷 نام قرعه‌کشی: <b>{html.escape(draft.get('title', ''))}</b>\n"
            f"👥 حداقل شرکت‌کننده: <b>{draft.get('min_participants', 0) or 'بدون حداقل'}</b>\n"
            f"👥 حداکثر شرکت‌کننده: <b>{draft.get('max_participants', 0) or 'بدون حداکثر'}</b>\n"
            f"📢 تعداد کانال‌های جوین اجباری: <b>{len(draft.get('force_channels', []))} کانال</b>\n"
            f"⏰ مدت زمان: <b>{mins} دقیقه</b>\n"
            f"🏆 تعداد برندگان: <b>{draft.get('winners_count', 1)} نفر</b>\n"
            f"🎯 کانال مقصد: <code>{html.escape(target_ch)}</code>\n\n"
            f"👇 برای انتشار فوری قرعه‌کشی در کانال روی دکمه سبز <b>«🚀 پست کردن در کانال»</b> کلیک کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    return LOTTO_WAIT_CONFIRM

async def lotto_step9_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    draft = context.user_data.get("lotto_draft")
    if not draft:
        await query.answer("⚠️ اطلاعات قرعه‌کشی یافت نشد.", show_alert=True)
        return ConversationHandler.END

    await query.answer("🚀 در حال ارسال قرعه‌کشی در کانال...")
    now_dt = datetime.now()
    end_dt = now_dt + timedelta(minutes=int(draft["duration_minutes"]))
    draft["end_time_display"] = end_dt.strftime("%Y-%m-%d %H:%M")

    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            """INSERT INTO channel_lotteries
               (creator_id, title, min_participants, max_participants, force_channels_json, description,
                duration_minutes, winners_count, target_channel, status, end_time, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
            (
                user.id,
                draft["title"],
                draft["min_participants"],
                draft["max_participants"],
                json.dumps(draft.get("force_channels", []), ensure_ascii=False),
                draft.get("description", ""),
                draft["duration_minutes"],
                draft["winners_count"],
                draft["target_channel"],
                end_dt.isoformat(),
                now_dt.isoformat(),
            )
        )
        lotto_id = cur.lastrowid

    bot_me = await context.bot.get_me()
    post_text = build_channel_lottery_post_text(draft, status_badge="🟢 در حال برگزاری")
    post_kb = build_channel_lottery_keyboard(bot_me.username, lotto_id, 0)

    try:
        sent_msg = await context.bot.send_message(
            chat_id=draft["target_channel"],
            text=post_text,
            parse_mode=ParseMode.HTML,
            reply_markup=post_kb
        )
        with closing(get_conn()) as conn, conn:
            conn.execute("UPDATE channel_lotteries SET channel_message_id=? WHERE id=?", (sent_msg.message_id, lotto_id))
    except Exception as e:
        with closing(get_conn()) as conn, conn:
            conn.execute("DELETE FROM channel_lotteries WHERE id=?", (lotto_id,))
        await query.edit_message_text(
            p_text(
                f"❌ <b>خطا در ارسال پست به کانال <code>{html.escape(draft['target_channel'])}</code>!</b>\n"
                f"لطفاً مطمئن شوید ربات را در کانال ادمین کرده‌اید و دسترسی ارسال پست دارد.\n"
                f"جزئیات: <code>{html.escape(str(e)[:120])}</code>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("self:features_page:4")
        )
        return ConversationHandler.END

    context.user_data.pop("lotto_draft", None)
    await query.edit_message_text(
        p_text(
            f"🎉 <b>قرعه‌کشی «{html.escape(draft['title'])}» با موفقیت در کانال <code>{html.escape(draft['target_channel'])}</code> پست شد!</b>\n\n"
            f"🟢 دکمه شیشه‌ای سبز شمارنده شرکت‌کنندگان و دکمه شیشه‌ای آبی شرکت در قرعه‌کشی فعال گردید.\n"
            f"⏰ در ساعت <code>{draft['end_time_display']}</code> نتایج قرعه‌کشی و آیدی برندگان به صورت کاملاً خودکار در کانال اعلام خواهد شد."
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )
    return ConversationHandler.END

async def handle_lottery_join_attempt(update: Update, context: ContextTypes.DEFAULT_TYPE, user, lotto_id: int, is_callback: bool = False):
    with closing(get_conn()) as conn:
        lotto = conn.execute("SELECT * FROM channel_lotteries WHERE id=?", (lotto_id,)).fetchone()
        if not lotto:
            txt = p_text("❌ این قرعه‌کشی یافت نشد.")
            if is_callback:
                await update.callback_query.answer("❌ قرعه‌کشی یافت نشد.", show_alert=True)
            else:
                await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
            return

        if lotto["status"] != "active":
            txt = p_text("🏁 مهلت این قرعه‌کشی به پایان رسیده است.")
            if is_callback:
                await update.callback_query.answer("🏁 این قرعه‌کشی به پایان رسیده است.", show_alert=True)
            else:
                await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
            return

        already = conn.execute(
            "SELECT 1 FROM lottery_participants WHERE lottery_id=? AND user_id=?",
            (lotto_id, user.id)
        ).fetchone()
        curr_cnt = conn.execute(
            "SELECT COUNT(*) c FROM lottery_participants WHERE lottery_id=?",
            (lotto_id,)
        ).fetchone()["c"]

    if already:
        msg = "✅ شما قبلاً در این قرعه‌کشی ثبت‌نام کرده‌اید!"
        if is_callback:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(p_text(msg), parse_mode=ParseMode.HTML, reply_markup=main_inline_keyboard(user.id))
        return

    if lotto["max_participants"] > 0 and curr_cnt >= lotto["max_participants"]:
        msg = "⚠️ ظرفیت شرکت‌کنندگان این قرعه‌کشی تکمیل شده است!"
        if is_callback:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(p_text(msg), parse_mode=ParseMode.HTML)
        return

    # بررسی عضویت در کانال‌های جوین اجباری قرعه‌کشی
    try:
        fch_list = json.loads(lotto["force_channels_json"] or "[]")
    except Exception:
        fch_list = []

    not_joined = []
    for ch in fch_list:
        try:
            m = await context.bot.get_chat_member(chat_id=ch["channel_id"], user_id=user.id)
            if m.status in ("left", "kicked"):
                not_joined.append(ch)
        except Exception:
            pass

    if not_joined:
        rows = [
            [p_btn(f"📢 عضویت در {c.get('title', c['channel_id'])}", url=c["channel_link"], style="primary", emoji_key="megaphone")]
            for c in not_joined
        ]
        rows.append([
            p_btn("🎁 عضو شدم و شرکت در قرعه‌کشی", callback_data=f"lottocheck:{lotto_id}", style="success", emoji_key="check")
        ])
        join_prompt = p_text(
            f"🎁 <b>شرکت در قرعه‌کشی «{html.escape(lotto['title'])}»</b>\n\n"
            f"⚠️ برای شرکت در این قرعه‌کشی، ابتدا باید در کانال‌های زیر عضو شوید و سپس روی دکمه سبز <b>«🎁 عضو شدم و شرکت در قرعه‌کشی»</b> کلیک کنید:"
        )
        if is_callback:
            await update.callback_query.answer("⚠️ هنوز در تمام کانال‌های قرعه‌کشی عضو نشده‌اید!", show_alert=True)
            try:
                await update.callback_query.edit_message_text(join_prompt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
            except Exception:
                pass
        else:
            await update.message.reply_text(join_prompt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
        return

    # ثبت قطعی کاربر در قرعه‌کشی و افزایش خودکار شمارنده روی دکمه شیشه‌ای سبز در کانال
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO lottery_participants (lottery_id, user_id, username, first_name, joined_at) VALUES (?, ?, ?, ?, ?)",
            (lotto_id, user.id, user.username or "", user.first_name or "کاربر", datetime.now().isoformat())
        )
        new_cnt = conn.execute(
            "SELECT COUNT(*) c FROM lottery_participants WHERE lottery_id=?",
            (lotto_id,)
        ).fetchone()["c"]

    # آپدیت لحظه‌ای دکمه شیشه‌ای سبز رنگ در کانال
    try:
        bot_me = await context.bot.get_me()
        if lotto["channel_message_id"]:
            await context.bot.edit_message_reply_markup(
                chat_id=lotto["target_channel"],
                message_id=lotto["channel_message_id"],
                reply_markup=build_channel_lottery_keyboard(bot_me.username, lotto_id, new_cnt)
            )
    except Exception as e:
        logger.debug(f"Update lottery channel button count error: {e}")

    ok_text = p_text(
        f"🎉 <b>تبریک! نام شما با موفقیت در قرعه‌کشی «{html.escape(lotto['title'])}» ثبت شد!</b>\n\n"
        f"👥 شماره شرکت‌کننده شما: <b>نفر {new_cnt}</b>\n"
        f"⏰ نتایج قرعه‌کشی پس از اتمام زمان به صورت خودکار در کانال اعلام خواهد شد."
    )
    if is_callback:
        await update.callback_query.answer("🎉 ثبت‌نام شما در قرعه‌کشی انجام شد!", show_alert=True)
        try:
            await update.callback_query.edit_message_text(ok_text, parse_mode=ParseMode.HTML, reply_markup=main_inline_keyboard(user.id))
        except Exception:
            pass
    else:
        await update.message.reply_text(ok_text, parse_mode=ParseMode.HTML, reply_markup=main_inline_keyboard(user.id))

async def lottery_callbacks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data.startswith("lottocnt:"):
        lid = int(data.split(":")[1])
        with closing(get_conn()) as conn:
            cnt = conn.execute("SELECT COUNT(*) c FROM lottery_participants WHERE lottery_id=?", (lid,)).fetchone()["c"]
        await query.answer(f"👥 تعداد شرکت‌کنندگان تا این لحظه: {cnt} نفر", show_alert=True)
    elif data.startswith("lottocheck:"):
        lid = int(data.split(":")[1])
        await handle_lottery_join_attempt(update, context, query.from_user, lid, is_callback=True)

async def lottery_expiration_job(context: ContextTypes.DEFAULT_TYPE):
    """بررسی خودکار زمان پایان قرعه‌کشی‌ها و اعلام تصادفی برندگان در کانال"""
    now_iso = datetime.now().isoformat()
    with closing(get_conn()) as conn:
        expired_lottos = conn.execute(
            "SELECT * FROM channel_lotteries WHERE status='active' AND end_time <= ?",
            (now_iso,)
        ).fetchall()

    bot = context.bot if hasattr(context, "bot") else (BOT_APP_REF.bot if BOT_APP_REF else None)
    if not bot:
        return

    for lotto in expired_lottos:
        lid = lotto["id"]
        with closing(get_conn()) as conn, conn:
            participants = conn.execute(
                "SELECT * FROM lottery_participants WHERE lottery_id=?",
                (lid,)
            ).fetchall()
            total_p = len(participants)

            if lotto["min_participants"] > 0 and total_p < lotto["min_participants"]:
                conn.execute("UPDATE channel_lotteries SET status='canceled' WHERE id=?", (lid,))
                cancel_kb = InlineKeyboardMarkup([
                    [p_btn(f"❌ قرعه‌کشی لغو شد ({total_p}/{lotto['min_participants']} نفر)", callback_data="noop", style="danger", emoji_key="fire")]
                ])
                try:
                    if lotto["channel_message_id"]:
                        await bot.edit_message_reply_markup(
                            chat_id=lotto["target_channel"],
                            message_id=lotto["channel_message_id"],
                            reply_markup=cancel_kb
                        )
                    await bot.send_message(
                        chat_id=lotto["target_channel"],
                        reply_to_message_id=lotto["channel_message_id"],
                        text=p_text(
                            f"❌ <b>قرعه‌کشی «{html.escape(lotto['title'])}» لغو شد!</b>\n\n"
                            f"به دلیل نرسیدن تعداد شرکت‌کنندگان (<b>{total_p} نفر</b>) به حدنصاب تعیین‌شده (<b>حداقل {lotto['min_participants']} نفر</b>)، این قرعه‌کشی لغو گردید."
                        ),
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass
                continue

            conn.execute("UPDATE channel_lotteries SET status='finished' WHERE id=?", (lid,))

        if total_p == 0:
            done_kb = InlineKeyboardMarkup([
                [p_btn("🏁 پایان قرعه‌کشی (بدون شرکت‌کننده)", callback_data="noop", style="danger", emoji_key="fire")]
            ])
            try:
                if lotto["channel_message_id"]:
                    await bot.edit_message_reply_markup(
                        chat_id=lotto["target_channel"],
                        message_id=lotto["channel_message_id"],
                        reply_markup=done_kb
                    )
            except Exception:
                pass
            continue

        win_count = min(int(lotto["winners_count"]), total_p)
        winners = random.sample(list(participants), win_count)

        winner_lines = []
        for idx, w in enumerate(winners, 1):
            w_name = html.escape(w["first_name"] or "کاربر")
            w_user = f"(@{w['username']})" if w["username"] else ""
            winner_lines.append(
                f"🏆 <b>برنده شماره {idx}:</b> <a href=\"tg://user?id={w['user_id']}\">{w_name}</a> {w_user} | آیدی عددی: <code>{w['user_id']}</code>"
            )

        done_kb = InlineKeyboardMarkup([
            [p_btn(f"🏁 قرعه‌کشی انجام شد ({total_p} شرکت‌کننده)", callback_data=f"lottocnt:{lid}", style="success", emoji_key="crown")]
        ])
        try:
            if lotto["channel_message_id"]:
                await bot.edit_message_reply_markup(
                    chat_id=lotto["target_channel"],
                    message_id=lotto["channel_message_id"],
                    reply_markup=done_kb
                )
            await bot.send_message(
                chat_id=lotto["target_channel"],
                reply_to_message_id=lotto["channel_message_id"],
                text=p_text(
                    f"🎉 <b>نتایج نهایی قرعه‌کشی «{html.escape(lotto['title'])}» اعلام شد!</b>\n\n"
                    f"👥 کل شرکت‌کنندگان: <b>{total_p} نفر</b>\n"
                    f"👑 <b>لیست برندگان خوش‌شانس (انتخاب کاملاً تصادفی):</b>\n\n"
                    + "\n".join(winner_lines)
                ),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.debug(f"Lottery result post error: {e}")

# ====================================================================
#  ۵. ساخت دکمه شیشه‌ای رنگی برای کانال (در بخش قابلیت‌های سلف)
# ====================================================================

async def chbtn_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["chbtn_draft"] = {}
    await query.edit_message_text(
        p_text(
            "✨ <b>ساخت دکمه شیشه‌ای رنگی برای کانال (مرحله ۱ از ۵: ارسال محتوا)</b>\n\n"
            "👇 لطفاً ابتدا <b>توضیحات یا پست خود را با عکس، ویدیو، گیف، فایل یا متن</b> (هر چیزی که می‌خواهید در کانال پست شود) ارسال کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("self:features_page:4")
    )
    return CHBTN_WAIT_CONTENT

async def chbtn_step1_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    draft = context.user_data.setdefault("chbtn_draft", {})
    draft["source_chat_id"] = msg.chat_id
    draft["source_message_id"] = msg.message_id
    draft["has_media"] = bool(msg.photo or msg.video or msg.document or msg.animation or msg.audio or msg.voice)
    draft["text_content"] = msg.text or msg.caption or ""

    await msg.reply_text(
        p_text(
            "🔗 <b>مرحله ۲ از ۵: لینک دکمه شیشه‌ای</b>\n\n"
            "👇 حالا <b>لینکی که می‌خواهید داخل دکمه شیشه‌ای باشد</b> را بفرستید:\n"
            "<i>(مثال: <code>https://t.me/YourChannel</code> یا آدرس سایت)</i>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("self:features_page:4")
    )
    return CHBTN_WAIT_LINK

async def chbtn_step2_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = (update.message.text or "").strip()
    if link.startswith("@"):
        link = f"https://t.me/{link.lstrip('@')}"
    elif link.startswith("t.me/"):
        link = f"https://{link}"
    elif not link.startswith("http://") and not link.startswith("https://") and not link.startswith("tg://"):
        link = f"https://{link}"

    context.user_data["chbtn_draft"]["btn_url"] = link
    await update.message.reply_text(
        p_text(
            "🏷 <b>مرحله ۳ از ۵: نام روی دکمه شیشه‌ای</b>\n\n"
            "👇 حالا <b>اسم دکمه شیشه‌ای</b> که می‌خواهید روی آن نمایش داده شود را بفرستید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("self:features_page:4")
    )
    return CHBTN_WAIT_NAME

async def chbtn_step3_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn_name = (update.message.text or "").strip()
    if not btn_name:
        await update.message.reply_text(p_text("⚠️ لطفاً نام دکمه شیشه‌ای را وارد کنید:"), parse_mode=ParseMode.HTML)
        return CHBTN_WAIT_NAME

    context.user_data["chbtn_draft"]["btn_name"] = btn_name
    kb = InlineKeyboardMarkup([
        [
            p_btn("🔵 آبی (Primary)", callback_data="chbtn_color:primary", style="primary", emoji_key="gem"),
            p_btn("🟢 سبز (Success)", callback_data="chbtn_color:success", style="success", emoji_key="check"),
        ],
        [
            p_btn("🔴 قرمز (Danger)", callback_data="chbtn_color:danger", style="danger", emoji_key="fire"),
            InlineKeyboardButton("⚪ رنگ معمولی شیشه‌ای", callback_data="chbtn_color:normal"),
        ],
        [p_btn("انصراف و بازگشت", callback_data="self:features_page:4", style="danger", emoji_key="fire")]
    ])
    await update.message.reply_text(
        p_text(
            "🎨 <b>مرحله ۴ از ۵: انتخاب رنگ دکمه شیشه‌ای</b>\n\n"
            "👇 لطفاً رنگ دکمه شیشه‌ای مورد نظر خود را از بین گزینه‌های <b>آبی، سبز، قرمز یا معمولی</b> انتخاب کنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    return CHBTN_WAIT_COLOR

async def chbtn_step4_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    color_style = query.data.split(":")[1]
    context.user_data["chbtn_draft"]["btn_style"] = color_style

    await query.edit_message_text(
        p_text(
            "📢 <b>مرحله ۵ از ۵: لینک یا آیدی کانال مقصد</b>\n\n"
            "⚠️ <i>توجه: ربات باید در کانال مقصد ادمین باشد.</i>\n"
            "👇 لطفاً <b>لینک یا آیدی کانالی</b> که می‌خواهید پست داخلش ارسال شود را بفرستید (مثلاً <code>@MyChannel</code> یا <code>https://t.me/MyChannel</code>):"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("self:features_page:4")
    )
    return CHBTN_WAIT_CHANNEL

async def chbtn_step5_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_ch = normalize_channel_identifier(update.message.text or "")
    draft = context.user_data.get("chbtn_draft", {})
    draft["target_channel"] = target_ch

    color_names = {
        "primary": "🔵 آبی",
        "success": "🟢 سبز",
        "danger": "🔴 قرمز",
        "normal": "⚪ معمولی شیشه‌ای",
    }
    kb = InlineKeyboardMarkup([
        [p_btn("🚀 پست کردن در کانال", callback_data="chbtn:publish", style="success", emoji_key="rocket")],
        [p_btn("انصراف و بازگشت", callback_data="self:features_page:4", style="danger", emoji_key="fire")]
    ])
    await update.message.reply_text(
        p_text(
            f"✨ <b>آماده انتشار پست با دکمه شیشه‌ای در کانال</b>\n\n"
            f"🏷 عنوان دکمه: <b>{html.escape(draft.get('btn_name', ''))}</b>\n"
            f"🔗 لینک دکمه: <code>{html.escape(draft.get('btn_url', ''))}</code>\n"
            f"🎨 رنگ دکمه: <b>{color_names.get(draft.get('btn_style', 'primary'), 'آبی')}</b>\n"
            f"📢 کانال مقصد: <code>{html.escape(target_ch)}</code>\n\n"
            f"👇 برای انتشار در کانال روی دکمه سبز <b>«🚀 پست کردن در کانال»</b> بزنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    return CHBTN_WAIT_CONFIRM

async def chbtn_step6_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    draft = context.user_data.get("chbtn_draft")
    if not draft:
        await query.answer("⚠️ اطلاعات پست یافت نشد.", show_alert=True)
        return ConversationHandler.END

    await query.answer("🚀 در حال ارسال پست به کانال...")
    style_choice = draft.get("btn_style", "primary")
    if style_choice == "normal":
        glass_btn = InlineKeyboardButton(draft["btn_name"], url=draft["btn_url"])
    else:
        glass_btn = p_btn(draft["btn_name"], url=draft["btn_url"], style=style_choice, emoji_key="sparkles")

    post_markup = InlineKeyboardMarkup([[glass_btn]])

    try:
        await context.bot.copy_message(
            chat_id=draft["target_channel"],
            from_chat_id=draft["source_chat_id"],
            message_id=draft["source_message_id"],
            reply_markup=post_markup
        )
    except Exception as e:
        await query.edit_message_text(
            p_text(
                f"❌ <b>خطا در ارسال پست به کانال <code>{html.escape(draft['target_channel'])}</code>!</b>\n"
                f"لطفاً مطمئن شوید ربات در کانال ادمین است و لینک دکمه معتبر است.\n"
                f"جزئیات: <code>{html.escape(str(e)[:120])}</code>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("self:features_page:4")
        )
        return ConversationHandler.END

    context.user_data.pop("chbtn_draft", None)
    await query.edit_message_text(
        p_text(
            f"✅ <b>پست شما با دکمه شیشه‌ای رنگی با موفقیت در کانال <code>{html.escape(draft['target_channel'])}</code> منتشر شد!</b>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )
    return ConversationHandler.END

# ====================================================================
#  ۵.۵ ساخت چالش لایکی برای کانال (با شرط عضویت اجباری در کانال و پس گرفتن لایک)
# ====================================================================

def build_like_challenge_keyboard(item_id: int, participant_name: str, likes_count: int) -> InlineKeyboardMarkup:
    short_name = (participant_name or "شرکت‌کننده").strip()[:28]
    return InlineKeyboardMarkup([
        [
            p_btn(
                f"❤️ {short_name} | {likes_count} لایک",
                callback_data=f"likechal_vote:{item_id}",
                style="danger",
                emoji_key="heart"
            )
        ]
    ])

async def likechal_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["likechal_draft"] = {"posted_count": 0}
    await query.edit_message_text(
        p_text(
            "❤️ <b>ساخت چالش لایکی برای کانال (مرحله ۱ از ۲: لینک کانال)</b>\n\n"
            "⚠️ <i>توجه: ربات باید در کانال مورد نظر <b>ادمین</b> باشد تا بتواند اسم‌ها را با دکمه شیشه‌ای لایک ارسال کند و عضویت لایک‌کنندگان را بررسی نماید.</i>\n\n"
            "👇 لطفاً <b>لینک یا آیدی کانالی</b> که می‌خواهید چالش لایکی در آن ارسال شود را بفرستید:\n"
            "<i>(مثال: <code>@MyChannel</code> یا <code>https://t.me/MyChannel</code>)</i>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_inline_keyboard("self:features_page:4")
    )
    return LIKECHAL_WAIT_CHANNEL

async def likechal_step1_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_ch = (update.message.text or "").strip()
    target_ch = normalize_channel_identifier(raw_ch)

    try:
        bot_me = await context.bot.get_me()
        chat = await context.bot.get_chat(chat_id=target_ch)
        bot_member = await context.bot.get_chat_member(chat_id=chat.id, user_id=bot_me.id)
        if bot_member.status not in ("administrator", "creator"):
            await update.message.reply_text(
                p_text(
                    "❌ <b>ربات در این کانال ادمین نیست!</b>\n"
                    "لطفاً ابتدا ربات را در کانال خود <b>ادمین (Administrator)</b> کنید و سپس مجدداً لینک یا آیدی کانال را بفرستید:"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_inline_keyboard("self:features_page:4")
            )
            return LIKECHAL_WAIT_CHANNEL

        ch_id_store = f"@{chat.username}" if chat.username else str(chat.id)
        ch_title = chat.title or target_ch
    except Exception as e:
        await update.message.reply_text(
            p_text(
                f"❌ <b>خطا در دسترسی به کانال <code>{html.escape(target_ch)}</code>!</b>\n"
                f"مطمئن شوید ربات در کانال ادمین است و لینک/آیدی کانال را درست وارد کرده‌اید:\n"
                f"<code>{html.escape(str(e)[:100])}</code>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_inline_keyboard("self:features_page:4")
        )
        return LIKECHAL_WAIT_CHANNEL

    context.user_data["likechal_draft"] = {
        "channel_id": ch_id_store,
        "channel_num_id": chat.id,
        "channel_title": ch_title,
        "posted_count": 0,
    }

    kb = InlineKeyboardMarkup([
        [p_btn("✅ اتمام ساخت چالش لایکی و بازگشت", callback_data="likechal:finish", style="success", emoji_key="check")],
        [p_btn("انصراف و بازگشت", callback_data="self:features_page:4", style="danger", emoji_key="fire")]
    ])
    await update.message.reply_text(
        p_text(
            f"✅ <b>کانال «{html.escape(ch_title)}» با موفقیت انتخاب شد!</b>\n\n"
            f"👤 <b>مرحله ۲ از ۲: ارسال اسم شرکت‌کنندگان</b>\n"
            f"👇 حالا <b>اسم (یا اسم‌ها)</b> را بفرستید (هر چند تا که می‌خواهید!):\n"
            f"• می‌توانید اسم‌ها را <b>یکی‌یکی در پیام‌های جداگانه</b> بفرستید.\n"
            f"• یا <b>چند اسم را در خط‌های جداگانه زیر هم</b> در یک پیام بفرستید.\n\n"
            f"❤️ به محض ارسال هر اسم، همان لحظه با <b>دکمه شیشه‌ای لایک</b> در کانال ارسال می‌شود!"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    return LIKECHAL_WAIT_NAMES

async def likechal_step2_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    draft = context.user_data.get("likechal_draft")
    if not draft or not draft.get("channel_id"):
        await update.message.reply_text(
            p_text("⚠️ نشست ساخت چالش لایکی منقضی شده است. لطفاً مجدداً از بخش قابلیت‌های سلف اقدام کنید."),
            parse_mode=ParseMode.HTML,
            reply_markup=main_inline_keyboard(user.id)
        )
        return ConversationHandler.END

    names = [ln.strip() for ln in (update.message.text or "").splitlines() if ln.strip()]
    if not names:
        await update.message.reply_text(p_text("⚠️ لطفاً حداقل یک اسم ارسال کنید:"), parse_mode=ParseMode.HTML)
        return LIKECHAL_WAIT_NAMES

    ch_id = draft["channel_id"]
    ch_title = draft.get("channel_title", ch_id)
    sent_now = 0

    for part_name in names:
        with closing(get_conn()) as conn, conn:
            cur = conn.execute(
                """INSERT INTO like_challenge_items (creator_id, channel_id, channel_title, participant_name, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user.id, str(draft.get("channel_num_id") or ch_id), ch_title, part_name, datetime.now().isoformat())
            )
            item_id = cur.lastrowid

        post_text = p_text(
            f"🔥 <b>چالش لایکی کانال {html.escape(ch_title)}</b>\n\n"
            f"👤 شرکت‌کننده: <b>{html.escape(part_name)}</b>\n\n"
            f"👇 برای لایک کردن <b>{html.escape(part_name)}</b> روی دکمه شیشه‌ای زیر بزنید:"
        )
        post_kb = build_like_challenge_keyboard(item_id, part_name, 0)

        try:
            sent_msg = await context.bot.send_message(
                chat_id=ch_id,
                text=post_text,
                parse_mode=ParseMode.HTML,
                reply_markup=post_kb
            )
            with closing(get_conn()) as conn, conn:
                conn.execute(
                    "UPDATE like_challenge_items SET message_id=?, channel_id=? WHERE id=?",
                    (sent_msg.message_id, str(sent_msg.chat.id), item_id)
                )
            sent_now += 1
            draft["posted_count"] = draft.get("posted_count", 0) + 1
        except Exception as e:
            with closing(get_conn()) as conn, conn:
                conn.execute("DELETE FROM like_challenge_items WHERE id=?", (item_id,))
            await update.message.reply_text(
                p_text(
                    f"❌ خطا در ارسال «{html.escape(part_name)}» به کانال:\n"
                    f"<code>{html.escape(str(e)[:100])}</code>"
                ),
                parse_mode=ParseMode.HTML
            )

    kb = InlineKeyboardMarkup([
        [p_btn(f"✅ اتمام ساخت چالش لایکی ({draft.get('posted_count', 0)} اسم ارسال شد)", callback_data="likechal:finish", style="success", emoji_key="check")],
        [p_btn("بازگشت به قابلیت‌های سلف", callback_data="self:features_page:4", style="primary", emoji_key="sparkles")]
    ])
    await update.message.reply_text(
        p_text(
            f"✅ <b>{sent_now} اسم جدید</b> با دکمه شیشه‌ای لایک در کانال <b>{html.escape(ch_title)}</b> ارسال شد! (مجموع ارسال‌شده: <b>{draft.get('posted_count', 0)} اسم</b>)\n\n"
            f"👇 اگر باز هم اسم دیگری دارید همین الان بفرستید تا در کانال پست شود، و هر زمان تمام شد روی دکمه سبز زیر بزنید:"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    return LIKECHAL_WAIT_NAMES

async def likechal_finish_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    draft = context.user_data.pop("likechal_draft", {}) or {}
    total_posted = draft.get("posted_count", 0)
    ch_title = draft.get("channel_title", "کانال")

    await query.answer("✅ ساخت چالش لایکی به پایان رسید!")
    await query.edit_message_text(
        p_text(
            f"🎉 <b>چالش لایکی شما در کانال «{html.escape(ch_title)}» با موفقیت فعال شد!</b>\n\n"
            f"👥 تعداد اسم‌های ارسال‌شده با دکمه شیشه‌ای لایک: <b>{total_posted} مورد</b>\n"
            f"🛡 <b>قانون ضد تقلب فعال است:</b> فقط کسانی که عضو کانال باشند می‌توانند لایک کنند و با کلیک مجدد نیز لایک پس گرفته می‌شود."
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=main_inline_keyboard(user.id)
    )
    return ConversationHandler.END

async def likechal_vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیک روی دکمه شیشه‌ای لایک در کانال (بررسی عضویت اجباری در کانال + ثبت لایک یا پس گرفتن لایک)"""
    query = update.callback_query
    voter = query.from_user
    data = query.data

    if not data.startswith("likechal_vote:"):
        return

    try:
        item_id = int(data.split(":")[1])
    except ValueError:
        await query.answer("⚠️ چالش معتبر نیست.", show_alert=True)
        return

    with closing(get_conn()) as conn:
        item = conn.execute("SELECT * FROM like_challenge_items WHERE id=?", (item_id,)).fetchone()

    if not item:
        await query.answer("⚠️ این آیتم چالش یافت نشد.", show_alert=True)
        return

    # ۱. بررسی حتمی عضویت کاربر در کانالی که چالش در آن قرار دارد
    target_chat_id = query.message.chat.id if (query.message and query.message.chat) else item["channel_id"]
    is_channel_member = False
    try:
        member = await context.bot.get_chat_member(chat_id=target_chat_id, user_id=voter.id)
        if member.status in ("creator", "administrator", "member"):
            is_channel_member = True
        elif member.status == "restricted" and getattr(member, "is_member", False):
            is_channel_member = True
    except Exception as e:
        logger.debug(f"Like challenge membership check error: {e}")
        is_channel_member = False

    if not is_channel_member:
        await query.answer(
            "⛔ شما عضو این کانال نیستید!\nبرای اینکه لایک شما ثبت و حساب شود، ابتدا باید در همین کانال عضو شوید.",
            show_alert=True
        )
        return

    # ۲. ثبت لایک جدید یا پس گرفتن لایک در صورت کلیک مجدد
    with closing(get_conn()) as conn, conn:
        existing_vote = conn.execute(
            "SELECT 1 FROM like_challenge_votes WHERE item_id=? AND user_id=?",
            (item_id, voter.id)
        ).fetchone()

        if existing_vote:
            conn.execute(
                "DELETE FROM like_challenge_votes WHERE item_id=? AND user_id=?",
                (item_id, voter.id)
            )
            was_unliked = True
        else:
            conn.execute(
                "INSERT INTO like_challenge_votes (item_id, user_id, created_at) VALUES (?, ?, ?)",
                (item_id, voter.id, datetime.now().isoformat())
            )
            was_unliked = False

        new_likes_count = conn.execute(
            "SELECT COUNT(*) c FROM like_challenge_votes WHERE item_id=?",
            (item_id,)
        ).fetchone()["c"]

    part_name = item["participant_name"]

    # ۳. بروزرسانی آنی دکمه شیشه‌ای لایک در کانال
    try:
        await query.edit_message_reply_markup(
            reply_markup=build_like_challenge_keyboard(item_id, part_name, new_likes_count)
        )
    except Exception as e:
        logger.debug(f"Update like challenge button error: {e}")

    if was_unliked:
        await query.answer(f"💔 لایک شما برای «{part_name}» پس گرفته شد! (تعداد لایک: {new_likes_count})", show_alert=False)
    else:
        await query.answer(f"❤️ لایک شما برای «{part_name}» ثبت شد! (تعداد لایک: {new_likes_count})", show_alert=False)


# ====================================================================
#  ۶. قابلیت‌های گروهی ربات: «موجودی»، «بازی [مبلغ]» و ریپلای «انتقال [مبلغ]»
# ====================================================================

async def group_commands_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش دستورات گروهی: ۱. موجودی | ۲. بازی [مبلغ] | ۳. ریپلای انتقال [مبلغ] با کارمزد ۱۰٪"""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or not user or chat.type not in ("group", "supergroup"):
        return

    raw_txt = (msg.text or "").strip()
    if not raw_txt:
        return

    norm_txt = normalize_digits(raw_txt)

    # ۱. دستور «موجودی» در گروه -> نمایش موجودی داخل دکمه شیشه‌ای آبی رنگ
    if norm_txt == "موجودی":
        db_user = get_or_create_user(user.id, user.username, user.first_name)
        kb = InlineKeyboardMarkup([
            [
                p_btn(
                    f"💎 موجودی {user.first_name[:22]}: {db_user['diamonds']:,} الماس",
                    callback_data=f"grpbal:{user.id}",
                    style="primary",
                    emoji_key="gem"
                )
            ]
        ])
        await msg.reply_text(
            p_text(f"👤 کاربر <b>{html.escape(user.first_name)}</b>، موجودی الماس شما در دکمه شیشه‌ای آبی زیر نمایش داده شده است:"),
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
        return

    # ۲. دستور «بازی [مبلغ]» در گروه (مثال: بازی 60) -> حداقل شرط ۱۵ الماس و جایزه ۲ برابر
    m_game = re.match(r"^بازی\s+(\d+)$", norm_txt)
    if m_game:
        bet = int(m_game.group(1))
        if bet < 15:
            await msg.reply_text(
                p_text("⚠️ <b>حداقل مبلغ شرط برای ساخت بازی ۱۵ الماس است!</b>\n<i>(مثال: <code>بازی 60</code>)</i>"),
                parse_mode=ParseMode.HTML
            )
            return

        db_user = get_or_create_user(user.id, user.username, user.first_name)
        if db_user["diamonds"] < bet:
            await msg.reply_text(
                p_text(
                    f"❌ <b>موجودی شما برای ساخت این بازی کافی نیست!</b>\n"
                    f"💎 مبلغ شرط بازی: <b>{bet:,} الماس</b> | موجودی فعلی شما: <b>{db_user['diamonds']:,} الماس</b>"
                ),
                parse_mode=ParseMode.HTML
            )
            return

        with closing(get_conn()) as conn, conn:
            cur = conn.execute(
                """INSERT INTO group_games (chat_id, creator_id, creator_name, bet_amount, status, created_at)
                   VALUES (?, ?, ?, ?, 'waiting', ?)""",
                (chat.id, user.id, user.first_name or "کاربر", bet, datetime.now().isoformat())
            )
            game_id = cur.lastrowid

        prize = bet * 2
        kb = InlineKeyboardMarkup([
            [
                p_btn(
                    f"🎲 شرکت در بازی (شرط: {bet:,} الماس | جایزه: {prize:,} الماس)",
                    callback_data=f"grpgame:join:{game_id}",
                    style="success",
                    emoji_key="party"
                )
            ],
            [
                p_btn(f"👤 بازیکن اول: {user.first_name[:18]}", callback_data="noop", style="primary", emoji_key="star"),
                p_btn("❌ لغو بازی", callback_data=f"grpgame:cancel:{game_id}", style="danger", emoji_key="fire"),
            ]
        ])
        await msg.reply_text(
            p_text(
                f"🎮 <b>چالش بازی دو نفره الماس در گروه ساخته شد!</b>\n\n"
                f"👤 سازنده بازی: <b>{html.escape(user.first_name)}</b>\n"
                f"💎 مبلغ شرط هر نفر: <b>{bet:,} الماس</b>\n"
                f"🏆 جایزه برنده نهایی (۲ برابر شرط): <b>{prize:,} الماس</b>\n"
                f"👥 ظرفیت: <b>فقط سازنده و ۱ نفر دیگر (۱/۲)</b>\n\n"
                f"👇 نفر دوم برای شروع بازی و انتخاب تصادفی برنده روی دکمه شیشه‌ای سبز زیر کلیک کند:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
        return

    # ۳. دستور ریپلای «انتقال [مبلغ]» در گروه (مثال: انتقال 50) -> کسر ۱۰٪ کارمزد و ارسال نوتیف در ربات
    m_tr = re.match(r"^انتقال\s+(\d+)$", norm_txt)
    if m_tr and msg.reply_to_message and msg.reply_to_message.from_user:
        if get_setting("transfer_enabled", "1") == "0" and not is_admin(user.id):
            await msg.reply_text(p_text("⛔ بخش انتقال الماس در حال حاضر توسط مدیریت غیرفعال شده است."), parse_mode=ParseMode.HTML)
            return

        target_user = msg.reply_to_message.from_user
        if target_user.is_bot:
            await msg.reply_text(p_text("⚠️ امکان انتقال الماس به ربات‌ها وجود ندارد!"), parse_mode=ParseMode.HTML)
            return
        if target_user.id == user.id:
            await msg.reply_text(p_text("⚠️ شما نمی‌توانید به خودتان الماس انتقال دهید!"), parse_mode=ParseMode.HTML)
            return

        amount = int(m_tr.group(1))
        min_tr = int(get_setting("min_transfer_diamonds", "50"))
        if amount < min_tr:
            await msg.reply_text(
                p_text(f"⚠️ حداقل تعداد مجاز برای انتقال <b>{min_tr} الماس</b> است! (مثال: <code>انتقال {min_tr}</code>)"),
                parse_mode=ParseMode.HTML
            )
            return

        fee, total_deduct = calc_transfer_fee(amount)
        sender_db = get_or_create_user(user.id, user.username, user.first_name)
        if sender_db["diamonds"] < total_deduct:
            await msg.reply_text(
                p_text(
                    f"❌ <b>موجودی شما با احتساب ۱۰٪ کارمزد کافی نیست!</b>\n"
                    f"💎 مبلغ انتقال: <b>{amount:,} الماس</b> | 💸 کارمزد (۱۰٪): <b>{fee:,} الماس</b>\n"
                    f"🔢 مجموع مورد نیاز: <b>{total_deduct:,} الماس</b> | 💰 موجودی شما: <b>{sender_db['diamonds']:,} الماس</b>"
                ),
                parse_mode=ParseMode.HTML
            )
            return

        get_or_create_user(target_user.id, target_user.username, target_user.first_name)
        add_user_diamonds(user.id, -total_deduct)
        add_user_diamonds(target_user.id, amount)

        new_sender = get_or_create_user(user.id)
        new_receiver = get_or_create_user(target_user.id)

        kb = InlineKeyboardMarkup([
            [
                p_btn(f"💎 انتقال موفق: {amount:,} الماس (کارمزد ۱۰٪: {fee:,})", callback_data="noop", style="success", emoji_key="check")
            ]
        ])
        await msg.reply_text(
            p_text(
                f"✅ <b>انتقال الماس در گروه با موفقیت انجام شد!</b>\n\n"
                f"📤 فرستنده: <b>{html.escape(user.first_name)}</b> (<code>{user.id}</code>)\n"
                f"📥 گیرنده: <b>{html.escape(target_user.first_name)}</b> (<code>{target_user.id}</code>)\n"
                f"💎 مبلغ واریزشده به گیرنده: <b>{amount:,} الماس</b>\n"
                f"💸 کارمزد انتقال (۱۰٪): <b>{fee:,} الماس</b> (مجموع کسر شده: <b>{total_deduct:,} الماس</b>)"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )

        # ارسال نوتیفیکیشن داخل پیوی ربات برای کاربر گیرنده
        try:
            await context.bot.send_message(
                chat_id=target_user.id,
                text=p_text(
                    f"🎁 <b>نوتیفیکیشن دریافت الماس از گروه!</b>\n\n"
                    f"👤 کاربر <b>{html.escape(user.first_name)}</b> (<code>{user.id}</code>) در گروه <b>{html.escape(chat.title or 'گروه')}</b> با ریپلای روی پیام شما تعداد <b>{amount:,} الماس</b> به حساب شما منتقل کرد!\n"
                    f"💎 موجودی جدید شما در ربات: <b>{new_receiver['diamonds']:,} الماس</b>"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=main_inline_keyboard(target_user.id)
            )
        except Exception:
            pass

async def group_callbacks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    if data.startswith("grpbal:"):
        owner_uid = int(data.split(":")[1])
        u_row = get_or_create_user(owner_uid)
        await query.answer(f"💎 موجودی الماس: {u_row['diamonds']:,} الماس", show_alert=True)
        return

    if data.startswith("grpgame:"):
        _, action, gid_str = data.split(":")
        gid = int(gid_str)

        with closing(get_conn()) as conn, conn:
            game = conn.execute("SELECT * FROM group_games WHERE id=?", (gid,)).fetchone()
            if not game:
                await query.answer("❌ بازی یافت نشد.", show_alert=True)
                return

            if game["status"] != "waiting":
                await query.answer("🏁 این بازی قبلاً به پایان رسیده یا لغو شده است.", show_alert=True)
                return

            if action == "cancel":
                if user.id != game["creator_id"] and not is_admin(user.id):
                    await query.answer("⛔ فقط سازنده بازی می‌تواند قبل از شروع آن را لغو کند!", show_alert=True)
                    return
                conn.execute("UPDATE group_games SET status='canceled' WHERE id=?", (gid,))
                await query.answer("🗑 بازی لغو شد.")
                await query.edit_message_text(
                    p_text(f"🗑 بازی شرطی <b>{game['bet_amount']:,} الماسی</b> توسط سازنده لغو گردید."),
                    parse_mode=ParseMode.HTML
                )
                return

            if action == "join":
                if user.id == game["creator_id"]:
                    await query.answer("⚠️ شما سازنده این بازی هستید! منتظر بمانید یک نفر دیگر شرکت کند.", show_alert=True)
                    return

                bet = int(game["bet_amount"])
                creator_db = get_or_create_user(game["creator_id"])
                opponent_db = get_or_create_user(user.id, user.username, user.first_name)

                if creator_db["diamonds"] < bet:
                    conn.execute("UPDATE group_games SET status='canceled' WHERE id=?", (gid,))
                    await query.answer("❌ موجودی سازنده بازی دیگر کافی نیست و بازی لغو شد!", show_alert=True)
                    await query.edit_message_text(p_text("❌ بازی به دلیل عدم موجودی کافی سازنده لغو شد."), parse_mode=ParseMode.HTML)
                    return

                if opponent_db["diamonds"] < bet:
                    await query.answer(f"⚠️ موجودی شما ({opponent_db['diamonds']} الماس) برای شرکت در این بازی ({bet} الماس) کافی نیست!", show_alert=True)
                    return

                # کسر مبلغ شرط از هر دو بازیکن و انتخاب کاملاً تصادفی برنده با جایزه ۲ برابر مبلغ شرط
                prize = bet * 2
                winner_id = secrets.choice([game["creator_id"], user.id])
                winner_name = game["creator_name"] if winner_id == game["creator_id"] else (user.first_name or "کاربر")
                loser_name = (user.first_name or "کاربر") if winner_id == game["creator_id"] else game["creator_name"]

                conn.execute("UPDATE users SET diamonds = diamonds - ? WHERE user_id=?", (bet, game["creator_id"]))
                conn.execute("UPDATE users SET diamonds = diamonds - ? WHERE user_id=?", (bet, user.id))
                conn.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id=?", (prize, winner_id))
                conn.execute(
                    "UPDATE group_games SET status='finished', opponent_id=?, opponent_name=?, winner_id=? WHERE id=?",
                    (user.id, user.first_name or "کاربر", winner_id, gid)
                )

        await query.answer(f"🎉 برنده مشخص شد: {winner_name}!", show_alert=True)
        res_kb = InlineKeyboardMarkup([
            [
                p_btn(f"🏆 برنده: {winner_name[:20]} (+{prize:,} الماس)", callback_data=f"grpbal:{winner_id}", style="success", emoji_key="crown")
            ],
            [
                p_btn(f"🎮 بازیکن ۱: {game['creator_name'][:15]}", callback_data=f"grpbal:{game['creator_id']}", style="primary"),
                p_btn(f"🎮 بازیکن ۲: {(user.first_name or 'کاربر')[:15]}", callback_data=f"grpbal:{user.id}", style="primary"),
            ]
        ])
        await query.edit_message_text(
            p_text(
                f"🎉 <b>نتیجه بازی دو نفره الماس مشخص شد!</b>\n\n"
                f"👤 بازیکن اول: <b>{html.escape(game['creator_name'])}</b>\n"
                f"👤 بازیکن دوم: <b>{html.escape(user.first_name or 'کاربر')}</b>\n"
                f"💎 مبلغ شرط هر نفر: <b>{bet:,} الماس</b>\n\n"
                f"👑 <b>برنده خوش‌شانس (انتخاب تصادفی):</b> <b>{html.escape(winner_name)}</b> (<code>{winner_id}</code>)\n"
                f"💰 <b>جایزه دریافتی (۲ برابر شرط):</b> <b>{prize:,} الماس</b>\n"
                f"💔 بازنده: <b>{html.escape(loser_name)}</b>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=res_kb
        )

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
        application.job_queue.run_repeating(lottery_expiration_job, interval=15, first=10)
    else:
        # در صورتی که job_queue نصب نبود، با تسک asyncio اجرا شود
        async def fallback_loop():
            tick = 0
            while True:
                await asyncio.sleep(15)
                tick += 15
                try:
                    await lottery_expiration_job(application)
                    if tick % 60 == 0:
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

    # ۵.۵ مکالمه انتقال الماس بین کاربران با آیدی عددی (با کارمزد ۱۰٪)
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

    # ۶. مکالمه ثبت تیکت پشتیبانی توسط کاربر
    ticket_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(support_ticket_start, pattern="^support:new_ticket$")],
        states={
            TICKET_WAIT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_ticket_receive)],
        },
        fallbacks=[
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۶.۵ مکالمه پاسخ ادمین به تیکت کاربران
    ticket_reply_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_ticket_reply_start, pattern="^ticket_reply:")],
        states={
            ADM_WAIT_TICKET_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ticket_reply_send)],
        },
        fallbacks=[
            CallbackQueryHandler(admin_page_callback, pattern="^admin:page:"),
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۷. مکالمه افزودن کانال به عضویت اجباری پیوی (حداکثر ۳ کانال)
    pvforce_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(pv_force_add_start, pattern="^pvforce:add$")],
        states={
            PVFORCE_WAIT_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, pv_force_add_receive)],
        },
        fallbacks=[
            CallbackQueryHandler(pv_force_menu_callback, pattern="^pvforce:menu$"),
            CallbackQueryHandler(self_features_callbacks, pattern="^self:features_page:"),
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۸. مکالمه ساخت قرعه‌کشی هوشمند برای کانال
    lotto_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lotto_create_start, pattern="^lotto:start$")],
        states={
            LOTTO_WAIT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lotto_step1_title)],
            LOTTO_WAIT_MIN: [
                CallbackQueryHandler(lotto_step2_min, pattern="^lotto:nomin$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lotto_step2_min),
            ],
            LOTTO_WAIT_MAX: [
                CallbackQueryHandler(lotto_step3_max, pattern="^lotto:nomax$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lotto_step3_max),
            ],
            LOTTO_WAIT_FCH: [
                CallbackQueryHandler(lotto_step4_fch, pattern="^lotto:fch_done$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lotto_step4_fch),
            ],
            LOTTO_WAIT_DESC: [
                CallbackQueryHandler(lotto_step5_desc, pattern="^lotto:nodesc$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lotto_step5_desc),
            ],
            LOTTO_WAIT_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, lotto_step6_duration)],
            LOTTO_WAIT_WINNERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, lotto_step7_winners)],
            LOTTO_WAIT_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, lotto_step8_channel)],
            LOTTO_WAIT_CONFIRM: [CallbackQueryHandler(lotto_step9_publish, pattern="^lotto:publish$")],
        },
        fallbacks=[
            CallbackQueryHandler(self_features_callbacks, pattern="^self:features_page:"),
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۹. مکالمه ساخت دکمه شیشه‌ای رنگی برای کانال
    chbtn_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(chbtn_create_start, pattern="^chbtn:start$")],
        states={
            CHBTN_WAIT_CONTENT: [MessageHandler(filters.ALL & ~filters.COMMAND, chbtn_step1_content)],
            CHBTN_WAIT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, chbtn_step2_link)],
            CHBTN_WAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, chbtn_step3_name)],
            CHBTN_WAIT_COLOR: [CallbackQueryHandler(chbtn_step4_color, pattern="^chbtn_color:")],
            CHBTN_WAIT_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, chbtn_step5_channel)],
            CHBTN_WAIT_CONFIRM: [CallbackQueryHandler(chbtn_step6_publish, pattern="^chbtn:publish$")],
        },
        fallbacks=[
            CallbackQueryHandler(self_features_callbacks, pattern="^self:features_page:"),
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۹.۵ مکالمه ساخت چالش لایکی برای کانال
    likechal_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(likechal_create_start, pattern="^likechal:start$")],
        states={
            LIKECHAL_WAIT_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, likechal_step1_channel)],
            LIKECHAL_WAIT_NAMES: [
                CallbackQueryHandler(likechal_finish_callback, pattern="^likechal:finish$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, likechal_step2_names),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(likechal_finish_callback, pattern="^likechal:finish$"),
            CallbackQueryHandler(self_features_callbacks, pattern="^self:features_page:"),
            CallbackQueryHandler(menu_router_callback, pattern="^menu:"),
            CommandHandler("start", start_cmd),
        ],
        allow_reentry=True,
    )

    # ۱۰. مکالمه پنل مدیریت ۴۰ قابلیته (شامل بکاپ کامل، بازگردانی بکاپ، الماس همگانی با متن دلخواه و ساخت کد هدیه مرحله‌ای)
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
            ADM_WAIT_PUBLIC_DIAMOND_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_public_diamond_step1_amount)],
            ADM_WAIT_PUBLIC_DIAMOND_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_public_diamond_step2_text)],
            ADM_WAIT_GIFT_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gift_code_step1_word)],
            ADM_WAIT_GIFT_DIAMONDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gift_code_step2_diamonds)],
            ADM_WAIT_GIFT_CAPACITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gift_code_step3_capacity)],
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
    app.add_handler(ticket_conv)
    app.add_handler(ticket_reply_conv)
    app.add_handler(pvforce_conv)
    app.add_handler(lotto_conv)
    app.add_handler(chbtn_conv)
    app.add_handler(likechal_conv)
    app.add_handler(admin_conv)
    app.add_handler(CommandHandler("start", start_cmd))

    app.add_handler(InlineQueryHandler(inline_pv_force_handler))
    app.add_handler(CallbackQueryHandler(activate_self_code_keypad_callback, pattern="^codepad:"))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(stop_self_now_callback, pattern="^self:stop_now$"))
    app.add_handler(CallbackQueryHandler(central_panel_24h_callback, pattern="^self:central_panel$"))
    app.add_handler(CallbackQueryHandler(pv_force_menu_callback, pattern="^pvforce:(menu|toggle|del:)"))
    app.add_handler(CallbackQueryHandler(pv_check_callback, pattern="^pvcheck:"))
    app.add_handler(CallbackQueryHandler(lottery_callbacks_handler, pattern="^(lottocnt:|lottocheck:)"))
    app.add_handler(CallbackQueryHandler(likechal_vote_callback, pattern="^likechal_vote:"))
    app.add_handler(CallbackQueryHandler(group_callbacks_handler, pattern="^(grpbal:|grpgame:)"))
    app.add_handler(CallbackQueryHandler(self_features_callbacks, pattern="^(self:features_page:|self:features_guide:|ftoggle:|fbulk:)"))
    app.add_handler(CallbackQueryHandler(tabchi_menu_callback, pattern="^(menu:tabchi|tabchi:)"))
    app.add_handler(CallbackQueryHandler(ton_paid_user_confirm_callback, pattern="^tonpaid:"))
    app.add_handler(CallbackQueryHandler(admin_ton_order_action_callback, pattern="^tonadm:"))
    app.add_handler(CallbackQueryHandler(admin_page_callback, pattern="^admin:page:"))
    app.add_handler(CallbackQueryHandler(admin_remove_fch_callback, pattern="^rmfch:"))
    app.add_handler(CallbackQueryHandler(menu_router_callback, pattern="^(menu:|buy:rial)"))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="^noop$"))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, group_commands_handler))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, fallback_pending_login_text_handler))

    logger.info("🌑 ربات سلف دارک (Self Dark) با ۴۶ قابلیت سلف، چالش لایکی کانال، لیدربورد، هدیه ورود ۶۰ الماس و پینگر ۵ دقیقه‌ای Render آماده به کار است.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

