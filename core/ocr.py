"""
OCR Utilities - Generic image text recognition

This module provides OCR utilities for reading text from game screenshots.
All functions are game-agnostic.
"""

import re
import cv2 as cv
import numpy as np
from PIL import Image
import pytesseract

# Pre-compiled regex patterns for performance
RATIO_PATTERN = re.compile(r'\b(\d+)/(\d+)\b')
RATIO_PATTERN_FLEXIBLE = re.compile(r'(\d+)\s*/\s*(\d+)')
LEVEL_PATTERN = re.compile(r'(?P<level>\d+)')
NUMBER_SLASH_PATTERN = re.compile(r'(?P<used>\d+)[^\d]+(?P<of>\d+)')


def extract_ratio_from_image(bot, image, fallback_used=0, fallback_of=1):
    """Extract 'number/number' ratio pattern from image using multi-strategy OCR

    This function uses multiple image preprocessing techniques and OCR configurations
    to maximize accuracy when reading ratio patterns (e.g., "3/6", "0/4") from
    game UI screenshots.

    Args:
        bot: Bot instance for logging errors
        image: OpenCV image (BGR numpy array) to process
        fallback_used: Default value for 'used' if all OCR attempts fail (default: 0)
        fallback_of: Default value for 'of' if all OCR attempts fail (default: 1)

    Returns:
        dict: {'used': int, 'of': int}
              - 'used': First number in ratio (numerator)
              - 'of': Second number in ratio (denominator)
              - Returns fallback values if OCR fails

    Note:
        Uses 4 preprocessing methods x 3 OCR configs = 12 total attempts
        to find the ratio pattern, prioritizing exact matches over flexible ones.
    """
    try:
        # Convert to grayscale for preprocessing
        gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

        # Try multiple preprocessing approaches to handle different text styles/backgrounds
        processed_images = [
            # Simple binary threshold at midpoint (127) - works for high contrast text
            ('Simple Threshold', cv.threshold(gray, 127, 255, cv.THRESH_BINARY)[1]),

            # Adaptive threshold - adjusts to local brightness variations
            ('Adaptive Threshold', cv.adaptiveThreshold(
                gray, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY, 11, 2
            )),

            # Otsu's method - automatically determines optimal threshold value
            ('OTSU Threshold', cv.threshold(gray, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)[1]),
        ]

        # Add morphological closing to remove small noise and connect broken characters
        kernel = np.ones((2, 2), np.uint8)
        morph = cv.morphologyEx(processed_images[2][1], cv.MORPH_CLOSE, kernel)
        processed_images.append(('Morphological', morph))

        # OCR configurations to try (different Page Segmentation Modes)
        configs = [
            r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789/',   # PSM 8: Single word
            r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789/',   # PSM 7: Single line
            r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789/'   # PSM 13: Raw line
        ]

        # Test each preprocessed image with each OCR config (12 combinations total)
        for name, processed_img in processed_images:
            pil_img = Image.fromarray(processed_img)

            for config in configs:
                text = pytesseract.image_to_string(pil_img, config=config).strip()

                # Look for exact number/number pattern (e.g., "3/6")
                match = RATIO_PATTERN.search(text)
                if match:
                    return {
                        'used': int(match.group(1)),
                        'of': int(match.group(2))
                    }

                # Look for flexible pattern with possible spaces (e.g., "3 / 6")
                flexible_match = RATIO_PATTERN_FLEXIBLE.search(text)
                if flexible_match:
                    return {
                        'used': int(flexible_match.group(1)),
                        'of': int(flexible_match.group(2))
                    }

        # All OCR attempts failed - return fallback values
        return {'used': fallback_used, 'of': fallback_of}

    except Exception as e:
        if bot:
            bot.log(f"OCR ERROR: {e}")
        return {'used': fallback_used, 'of': fallback_of}


def prepare_white_text_for_ocr(image, white_threshold=200, scale_factor=6):
    """Prepare image with white text for OCR by isolating and enhancing

    Args:
        image: OpenCV image (BGR numpy array)
        white_threshold: Brightness threshold for white pixels (default: 200)
        scale_factor: Factor to upscale image for better OCR (default: 6)

    Returns:
        numpy array: Processed image ready for OCR (black text on white bg)
    """
    # Convert to grayscale for thresholding
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

    # Binary threshold: white pixels become 255, rest become 0
    _, white_mask = cv.threshold(gray, white_threshold, 255, cv.THRESH_BINARY)

    # Upscale for better OCR accuracy
    resized = cv.resize(white_mask, None, fx=scale_factor, fy=scale_factor,
                        interpolation=cv.INTER_CUBIC)

    # Apply morphological operations to clean up noise
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv.morphologyEx(resized, cv.MORPH_OPEN, kernel, iterations=1)
    cleaned = cv.morphologyEx(cleaned, cv.MORPH_CLOSE, kernel, iterations=1)

    # Invert so text is BLACK on WHITE (Tesseract preference)
    processed = cv.bitwise_not(cleaned)

    return processed


def ocr_single_line(image, whitelist=None):
    """Perform OCR on image expecting a single line of text

    Args:
        image: Image to process (numpy array or PIL Image)
        whitelist: Optional string of allowed characters

    Returns:
        str: Recognized text, stripped of whitespace
    """
    config = '--psm 7'
    if whitelist:
        config += f' -c tessedit_char_whitelist={whitelist}'

    text = pytesseract.image_to_string(image, config=config)
    return text.strip()
