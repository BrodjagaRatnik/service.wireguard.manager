""" ./resources/scripts/show_terms_of_service.py """
import os
import sys

try:
    import kodi_env
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
    import kodi_env

from logger import log_message

try:
    import xbmcgui
    HAS_KODI_UI = True
except ImportError:
    HAS_KODI_UI = False


def show_tos():
    try:
        addon_obj = kodi_env.get_addon_instance()
        if not addon_obj or not HAS_KODI_UI:
            log_message("ShowToS: Environment missing Kodi abstractions. Execution stopped.", 2)
            kodi_env.clear_script_globals()
            return

        addon_path = kodi_env.ADDON_DIR
        black_png = os.path.join(addon_path, "resources", "media", "show_black.png")

        text = (
            "[B][COLOR yellow]Terms of Service.[/COLOR][/B][CR][CR]"
            "1. [B]Independent Project:[/B]  This addon is an independent, "
            "community-driven project. It is NOT affiliated with, "
            "authorized, or endorsed by NordVPN, Nord Security, or its "
            "affiliates, or any other VPN provider. 'NordVPN' and "
            "'NordLynx' are trademarks of Nord Security.[CR][CR]"
            "2. [B]Using service:[/B] To bypass any regulatory or "
            "judicial measures, or for any other illegal activities, "
            "is strictly prohibited and violates all VPN Providers Terms "
            "of Service.[CR][CR]"
            "3. [B]Compliance:[/B] Make sure you use this in compliance "
            "with all applicable laws and regulations, as well as the "
            "terms of any websites or services you access.[CR][CR]"
            "4. [B]Terms of Service:[/B] Look up TOS of your VPN "
            "Provider. [CR][CR]"
            "[I]By using this manager, you acknowledge that you have "
            "read and agree to these terms.[/I]"
        )

        class StyledTermsDialog(xbmcgui.WindowDialog):

            def __init__(self, content, bg_image):
                self.w, self.h = 1200, 600
                self.x, self.y = (1280 - self.w) // 2, (720 - self.h) // 2
                self.addControl(xbmcgui.ControlImage(self.x, self.y, self.w, self.h, bg_image))
                self.textbox = xbmcgui.ControlTextBox(
                    self.x + 40, self.y + 40, self.w - 80, self.h - 140, font="font13"
                )
                self.addControl(self.textbox)
                self.textbox.setText(content)
                self.ok_button = xbmcgui.ControlButton(
                    self.x + (self.w // 2) - 80, self.y + self.h - 80, 160, 50, "OK",
                    focusTexture=bg_image,
                    noFocusTexture=bg_image,
                    textColor="0xFFFFFFFF",
                    focusedColor="0xFFFFFF00",
                    alignment=6
                )
                self.addControl(self.ok_button)
                self.setFocus(self.ok_button)

            def onControl(self, control):
                if control == self.ok_button:
                    self.close()

            def onAction(self, action):
                action_id = action.getId()
                exit_codes = (7, 10, 92, 100)
                if action_id in exit_codes:
                    self.close()

        window = StyledTermsDialog(text, black_png)
        window.doModal()
        del window

    except Exception as e:
        log_message(f"ShowInfo: Error in Terms of Service {e}", 3)
    finally:
        kodi_env.clear_script_globals()


if __name__ == "__main__":
    show_tos()
