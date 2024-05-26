import random
import re
import logging
import sqlite3
import enum
from config import API_TOKEN
from telegram import ReplyKeyboardMarkup, Update, ForceReply
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="logs.log",
)
logger = logging.getLogger(__name__)


class Servers(enum.Enum):
    UNKNOWN = 0
    EU = 1
    NA = 2
    SAR = 4
    ASIA = 3


db_name = "db.sqlite"
conn = sqlite3.connect(db_name)


class SQL:
    def __init__(self, conn):
        self.conn = conn

    def create_tables(self):
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                server INTEGER NOT NULL,
                lottery INTEGER DEFAULT 0
            )
            """
        )
        self.conn.commit()
        c.close()

    def add_user(self, username: str, password: str, server: Servers, user_id: int):
        try:
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO users (id, username, password, server) VALUES (?, ?, ?, ?)",
                (user_id, username, password, server.value),
            )
            self.conn.commit()
            c.close()
        except Exception as ex:
            logger.critical(ex)
            return False

    def update_user(self, username: str, password: str, server: Servers, user_id: int):
        try:
            c = self.conn.cursor()
            c.execute(
                "UPDATE users set username = ?, password = ?, server = ? where id = ?",
                (username, password, server.value, user_id),
            )
            self.conn.commit()
            c.close()
            return True
        except Exception as ex:
            logger.critical(ex)
            return False

    def exists_user(self, user_id: int):
        c = self.conn.cursor()
        c.execute("SELECT id from users where id = ?;", (user_id,))
        sqData = c.fetchone()
        self.conn.commit()
        c.close()
        return sqData != None

    def SqliteSelectOne(self, query: str, params: tuple = None):
        cursor = self.conn.cursor()
        if params is not None:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        sqData = cursor.fetchone()
        cursor.close()
        return sqData

    def check_Lottery(self):
        try:
            c = self.conn.cursor()
            c.execute("SELECT * FROM users")
            my_list = c.fetchall()
            if my_list:
                my_list = [i[0] for i in my_list]
                random_user = random.choice(my_list)
                c.execute("SELECT * FROM users WHERE id=?", (random_user,))
                user_data = c.fetchone()

                if user_data[4] == 0:
                    c.execute("UPDATE users SET lottery=1 WHERE id=?", (random_user,))
                    my_list.remove(random_user)
                    self.conn.commit()
                    c.close()
                    return random_user
                else:
                    # return user_data
                    return "User has already won the lottery"
            else:
                c.close()
                return "No users found in the database"
        except Exception as ex:
            logger.critical(ex)
            return "An error occurred"


mySql = SQL(conn)

USERNAME, PASSWORD, SERVER = range(3)


def is_farsi(text):
    farsi_char = re.compile("[آ-ی]+")
    return bool(farsi_char.fullmatch(text))


def is_correct(password):
    return len(password) >= 7


async def random_lottery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_telegram = update.message.from_user.username
    if id_telegram == "S_abyss7":
        name_user = mySql.check_Lottery()
        await update.message.reply_text(f"قرعه به اسم {name_user} افتادش ")
    else:
        await update.message.reply_text("شما اجازه ی قرعه کشی انداختن ندارید ")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = update.message.from_user.full_name
    id_telegram = update.message.from_user.username
    context.user_data["telegram_id"] = (
        update.message.from_user.id
    )  # ذخیره آیدی تلگرام در user_data
    await update.message.reply_text(
        f"سلام  😍 {full_name}! لطفاً یوزرنیم خود را وارد کنید:\n"
        f"شما با آیدی  - {id_telegram} -  ربات ما را استارت کردید\n"
        f"\n/cancel بزن اگه منصرف شدی 😑\n"
    )
    return USERNAME


async def username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_farsi(update.message.text):
        await update.message.reply_text(
            "لطفاً از حروف انگلیسی برای یوزرنیم استفاده کنید."
        )
        return USERNAME
    else:
        context.user_data["username"] = update.message.text
        await update.message.reply_text(
            "یوزرنیم شما ذخیره شد. حالا لطفاً پسورد خود را وارد کنید:"
        )
        return PASSWORD


async def password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_correct(update.message.text):
        await update.message.reply_text("پسورد باید حداقل ۷ کاراکتر باشد.")
        return PASSWORD
    else:
        context.user_data["password"] = update.message.text
        reply_keyboard = [["Asia", "Europe", "America", "TW/HK/MO"]]
        await update.message.reply_text(
            f"پسورد شما ذخیره شد.😊 حالا لطفاً سرور خود را انتخاب کنید:\n"
            f"/cancel بزن اگه منصرف شدی 😑",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard,
                one_time_keyboard=True,
                input_field_placeholder="کدوم سروری؟",
            ),
        )
        return SERVER


async def server(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    server_text = update.message.text
    server_mapping = {
        "Asia": Servers.ASIA,
        "Europe": Servers.EU,
        "America": Servers.NA,
        "TW/HK/MO": Servers.SAR,
    }
    server = server_mapping.get(server_text, Servers.UNKNOWN)

    context.user_data["server"] = server

    # Save user data to database
    username = context.user_data["username"]
    password = context.user_data["password"]
    telegram_id = context.user_data["telegram_id"]  # دریافت آیدی تلگرام از user_data
    if mySql.exists_user(telegram_id):
        mySql.update_user(username, password, server, telegram_id)

    else:
        mySql.add_user(username, password, server, telegram_id)
    await update.message.reply_text(
        f" 🙃 اطلاعات شما ذخیره شد:\n"
        f"یوزرنیم: {username}\n"
        f"پسورد: {password}\n"
        f"سرور: {server.name}"
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("باشه بابا دفعه بدی 😒", reply_markup=ForceReply())
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token(API_TOKEN).build()
    mySql.create_tables()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, username)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password)],
            SERVER: [
                MessageHandler(
                    filters.Regex("^(Asia|Europe|America|TW/HK/MO)$"), server
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    lottery_handler = CommandHandler("lottery", random_lottery)
    application.add_handler(lottery_handler)
    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
