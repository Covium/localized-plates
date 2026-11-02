# Localized Plates

Tokyo Xtreme Racer supports several languages, but its license-plate region names stay in Japanese. Finding Naniwa in Osaka is difficult when the menu only shows kanji and kana. Localized Plates translates those names so you can find the region you want.

## Features

- Translates prefecture and location names in the license-plate menu.
- Supports English, French, Spanish (Spain), Simplified Chinese, and Traditional Chinese. Japanese keeps the original names.
- Follows the game's language setting immediately, without restarting.
- Includes two versions: **Replacement**, which shows only the translation, and **Bilingual**, which shows both names, such as `Naniwa(なにわ)`.

The Japanese lettering on the physical plates is unchanged.

## Installation

No additional software is required.

1. Close the game and extract the archive.
2. Choose **Replacement** or **Bilingual**.
3. Copy that folder's `.pak`, `.ucas`, and `.utoc` files into:

   ```text
   <GAME_LOCATION>/TokyoXtremeRacer/Content/Paks/~mods
   ```

Create `~mods` if it does not exist. Replace older `LocalizedPlates_P` files and keep all three files together. Install only one version at a time.

To switch versions, close the game and replace the three files with those from the other folder.

To uninstall, close the game and remove `LocalizedPlates_P.pak`, `LocalizedPlates_P.ucas`, and `LocalizedPlates_P.utoc` from `~mods`.

## How it works

The mod adds translations for the plate menu's existing text entries to the game's localization resources. The game then selects the appropriate names through its normal language system. Both versions use the same translations; Bilingual adds the original Japanese name in parentheses.

The builder merges the plate names with a saved copy of the game's translations, preserving unrelated text. Because those resources can change after a game update, the mod may need rebuilding for a new game version. Other mods that replace the same localization resources may conflict.

## Building and updating

Building requires Windows and Python 3.12 or newer. From the project folder, run:

```powershell
python fetch_tools.py
python build_release.py
```

The finished archive is `dist/Localized Plates.zip`. The tools are downloaded from their authors' releases and verified before use. The builder checks that the original translations are preserved and validates both packages.

To check an installed game for localization changes:

```powershell
python update_mod.py --check
```

To refresh the mod after a game update, pass the actual game version and the path to its `Paks` folder. For example:

```powershell
python update_mod.py --game-version 1.6.2 --paks "D:\SteamLibrary\steamapps\common\TokyoXtremeRacer\TokyoXtremeRacer\Content\Paks"
```

The updater backs up the previous build and creates both versions. Install your chosen version manually and check it in-game. Newly added regions or changes to the game's asset format may require updating the translations or build tools.

## Credits

Built with [retoc](https://github.com/trumank/retoc), [repak](https://github.com/trumank/repak), and [UnrealLocres](https://github.com/akintos/UnrealLocres). [FModel](https://github.com/4sval/FModel), [RE-UE4SS](https://github.com/UE4SS-RE/RE-UE4SS), and [UAssetGUI](https://github.com/atenfyr/UAssetGUI) helped locate and inspect the game assets. Thanks to their authors and contributors.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for build-tool credits and licensing information.
