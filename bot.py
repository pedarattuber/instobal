import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from instagrapi import Client

# --------------------- تنظیمات ---------------------
TOKEN = "1747414200:ijR7oyeA3Iae0c-Pv70-Izf5o9tUdPdntgI"  # ← توکن ربات بله را جایگزین کنید
BALE_BASE_URL = "https://tapi.bale.ai/bot"           # پایگاه API اصلی
BALE_BASE_FILE_URL = "https://tapi.bale.ai/file/bot" # پایگاه دانلود فایل

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

LOGIN_STATE, MAIN_MENU, AWAITING_INPUT = range(3)

# ساختار جدید: user_data[user_id] = {'manager': InstagramManager, 'pending': None}
user_data = {}

# --------------------- کلاس مدیریت اینستاگرام ---------------------
class InstagramManager:
    def __init__(self):
        self.cl = Client()

    def login_with_session(self, session_file):
        try:
            if os.path.exists(session_file):
                self.cl.load_settings(session_file)
                self.cl.get_timeline_feed()
                return True
        except Exception as e:
            logger.error(f"Session invalid: {e}")
        return False

    def login_with_credentials(self, username, password):
        try:
            self.cl.login(username, password)
            self.cl.dump_settings(f"{username}_session.json")
            return True
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    def get_profile_info(self, username):
        try:
            user_id = self.cl.user_id_from_username(username)
            user_info = self.cl.user_info(user_id)
            return {
                "username": user_info.username,
                "full_name": user_info.full_name,
                "followers": user_info.follower_count,
                "following": user_info.following_count,
                "posts": user_info.media_count,
                "bio": user_info.biography,
                "is_private": user_info.is_private
            }
        except:
            return None

    def upload_photo(self, photo_path, caption=""):
        try:
            media = self.cl.photo_upload(photo_path, caption)
            return media.code
        except:
            return None

    def like_post(self, media_pk):
        try:
            self.cl.media_like(media_pk)
            return True
        except:
            return False

    def follow_user(self, username):
        try:
            user_id = self.cl.user_id_from_username(username)
            self.cl.user_follow(user_id)
            return True
        except:
            return False

    def unfollow_user(self, username):
        try:
            user_id = self.cl.user_id_from_username(username)
            self.cl.user_unfollow(user_id)
            return True
        except:
            return False

    def media_pk_from_url(self, url):
        try:
            return self.cl.media_pk_from_url(url)
        except:
            return None

    def download_media(self, media_pk):
        try:
            info = self.cl.media_info(media_pk)
            if info.media_type == 1:
                data = self.cl.photo_download(media_pk)
                return data, 'photo', info.thumbnail_url if hasattr(info, 'thumbnail_url') else None
            elif info.media_type == 2:
                data = self.cl.video_download(media_pk)
                return data, 'video', None
            elif info.media_type == 8:
                if info.resources:
                    first = info.resources[0]
                    if first.media_type == 1:
                        data = self.cl.photo_download(media_pk)
                        return data, 'photo', None
                    else:
                        data = self.cl.video_download(media_pk)
                        return data, 'video', None
                else:
                    return None, None, None
        except:
            return None, None, None

    def get_story_feed(self):
        try:
            tray = self.cl.get_tray()
            stories = []
            for item in tray:
                if item.media:
                    for m in item.media:
                        stories.append({
                            'id': m.pk,
                            'user': item.user.username,
                            'media_type': m.media_type,
                            'url_photo': m.thumbnail_url if m.media_type == 1 else None,
                            'url_video': m.video_url if m.media_type == 2 else None,
                        })
            return stories
        except:
            return []

    def get_user_stories(self, username):
        try:
            user_id = self.cl.user_id_from_username(username)
            stories = self.cl.user_stories(user_id)
            result = []
            for s in stories:
                result.append({
                    'id': s.pk,
                    'media_type': s.media_type,
                    'url_photo': s.thumbnail_url if s.media_type == 1 else None,
                    'url_video': s.video_url if s.media_type == 2 else None,
                })
            return result
        except:
            return []

    def get_reels_feed(self):
        try:
            tray = self.cl.reels_tray()
            reels = []
            for item in tray:
                if item.media:
                    for m in item.media:
                        reels.append({
                            'id': m.pk,
                            'user': item.user.username,
                            'media_type': m.media_type,
                            'url_video': m.video_url if m.media_type == 2 else None,
                            'url_photo': m.thumbnail_url if m.media_type == 1 else None,
                        })
            return reels
        except:
            return []

    def get_user_reels(self, username):
        try:
            user_id = self.cl.user_id_from_username(username)
            clips = self.cl.user_clips(user_id)
            result = []
            for c in clips:
                result.append({
                    'id': c.pk,
                    'media_type': c.media_type,
                    'url_video': c.video_url if c.media_type == 2 else None,
                    'url_photo': c.thumbnail_url if c.media_type == 1 else None,
                })
            return result
        except:
            return []

    def download_story(self, pk):
        try:
            info = self.cl.media_info(pk)
            if info.media_type == 1:
                return self.cl.photo_download(pk), 'photo'
            else:
                return self.cl.video_download(pk), 'video'
        except:
            return None, None

# --------------------- کیبوردها ---------------------
def start_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 ورود با نام کاربری و رمز عبور", callback_data="login_cred")],
        [InlineKeyboardButton("🔁 ورود با فایل Session", callback_data="login_session")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")]
    ])

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 پروفایل من", callback_data="my_profile"),
         InlineKeyboardButton("📊 اطلاعات کاربر", callback_data="user_info")],
        [InlineKeyboardButton("📸 آپلود عکس", callback_data="upload_photo"),
         InlineKeyboardButton("❤️ لایک پست", callback_data="like_post")],
        [InlineKeyboardButton("➕ فالو کاربر", callback_data="follow_user"),
         InlineKeyboardButton("➖ آنفالو کاربر", callback_data="unfollow_user")],
        [InlineKeyboardButton("📖 استوری‌های من", callback_data="story_feed"),
         InlineKeyboardButton("👥 استوری کاربر", callback_data="story_user")],
        [InlineKeyboardButton("🎥 ریلزهای من", callback_data="reels_feed"),
         InlineKeyboardButton("👤 ریلز کاربر", callback_data="reels_user")],
        [InlineKeyboardButton("🔗 دریافت پست", callback_data="view_post")],
        [InlineKeyboardButton("🚪 خروج", callback_data="logout")]
    ])

# --------------------- هندلرها ---------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "👋 به ربات مدیریت اینستاگرام خوش آمدید!\nیک روش ورود را انتخاب کنید:",
        reply_markup=start_keyboard()
    )
    return LOGIN_STATE

async def login_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "login_cred":
        await query.edit_message_text("📧 نام کاربری و رمز عبور اینستاگرام را به صورت زیر ارسال کنید:\n\n`username:password`")
        return LOGIN_STATE
    elif query.data == "login_session":
        await query.edit_message_text("📂 فایل session با پسوند `.json` را ارسال کنید.")
        return LOGIN_STATE
    elif query.data == "help":
        await query.edit_message_text(
            "ℹ️ **راهنمای ربات:**\n"
            "این ربات امکان مدیریت حساب اینستاگرام را از طریق تلگرام فراهم می‌کند.\n"
            "تمام عملیات با منوهای دکمه‌ای انجام می‌شود.\n\n"
            "**⚠️ هشدار:** استفاده از این ربات قوانین اینستاگرام را نقض می‌کند و احتمال مسدود شدن حساب وجود دارد.\n"
            "/start - شروع دوباره"
        )
        return MAIN_MENU

async def handle_login_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    insta = InstagramManager()

    if update.message.document:
        file = await update.message.document.get_file()
        session_path = f"{user_id}_session.json"
        await file.download_to_drive(session_path)
        if insta.login_with_session(session_path):
            user_data[user_id] = {'manager': insta, 'pending': None}  # ذخیره به‌عنوان دیکشنری
            await update.message.reply_text("✅ ورود موفق!")
            return await show_main_menu(update)
        else:
            await update.message.reply_text("❌ فایل session معتبر نیست.")
            return LOGIN_STATE

    elif ":" in update.message.text:
        username, password = update.message.text.split(":", 1)
        if insta.login_with_credentials(username.strip(), password.strip()):
            user_data[user_id] = {'manager': insta, 'pending': None}  # ذخیره به‌عنوان دیکشنری
            await update.message.delete()
            await update.message.reply_text("✅ ورود موفق!")
            return await show_main_menu(update)
        else:
            await update.message.reply_text("❌ نام کاربری یا رمز عبور اشتباه است.")
            return LOGIN_STATE
    else:
        await update.message.reply_text("⚠️ فرمت نادرست. دوباره تلاش کنید.")
        return LOGIN_STATE

async def show_main_menu(update: Update):
    await update.message.reply_text("📋 منوی اصلی:", reply_markup=main_menu_keyboard())
    return MAIN_MENU

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_entry = user_data.get(user_id)

    if not user_entry or 'manager' not in user_entry:
        await query.edit_message_text("⚠️ لطفاً ابتدا وارد شوید: /start")
        return ConversationHandler.END

    insta = user_entry['manager']
    action = query.data

    if action == "my_profile":
        profile = insta.get_profile_info(insta.cl.username)
        if profile:
            text = (f"👤 **پروفایل شما:**\n🔹 @{profile['username']}\n🔹 {profile['full_name']}\n"
                    f"🔹 دنبال‌کنندگان: {profile['followers']}\n🔹 دنبال‌شونده: {profile['following']}\n"
                    f"🔹 پست‌ها: {profile['posts']}\n{'🔒 خصوصی' if profile['is_private'] else '🔓 عمومی'}")
        else:
            text = "❌ خطا در دریافت اطلاعات."
        await query.edit_message_text(text)
        return MAIN_MENU

    elif action == "story_feed":
        await query.edit_message_text("⏳ در حال دریافت استوری‌های دوستان...")
        stories = insta.get_story_feed()
        if not stories:
            await query.message.reply_text("ℹ️ هیچ استوری جدیدی وجود ندارد.")
        else:
            for s in stories:
                if s['media_type'] == 1:
                    await query.message.reply_photo(photo=s['url_photo'], caption=f"استوری از @{s['user']}")
                else:
                    await query.message.reply_video(video=s['url_video'], caption=f"استوری از @{s['user']}")
        return MAIN_MENU

    elif action == "reels_feed":
        await query.edit_message_text("⏳ در حال دریافت ریلزهای دوستان...")
        reels = insta.get_reels_feed()
        if not reels:
            await query.message.reply_text("ℹ️ هیچ ریلزی وجود ندارد.")
        else:
            for r in reels:
                if r.get('url_video'):
                    await query.message.reply_video(video=r['url_video'], caption=f"ریلز از @{r['user']}")
                else:
                    await query.message.reply_photo(photo=r['url_photo'], caption=f"ریلز از @{r['user']}")
        return MAIN_MENU

    elif action == "logout":
        del user_data[user_id]
        await query.edit_message_text("👋 از حساب خارج شدید. /start")
        return ConversationHandler.END

    # عملیات نیازمند ورودی — ذخیره pending در دیکشنری
    user_entry['pending'] = action
    prompts = {
        "user_info": "🔍 نام کاربری اینستاگرام را وارد کنید:",
        "upload_photo": "📸 عکس خود را به همراه کپشن (اختیاری) ارسال کنید.\n"
                        "می‌توانید ابتدا عکس را بفرستید و سپس کپشن را جداگانه ارسال کنید.",
        "like_post": "❤️ لینک پست اینستاگرام را ارسال کنید:",
        "follow_user": "➕ نام کاربری برای فالو را وارد کنید:",
        "unfollow_user": "➖ نام کاربری برای آنفالو را وارد کنید:",
        "story_user": "👥 نام کاربری برای مشاهده استوری‌هایش را وارد کنید:",
        "reels_user": "👤 نام کاربری برای مشاهده ریلزهایش را وارد کنید:",
        "view_post": "🔗 لینک پست اینستاگرام را برای دانلود ارسال کنید:"
    }
    await query.edit_message_text(prompts[action])
    return AWAITING_INPUT

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_entry = user_data.get(user_id)

    if not user_entry or 'manager' not in user_entry:
        await update.message.reply_text("خطا. /start را بزنید.")
        return ConversationHandler.END

    insta = user_entry['manager']
    pending = user_entry.pop('pending', None)  # برداشتن pending برای جلوگیری از تکرار

    if not pending:
        await update.message.reply_text("⚠️ دستور نامشخص. از منو استفاده کنید.")
        return await show_main_menu(update)

    # ----- ورودی متنی (بدون عکس) -----
    if update.message.text and not update.message.photo:
        text = update.message.text.strip()

        if pending in ("user_info", "follow_user", "unfollow_user", "story_user", "reels_user"):
            if pending == "user_info":
                profile = insta.get_profile_info(text)
                if profile:
                    answer = (f"📊 **@{profile['username']}**\nنام: {profile['full_name']}\n"
                              f"دنبال‌کنندگان: {profile['followers']}\nدنبال‌شونده: {profile['following']}\n"
                              f"پست‌ها: {profile['posts']}\n{'🔒 خصوصی' if profile['is_private'] else '🔓 عمومی'}\n"
                              f"بیو: {profile['bio']}")
                else:
                    answer = "❌ کاربر یافت نشد."
            elif pending == "follow_user":
                answer = "✅ فالو شد." if insta.follow_user(text) else "❌ خطا در فالو."
            elif pending == "unfollow_user":
                answer = "✅ آنفالو شد." if insta.unfollow_user(text) else "❌ خطا در آنفالو."
            elif pending == "story_user":
                stories = insta.get_user_stories(text)
                if not stories:
                    answer = "ℹ️ استوری‌ای وجود ندارد یا کاربر خصوصی است."
                else:
                    await update.message.reply_text(f"📖 استوری‌های @{text}:")
                    for s in stories:
                        data, mtype = insta.download_story(s['id'])
                        if mtype == 'photo':
                            await update.message.reply_photo(photo=data)
                        elif mtype == 'video':
                            await update.message.reply_video(video=data)
                    answer = "✅ پایان استوری‌ها."
            elif pending == "reels_user":
                reels = insta.get_user_reels(text)
                if not reels:
                    answer = "ℹ️ ریلزی وجود ندارد."
                else:
                    await update.message.reply_text(f"🎥 ریلزهای @{text}:")
                    for r in reels:
                        if r.get('url_video'):
                            await update.message.reply_video(video=r['url_video'])
                        else:
                            await update.message.reply_photo(photo=r['url_photo'])
                    answer = "✅ پایان ریلزها."
            await update.message.reply_text(answer)
            return await show_main_menu(update)

        elif pending == "like_post":
            media_pk = insta.media_pk_from_url(text)
            if media_pk and insta.like_post(media_pk):
                await update.message.reply_text("❤️ لایک شد.")
            else:
                await update.message.reply_text("❌ لینک نامعتبر یا خطا در لایک.")
            return await show_main_menu(update)

        elif pending == "view_post":
            media_pk = insta.media_pk_from_url(text)
            if not media_pk:
                await update.message.reply_text("❌ لینک نامعتبر.")
            else:
                data, mtype, _ = insta.download_media(media_pk)
                if mtype == 'photo':
                    await update.message.reply_photo(photo=data)
                elif mtype == 'video':
                    await update.message.reply_video(video=data)
                else:
                    await update.message.reply_text("❌ دانلود ممکن نشد.")
            return await show_main_menu(update)

    # ----- آپلود عکس -----
    if update.message.photo and pending == "upload_photo":
        file = await update.message.photo[-1].get_file()
        photo_path = f"temp_{user_id}.jpg"
        await file.download_to_drive(photo_path)
        caption = update.message.caption or ""
        shortcode = insta.upload_photo(photo_path, caption)
        os.remove(photo_path)
        if shortcode:
            await update.message.reply_text(f"📸 عکس آپلود شد.\n🔗 https://instagram.com/p/{shortcode}")
        else:
            await update.message.reply_text("❌ آپلود ناموفق.")
        return await show_main_menu(update)

    await update.message.reply_text("⚠️ دستور نامشخص.")
    return await show_main_menu(update)

# --------------------- اجرای ربات ---------------------
def main():
    application = (
        Application.builder()
        .token(TOKEN)
        .base_url(BALE_BASE_URL)
        .base_file_url(BALE_BASE_FILE_URL)  # تنظیم آدرس دانلود فایل برای بله
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOGIN_STATE: [
                CallbackQueryHandler(login_callback),
                MessageHandler(filters.Document.FileExtension("json"), handle_login_message),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login_message)
            ],
            MAIN_MENU: [
                CallbackQueryHandler(main_menu_handler),
            ],
            AWAITING_INPUT: [
                MessageHandler(filters.TEXT | filters.PHOTO, handle_input)
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
