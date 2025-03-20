import logging
import os
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Загрузка переменных окружения из файла .env
load_dotenv()

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Константы для SWAPI
SWAPI_BASE_URL = "https://swapi.dev/api"
CHARACTERS_PER_PAGE = 10

# Получение токена бота из переменной окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Токен бота не найден в переменных окружения. Убедитесь, что файл .env настроен правильно.")

# Функция для получения списка персонажей с SWAPI
def get_characters(page: int):
    url = f"{SWAPI_BASE_URL}/people/?page={page}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get("results", []), data.get("next"), data.get("previous")
    return [], None, None

# Функция для получения информации о персонаже
def get_character_info(character_url: str):
    response = requests.get(character_url)
    if response.status_code == 200:
        return response.json()
    return None

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Инициализация страницы
    context.user_data['page'] = 1  # SWAPI начинает страницы с 1
    await show_characters(update, context)

# Показ списка персонажей
async def show_characters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем текущую страницу из context.user_data
    page = context.user_data.get('page', 1)  # По умолчанию страница 1
    characters, next_page, previous_page = get_characters(page)
    
    if not characters:
        await update.message.reply_text("Персонажи не найдены.")
        return
    
    keyboard = []
    for character in characters:
        character_name = character.get("name", "Unknown")
        character_url = character.get("url")
        keyboard.append([InlineKeyboardButton(character_name, callback_data=f"character_{character_url}")])
    
    navigation_buttons = []
    if previous_page:
        navigation_buttons.append(InlineKeyboardButton("Предыдущая", callback_data="prev_page"))
    # Показываем кнопку "Следующая" только если есть следующая страница
    if next_page:
        navigation_buttons.append(InlineKeyboardButton("Следующая", callback_data="next_page"))
    
    if navigation_buttons:
        keyboard.append(navigation_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Если это новое сообщение (например, после /start), используем reply_text
    if update.message:
        sent_message = await update.message.reply_text("Выберите персонажа:", reply_markup=reply_markup)
        # Сохраняем ID сообщения бота
        if 'message_ids' not in context.user_data:
            context.user_data['message_ids'] = []
        context.user_data['message_ids'].append(sent_message.message_id)
    # Если это редактирование существующего сообщения (например, после нажатия кнопки), используем edit_message_text
    elif update.callback_query:
        await update.callback_query.edit_message_text("Выберите персонажа:", reply_markup=reply_markup)

# Обработка нажатий на кнопки
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("character_"):
        character_url = query.data.split("_", 1)[1]
        character_info = get_character_info(character_url)
        
        if character_info:
            info_text = (
                f"Имя: {character_info.get('name', 'Unknown')}\n"
                f"Рост: {character_info.get('height', 'Unknown')}\n"
                f"Вес: {character_info.get('mass', 'Unknown')}\n"
                f"Цвет волос: {character_info.get('hair_color', 'Unknown')}\n"
                f"Цвет кожи: {character_info.get('skin_color', 'Unknown')}\n"
                f"Цвет глаз: {character_info.get('eye_color', 'Unknown')}\n"
                f"Год рождения: {character_info.get('birth_year', 'Unknown')}\n"
                f"Пол: {character_info.get('gender', 'Unknown')}"
            )
            keyboard = [[InlineKeyboardButton("Вернуться обратно", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(info_text, reply_markup=reply_markup)
        else:
            await query.edit_message_text("Информация о персонаже не найдена.")
    elif query.data == "prev_page":
        # Уменьшаем номер страницы
        context.user_data['page'] = max(1, context.user_data.get('page', 1) - 1)
        await show_characters(update, context)
    elif query.data == "next_page":
        # Увеличиваем номер страницы
        context.user_data['page'] = context.user_data.get('page', 1) + 1
        await show_characters(update, context)
    elif query.data == "back":
        # Возвращаемся к списку персонажей
        await show_characters(update, context)

# Обработка текстовых сообщений (ввод порядкового номера персонажа)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        character_id = int(update.message.text)
        if character_id < 1 or character_id > 83:
            await update.message.reply_text("Пожалуйста, введите число от 1 до 83.")
            return
        
        # Удаляем предыдущие сообщения бота и запрос пользователя
        if 'message_ids' in context.user_data:
            for message_id in context.user_data['message_ids']:
                try:
                    await context.bot.delete_message(update.effective_chat.id, message_id)
                except Exception as e:
                    logging.error(f"Ошибка при удалении сообщения {message_id}: {e}")
            # Очищаем список сообщений
            context.user_data['message_ids'] = []
        
        # Удаляем запрос пользователя
        try:
            await context.bot.delete_message(update.effective_chat.id, update.message.message_id)
        except Exception as e:
            logging.error(f"Ошибка при удалении запроса пользователя: {e}")
        
        # Получаем информацию о персонаже по его ID
        character_url = f"{SWAPI_BASE_URL}/people/{character_id}/"
        character_info = get_character_info(character_url)
        
        if character_info:
            info_text = (
                f"Имя: {character_info.get('name', 'Unknown')}\n"
                f"Рост: {character_info.get('height', 'Unknown')}\n"
                f"Вес: {character_info.get('mass', 'Unknown')}\n"
                f"Цвет волос: {character_info.get('hair_color', 'Unknown')}\n"
                f"Цвет кожи: {character_info.get('skin_color', 'Unknown')}\n"
                f"Цвет глаз: {character_info.get('eye_color', 'Unknown')}\n"
                f"Год рождения: {character_info.get('birth_year', 'Unknown')}\n"
                f"Пол: {character_info.get('gender', 'Unknown')}"
            )
            keyboard = [[InlineKeyboardButton("Вернуться обратно", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            sent_message = await update.message.reply_text(info_text, reply_markup=reply_markup)
            # Сохраняем ID последнего сообщения
            if 'message_ids' not in context.user_data:
                context.user_data['message_ids'] = []
            context.user_data['message_ids'].append(sent_message.message_id)
        else:
            await update.message.reply_text("Персонаж с таким ID не найден.")
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите порядковый номер персонажа (число от 1 до 83).")

# Команда /clear
async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        # Удаляем все сообщения бота и пользователя
        if 'message_ids' in context.user_data:
            for message_id in context.user_data['message_ids']:
                try:
                    await context.bot.delete_message(chat_id, message_id)
                except Exception as e:
                    logging.error(f"Ошибка при удалении сообщения {message_id}: {e}")
            # Очищаем список сообщений
            context.user_data['message_ids'] = []
        
        # Удаляем последний запрос пользователя
        try:
            await context.bot.delete_message(chat_id, update.message.message_id)
        except Exception as e:
            logging.error(f"Ошибка при удалении запроса пользователя: {e}")
        
        await update.message.reply_text("Чат очищен.")
    except Exception as e:
        logging.error(f"Ошибка при очистке чата: {e}")
        await update.message.reply_text("Не удалось очистить чат полностью.")

# Запуск бота
def main():
    # Используем токен из переменной окружения
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear_chat))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == '__main__':
    main()
