import json
import urllib
import urllib2

from telebot import TeleBot
from telebot.types import InlineKeyboardButton
from telebot.types import InlineKeyboardMarkup
from telebot.util import extract_command

from utils import str_escape, is_info_hash, get_files_size, sizeof_fmt, paginator


def search_torrents(query="latest", page=0):
    find_latest = query == "latest"
    api_url = "http://localhost:8081/api"

    if find_latest:
        url = "{0}/latest?limit=10&offset={1}".format(api_url, page * 10)
    else:
        url = "{0}/search?{1}&limit=10&offset={2}".format(api_url, urllib.urlencode({"query": query}), page * 10)

    server_result = urllib2.urlopen(url).read()

    api_response = json.loads(server_result)

    results = api_response["result"]
    results_count = api_response["count"]
    total_count = api_response.get("total_count", results_count)

    if results:
        if find_latest:
            response_head = "\xF0\x9F\x94\xA5 Last {count} from {total_count} torrents{paginator}:\r\n\r\n".format(
                count=min(results_count, 100),
                total_count=total_count,
                paginator=paginator(page, results_count))
        else:
            response_head = "\xF0\x9F\x94\x8D Search *results* by keywords \"_{query}_\"{paginator}:\r\n\r\n".format(
                query=query,
                paginator=paginator(page, results_count))

        return reduce(
            lambda r, e: r + "\xE2\x96\xAB `{name}`\r\n/{info_hash}\r\n\r\n".format(
                name=e["name"].encode('utf-8').strip(),
                info_hash=e["info_hash"]),
            results,
            response_head
        ), results_count
    else:
        if find_latest:
            return "\xF0\x9F\x98\xB1 No results found."
        else:
            return ("\xF0\x9F\x94\x8D Your search - *{0}* - did not match any documents.\r\n\r\n"
                    "Suggestions:\r\n"
                    "\xE2\x84\xB9 Make sure all words are spelled correctly.\r\n"
                    "\xE2\x84\xB9 Try different keywords.\r\n"
                    "\xE2\x84\xB9 Try more general keywords."
                    ).format(query), 0


def get_torrent_details(info_hash, page=0):
    url = "http://localhost:8081/api/details?{0}".format(
        urllib.urlencode({"info_hash": info_hash})
    )
    server_result = urllib2.urlopen(url).read()
    result = json.loads(server_result)["result"]
    if result:
        return reduce(
            lambda r, e: r + "`{path} ({size})`\r\n".format(
                path=reduce(lambda p, f: p + ("/" if p else "") + f.encode('utf-8').strip(), e["path"], ""),
                size=sizeof_fmt(e["length"])),
            result["files"][page * 10: page * 10 + 10],
            ("\xF0\x9F\x93\x96 *Torrent* details\r\n\r\n"
             "\xE2\x96\xAB *Name*: `{torrent_name}`\r\n\r\n"
             "\xE2\x96\xAB *Size*: `{torrent_size}`\r\n\r\n"
             "\xE2\x96\xAB *Hash*: `{info_hash}`\r\n\r\n"
             "\xE2\x96\xAB *URL*: `magnet:?xt=urn:btih:{info_hash}&dn={torrent_name}`\r\n\r\n"
             "\xE2\x96\xAB *Files*{paginator}:\r\n").format(
                info_hash=result["info_hash"],
                torrent_name=result["name"].encode('utf-8').strip(),
                torrent_size=get_files_size(result["files"]),
                paginator=paginator(page, len(result["files"]))
            )
        ), len(result["files"])
    else:
        return ("Detailed information by torrent - *{0}* - not found.\r\n\r\n"
                "Suggestions:\r\n"
                "\xE2\x84\xB9 Make sure *torrent hash* are spelled correctly.\r\n"
                "\xE2\x84\xB9 Try different torrent."
                ).format(info_hash), 0


def start_bot(bot_token):
    while True:
        try:
            bot = TeleBot(token=bot_token, threaded=False)

            def response_error(chat_id):
                error_string = (
                    "*Bot error*\r\n\r\n"
                    "Sorry, something went wrong! Please, retry later."
                )

                bot.send_message(chat_id=chat_id,
                                 parse_mode="Markdown",
                                 text=error_string)

            @bot.message_handler(commands=["start", "help"])
            def handle_start_help(message):
                help_string = (
                    "Welcome to *Grapefruit torrents* search bot!\r\n\r\n"
                    "Hello, I'm a telegram bot who can search torrents by keyword (such as torrent name or file name in torrent).\r\n\r\n"
                    "Just send me keyword to find torrent, or send _info hash_ to get details torrent information.\r\n\r\n"
                    "\xE2\x9A\xA0 *Note:*\r\n"
                    "\xE2\x9A\xA0 *Bot* can return _only_ [magnet url](https://en.wikipedia.org/wiki/Magnet_URI_scheme#BitTorrent_info_hash_.28BTIH.29) to download.\r\n"
                    "\xE2\x9A\xA0 *Bot* doesnt contains any _torrent files_, only *torrent hashes* available.\r\n"
                )

                bot.send_message(
                    chat_id=message.chat.id,
                    parse_mode="Markdown",
                    text=help_string)

            @bot.message_handler(func=lambda message: message.content_type == "text" and
                                                      is_info_hash(extract_command(message.text)))
            def handle_details(message):
                info_hash = extract_command(message.text.lower()).encode('utf-8').strip()
                try:
                    response_text, files_count = get_torrent_details(info_hash)

                    if files_count > 10:
                        btn_next_data = json.dumps({
                            "m": "d",
                            "a": info_hash,
                            "p": 1  # Go to page #1
                        }).replace(" ", "")

                        keyboard = InlineKeyboardMarkup()
                        keyboard.add(InlineKeyboardButton(text="Next page \xE2\x9E\xA1",
                                                          callback_data=btn_next_data))
                    else:
                        keyboard = None

                    bot.send_message(chat_id=message.chat.id,
                                     parse_mode="Markdown",
                                     text=response_text,
                                     reply_markup=keyboard)
                except:
                    response_error(message.chat.id)

            @bot.message_handler(content_types=["text"])
            def handle_search(message):
                request = str_escape(message.text.lower()).encode('utf-8').strip()[:50]
                try:
                    response_text, results_count = search_torrents(request)

                    if results_count > 10:
                        btn_next_data = json.dumps({
                            "m": "s",
                            "a": request,
                            "p": 1  # Go to page #1
                        })

                        keyboard = InlineKeyboardMarkup()
                        keyboard.add(InlineKeyboardButton(text="Next page \xE2\x9E\xA1",
                                                          callback_data=btn_next_data))
                    else:
                        keyboard = None

                    bot.send_message(chat_id=message.chat.id,
                                     parse_mode="Markdown",
                                     text=response_text,
                                     reply_markup=keyboard)
                except:
                    response_error(message.chat.id)

            @bot.callback_query_handler(func=lambda data: data.data is not None)
            def handle_buttons(data):
                message = data.message
                button_data = json.loads(data.data)

                page = button_data["p"]
                mode = button_data["m"]
                arg = button_data["a"]

                keyboard = InlineKeyboardMarkup()
                response_text = message.text
                buttons = []

                try:
                    if mode == "s":
                        response_text, results_count = search_torrents(query=arg, page=page)

                        if page > 0:
                            buttons.append(InlineKeyboardButton(
                                text="\xE2\xAC\x85 Prev page",
                                callback_data=json.dumps({"m": "s", "a": arg, "p": page - 1})))

                            buttons.append(InlineKeyboardButton(
                                text="\xE2\x86\xA9 Home",
                                callback_data=json.dumps({"m": "s", "a": arg, "p": 0})))

                        if results_count - page * 10 > 10:
                            buttons.append(InlineKeyboardButton(
                                text="Next page \xE2\x9E\xA1",
                                callback_data=json.dumps({"m": "s", "a": arg, "p": page + 1})))

                    elif mode == "d":
                        response_text, files_count = get_torrent_details(info_hash=arg, page=page)

                        if page > 0:
                            buttons.append(InlineKeyboardButton(
                                text="\xE2\xAC\x85 Prev page",
                                callback_data=json.dumps(
                                    {"m": "d", "a": arg, "p": page - 1}).replace(" ", "")))

                            buttons.append(InlineKeyboardButton(
                                text="\xE2\x86\xA9 Home",
                                callback_data=json.dumps(
                                    {"m": "d", "a": arg, "p": 0}).replace(" ", "")))

                        if files_count - page * 10 > 10:
                            buttons.append(InlineKeyboardButton(
                                text="Next page \xE2\x9E\xA1",
                                callback_data=json.dumps(
                                    {"m": "d", "a": arg, "p": page + 1}).replace(" ", "")))

                    keyboard.row(*buttons)
                    bot.edit_message_text(chat_id=message.chat.id,
                                          parse_mode="Markdown",
                                          text=response_text,
                                          message_id=message.message_id,
                                          reply_markup=keyboard)
                except:
                    response_error(message.chat.id)

            # start polling
            bot.polling(none_stop=True)
        except (KeyboardInterrupt, SystemExit):
            break
        except:
            pass
