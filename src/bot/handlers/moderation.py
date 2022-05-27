import json
import logging

from django.conf import settings
from telegram import Update
from telegram.ext import CallbackContext

from devyatki.models import User, PlateEntry

log = logging.getLogger(__name__)


def approve_photo(update: Update, context: CallbackContext) -> None:
    """approve photo, add plate entry, notify chat"""
    _, message_id = update.callback_query.data.split(":", 1)

    message = context.bot_data.get(int(message_id))
    if message is None:
        update.callback_query.edit_message_reply_markup(reply_markup=None)
        update.callback_query.edit_message_text("Фигня случилась, не получается найти информацию о сообщении 🤷")
        return None

    user, created = User.objects.get_or_create(telegram_username=message.chat.username)

    if created:
        user.telegram_chat_id = message.chat.id,
        user.telegram_data = json.dumps({
            "id": message.chat.id,
            "username": message.chat.username,
            "first_name": message.chat.first_name,
            "last_name": message.chat.last_name,
        })
        user.save()

        context.bot.send_message(chat_id=message.chat.id, text=f"Приятно познакомиться, @{message.chat.username}")

    if not user.is_approved:
        user.moderation_status = User.MODERATION_STATUS_APPROVED
        user.save()

        # send welcome drink
        link = context.bot.create_chat_invite_link(chat_id=settings.TELEGRAM_999_CHANNEL_ID,
                                                   api_kwargs={"pending_join_request_count": 1})
        context.bot.send_message(chat_id=message.chat.id,
                                 text=f"Привет, @{user.telegram_username}! Ты прошел модерацию и теперь можешь \
                                 попасть в чат 𝟡⓽⒐\n\nПриглашение: {link.invite_link}")

    # save plate entry
    plate = PlateEntry(telegram_photo_id=message.photo[0].file_id, user=user, telegram_message=str(message),
                       telegram_message_id=message_id)
    plate.save()

    # notify chat 999 about new photo
    context.bot.send_photo(chat_id=settings.TELEGRAM_999_CHANNEL_ID, photo=message.photo[0].file_id)
    context.bot.send_message(chat_id=settings.TELEGRAM_999_CHANNEL_ID,
                             text=f"{message.from_user.first_name} @{message.from_user.username} зарабатывает +1 в карму")

    # hide buttons and send verdict
    update.callback_query.edit_message_reply_markup(reply_markup=None)
    update.callback_query.edit_message_text("Фото одобрено 👍")
    return None


def reject_photo(update: Update, context: CallbackContext) -> None:
    """rejects photo, increment reject_count for user if exists"""
    _, message_id = update.callback_query.data.split(":", 1)

    message = context.bot_data.get(int(message_id))
    if message is None:
        update.callback_query.edit_message_reply_markup(reply_markup=None)
        update.callback_query.edit_message_text("Фигня случилась, не получается найти информацию о сообщении 🤷")
        return None

    try:
        user = User.objects.get(telegram_username=message.from_user.username)
    except User.DoesNotExist:
        user = None

    if not user:
        context.bot.send_message(chat_id=message.chat.id,
                                 text="Привет, для начала нажми /start и у нас все сложится! \n\n"
                                      "И не присылай фигню больше, пожалуйста.")
    else:
        user.rejected_count += 1
        user.save()
        context.bot.send_message(chat_id=message.chat.id,
                                 text=f"Это [{user.rejected_count}] сколько раз ты присылал фигню!\n\n"
                                      "Самое время остановиться.")

    # hide buttons and send verdict
    update.callback_query.edit_message_reply_markup(reply_markup=None)
    update.callback_query.edit_message_text("Фото отклонено 🫣")

    return None
