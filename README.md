# Twilight Princess maps for Universal Tracker

The maps and pins of [Kizugaya's Twilight Princess PopTracker pack](https://github.com/Kizugaya/TPRAP_poptracker),
reduced to what [Universal Tracker](https://github.com/FarisTheAncient/Archipelago) shows. Universal Tracker takes the
logic from the Twilight Princess apworld, so this pack has no logic, scripts, items or layouts, and does not work in
the PopTracker program. For PopTracker, use the full pack.

To use it, download this branch as a .zip with `manifest.json` at the root of the zip (for example
`git archive --format=zip -o TPRAP_ut_maps.zip ut-only`), and set `twilight_princess_options.ut_pack_path` in your
Archipelago `host.yaml` to that file.

## How it is made

`tools/make_ut_pack.py` builds it from the full pack (branch `ut-fixes`, which names every check after its
Archipelago location):

    python tools/make_ut_pack.py <full pack checkout> .

It keeps the maps shown in the pack's tabs and their images, and the location files reduced to location names, map
positions and the sections that are Archipelago locations. Pins that PopTracker only shows once the player marks a
randomized entrance are dropped. File paths, location names and section names are unchanged, so the apworld's map data
works with this pack and the full one.

## Credits and license

Maps, pin positions and location data by [Kizugaya](https://github.com/Kizugaya). Kizugaya's pack thanks
[AudioPixie](https://github.com/AudioPixie) and [Darkzant](https://github.com/darkzant) for letting it use their assets.

Changed from the original: reduced to Universal Tracker's needs as described above (2026-11-23). Licensed under the
GNU General Public License v3.0, like the original; see LICENSE.
