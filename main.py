import asyncio
import pydirectinput
import traceback
from nicegui import ui, run
from characterai import PyCAI
from util import *

theme = ui.dark_mode()
theme.enable()

ui.query('.nicegui-content').classes('p-0')
ui.colors(primary='#ec4899', secondary='#ec4899')

character_selected = False

# c.ai vars
client = None
char_id = None

tgt = None
chat = None

# Game
cs_path = get_steam_path() + '\\steamapps\\common\\Counter-Strike Global Offensive\\game\\csgo\\'
log_dir = cs_path + 'console.log'
exec_dir = cs_path + 'cfg\\message.cfg'

chat_char_limit = 222
chat_delay = 0.5
last_log = ''


class ToggleButton(ui.button):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._state = False
        self.on('click', self.toggle)

    def toggle(self) -> None:
        """Toggle the button state."""
        self._state = not self._state
        self.update()

        if cai_token.value == '':
            ui.notify('Please set a C.AI token!', type='negative')
            tabs.set_value('Settings')
            self._state = not self._state
        elif not character_selected:
            ui.notify('Please select a character to use!', type='negative')
            tabs.set_value('Characters')
            self._state = not self._state
        elif self._state:
            ui.notify('Chatbot is now running!', type='positive', color='pink')
            self.text = 'On'
            cai_token.disable()
        else:
            ui.notify('Chatbot has been disabled.', type='warning')
            self.text = 'Off'
            cai_token.enable()

        self.update()

    def update(self) -> None:
        self.props(f'color={"green" if self._state else "pink"}')
        super().update()


async def handle_chat():
    global last_log
    if toggle_active._state:
        log = get_last_chat(log_dir)

        # Don't respond to same message or when there's no [ALL] chat message
        if log == last_log or log is None:
            return

        data = log.split(': ')

        # Don't respond to self
        if get_last_game_name_used() in data[0]:
            return

        last_log = log
        message = data[1]

        data = client.chat.send_message(
            chat['external_id'], tgt, message
        )

        #name = data['src_char']['participant']['name']
        text = data['replies'][0]['text'].replace('\n', ' ').replace('"', "''").replace(';', '')

        # Chunk our message in order to send everything
        texts = [text[i:i + chat_char_limit] for i in range(0, len(text), chat_char_limit)]

        for text in texts:
            with open(exec_dir, 'w', encoding='utf-8') as f:
                f.write(f'say "{text}"')

            # Don't send an input to other windows
            if get_window() == 'Counter-Strike 2':
                pydirectinput.write('p')
                await asyncio.sleep(chat_delay)


def swap_theme(e):
    if e.value:
        theme.enable()
    else:
        theme.disable()


def select_character(char):
    if not client:
        ui.notify('Please set a C.AI token!', type='negative')
        tabs.set_value('Settings')
        return

    global char_id
    global character_selected
    global tgt

    character_selected = True
    ui.notify('Selected: ' + char['participant__name'])
    char_id = char['external_id']

    try:
        client.chat.new_chat(char_id)
    except:
        ui.notify('Failed to create chat, check your token!', type='negative')
        return

    # Save tgt and history_external_id
    # to avoid making a lot of requests
    global chat
    chat = client.chat.get_chat(char_id)

    participants = chat['participants']

    # In the list of "participants",
    # a character can be at zero or in the first place
    if not participants[0]['is_human']:
        tgt = participants[0]['user']['username']
    else:
        tgt = participants[1]['user']['username']


async def set_token(e):
    global client

    # we should validate whether the token is correct in the future
    client = PyCAI(e.value)
    ui.notify('Token updated')

    await search(recent_only=True)


async def search(recent_only=False):

    if cai_token.value == '':
        ui.notify('Please set a C.AI token!', type='negative')
        tabs.set_value('Settings')
        return

    search_btn.disable()

    try:
        if recent_only:
            response = await run.io_bound(client.character.recommended)
            characters = response['recommended_characters']
        else:
            response = await run.io_bound(client.character.search, character_input.value)
            characters = response['characters']

        results.clear()

        for character in characters:
            name = character['participant__name']
            avatar = 'https://characterai.io/i/80/static/avatars/' + character['avatar_file_name']

            with results:
                with ui.link().on('click', lambda char=character: select_character(char)).classes('no-underline hover:scale-105 duration-100 active:scale-100'):
                    with ui.card().tight().classes('w-36 h-48 text-center'):
                        ui.image(avatar).classes('w-36 h-32')
                            #ui.label(name).classes('absolute-bottom text-subtitle2 text-center')
                        with ui.row().classes('absolute right-2 top-1'):
                            if 'upvotes' not in character:
                                character["upvotes"] = '0'
                            ui.label(f'⭐{character["upvotes"]}').classes('text-subtitle2 text-center drop-shadow-[0_1.2px_1.2px_rgba(0,0,0,0.8)]')
                        with ui.card_section().classes('h-6 w-full font-bold'):
                            ui.label(name).classes('drop-shadow-[0_1.2px_1.2px_rgba(0,0,0,0.8)]')

        ui.notify(f'Found {len(characters)} top results!', type='positive', color='pink')

    except Exception as e:
        ui.notify(traceback.format_exc())
        search_btn.enable()

    search_btn.enable()


handle_chat_timer = ui.timer(0.1, handle_chat, active=True)

with ui.dialog() as dialog_help_api, ui.card():
    ui.markdown('''
    ## Get API Token
    
    <ol>
        <li> Visit <a target='_blank' href='https://old.character.ai/'>https://old.character.ai/</a> </li>
        <li> Open DevTools in your browser </li>
        <li> Go to Storage → Local Storage → char_token </li>
        <li> Copy value </li>
    </ol>
    ''')

    ui.button('Close', on_click=dialog_help_api.close).props('outline')

with ui.dialog() as dialog_wipe, ui.card():
    ui.markdown('''
    ## Wipe History

    Are you sure you'd like to wipe {current character's} chat history/memory? This cannot be undone.
    ''')

    with ui.row():
        ui.button('Yes', on_click=dialog_wipe.close)
        ui.button('Close', on_click=dialog_wipe.close).props('outline')

with ui.splitter(value=16).classes('w-full h-screen') as splitter:
    with splitter.before:
        ui.icon('chat', color='#ec4899').classes('m-auto text-5xl mt-6')
        with ui.tabs().props('vertical').classes('w-full h-full') as tabs:
            characters = ui.tab('Characters', icon='group')
            settings = ui.tab('Settings', icon='settings')

        toggle_active = ToggleButton('Toggle', icon='power_settings_new').classes('bg-pink-600 w-full h-16 rounded-none mt-auto')

    with splitter.after:
        with ui.tab_panels(tabs, value=characters).props('vertical').classes('w-full h-full'):
            with ui.tab_panel(characters):
                with ui.row().classes('flex items-center'):
                    character_input = ui.input('Character').on('keypress.enter', search)
                    search_btn = ui.button(on_click=search, icon='search').classes('outline mt-auto')

                ui.separator()
                results = ui.row().classes('flex justify-center')
                with results:
                    ui.label("Hello, recommended characters will be displayed here once you've set a C.AI token.")
            with ui.tab_panel(settings):
                with ui.grid(columns=2).classes('w-full'):
                    with ui.card().tight():
                        with ui.card_section():
                            ui.badge('API ', color='#ec4899')
                            cai_token = ui.input(label='C.AI Token', password=True, on_change=set_token)

                            with ui.row().classes('mt-5'):
                                ui.button(icon='help', on_click=dialog_help_api.open).props('rounded')

                    with ui.card().tight():
                        with ui.card_section():
                            ui.badge('Appearance', color='#ec4899')
                            ui.html('<br>')

                            ui.switch('Dark Theme', on_change=swap_theme, value=True)

                            """
                            with ui.button(icon='colorize') as button:
                                ui.label('Primary Color')
                                ui.color_picker(on_pick=lambda e: ui.colors(primary=e.color))
                            

                    with ui.card().tight():
                        with ui.card_section().classes('w-full'):
                            ui.badge('Chatbot', color='#ec4899')
                            ui.html('<br>')

                            ui.button('Wipe History', on_click=dialog_wipe.open)
                            """


ui.run(show=False, window_size=(820, 600), title='CS2 Chatbot')