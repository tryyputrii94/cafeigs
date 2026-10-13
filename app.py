"""
127 Coffeeshop — IG Story Live Music Poster Generator (v2)
==========================================================
Jalankan:
    pip install -r requirements.txt      (streamlit + pillow)
    streamlit run app.py

Fitur v2:
- Bagian pantun / ajakan / tagline (pilih dari pustaka, acak, atau tulis sendiri).
- Tema font (kombinasi font per elemen) — font Google diunduh otomatis
  SEKALI ke folder `fonts/`, setelah itu bisa dipakai offline.
  Tanpa internet -> otomatis pakai font cadangan sistem (tidak error).
- Tema warna (preset) + pengaturan warna manual (color picker).
- Auto-kontras: area foto yang terlalu terang otomatis digelapkan agar teks terbaca.

Semua pengaturan dipakai oleh SATU fungsi `render_poster()`, jadi preview
dan file unduhan selalu identik.
"""

import io
import os
import random
import re
import urllib.parse
import urllib.request
from collections import namedtuple
from functools import lru_cache

import streamlit as st
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# =====================================================================
# KONFIGURASI DASAR
# =====================================================================
CANVAS_W, CANVAS_H = 1080, 1920
CENTER_X = CANVAS_W // 2

APP_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(APP_DIR, "fonts")   # font hasil unduhan disimpan di sini
AUTO_DOWNLOAD_FONTS = True                   # False = tidak pernah mengunduh font

# Teks identitas brand (tidak diubah otomatis oleh program)
CAFE_NAME = "127 Coffeeshop"
SUB_1 = "127 COFFE AND TEA HOUSE"
SUB_2 = "JALAN TADUAN NO 127"
MAIN_TITLE = "Live Music"
TAGLINE = "GOOD COFFEE  •  GOOD FOOD  •  GREAT VIBES"
MENU_COLUMNS = [
    ("COFFEE", ["Espresso", "Americano", "Cappuccino"]),
    ("PREMIUM TEA", ["Black Tea", "Green Tea", "Lemon Tea"]),
    ("REGULER", ["Kopi Susu", "Kopi Gula Aren", "Chocolate"]),
    ("MAKANAN", ["Nasi Goreng", "Mie Goreng", "Snack"]),
]
FOOTER_1 = "Jalan Taduan No 127"
FOOTER_2 = "See You at 127 Coffeeshop"

# =====================================================================
# PUSTAKA TEKS: PANTUN / AJAKAN / TAGLINE  (silakan tambah sendiri)
# Gunakan "\n" untuk pindah baris.
# =====================================================================
TEXT_LIBRARY = {
    "Pantun": [
        "Senja datang membawa cerita,\nKopi hangat menemani suasana.\nYuk, nikmati musik dan tawa,\nDi 127 Coffeeshop kita berjumpa!",
        "Jalan-jalan ke Taduan,\nMampir sebentar minum kopi.\nMalam ini ada hiburan,\nLive music menemani hati.",
        "Petik gitar di bawah bulan,\nSuaranya merdu sampai ke hati.\nKopi hangat sudah disiapkan,\nTinggal kamu yang kami nanti.",
        "Ke Taduan naik sepeda,\nSinggah dulu di kedai kopi.\nLagu syahdu, suasana beda,\nAyo datang, jangan cuma mimpi!",
        "Burung camar terbang tinggi,\nHinggap sebentar di ujung dahan.\nDaripada galau sendiri,\nYuk ngopi, ada musik hiburan.",
        "Hujan rintik di malam hari,\nPaling pas ditemani kopi.\nAda musik, ada teman berbagi,\nDi 127 malam makin berarti.",
        "Pergi ke pasar membeli kain,\nKainnya merah bercorak bunga.\nMalam ini jangan ke lain,\nLive music 127 menunggu kita.",
        "Bunga melati harum mewangi,\nDipetik pagi di tepi taman.\nKopi dan lagu menemani hati,\nDatang sendiri pulang dapat teman.",
    ],
    "Ajakan": [
        "Kopi sudah siap, musik segera dimulai.\nYuk, habiskan malam bersama di 127 Coffeeshop!",
        "Ada kopi untuk menemani, ada musik untuk mengisi hati.\nSampai jumpa di Live Music 127 Coffeeshop!",
        "Ajak teman, ajak pasangan, atau datang cari suasana baru.\nLive Music malam ini, ketemunya di 127 Coffeeshop!",
        "Lepas penat seharian, sini duduk dan dengarkan.\nSecangkir kopi dan lagu favorit sudah menunggu.",
        "Malam terlalu indah buat dihabiskan di rumah.\nYuk keluar, ngopi, dan nikmati live music bareng kami!",
        "Satu meja, beberapa cangkir, dan lagu-lagu yang bikin rindu.\nKami tunggu kamu di 127 Coffeeshop.",
        "Bawa cerita, bawa teman, siapkan suara buat sing along.\nSisanya biar kopi dan musik yang urus.",
        "Mau quality time tanpa ribet?\nCukup datang, pilih kopi, dan biarkan musik bekerja.",
    ],
    "Tagline": [
        "Good Coffee, Good Music, Good Memories.\nMalam ini waktunya kamu menikmati semuanya!",
        "Secangkir kopi, sebait lagu, sejuta cerita.",
        "Sip. Listen. Repeat.",
        "Kopi hangat, lagu syahdu,\nmalam pun jadi seru.",
        "Nada pelan, kopi hangat, hati tenang.",
        "Dari senja sampai lagu terakhir.",
        "Ngopi makin syahdu, kalau ada lagu.",
        "Where every cup comes with a song.",
    ],
}

# =====================================================================
# TEMA FONT
# Tiap elemen poster punya "peran" (role) sendiri:
#   brand = "127 Coffeeshop" & penutup   | title = "Live Music"
#   caps  = sub-teks, tagline, label, judul menu, alamat (huruf kapital berjarak)
#   event = tanggal & jam                | quote = pantun / ajakan
#   body  = isi menu
# F(family Google Fonts / path .ttf lokal, weight, italic, kategori_cadangan, skala)
# =====================================================================
FontSpec = namedtuple("FontSpec", "family weight italic fallback scale")


def F(family, weight=400, italic=False, fallback="sans", scale=1.0):
    return FontSpec(family, weight, italic, fallback, scale)


FONT_THEMES = {
    "Elegant Luxury": {
        "desc": "Serif elegan + sans bersih. Tema default, kesan premium.",
        "brand": F("Playfair Display", 700, False, "serif_bold"),
        "title": F("Playfair Display", 700, True, "serif_bold_italic"),
        "caps": F("Montserrat", 500, False, "sans_medium"),
        "event": F("Montserrat", 700, False, "sans_bold"),
        "quote": F("Playfair Display", 400, True, "serif_italic"),
        "body": F("Montserrat", 400, False, "sans"),
    },
    "Modern Minimalist": {
        "desc": "Sans-serif tipis & bersih, judul kapital berjarak lebar.",
        "brand": F("Montserrat", 800, False, "sans_bold"),
        "title": F("Montserrat", 300, False, "sans_light"),
        "caps": F("Montserrat", 500, False, "sans_medium"),
        "event": F("Montserrat", 600, False, "sans_bold"),
        "quote": F("Montserrat", 400, True, "sans_italic"),
        "body": F("Montserrat", 400, False, "sans"),
        "title_upper": True,
        "title_tracking": 14,
    },
    "Classic Vintage": {
        "desc": "Serif klasik tebal + huruf kondensasi ala poster retro.",
        "brand": F("Libre Baskerville", 700, False, "serif_bold"),
        "title": F("Abril Fatface", 400, False, "serif_bold"),
        "caps": F("Oswald", 500, False, "condensed", 1.05),
        "event": F("Oswald", 600, False, "condensed", 1.1),
        "quote": F("Libre Baskerville", 400, True, "serif_italic", 0.92),
        "body": F("Libre Baskerville", 400, False, "serif", 0.92),
    },
    "Bold & Energetic": {
        "desc": "Huruf tebal & padat untuk suasana musik yang hidup.",
        "brand": F("Anton", 400, False, "condensed"),
        "title": F("Bebas Neue", 400, False, "condensed"),
        "caps": F("Oswald", 600, False, "condensed", 1.05),
        "event": F("Oswald", 700, False, "condensed", 1.12),
        "quote": F("Poppins", 500, False, "sans_medium"),
        "body": F("Poppins", 400, False, "sans"),
        "title_upper": True,
        "title_tracking": 6,
    },
    "Romantic": {
        "desc": "Script lembut + serif Garamond yang anggun.",
        "brand": F("Cormorant Garamond", 700, False, "serif_bold", 1.08),
        "title": F("Great Vibes", 400, False, "script", 1.1),
        "caps": F("Cormorant Garamond", 600, False, "serif", 1.15),
        "event": F("Cormorant Garamond", 700, False, "serif_bold", 1.12),
        "quote": F("Cormorant Garamond", 500, True, "serif_italic", 1.15),
        "body": F("Cormorant Garamond", 500, False, "serif", 1.15),
    },
    "Art Deco": {
        "desc": "Nuansa jazz 1920-an: huruf Romawi klasik & geometris.",
        "brand": F("Cinzel", 700, False, "serif_bold"),
        "title": F("Cinzel Decorative", 700, False, "serif_bold"),
        "caps": F("Josefin Sans", 600, False, "sans_medium", 1.05),
        "event": F("Josefin Sans", 700, False, "sans_bold", 1.08),
        "quote": F("Marcellus", 400, False, "serif"),
        "body": F("Josefin Sans", 400, False, "sans", 1.05),
    },
    "Retro Groovy": {
        "desc": "Judul script membulat ala kafe retro, teks sans ramah.",
        "brand": F("Poppins", 800, False, "sans_bold"),
        "title": F("Pacifico", 400, False, "script"),
        "caps": F("Poppins", 600, False, "sans_medium"),
        "event": F("Poppins", 700, False, "sans_bold"),
        "quote": F("Poppins", 400, True, "sans_italic"),
        "body": F("Poppins", 400, False, "sans"),
    },
    "Acoustic Handwritten": {
        "desc": "Tulisan tangan santai, cocok untuk akustik & pantun.",
        "brand": F("Amatic SC", 700, False, "condensed", 1.35),
        "title": F("Dancing Script", 700, False, "script"),
        "caps": F("Quicksand", 600, False, "sans_medium"),
        "event": F("Quicksand", 700, False, "sans_bold"),
        "quote": F("Caveat", 500, False, "script", 1.25),
        "body": F("Quicksand", 500, False, "sans"),
    },
}
DEFAULT_FONT_THEME = "Elegant Luxury"
FONT_ROLES = ("brand", "title", "caps", "event", "quote", "body")

# Font cadangan per kategori (Windows, macOS, Linux) bila font tema tidak tersedia
_W, _M = "C:/Windows/Fonts/", "/System/Library/Fonts/Supplemental/"
_DJ, _GF = "/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/truetype/google-fonts/"
_TG = "/usr/share/texmf/fonts/opentype/public/tex-gyre/"
FALLBACK_FONTS = {
    "script": [_W + "segoesc.ttf", _M + "SnellRoundhand.ttc", _TG + "texgyrechorus-mediumitalic.otf",
               _DJ + "DejaVuSerif-BoldItalic.ttf", "DejaVuSerif-BoldItalic.ttf"],
    "serif_bold": [_W + "georgiab.ttf", _M + "Georgia Bold.ttf", _TG + "texgyrebonum-bold.otf",
                   _DJ + "DejaVuSerif-Bold.ttf", "DejaVuSerif-Bold.ttf"],
    "serif_bold_italic": [_W + "georgiaz.ttf", _M + "Georgia Bold Italic.ttf", _TG + "texgyrebonum-bolditalic.otf",
                          _DJ + "DejaVuSerif-BoldItalic.ttf", "DejaVuSerif-BoldItalic.ttf"],
    "serif_italic": [_W + "georgiai.ttf", _M + "Georgia Italic.ttf", _TG + "texgyrepagella-italic.otf",
                     _DJ + "DejaVuSerif-Italic.ttf", "DejaVuSerif-Italic.ttf"],
    "serif": [_W + "georgia.ttf", _M + "Georgia.ttf", _TG + "texgyrepagella-regular.otf",
              _DJ + "DejaVuSerif.ttf", "DejaVuSerif.ttf"],
    "sans_bold": [_W + "segoeuib.ttf", _W + "arialbd.ttf", _M + "Arial Bold.ttf", _GF + "Poppins-Bold.ttf",
                  _DJ + "DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"],
    "sans_medium": [_W + "seguisb.ttf", _W + "arial.ttf", _M + "Arial.ttf", _GF + "Poppins-Medium.ttf",
                    _DJ + "DejaVuSans.ttf", "DejaVuSans.ttf"],
    "sans": [_W + "segoeui.ttf", _W + "arial.ttf", _M + "Arial.ttf", _GF + "Poppins-Regular.ttf",
             _DJ + "DejaVuSans.ttf", "DejaVuSans.ttf"],
    "sans_italic": [_W + "segoeuii.ttf", _W + "ariali.ttf", _M + "Arial Italic.ttf", _GF + "Poppins-Italic.ttf",
                    _DJ + "DejaVuSans-Oblique.ttf", "DejaVuSans-Oblique.ttf"],
    "sans_light": [_W + "segoeuil.ttf", _W + "arial.ttf", _M + "Arial.ttf", _GF + "Poppins-Light.ttf",
                   _DJ + "DejaVuSans-ExtraLight.ttf", "DejaVuSans.ttf"],
    "condensed": [_W + "impact.ttf", _M + "Impact.ttf", _TG + "texgyreheroscn-bold.otf",
                  _DJ + "DejaVuSansCondensed-Bold.ttf", "DejaVuSansCondensed-Bold.ttf"],
}

# =====================================================================
# TEMA WARNA
#   main   = warna utama (tint overlay & panel; otomatis dijaga tetap gelap)
#   accent = warna aksen (sub-judul, garis, ikon, border, tagline)
#   text   = warna teks utama | muted (opsional) = teks sekunder
# =====================================================================
COLOR_THEMES = {
    "Black & Gold Luxury": {"main": "#000000", "accent": "#D4AF69", "text": "#FFFFFF"},
    "Classic Burgundy": {"main": "#3D0A17", "accent": "#E2BE7E", "text": "#FFF8EC", "muted": "#EADBC8"},
    "Midnight Blue": {"main": "#081329", "accent": "#D8B86E", "text": "#EEF2F8", "muted": "#A9B8CF"},
    "Earthy Coffee": {"main": "#2E1D12", "accent": "#E3C9A0", "text": "#FFF9F0", "muted": "#D9C7B0"},
    "Forest Green": {"main": "#0D2619", "accent": "#D6B46A", "text": "#F6F0DF", "muted": "#CFD8C6"},
    "Monochrome": {"main": "#000000", "accent": "#CFCFCF", "text": "#FFFFFF", "muted": "#B5B5B5"},
    "Warm Sunset": {"main": "#3A1A0E", "accent": "#EE8F62", "text": "#FFF1DE", "muted": "#F0D5BC"},
    "Rose Gold Night": {"main": "#24121C", "accent": "#E8B4A0", "text": "#FFF3F0", "muted": "#E3CBCB"},
    "Teal Jazz": {"main": "#06262A", "accent": "#E9C46A", "text": "#F1FAF8", "muted": "#B7D3CF"},
}
DEFAULT_COLOR_THEME = "Black & Gold Luxury"

QUOTE_MIN_SIZE = 30        # ukuran font pantun terkecil (agar tetap terbaca)
QUOTE_SOFT_LIMIT = 200     # di atas jumlah karakter ini, UI memberi peringatan


# =====================================================================
# HELPER: WARNA
# =====================================================================
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rel_luminance(rgb):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def mix(a, b, t):
    """Campur warna a -> b sebesar t (0..1)."""
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _push_luminance(rgb, target, darken):
    """Gelapkan (darken=True) / terangkan warna sampai melewati target luminance."""
    out = rgb
    for step in range(1, 21):
        lum = rel_luminance(out)
        if (darken and lum <= target) or (not darken and lum >= target):
            return out, step > 1
        out = mix(rgb, (0, 0, 0) if darken else (255, 255, 255), step * 0.05)
    return out, True


def build_palette(main, accent, text, muted=None):
    """Bangun palet lengkap dari kode hex + jaga kontras. Return (palette, adjusted_flag)."""
    main, a1 = _push_luminance(hex_to_rgb(main), 0.035, darken=True)   # tint harus gelap
    accent, a2 = _push_luminance(hex_to_rgb(accent), 0.30, darken=False)
    text, a3 = _push_luminance(hex_to_rgb(text), 0.65, darken=False)
    if muted:
        muted, _ = _push_luminance(hex_to_rgb(muted), 0.45, darken=False)
    else:
        muted = mix(text, accent, 0.15)
    pal = {
        "main": main + (255,),
        "accent": accent + (255,),
        "text": text + (255,),
        "muted": muted + (255,),
        "line": text + (105,),
        "border": accent + (210,),
    }
    return pal, (a1 or a2 or a3)


# =====================================================================
# HELPER: FONT (unduh otomatis + cadangan)
# =====================================================================
def _font_registry():
    """Menyimpan daftar font yang gagal diunduh agar tidak dicoba terus tiap rerun."""
    return {"failed": set()}


try:  # dibagikan antar-rerun Streamlit
    _font_registry = st.cache_resource(_font_registry)
except Exception:  # dijalankan tanpa Streamlit
    _font_registry = lru_cache(maxsize=1)(_font_registry)


def _is_local_path(family):
    return family.lower().endswith((".ttf", ".otf", ".ttc"))


def font_file_path(spec):
    if _is_local_path(spec.family):
        p = spec.family
        return p if os.path.isabs(p) else os.path.join(APP_DIR, p)
    name = f"{spec.family.replace(' ', '')}-{spec.weight}{'i' if spec.italic else ''}.ttf"
    return os.path.join(FONT_DIR, name)


def download_google_font(spec, timeout=8):
    """Unduh 1 font dari Google Fonts (format TTF) ke folder fonts/. Return path / None."""
    dest = font_file_path(spec)
    if os.path.exists(dest):
        return dest
    if _is_local_path(spec.family) or not AUTO_DOWNLOAD_FONTS:
        return None
    key = (spec.family, spec.weight, spec.italic)
    failed = _font_registry()["failed"]
    if key in failed:
        return None
    try:
        axis = f"ital,wght@1,{spec.weight}" if spec.italic else f"wght@{spec.weight}"
        url = ("https://fonts.googleapis.com/css2?family="
               + urllib.parse.quote_plus(spec.family) + ":" + axis)
        # User-Agent sederhana -> Google mengirim format TTF (bukan WOFF2)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/4.0"})
        css = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8")
        if "/* latin */" in css:
            css = css.split("/* latin */", 1)[1]
        m = re.search(r"url\((https://[^)]+)\)", css)
        if not m:
            raise ValueError("URL font tidak ditemukan")
        data = urllib.request.urlopen(m.group(1), timeout=timeout).read()
        if data[:4] not in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
            raise ValueError("Format font bukan TTF/OTF")
        os.makedirs(FONT_DIR, exist_ok=True)
        tmp = dest + ".part"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, dest)
        return dest
    except Exception:
        failed.add(key)
        return None


def theme_font_specs(theme_name):
    theme = FONT_THEMES[theme_name]
    return [theme[r] for r in FONT_ROLES]


def missing_fonts(theme_name):
    return sorted({s.family for s in theme_font_specs(theme_name) if not os.path.exists(font_file_path(s))})


def ensure_theme_fonts(theme_name):
    for spec in theme_font_specs(theme_name):
        download_google_font(spec)


@lru_cache(maxsize=512)
def load_font(spec, size):
    """Font tema -> unduh bila belum ada -> font cadangan sistem -> default PIL. Tidak pernah error."""
    if isinstance(spec, str):  # kompatibel dgn versi lama: load_font("bold", 40)
        spec = F("", 400, False, {"script": "script", "bold": "sans_bold"}.get(spec, "sans"))
    size = max(8, int(round(size * spec.scale)))
    candidates = []
    if spec.family:
        path = font_file_path(spec)
        if not os.path.exists(path):
            path = download_google_font(spec) or path
        candidates.append(path)
    candidates += FALLBACK_FONTS.get(spec.fallback, []) + FALLBACK_FONTS["sans"]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError, ValueError):
            continue
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


# =====================================================================
# HELPER: TEKS
# =====================================================================
def text_size(draw, text, font, tracking=0):
    """Lebar & tinggi teks (termasuk letter-spacing / tracking)."""
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    if tracking == 0:
        return r - l, b - t
    width = sum(draw.textlength(ch, font=font) for ch in text) + tracking * (len(text) - 1)
    return int(width), b - t


def draw_text_at(draw, x, y, text, font, fill, tracking=0):
    """Gambar teks mulai dari (x, y) = pojok kiri-atas visual."""
    l, t, _, _ = draw.textbbox((0, 0), text, font=font)
    ox, oy = x - l, y - t  # buang offset internal font
    if tracking == 0:
        draw.text((ox, oy), text, font=font, fill=fill)
    else:
        cx = ox
        for ch in text:
            draw.text((cx, oy), ch, font=font, fill=fill)
            cx += draw.textlength(ch, font=font) + tracking


def draw_centered(draw, text, y, font, fill, tracking=0, center_x=CENTER_X):
    """Center alignment horizontal. Return: koordinat Y bawah teks."""
    w, h = text_size(draw, text, font, tracking)
    draw_text_at(draw, center_x - w / 2, y, text, font, fill, tracking)
    return y + h


def draw_line_on_baseline(draw, text, cx, baseline, font, fill):
    """Teks rata tengah di atas garis dasar (baseline) — rapi untuk teks multi-baris."""
    try:
        draw.text((cx, baseline), text, font=font, fill=fill, anchor="ms")
    except (ValueError, TypeError):  # font bitmap lama tidak mendukung anchor
        w, h = text_size(draw, text, font)
        draw.text((cx - w / 2, baseline - h), text, font=font, fill=fill)


def line_metrics(font, factor=1.3):
    try:
        asc, desc = font.getmetrics()
    except AttributeError:
        asc, desc = 12, 4
    return asc, int((asc + desc) * factor)


def fit_font(draw, spec, text, max_size, max_width, tracking=0, min_size=14, max_height=None):
    """Kecilkan ukuran font sampai teks muat (lebar & tinggi) — anti terpotong."""
    size = max_size
    while size > min_size:
        font = load_font(spec, size)
        w, h = text_size(draw, text, font, tracking)
        if w <= max_width and (max_height is None or h <= max_height):
            return font
        size -= 3
    return load_font(spec, min_size)


def wrap_text(draw, text, font, max_width):
    """Bungkus teks per kata agar tidak melebihi max_width. Baris kosong dipertahankan."""
    lines = []
    for para in text.strip().splitlines():
        para = " ".join(para.split())
        if not para:
            lines.append("")
            continue
        current = ""
        for word in para.split(" "):
            test = f"{current} {word}".strip()
            if not current or draw.textlength(test, font=font) <= max_width:
                current = test
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_divider(draw, y, half_width, line_color, diamond_color, cx=CENTER_X):
    draw.line([(cx - half_width, y), (cx + half_width, y)], fill=line_color, width=2)
    s = 7
    draw.polygon([(cx, y - s), (cx + s, y), (cx, y + s), (cx - s, y)], fill=diamond_color)


# =====================================================================
# HELPER: IKON (digambar manual, tanpa file eksternal)
# =====================================================================
def draw_calendar_icon(draw, x, y, size, color):
    r = size // 8
    draw.rounded_rectangle([x, y + 6, x + size, y + size], radius=r, outline=color, width=4)
    draw.rectangle([x, y + 6, x + size, y + 6 + size // 4], fill=color)
    for rx in (x + size // 4, x + 3 * size // 4):  # ring binder
        draw.line([(rx, y), (rx, y + 14)], fill=color, width=5)
    dot = 4
    for row in range(2):
        for col in range(3):
            cx = x + size * (col + 1) // 4
            cy = y + 6 + size // 4 + (size - size // 4 - 6) * (row + 1) // 3
            draw.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill=color)


def draw_clock_icon(draw, x, y, size, color):
    draw.ellipse([x, y, x + size, y + size], outline=color, width=4)
    cx, cy = x + size / 2, y + size / 2
    draw.line([(cx, cy), (cx, y + size * 0.22)], fill=color, width=4)
    draw.line([(cx, cy), (x + size * 0.74, cy)], fill=color, width=4)
    draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=color)


def draw_icon_row(draw, icon_fn, text, y, font, text_color, icon_color, icon_size=46, gap=24):
    """Ikon + teks, grup keseluruhan di-center-kan. Return Y bawah."""
    tw, th = text_size(draw, text, font, tracking=2)
    start_x = CENTER_X - (icon_size + gap + tw) / 2
    row_h = max(icon_size, th)
    icon_fn(draw, start_x, y + (row_h - icon_size) / 2, icon_size, icon_color)
    draw_text_at(draw, start_x + icon_size + gap, y + (row_h - th) / 2, text, font, text_color, tracking=2)
    return y + row_h


# =====================================================================
# LAYER: BACKGROUND, OVERLAY, AUTO-KONTRAS, PANEL, BAYANGAN
# =====================================================================
def make_background(uploaded_img):
    if uploaded_img is None:
        return Image.new("RGBA", (CANVAS_W, CANVAS_H), (30, 24, 20, 255))
    img = ImageOps.exif_transpose(uploaded_img).convert("RGB")
    # Resize + crop tengah agar penuh 1080x1920 (seperti object-fit: cover)
    img = ImageOps.fit(img, (CANVAS_W, CANVAS_H), method=Image.LANCZOS, centering=(0.5, 0.5))
    return img.convert("RGBA")


def _gradient_layer(alphas, color):
    """Layer warna `color` dengan alpha per-baris (list 0..1 sepanjang CANVAS_H)."""
    layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rgb = tuple(color[:3])
    for y, a in enumerate(alphas):
        d.line([(0, y), (CANVAS_W, y)], fill=rgb + (int(a * 255),))
    return layer


def make_overlay(base_alpha=0.55, color=(0, 0, 0)):
    """Overlay berwarna: ~base_alpha, lebih pekat di atas & bawah (gradient)."""
    alphas = []
    for y in range(CANVAS_H):
        t = y / (CANVAS_H - 1)
        top_boost = max(0.0, 0.30 - t) / 0.30 * 0.25        # 30% atas
        bottom_boost = max(0.0, t - 0.62) / 0.38 * 0.35     # 38% bawah
        alphas.append(min(0.92, base_alpha + top_boost + bottom_boost))
    return _gradient_layer(alphas, color)


def auto_contrast_layer(canvas, color, target=80, max_alpha=0.6):
    """Ukur kecerahan tiap baris foto (setelah overlay); baris yang terlalu terang
    diberi lapisan gelap tambahan supaya teks putih/emas tetap terbaca."""
    cols, rows = 36, 96
    small = canvas.convert("L").resize((cols, rows), Image.BOX)
    px = small.load()
    bright = []
    for r in range(rows):
        vals = sorted(px[c, r] for c in range(cols))
        bright.append(vals[int(cols * 0.85)])            # titik terang (persentil 85)
    need = [min(max_alpha, 1 - target / v) if v > target else 0.0 for v in bright]
    need = [max(need[max(0, i - 3):i + 4]) for i in range(rows)]                 # perlebar
    need = [sum(need[max(0, i - 2):i + 3]) / len(need[max(0, i - 2):i + 3]) for i in range(rows)]  # haluskan
    if max(need) <= 0.01:
        return None
    alphas = []
    for y in range(CANVAS_H):
        f = y / CANVAS_H * rows - 0.5
        i0 = min(rows - 1, max(0, int(f)))
        i1 = min(rows - 1, i0 + 1)
        t = min(1.0, max(0.0, f - i0))
        alphas.append(need[i0] * (1 - t) + need[i1] * t)
    return _gradient_layer(alphas, color)


def frosted_panel(canvas, rect, tint, alpha=120, radius=28, blur=16):
    """Panel 'kaca buram': foto di belakang di-blur + diberi warna utama transparan."""
    l, t, r, b = (int(round(v)) for v in rect)
    l, t, r, b = max(0, l), max(0, t), min(CANVAS_W, r), min(CANVAS_H, b)
    if r - l < 4 or b - t < 4:
        return
    region = canvas.crop((l, t, r, b)).filter(ImageFilter.GaussianBlur(blur))
    region = Image.alpha_composite(region, Image.new("RGBA", region.size, tuple(tint[:3]) + (alpha,)))
    mask = Image.new("L", region.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, r - l - 1, b - t - 1], radius=radius, fill=255)
    canvas.paste(region, (l, t), mask)


def add_soft_shadow(canvas, fg, offset=3, blur=5, strength=0.85):
    """Bayangan lembut di belakang SEMUA teks & ornamen (dibuat dari alpha layer fg)."""
    alpha = fg.getchannel("A").filter(ImageFilter.GaussianBlur(blur))
    alpha = alpha.point(lambda v: int(v * strength))
    shadow = Image.new("RGBA", fg.size, (0, 0, 0, 255))
    shadow.putalpha(alpha)
    shadow = shadow.crop((0, 0, CANVAS_W, CANVAS_H - offset))
    canvas.alpha_composite(shadow, dest=(0, offset))


# =====================================================================
# BLOK-BLOK LAYOUT
# Tiap blok: fungsi(ctx, y) -> y_bawah. Dipanggil 2x: ukur (dry) lalu gambar.
# =====================================================================
class Ctx:
    def __init__(self, draw, pal, theme, date_text, time_text, quote_text, dry):
        self.draw, self.pal, self.theme = draw, pal, theme
        self.date_text, self.time_text, self.quote_text = date_text, time_text, quote_text
        self.dry = dry
        self.panels = []          # area panel kaca buram (diisi saat menggambar)
        self.quote_budget = 520   # tinggi maksimal blok pantun

    def font(self, role, size):
        return load_font(self.theme[role], size)

    def fit(self, role, text, size, max_w, tracking=0, max_h=None):
        return fit_font(self.draw, self.theme[role], text, size, max_w, tracking, max_height=max_h)


def block_header(c, y):
    d, p = c.draw, c.pal
    f_brand = c.fit("brand", CAFE_NAME, 80, CANVAS_W - 160, tracking=1, max_h=90)
    y = draw_centered(d, CAFE_NAME, y, f_brand, p["text"], tracking=1)
    y += 28
    f_sub = c.fit("caps", SUB_1, 27, CANVAS_W - 160, tracking=6)
    y = draw_centered(d, SUB_1, y, f_sub, p["accent"], tracking=6)
    y += 16
    y = draw_centered(d, SUB_2, y, f_sub, p["muted"], tracking=6)
    y += 40
    draw_divider(d, y, 150, p["line"], p["accent"])
    return y + 8


def block_title(c, y):
    d, p, th = c.draw, c.pal, c.theme
    text = MAIN_TITLE.upper() if th.get("title_upper") else MAIN_TITLE
    tr = th.get("title_tracking", 0)
    f_title = c.fit("title", text, 240, CANVAS_W - 100, tracking=tr, max_h=215)
    y = draw_centered(d, text, y, f_title, p["text"], tracking=tr)
    y += 46
    f_tag = c.fit("caps", TAGLINE, 27, CANVAS_W - 120, tracking=4)
    return draw_centered(d, TAGLINE, y, f_tag, p["accent"], tracking=4)


def block_event(c, y):
    d, p = c.draw, c.pal
    box_l, box_r = 140, CANVAS_W - 140
    date_txt, time_txt = c.date_text.upper(), c.time_text
    longest = max(date_txt, time_txt, key=lambda s: text_size(d, s, c.font("event", 46), 2)[0])
    f_ev = c.fit("event", longest, 46, box_r - box_l - 150, tracking=2)
    f_lab = c.font("caps", 22)
    label = "SAVE THE DATE"
    lw, lh = text_size(d, label, f_lab, tracking=6)

    top = y + lh / 2
    y1 = draw_icon_row(d, draw_calendar_icon, date_txt, top + 62, f_ev, p["text"], p["accent"])
    y2 = draw_icon_row(d, draw_clock_icon, time_txt, y1 + 46, f_ev, p["text"], p["accent"])
    bottom = y2 + 58

    if not c.dry:
        c.panels.append((box_l, top, box_r, bottom))
    # Border kotak dengan celah untuk label "SAVE THE DATE"
    d.rounded_rectangle([box_l, top, box_r, bottom], radius=28, outline=p["border"], width=2)
    d.rectangle([CENTER_X - lw / 2 - 22, top - 4, CENTER_X + lw / 2 + 22, top + 4], fill=(0, 0, 0, 0))
    draw_centered(d, label, top - lh / 2, f_lab, p["accent"], tracking=6)
    return bottom


def block_menu(c, y):
    d, p = c.draw, c.pal
    margin = 40
    col_w = (CANVAS_W - 2 * margin) / 4
    d.line([(margin, y), (CANVAS_W - margin, y)], fill=p["line"], width=1)
    f_item = c.font("body", 24)
    asc, step = line_metrics(f_item, 1.42)
    col_bottom = y
    for i, (head, items) in enumerate(MENU_COLUMNS):
        cx = margin + col_w * i + col_w / 2
        f_head = c.fit("caps", head, 27, col_w - 18, tracking=2)
        yy = draw_centered(d, head, y + 32, f_head, p["accent"], tracking=2, center_x=cx) + 14
        for item in items:
            draw_line_on_baseline(d, item, cx, yy + asc, f_item, p["muted"])
            yy += step
        col_bottom = max(col_bottom, yy)
    bottom = col_bottom + 18
    for i in range(1, 4):  # garis pemisah vertikal antar kolom
        sx = margin + col_w * i
        d.line([(sx, y + 32), (sx, bottom - 18)], fill=p["line"], width=1)
    d.line([(margin, bottom), (CANVAS_W - margin, bottom)], fill=p["line"], width=1)
    return bottom


def block_quote(c, y):
    """Pantun / ajakan / tagline dalam panel kaca buram. Ukuran font menyesuaikan panjang teks."""
    d, p = c.draw, c.pal
    text = (c.quote_text or "").strip()
    if not text:
        return y
    box_l, box_r = 90, CANVAS_W - 90
    pad_x, pad_top, pad_bottom, ornament = 56, 40, 44, 34
    max_w = box_r - box_l - 2 * pad_x

    # Teks pendek boleh lebih besar (mengisi ruang), teks panjang mengecil
    # sampai batas minimum yang masih nyaman dibaca.
    start = 64 if len(text) <= 60 else 54
    for size in range(start, QUOTE_MIN_SIZE - 1, -2):
        f = c.font("quote", size)
        lines = wrap_text(d, text, f, max_w)
        asc, lh = line_metrics(f, 1.32)
        text_h = sum(lh if ln else lh // 2 for ln in lines)
        total = pad_top + ornament + text_h + pad_bottom
        if total <= c.quote_budget:
            break
    # Masih terlalu panjang di ukuran minimum -> potong baris berlebih dengan "…"
    while total > c.quote_budget and len(lines) > 1:
        lines = lines[:-1]
        lines[-1] = lines[-1].rstrip(" ,.;") + "…"
        text_h = sum(lh if ln else lh // 2 for ln in lines)
        total = pad_top + ornament + text_h + pad_bottom

    bottom = y + total
    if not c.dry:
        c.panels.append((box_l, y, box_r, bottom))
    draw_divider(d, y + pad_top, 60, p["border"], p["accent"])
    ty = y + pad_top + ornament
    for ln in lines:
        if ln:
            draw_line_on_baseline(d, ln, CENTER_X, ty + asc, f, p["text"])
            ty += lh
        else:
            ty += lh // 2
    return bottom


def block_footer(c, y):
    d, p = c.draw, c.pal
    draw_divider(d, y, 150, p["line"], p["accent"])
    y += 34
    f_addr = c.fit("caps", FOOTER_1, 26, CANVAS_W - 160, tracking=3)
    y = draw_centered(d, FOOTER_1, y, f_addr, p["muted"], tracking=3)
    y += 18
    f_close = c.fit("brand", FOOTER_2, 36, CANVAS_W - 140, max_h=48)
    return draw_centered(d, FOOTER_2, y, f_close, p["text"])


def plan_layout(blocks, heights, top=105, bottom=70, min_gap=40):
    """Hitung posisi Y tiap blok: header menempel atas, footer menempel bawah,
    sisa ruang dibagi rata di antara blok agar komposisi seimbang."""
    n = len(blocks)
    free = CANVAS_H - top - bottom - sum(heights)
    gaps = [max(min_gap, free / (n - 1))] * (n - 1)
    ys, y = [], top
    for h, g in zip(heights, gaps + [0]):
        ys.append(y)
        y += h + g
    return ys


# =====================================================================
# RENDER POSTER (dipakai untuk preview DAN file unduhan)
# =====================================================================
def render_poster(uploaded_img, date_text, time_text, overlay_alpha=0.55, *,
                  quote_text="", font_theme=DEFAULT_FONT_THEME, palette=None,
                  show_menu=True, show_quote=True, auto_contrast=True):
    if palette is None:
        palette, _ = build_palette(**COLOR_THEMES[DEFAULT_COLOR_THEME])
    theme = FONT_THEMES.get(font_theme, FONT_THEMES[DEFAULT_FONT_THEME])
    quote_text = quote_text if show_quote else ""

    # 1) Background + overlay berwarna (+ auto-kontras)
    canvas = make_background(uploaded_img)
    canvas = Image.alpha_composite(canvas, make_overlay(overlay_alpha, palette["main"]))
    if auto_contrast:
        extra = auto_contrast_layer(canvas, palette["main"])
        if extra is not None:
            canvas = Image.alpha_composite(canvas, extra)

    # 2) Susunan blok
    blocks = [block_header, block_title, block_event]
    if show_menu:
        blocks.append(block_menu)
    if quote_text.strip():
        blocks.append(block_quote)
    blocks.append(block_footer)

    # 3) Ukur tinggi tiap blok (dry run di kanvas coretan)
    scratch = ImageDraw.Draw(Image.new("RGBA", (CANVAS_W, CANVAS_H)))
    mctx = Ctx(scratch, palette, theme, date_text, time_text, quote_text, dry=True)
    heights = {b: b(mctx, 0) for b in blocks if b is not block_quote}
    if block_quote in blocks:
        min_gap = 40
        room = CANVAS_H - 105 - 70 - sum(heights.values()) - min_gap * (len(blocks) - 1)
        mctx.quote_budget = max(160, min(560, room))
        heights[block_quote] = block_quote(mctx, 0)
    ys = plan_layout(blocks, [heights[b] for b in blocks])

    # 4) Gambar teks & ornamen di layer terpisah
    fg = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    ctx = Ctx(ImageDraw.Draw(fg), palette, theme, date_text, time_text, quote_text, dry=False)
    ctx.quote_budget = mctx.quote_budget
    for b, y in zip(blocks, ys):
        b(ctx, y)

    # 5) Panel kaca buram -> bayangan lembut -> teks
    for rect in ctx.panels:
        frosted_panel(canvas, rect, palette["main"])
    add_soft_shadow(canvas, fg)
    canvas = Image.alpha_composite(canvas, fg)
    return canvas.convert("RGB")


def to_bytes(img, fmt):
    buf = io.BytesIO()
    if fmt == "JPG":
        img.save(buf, format="JPEG", quality=95, subsampling=0, optimize=True)
    else:
        img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# =====================================================================
# STREAMLIT UI
# =====================================================================
def _init_state():
    ss = st.session_state
    ss.setdefault("txt_mode", "Pantun")
    ss.setdefault("txt_choice", 0)
    ss.setdefault("txt_body", TEXT_LIBRARY["Pantun"][0])
    ss.setdefault("color_preset", DEFAULT_COLOR_THEME)
    preset = COLOR_THEMES[ss["color_preset"]]
    ss.setdefault("cp_main", preset["main"])
    ss.setdefault("cp_accent", preset["accent"])
    ss.setdefault("cp_text", preset["text"])


def _on_mode_change():
    ss = st.session_state
    ss["txt_choice"] = 0
    ss["txt_body"] = TEXT_LIBRARY[ss["txt_mode"]][0]


def _on_choice_change():
    ss = st.session_state
    ss["txt_body"] = TEXT_LIBRARY[ss["txt_mode"]][ss["txt_choice"]]


def _on_random_text():
    """Hanya mengubah teks pantun — pengaturan lain tidak disentuh."""
    ss = st.session_state
    options = TEXT_LIBRARY[ss["txt_mode"]]
    pool = [i for i in range(len(options)) if i != ss.get("txt_choice")] or [0]
    ss["txt_choice"] = random.choice(pool)
    ss["txt_body"] = options[ss["txt_choice"]]


def _on_preset_change():
    ss = st.session_state
    preset = COLOR_THEMES[ss["color_preset"]]
    ss["cp_main"], ss["cp_accent"], ss["cp_text"] = preset["main"], preset["accent"], preset["text"]


def _preview_label(text, n=46):
    first = text.strip().splitlines()[0] if text.strip() else "(kosong)"
    return first if len(first) <= n else first[: n - 1] + "…"


def main():
    st.set_page_config(page_title="127 Coffeeshop • Live Music Poster", page_icon="🎶", layout="wide")
    _init_state()
    ss = st.session_state

    with st.sidebar:
        # ---------- 1. Foto & Jadwal ----------
        st.header("1 · Foto & Jadwal")
        uploaded = st.file_uploader("Upload Foto Background (Landscape/Portrait)",
                                    type=["jpg", "jpeg", "png", "webp"])
        date_text = st.text_input("Hari & Tanggal", value="SABTU, 26 SEPTEMBER 2026")
        time_text = st.text_input("Waktu", value="19.30 - 22.30")

        # ---------- 2. Pantun / Ajakan ----------
        st.header("2 · Pantun / Ajakan")
        show_quote = st.checkbox("Tampilkan di poster", value=True, key="show_quote")
        st.radio("Jenis teks", list(TEXT_LIBRARY), key="txt_mode", horizontal=True,
                 on_change=_on_mode_change)
        options = TEXT_LIBRARY[ss["txt_mode"]]
        st.selectbox("Pilih dari daftar", list(range(len(options))), key="txt_choice",
                     format_func=lambda i: f"{i + 1}. {_preview_label(options[i])}",
                     on_change=_on_choice_change)
        st.button("🎲 Acak Teks", on_click=_on_random_text, use_container_width=True)
        quote_text = st.text_area("Edit teks (Enter = baris baru)", key="txt_body", height=140)
        if len(quote_text.strip()) > QUOTE_SOFT_LIMIT:
            st.caption(f"⚠️ Teks cukup panjang ({len(quote_text.strip())} karakter). "
                       "Idealnya ≤ 4 baris; kelebihan akan dipotong dengan '…'.")

        # ---------- 3. Tema Font ----------
        st.header("3 · Tema Font")
        font_theme = st.selectbox("Pilih tema font", list(FONT_THEMES), key="font_theme")
        st.caption(FONT_THEMES[font_theme]["desc"])

        # ---------- 4. Tema Warna ----------
        st.header("4 · Tema Warna")
        st.selectbox("Pilih tema warna", list(COLOR_THEMES), key="color_preset",
                     on_change=_on_preset_change)
        manual = st.checkbox("Atur warna manual", value=False, key="color_manual")
        if manual:
            c1, c2, c3 = st.columns(3)
            c1.color_picker("Utama", key="cp_main", help="Warna dasar overlay & panel (dijaga tetap gelap)")
            c2.color_picker("Aksen", key="cp_accent", help="Sub-judul, garis, ikon, border")
            c3.color_picker("Teks", key="cp_text", help="Warna teks utama")
            palette, adjusted = build_palette(ss["cp_main"], ss["cp_accent"], ss["cp_text"])
            if adjusted:
                st.caption("ℹ️ Sebagian warna disesuaikan otomatis agar teks tetap terbaca.")
        else:
            palette, _ = build_palette(**COLOR_THEMES[ss["color_preset"]])

        # ---------- Lainnya ----------
        with st.expander("⚙️ Pengaturan lain"):
            show_menu = st.checkbox("Tampilkan daftar menu", value=True, key="show_menu")
            overlay_alpha = st.slider("Kegelapan overlay", 0.30, 0.80, 0.55, 0.05)
            auto_contrast = st.checkbox("Auto-kontras (gelapkan area foto yang terlalu terang)",
                                        value=True)
            out_fmt = st.radio("Format unduhan", ["PNG", "JPG"], horizontal=True)
            if st.button("📥 Unduh semua font tema (untuk offline)"):
                _font_registry()["failed"].clear()
                bar = st.progress(0.0)
                for i, name in enumerate(FONT_THEMES):
                    ensure_theme_fonts(name)
                    bar.progress((i + 1) / len(FONT_THEMES))
                load_font.cache_clear()
                st.success("Selesai. Font tersimpan di folder fonts/.")

    # Siapkan font tema yang dipilih (unduh sekali bila belum ada)
    if AUTO_DOWNLOAD_FONTS and missing_fonts(font_theme):
        with st.spinner("Menyiapkan font tema (hanya sekali)…"):
            ensure_theme_fonts(font_theme)
        load_font.cache_clear()
    still_missing = missing_fonts(font_theme)
    if still_missing:
        st.sidebar.caption("⚠️ Font belum tersedia (offline?): " + ", ".join(still_missing)
                           + " — sementara memakai font cadangan.")

    st.title("🎶 IG Story Live Music Generator")
    st.caption("127 Coffeeshop • Output 1080 × 1920 px (9:16)")

    img = Image.open(uploaded) if uploaded else None
    if img is None:
        st.info("Belum ada foto — preview memakai background polos. Upload foto di sidebar.")

    poster = render_poster(
        img, date_text, time_text, overlay_alpha,
        quote_text=quote_text, font_theme=font_theme, palette=palette,
        show_menu=show_menu, show_quote=show_quote, auto_contrast=auto_contrast,
    )

    col_preview, col_action = st.columns([3, 2])
    with col_preview:
        st.image(poster, caption="Preview = hasil unduhan (1080 × 1920)", width=440)
    with col_action:
        st.subheader("⬇️ Unduh")
        ext = "jpg" if out_fmt == "JPG" else "png"
        safe_date = "".join(ch if ch.isalnum() else "_" for ch in date_text)[:40]
        st.download_button(
            label=f"Download {out_fmt} (1080 × 1920)",
            data=to_bytes(poster, out_fmt),
            file_name=f"127coffeeshop_livemusic_{safe_date}.{ext}",
            mime="image/jpeg" if out_fmt == "JPG" else "image/png",
            use_container_width=True,
            type="primary",
        )
        st.markdown(
            f"**Pengaturan aktif**  \n"
            f"• Font: {font_theme}  \n"
            f"• Warna: {'Manual' if manual else ss['color_preset']}  \n"
            f"• Teks: {ss['txt_mode'] if show_quote else 'disembunyikan'}  \n"
            f"• Menu: {'tampil' if show_menu else 'disembunyikan'}"
        )
        st.caption("File unduhan dibuat dari gambar preview yang sama, "
                   "jadi semua font, warna, dan teks pasti ikut.")


if __name__ == "__main__":
    main()