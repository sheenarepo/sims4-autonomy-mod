"""Thin wrappers around the game's dialog classes (list picker, text entry, notice).

All game-API details live here so they can be checked against the real game
code in one place.
"""

from sleepcontrol import log


def _raw(text):
    from sims4.localization import LocalizationHelperTuning
    return LocalizationHelperTuning.get_raw_text(text)


def _text_factory(text):
    localized = _raw(text)
    return lambda *_, **__: localized


# The game's own energy-need icon (commodity_energy_00.png), so rows don't show
# the red "missing icon" placeholder.
ROW_ICON_INSTANCE = 0xDEFF693DCFB5DDCE


def _row_icon():
    try:
        import sims4.resources
        return sims4.resources.get_resource_key(ROW_ICON_INSTANCE, sims4.resources.Types.PNG)
    except Exception:
        return None


def _owner():
    import services
    sim = services.get_active_sim()
    if sim is not None:
        return sim.sim_info
    client = services.client_manager().get_first_client()
    return client.active_sim_info if client is not None else None


def show_list(title, text, rows, on_choose):
    """Show an MCCC-style list. rows = [(label, description, value)].

    on_choose(value) is called with the chosen row's value; nothing is called
    if the player cancels.
    """
    try:
        from ui.ui_dialog_picker import UiObjectPicker, ObjectPickerRow
        # max_selectable is left at the game's default (static count of 1).
        dialog = UiObjectPicker.TunableFactory().default(
            _owner(),
            text=_text_factory(text),
            title=_text_factory(title),
            min_selectable=1,
            picker_type=UiObjectPicker.UiObjectPickerObjectPickerType.OBJECT,
        )
        icon = _row_icon()
        for index, (label, description, value) in enumerate(rows):
            dialog.add_row(ObjectPickerRow(
                icon=icon,
                option_id=index,
                name=_raw(label),
                row_description=_raw(description) if description else None,
                tag=value,
            ))

        def _on_response(d):
            try:
                if not d.accepted:
                    return
                value = d.get_single_result_tag()
                if value is not None:
                    on_choose(value)
            except Exception:
                log.exception('list dialog response')

        dialog.add_listener(_on_response)
        dialog.show_dialog()
    except Exception:
        log.exception('showing list dialog "{}"'.format(title))


def ask_text(title, text, initial, on_submit):
    """Ask the player to type a value. on_submit(str) runs when they press OK."""
    try:
        from sims4.collections import AttributeDict
        from ui.ui_dialog_generic import UiDialogTextInputOkCancel
        from ui.ui_text_input import UiTextInput, _TextInputLengthFixed
        input_name = 'value'
        text_input = UiTextInput(sort_order=0)
        text_input.default_text = None
        text_input.initial_value = _text_factory(str(initial))
        text_input.title = None
        text_input.length_restriction = _TextInputLengthFixed(min_length=None, max_length=8)
        text_input.restricted_characters = None
        text_input.check_profanity = False
        text_input.height = None
        # The game records typed answers only for names it can find with
        # hasattr(), so this must be an AttributeDict, not a plain dict.
        dialog = UiDialogTextInputOkCancel.TunableFactory(text_inputs=(input_name,)).default(
            _owner(),
            text=_text_factory(text),
            title=_text_factory(title),
            text_inputs=AttributeDict({input_name: text_input}),
        )

        def _on_response(d):
            try:
                if d.accepted:
                    on_submit(d.text_input_responses.get(input_name, ''))
            except Exception:
                log.exception('text dialog response')

        dialog.add_listener(_on_response)
        dialog.show_dialog()
    except Exception:
        log.exception('showing text dialog "{}"'.format(title))


def notify(title, text):
    """Small notification in the top corner (used to confirm changes or report bad input)."""
    try:
        from ui.ui_dialog_notification import UiDialogNotification
        notification = UiDialogNotification.TunableFactory().default(
            _owner(),
            text=_text_factory(text),
            title=_text_factory(title),
        )
        notification.show_dialog()
    except Exception:
        log.exception('showing notification')
