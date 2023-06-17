#!/srv/horizon/venv/bin/python3
import json
import logging
import re
import os

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
import db_api

ADMIN_ID = 212504240

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

AUTH, FIO, PHONE = range(3)
WORKER_CHOICE, WORKER_NOT_FOUND = range(3, 5)
GIVE_SEARCH, GIVE_CHOOSE_WORKER, GIVE_CHOOSE_REASON = range(6, 9)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    user_status = db_api.getUserStatus(update.effective_user.id)
    if user_status:
        if user_status == 'active':
            keyboard = [
                [
                    InlineKeyboardButton("Начислить движки", callback_data=f"give"),
                    InlineKeyboardButton("Кошелек", callback_data=f"wallet")
                ],
                [
                    InlineKeyboardButton("Мой баланс", callback_data=f"balance"),
                    InlineKeyboardButton("Статистика", callback_data=f"stats")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            name = db_api.get_user_name(update.effective_user.id).split()[1]
            await update.message.reply_text(f"Приветствую, {name}! Чем могу быть полезен?", reply_markup=reply_markup)
        elif user_status == 'pending':
            await update.message.reply_text('Ожидается подтверждение учетной записи администратором', reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif user_status == 'rejected':
            await update.message.reply_text('Запрос на авторизацию отклонен администратором', reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif user_status == 'disabled':
            await update.message.reply_text('Учетная запись заблокирована', reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
    else:
        reply_keyboard = [["Регистрация", "Правила"]]
        await update.message.reply_html("""
У каждого свой горизонт 🌅

Горизонт - это новый мотивационный инструмент, позволяющий оперативно оценивать и поощрять сотрудника за продуктивную работу в рамках основной, проектной, поддерживающей деятельности и кроссфункционального взаимодействия.

Начисляйте и получайте баллы - «движки»! Чем больше «движков», тем существеннее поощрение!

Действуй! Шагни за Горизонт!
        """, 
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True
            )
        )
        return AUTH

async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    await update.message.reply_text(
            "Введите ваши ФИО:", reply_markup=ReplyKeyboardRemove()
    )
    return FIO

async def get_fio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    context.user_data["fio"] = update.message.text
    logger.info(context.user_data["fio"])
    await update.message.reply_text(
            "Введите ваш номер ВТС:", reply_markup=ReplyKeyboardRemove()
    )
    return PHONE 

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    context.user_data["phone"] = update.message.text
    logger.info(context.user_data["phone"])
    user_data = {"fio": context.user_data.pop("fio"), "phone": context.user_data.pop("phone"), "id": user.id}
    db_api.register_user(user_data)
    await send_auth_message(user_data, context)
    await update.message.reply_text(
            "Ваши данные переданы администратору! После подтверждения регистрации Вам поступит сообщение.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def send_auth_message(user_data, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
                [
                InlineKeyboardButton("Зарегистрировать", callback_data=f"register_{user_data['id']}"),
                InlineKeyboardButton("Отказать", callback_data=f"reject_{user_data['id']}")
            ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"""Новая регистрация:
ФИО: {user_data['fio']}
ВТС: {user_data['phone']}
id: {user_data['id']}""", reply_markup=reply_markup)

async def register_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.data.split('_')[1]
    fio = re.search("ФИО: (?P<fio>.*)", query.message.text)
    if fio:
        #уберем пробелы и спецсимволы, сделаем букву каждого слова заглавной для поиска
        context.user_data['reg_fio'] = ' '.join([re.sub(r'[\W\d_]+', '', s.capitalize()) for s in fio['fio'].lower().split()])
        context.user_data['reg_user_id'] = int(user_id)
        context.user_data['reg_message_id'] = query.message.id
        new_text = query.message.text + '\nВыбрана опция "Зарегистрировать". Выберите работника'
        await query.edit_message_reply_markup(reply_markup=None)
        context.user_data['reg_workers_msgs'] = []
        workers = db_api.get_workers(context.user_data['reg_fio'])
        if len(workers) > 0:
            msg = await context.bot.send_message(chat_id=ADMIN_ID, text="Вот кого я нашел по ФИО:")
            context.user_data['reg_workers_msgs'].append(msg.id)
            for worker in workers:
                keyboard = [
                        [
                            InlineKeyboardButton("Выбрать", callback_data=f"worker_{worker['id']}")
                        ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                msg = await context.bot.send_message(chat_id=ADMIN_ID, text=f"""id: {worker['id']}
ФИО: {worker['fio']}
ТУ: {worker['tu']}
Телефоны: {worker['phone']}""", reply_markup=reply_markup)
                context.user_data['reg_workers_msgs'].append(msg.id)
            keyboard = [
                [
                    InlineKeyboardButton("Выбрать", callback_data=f"worker_{worker['id']}"),
                    InlineKeyboardButton("Ввести id вручную", callback_data=f"worker_not_found")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.edit_message_reply_markup(chat_id=ADMIN_ID, message_id=context.user_data['reg_workers_msgs'][-1], reply_markup=reply_markup)
            return WORKER_CHOICE
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text="По указанным ФИО в БД работников никого не найдено")
            return ConversationHandler.END
    else:
        return ConversationHandler.END

async def choose_worker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if len(query.data.split('_')) == 2:
        worker_id = query.data.split('_')[1]
        db_api.set_worker(context.user_data['reg_user_id'], worker_id)
        await context.bot.send_message(chat_id=context.user_data['reg_user_id'], text="Ваше участие подтверждено. Добро пожаловать в программу!")
        text = f"""Пользователь id {context.user_data['reg_user_id']} зарегистрирован
Связан с работником:
{query.message.text}"""
        await context.bot.edit_message_text(chat_id=ADMIN_ID, message_id=context.user_data['reg_message_id'], text=text)
        for msg in context.user_data['reg_workers_msgs']:
            await context.bot.delete_message(chat_id=ADMIN_ID, message_id=msg)
        context.user_data.pop('reg_workers_msgs')
        context.user_data.pop('reg_fio')
        context.user_data.pop('reg_user_id')
        context.user_data.pop('reg_message_id')
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=ADMIN_ID, text="Введите id работника вручную: ")
        return WORKER_NOT_FOUND

async def assign_worker_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    worker_id = int(update.message.text)
    logger.info(worker_id)
    worker = db_api.get_worker_by_id(worker_id)
    if worker:
        db_api.set_worker(context.user_data['reg_user_id'], worker_id)
        await context.bot.send_message(chat_id=context.user_data['reg_user_id'], text="Ваше участие подтверждено. Добро пожаловать в программу!")
        text = f"""Пользователь id {context.user_data['reg_user_id']} зарегистрирован
Связан с работником:
id: {worker['id']}
ФИО: {worker['fio']}
ТУ: {worker['tu']}
Телефоны: {worker['phone']}"""
        await context.bot.edit_message_text(chat_id=ADMIN_ID, message_id=context.user_data['reg_message_id'], text=text)
        for msg in context.user_data['reg_workers_msgs']:
            await context.bot.delete_message(chat_id=ADMIN_ID, message_id=msg)
        context.user_data.pop('reg_workers_msgs')
        context.user_data.pop('reg_fio')
        context.user_data.pop('reg_user_id')
        context.user_data.pop('reg_message_id')
    else:
        keyboard = [
                [
                InlineKeyboardButton("Зарегистрировать", callback_data=f"register_{context.user_data['reg_user_id']}"),
                InlineKeyboardButton("Отказать", callback_data=f"reject_{context.user_data['reg_user_id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_reply_markup(reply_markup=reply_markup)
        await context.bot.send_message(chat_id=ADMIN_ID, text="Работников с таким id не найдено! Регистрация не завершена")
    return ConversationHandler.END

async def reject_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = query.data.split('_')[1]
    db_api.reject_user({"id": int(user_id)})
    await query.answer()
    new_text = query.message.text + '\nРегистрация не подтверждена'
    await query.edit_message_text(text=new_text)
    return ConversationHandler.END

async def wallet_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    engines = db_api.get_wallet(int(user.id))
    await context.bot.send_message(chat_id=user.id, text=
            f"Вам доступно для начисления {engines} движков до конца месяца.")
    await query.message.edit_reply_markup()

async def balance_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    engines = db_api.get_engines(int(user.id))
    await context.bot.send_message(chat_id=user.id, text=
            f"Ваш баланс: {engines} движков")
    await query.message.edit_reply_markup()

async def stats_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    await context.bot.send_message(chat_id=user.id, text=
            f"Чуть позже здесь будет статистика начисления движков. Ожидайте в обновлениях.")
    await query.message.edit_reply_markup()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    await update.message.reply_text(
            "Операция отменена", reply_markup=ReplyKeyboardRemove()
    )
    keys = [key for key in context.user_data.keys()]
    for key in keys:
        context.user_data.pop(key)
    return ConversationHandler.END

async def cancel_cbq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    await query.message.edit_text(
            f"{query.message.text}\nОперация отменена", reply_markup=None
    )
    keys = [key for key in context.user_data.keys()]
    for key in keys:
        context.user_data.pop(key)
    return ConversationHandler.END


async def give_start_cbq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    engines = db_api.get_wallet(int(user.id))
    if engines > 0:
        return await give_start(user.id, update, context)
    else:
        await context.bot.send_message(chat_id=user.id, text=
                "К сожалению, в этом месяце вы исчерпали все доступные для начисления движки :(")
        return ConversationHandler.END
        

async def give_start_cmnd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    engines = db_api.get_wallet(int(user.id))
    if engines > 0:
        return await give_start(user.id, update, context)
    else:
        await context.bot.send_message(chat_id=user.id, text=
                "К сожалению, в этом месяце вы исчерпали все доступные для начисления движки :(")
        return ConversationHandler.END

async def give_start(user_id, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await context.bot.send_message(chat_id=user_id, text=
            "Кого бы вы хотели поощрить? Введите строку для поиска:")
    return GIVE_SEARCH

async def give_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    search_query = ' '.join([re.sub(r'[\W\d_]+', '', s.capitalize()) for s in update.message.text.lower().split()])
    workers = db_api.get_workers(search_query)
    if len(workers) > 0:
        context.user_data['give_workers_msgs'] = []
        msg = await context.bot.send_message(chat_id=user.id, text="Вот кого я нашел по ФИО:")
        context.user_data['give_workers_msgs'].append(msg.id)
        for worker in workers:
            keyboard = [
                [
                    InlineKeyboardButton("Выбрать", callback_data=f"give_{worker['id']}")
                    ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            msg = await context.bot.send_message(chat_id=user.id, text=f"""ФИО: {worker['fio']}
ТУ: {worker['tu']}
Телефоны: {worker['phone']}""", reply_markup=reply_markup)
            context.user_data['give_workers_msgs'].append(msg.id)
        return GIVE_CHOOSE_WORKER
    else:
        await context.bot.send_message(chat_id=user.id, text="К сожалению, таких коллег я не нашел :(")
        return ConversationHandler.END

async def give_choose_worker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    msgs_to_delete = [id for id in context.user_data['give_workers_msgs'] if id != query.message.id]
    for msg in msgs_to_delete:
        await context.bot.delete_message(chat_id=user.id, message_id=msg)
    worker_id = query.data.split('_')[1]
    context.user_data['give_worker'] = int(worker_id)
    new_text = query.message.text + "\nВыберите причину:"
    reasons = db_api.get_reasons()
    reply_markup = None
    if len(reasons) > 0:
        keyboard = []
        for reason in reasons:
            keyboard.append( 
                [
                    InlineKeyboardButton(f"{reason['text']}", callback_data=f"reason_{reason['id']}")
                ]
            )
        keyboard.append( 
            [
                InlineKeyboardButton("Отменить выбор", callback_data="cancel")
            ]
        )
        reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(text=new_text, reply_markup=reply_markup)
    return GIVE_CHOOSE_REASON

async def give_choose_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    reason_id = int(query.data.split('_')[1])
    result = db_api.give_engines(user.id, context.user_data['give_worker'], reason_id)
    if result[0]:
        new_text = '\n'.join(query.message.text.split('\n')[0: -1]) + f"""
✅ Начислено 10 движков!
За: {db_api.get_reason_text(reason_id)}"""
        await query.message.edit_text(text=new_text, reply_markup=None)
        cheer = db_api.get_random_cheer()[0]
        reason = db_api.get_reason_text(reason_id)
        worker_user = db_api.get_user_by_worker_id(context.user_data['give_worker'])
        cheer_text = f'Вам начислил движки пользователь: {db_api.get_user_name(user.id)}\nЗа: {reason}\n\n🚀 <i>{cheer}</i>'
        if worker_user:
            await context.bot.send_message(chat_id=worker_user, text=cheer_text, parse_mode='HTML')
        context.user_data.pop('give_worker')
        context.user_data.pop('give_workers_msgs')
    else:
        new_text = '\n'.join(query.message.text.split('\n')[0: -1]) + f"""
❌ Ошибка начисления движков!
Причина: {result[1]}"""
        await query.message.edit_text(text=new_text, reply_markup=None)
    return ConversationHandler.END

async def init(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db_api.init_tu()

def main() -> None:

    token = open(os.path.abspath('token.txt')).read().strip()

    application = Application.builder().token(token).build()
    start_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                AUTH: [MessageHandler(filters.Regex("^(Регистрация)$"), auth)],
                FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fio)],
                PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
    )
    register_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(register_button, pattern='^register_.*')],
            states={
                WORKER_CHOICE: [CallbackQueryHandler(choose_worker, pattern='^worker_.*')],
                WORKER_NOT_FOUND: [MessageHandler(filters.Regex("^\d+$"), assign_worker_id)]
            },
            fallbacks=[]
    )
    give_handler = ConversationHandler(
            entry_points=[
                CommandHandler("give", give_start_cmnd),
                CallbackQueryHandler(give_start_cbq, pattern='^give$')
            ],
            states={
                GIVE_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, give_search)],
                GIVE_CHOOSE_WORKER: [CallbackQueryHandler(give_choose_worker, pattern='^give_.*')],
                GIVE_CHOOSE_REASON: [CallbackQueryHandler(give_choose_reason, pattern='^reason_.*')],
            },
            fallbacks=[
                CommandHandler("cancel", cancel),
                CallbackQueryHandler(cancel_cbq, pattern='^cancel$')
            ]
    )
    reject_handler = CallbackQueryHandler(reject_button, pattern='^reject_.*')
    wallet_handler = CallbackQueryHandler(wallet_button, pattern='^wallet$')
    balance_handler = CallbackQueryHandler(balance_button, pattern='^balance$')
    stats_handler = CallbackQueryHandler(stats_button, pattern='^stats$')
    application.add_handler(start_handler)
    application.add_handler(register_handler)
    application.add_handler(give_handler)
    application.add_handler(reject_handler)
    application.add_handler(wallet_handler)
    application.add_handler(balance_handler)
    application.add_handler(stats_handler)
    #init_handler = CommandHandler("init", init)
    #application.add_handler(init_handler)
    application.run_polling()

if __name__ == "__main__":

    main()
