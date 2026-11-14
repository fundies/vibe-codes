"""Script entry point: RunScript(service.animetracks,reset|forget) or open settings."""
import sys

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import logic, store


def main(args):
    addon = xbmcaddon.Addon()
    dialog = xbmcgui.Dialog()
    if 'reset' in args:
        if dialog.yesno('Anime Tracks', 'Forget every remembered folder track choice?'):
            store.clear()
            dialog.notification('Anime Tracks', 'All folder choices cleared',
                                xbmcgui.NOTIFICATION_INFO, 2500, False)
        return
    if 'forget' in args:
        player = xbmc.Player()
        if not player.isPlayingVideo():
            dialog.notification('Anime Tracks', 'Play a file from the folder first',
                                xbmcgui.NOTIFICATION_WARNING, 2500, False)
            return
        playing = player.getPlayingFile()
        folder = logic.folder_of(playing)
        roots = [r for r in (addon.getSetting('folders') or 'Anime').split(',') if r.strip()]
        root = logic.anime_root(folder, roots)
        try:
            scope = int(addon.getSetting('scope'))
        except ValueError:
            scope = 0
        key = logic.pref_key(folder, root, scope, playing) if root else folder
        removed = store.forget(key)
        dialog.notification('Anime Tracks', 'Forgot this folder' if removed else 'Nothing saved here',
                            xbmcgui.NOTIFICATION_INFO, 2500, False)
        return
    addon.openSettings()


if __name__ == '__main__':
    main(sys.argv[1:])
