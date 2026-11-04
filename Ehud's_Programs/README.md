# Western blot TIFF main-band densitometry

This program estimates lane positions, selects one shared main-band region from the sample lanes, and measures background-corrected density in that same region for every sample. Marker lanes are excluded from target-band selection and the output.

## Setup

From the repository root, install the dependencies into the Python environment selected in VS Code:

```powershell
python -m pip install -r "Ehud's_Programs\requirements.txt"
```

NumPy handles image measurements and Pillow reads TIFF files. Biopython is for biological sequence data, not blot-image densitometry, so it is not used.

## Run

```powershell
python western_blot_densitometry.py "blot.tif"
```

Without a filename, run the script using VS Code's **Run Python File** button to open a TIFF file picker. The program then asks for the total number of loaded lanes and comma-separated marker lane numbers (for example `1,12`); lane numbers go left to right. It analyzes the TIFF and automatically estimates the shared main-band Y range; no Y coordinates are needed from you.

Example for 10 samples with markers in lanes 1 and 12:

```powershell
python western_blot_densitometry.py "blot.tif" --lane-count 12 --marker-lanes 1,12
```

If you want to override the automatic band selection, set the shared Y range on the command line in image pixels. For example, if the desired band is bounded by Y=750 and Y=840:

```powershell
python western_blot_densitometry.py "blot.tif" --lane-count 15 --marker-lanes 5,10,15 --band-y-range 750:840
```

`--lane-count` and `--marker-lanes` can be omitted to answer interactively. `--polarity` can be `dark`, `bright`, or `auto`; `--band-y-range START:END` optionally overrides automatic band selection, `--page` selects a TIFF page, `--output` sets the CSV path, and `--plot-output` sets the annotated plot path.

The program estimates lane centers and fits them to a uniformly spaced grid. Within each sample lane it estimates row-by-row background from the inter-lane gutters, then compares the sample lanes using a median signal profile. This helps ignore horizontal illumination/artifact streaks shared by the membrane and prevents marker lanes from deciding the target-band Y range. Automatic polarity selection compares the local sample signal against gutter background for both bright and dark bands. It selects the most prominent shared band and applies its Y range and an equal-width X ROI to every sample lane. By default it saves both `<image>_densitometry.csv` and an annotated `<image>_densitometry.png` beside the script (not beside the TIFF), so it can write results even when the image is in a read-only or synchronized folder. Use `--output` and `--plot-output` to select other writable paths. The plot shows the membrane with X/Y pixel axes, outlines the measured region in each sample lane, labels the lane, and displays integrated density beneath the image. The CSV contains one measurement per sample lane with coordinates, local background, integrated background-corrected density, and mean corrected density. Check the overlay against the membrane before interpreting results. Density is in grayscale pixel-value units, not an absolute protein concentration; quantitative comparisons require consistent imaging, exposure, and background conditions.

## Face age estimator

Estimate the apparent age of the single person in an image using DeepFace's pretrained age model:

```powershell
python face_age_estimator.py "person.jpg"
```

When started with VS Code's **Run Python File** button and no image argument, the program opens an image picker. You can also pass the image path as above. Image files with non-English characters in their names or folders are supported.

The program tries YuNet first and falls back to OpenCV if it cannot detect a face. It saves a report as `person_age_estimate.txt` beside the image; use `--output` to choose another report path. YuNet model weights may be downloaded on first use. If neither detector finds a face, use a clear, well-lit photo with one visible, front-facing face that is not too small or obstructed. If DeepFace is missing, the error shows an install command using the exact Python interpreter running the program. The report explains that the estimate comes from learned facial-appearance patterns and that the model does not provide specific feature-level reasons. This is only a rough estimate, not a verified age; image quality and other factors can affect it.
## NBA face puzzle

Play the [NBA Face Puzzle in your browser](https://ehudelfer.github.io/Ehud_Maven_Assignments/). The desktop Python source is [nba_puzzle_game.py](nba_puzzle_game.py).

To publish the browser game, push this repository to `main`, then open **Settings > Pages** on GitHub and set the source to **GitHub Actions**. The included workflow deploys the game automatically. The share link above works after that first deployment completes. The browser leaderboard is saved on each player's device; it is not shared across players.

Start the Tkinter game with the Python environment that has Pillow installed:

```powershell
python nba_puzzle_game.py
```

Enter a nickname, then guess the NBA player shown by the revealed face tiles. Submit guesses with Enter, reveal more tiles, or skip to another player. The roster includes current and historical NBA players. Their headshots download from the NBA CDN on demand and are cached under `~/.nba_puzzle_game/images`; an internet connection is needed the first time each photo is used. To use your own image files, place them in `nba_player_images` beside the script and name each file with the player's name normalized to lowercase letters and digits, such as `lebronjames.jpg`. The top-five session leaderboard is stored in `leaderboard.json` beside the script.

## Test

```powershell
python -m unittest -v
```
