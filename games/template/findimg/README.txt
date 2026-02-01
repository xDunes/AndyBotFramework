Template findimg Folder
=======================

This folder should contain your needle images (PNG files) for game element detection.

How to create needle images:
1. Run: python tools/getScreenShot.py Device1 -p
2. Crop the UI element in MS Paint
3. Save as PNG in this folder
4. Use in code: bot.find_and_click('filename_without_extension')

Example structure:
  findimg/
    play_button.png
    close_icon.png
    reward_claim.png
    back_arrow.png

Tips:
- Keep images small (just the element, minimal background)
- Use descriptive lowercase names with underscores
- PNG format is recommended for transparency support
