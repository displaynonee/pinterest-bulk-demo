import os
import json
import csv
import random
import re
import datetime as _dt
import shutil
import hashlib
import urllib.request
import urllib.parse
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# ─────────────────────────────────────────────
# DEMO MODE SETTINGS (FOR LIVE DEMO)
# ─────────────────────────────────────────────
DEMO_MODE = True       # Set to True for live demo, False for Full Version
DEMO_PIN_LIMIT = 2     # Max pins per category in Demo Mode

# Page Configuration
st.set_page_config(page_title="Pinterest Bulk Image & Content Engine (Demo)", layout="wide")

CONFIG_FILE = "config.json"
USED_PINS_FILE = "used_pins.json"
BASE_BG_DIR = "backgrounds"
FONTS_DIR = "fonts"

os.makedirs(BASE_BG_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)

# Top Badge Dynamic CTA Pool (English / Global)
BADGE_CTA_POOL = [
    "EASY TO APPLY", "MUST READ", "TRENDING IDEAS", "STEP BY STEP", 
    "FREE GUIDE", "MOST POPULAR", "BEGINNER GUIDE", "CREATIVE IDEAS", 
    "BUDGET FRIENDLY", "EXPERT TIPS"
]

def hex_to_rgb(hex_str):
    """Converts HEX color string to RGB tuple"""
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def load_full_config():
    default_config = {
        "settings": {
            "site_url": "https://example.com/",
            "wp_upload_base": "https://example.com/wp-content/uploads/",
            "board_name": "My Pinterest Board",
            "start_delay_min": 5,
            "interval_min": 10,
            "ab_test_ratio": 0.0,
            "panel_alpha_top": 120,
            "panel_alpha_bot": 165,
            "pexels_api_key": "",
            "max_pins_per_cat": 50,
            "selected_font": "Varsayılan Sistem",
            "badge_color": "#F26C3F",
            "btn_color": "#FBA167"
        },
        "categories": {
            "general": {
                "pillar_url": "guide/",
                "keywords": "home decor ideas, interior design, diy crafts, practical tips, modern styles",
                "pexels_terms": "home decor"
            }
        }
    }
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
        return default_config
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return default_config

def save_full_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def load_used_pins():
    if not os.path.exists(USED_PINS_FILE):
        return {}
    with open(USED_PINS_FILE, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return {}

def save_used_pins(used_data):
    with open(USED_PINS_FILE, 'w', encoding='utf-8') as f:
        json.dump(used_data, f, ensure_ascii=False, indent=4)

def get_available_fonts():
    """Lists .ttf fonts in fonts/ directory"""
    fonts = ["Varsayılan Sistem", "arial.ttf", "Courier"]
    if os.path.exists(FONTS_DIR):
        local_fonts = [f for f in os.listdir(FONTS_DIR) if f.lower().endswith(".ttf")]
        for lf in sorted(local_fonts):
            fonts.insert(0, os.path.join(FONTS_DIR, lf))
    return fonts

COLOR_PALETTES = [
    {"panel_fill": (20, 10, 0, 120), "title_color": (255, 255, 255, 255), "title_shadow": (15, 8, 0, 220)},
    {"panel_fill": (0, 30, 38, 120), "title_color": (255, 255, 255, 255), "title_shadow": (0, 15, 20, 220)},
    {"panel_fill": (40, 20, 40, 130), "title_color": (255, 255, 255, 255), "title_shadow": (20, 5, 20, 220)},
    {"panel_fill": (15, 15, 15, 140), "title_color": (255, 255, 255, 255), "title_shadow": (0, 0, 0, 240)}
]

def slugify(text):
    text = text.lower()
    for src, dst in {"ı":"i","ğ":"g","ü":"u","ş":"s","ö":"o","ç":"c"}.items(): text = text.replace(src, dst)
    return re.sub(r"[\s-]+", "-", re.sub(r"[^a-z0-9\s-]", "", text)).strip("-")

def clean_title_input(kw):
    kw_clean = re.sub(r"^(best|how to choose|how to make)\s+", "", kw, flags=re.IGNORECASE)
    kw_clean = re.sub(r"\s+(guide|tips|ideas)$", "", kw_clean, flags=re.IGNORECASE)
    return kw_clean.strip().title()

def load_font(font_setting, size):
    paths_to_try = [font_setting, "fonts/Montserrat-Bold.ttf", "arial.ttf", "Courier"]
    for path in paths_to_try:
        if path == "Varsayılan Sistem":
            continue
        try: return ImageFont.truetype(path, size)
        except: continue
    return ImageFont.load_default()

def text_wh(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def draw_centered_text(draw, cx, y, text, font, fill, shadow=None):
    if shadow: 
        draw.text((cx + 3, y + 3), text, fill=shadow, font=font, anchor="mm")
    draw.text((cx, y), text, fill=fill, font=font, anchor="mm")

def wrap_to_lines(draw, text, font, max_px):
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        w, _ = text_wh(draw, candidate, font)
        if w <= max_px: current = candidate
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    return [(l, *text_wh(draw, l, font)) for l in lines]

def create_pin_new(bg_path, output_path, title, alpha_top, alpha_bot, palette, site_url_input, font_setting, badge_color_hex, btn_color_hex):
    bg = Image.open(bg_path).resize((1000, 1500), Image.Resampling.LANCZOS)
    canvas = bg.convert("RGBA")
    mask = Image.new("L", canvas.size, 0)
    
    panel_top, panel_bottom = 400, 1100
    ImageDraw.Draw(mask).rounded_rectangle([70, panel_top, 930, panel_bottom], radius=24, fill=255)
    
    grad = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad)
    r, g, b, _ = palette["panel_fill"]
    for y_line in range(panel_top, panel_bottom):
        t = (y_line - panel_top) / (panel_bottom - panel_top)
        alpha = int(alpha_top + (alpha_bot - alpha_top) * t)
        grad_draw.line([(70, y_line), (930, y_line)], fill=(r, g, b, alpha))
        
    grad_arr = np.array(grad)
    grad_arr[...,3] = (grad_arr[...,3].astype(np.uint16) * np.array(mask) // 255).astype(np.uint8)
    canvas = Image.alpha_composite(canvas, Image.fromarray(grad_arr, "RGBA"))
    draw = ImageDraw.Draw(canvas)
    
    # Top Badge Transformation
    badge_rgb = hex_to_rgb(badge_color_hex) + (255,)
    badge_text = random.choice(BADGE_CTA_POOL)
    badge_font = load_font(font_setting, 32)
    badge_w, badge_h = text_wh(draw, badge_text, badge_font)
    
    badge_padding_x, badge_padding_y = 30, 12
    bx1 = 500 - (badge_w // 2) - badge_padding_x
    by1 = panel_top + 40
    bx2 = 500 + (badge_w // 2) + badge_padding_x
    by2 = by1 + badge_h + (badge_padding_y * 2)
    
    ImageDraw.Draw(canvas).rounded_rectangle([bx1, by1, bx2, by2], radius=12, fill=badge_rgb)
    
    badge_center_y = by1 + (by2 - by1) // 2
    draw_centered_text(draw, 500, badge_center_y, badge_text, badge_font, (255, 255, 255, 255))
    
    # CTA Button Transformation (English)
    btn_rgb = hex_to_rgb(btn_color_hex) + (255,)
    btn_text = "READ MORE"
    btn_font = load_font(font_setting, 36)
    btn_w, btn_h = text_wh(draw, btn_text, btn_font)
    
    btn_padding_x, btn_padding_y = 50, 15
    btn_x1 = 500 - (btn_w // 2) - btn_padding_x
    btn_y1 = panel_bottom - 150
    btn_x2 = 500 + (btn_w // 2) + btn_padding_x
    btn_y2 = btn_y1 + btn_h + (btn_padding_y * 2)
    
    ImageDraw.Draw(canvas).rounded_rectangle([btn_x1, btn_y1, btn_x2, btn_y2], radius=15, fill=btn_rgb)
    
    btn_center_x = 500
    btn_center_y = btn_y1 + (btn_y2 - btn_y1) // 2
    draw_centered_text(draw, btn_center_x, btn_center_y, btn_text, btn_font, (20, 10, 0, 255))
    
    font = load_font(font_setting, 62)
    lines_data = wrap_to_lines(draw, title, font, 760)
    
    center_start_y = by2 + 20
    center_end_y = btn_y1 - 20
    available_height = center_end_y - center_start_y
    
    ascent, descent = font.getmetrics()
    real_line_height = ascent + descent
    spacing = 14
    
    total_text_height = (real_line_height * len(lines_data)) + (spacing * (len(lines_data) - 1))
    start_y = center_start_y + (available_height - total_text_height) // 2
    
    for i, (line, _, _) in enumerate(lines_data):
        line_top_y = start_y + i * (real_line_height + spacing)
        line_center_y = line_top_y + (real_line_height // 2)
        final_y = line_center_y + 10 
        
        draw_centered_text(draw, 500, final_y, line, font, palette["title_color"], palette["title_shadow"])
    
    clean_domain = site_url_input.replace("https://", "").replace("http://", "").strip("/")
    if not clean_domain:
        clean_domain = "yoursite.com"
        
    watermark_font = load_font(font_setting, 28)
    draw_centered_text(draw, 500, btn_y2 + 20, clean_domain, watermark_font, (255, 255, 255, 220))
    
    # DEMO MODE WATERMARK
    if DEMO_MODE:
        demo_font = load_font(font_setting, 80)
        draw_centered_text(draw, 500, 750, "DEMO VERSION", demo_font, (255, 255, 255, 160), shadow=(0, 0, 0, 220))

    canvas.convert("RGB").save(output_path, "WEBP", quality=87)

# Global / English Title Templates
TITLE_TEMPLATES = [
    "How to Choose the Best {keyword}", "10 Amazing {keyword} Ideas You Must See", "Ultimate {keyword} Guide for Beginners",
    "Essential Tips for a Perfect {keyword}", "Top Trending {keyword} Ideas This Year", "Secrets to Choosing the Right {keyword}",
    "Budget-Friendly & Easy {keyword} Solutions", "Everything You Need to Know About {keyword}", "How to Find High-Quality {keyword}",
    "Why You Need a Good {keyword} Plan", "Modern {keyword} Styles and Inspiration", "7 Surprising {keyword} Hacks You Should Know",
    "Common Mistakes to Avoid in {keyword}", "The Only {keyword} Checklist You Need", "Stunning {keyword} Designs and Examples",
    "Smart Budgeting for Your {keyword}", "Expert Guide to {keyword}", "Top {keyword} Trends for 2026",
    "Step-by-Step {keyword} Tutorial", "The Untold Truth About {keyword}", "Quality vs Affordable {keyword} Comparison",
    "Expert Advice: How to Find {keyword}", "How to Build Your Own {keyword} Style", "Featured New {keyword} Concepts",
    "Complete Roadmap for {keyword}", "Quick Guide: All {keyword} Options", "How to Select Long-Lasting {keyword}",
    "Creative {keyword} Ideas & Strategies", "Things to Consider Before Buying {keyword}", "Stress-Free Ways to Choose {keyword}",
    "Why {keyword} is More Important Than You Think", "Popular {keyword} Examples for Every Style", "Simple Hacks to Simplify Your {keyword}",
    "Find the Perfect {keyword} for Your Style", "Beautiful {keyword} Ideas for Inspiration", "Simple Ways to Upgrade Your {keyword}",
    "10 Game-Changing {keyword} Tips", "The Best {keyword} Recommendations", "Benefits of Modern {keyword} Options",
    "Alternative & Creative {keyword} Solutions"
]

def generate_unique_title(keyword, folder_slug, used_global_dict):
    clean_kw = clean_title_input(keyword)
    if folder_slug not in used_global_dict:
        used_global_dict[folder_slug] = []
    
    past_titles = used_global_dict[folder_slug]
    shuffled_templates = list(TITLE_TEMPLATES)
    random.shuffle(shuffled_templates)
    
    for template in shuffled_templates:
        candidate = template.format(keyword=clean_kw)
        if candidate not in past_titles:
            return candidate
            
    suffixes = ["Secrets & Hacks", "2026 Ideas", "Expert Guide", "Special Tips", "Best Options"]
    for _ in range(50):
        candidate = f"Best {clean_kw} {random.choice(suffixes)} - {random.randint(100, 999)}"
        if candidate not in past_titles:
            return candidate
            
    return f"Awesome {clean_kw} Ideas - {random.randint(1000, 9999)}"

def download_pexels_images(api_key, query, target_folder, count=10):
    if not api_key: return False, "Pexels API Key missing!"
    os.makedirs(target_folder, exist_ok=True)
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&orientation=portrait&per_page={count}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", str(api_key).strip())
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            photos = data.get("photos", [])
            if not photos: return False, f"No images found for '{query}'."
            downloaded = 0
            for idx, photo in enumerate(photos):
                img_url = photo.get("src", {}).get("large2x")
                if img_url:
                    file_path = os.path.join(target_folder, f"pexels-{idx}-{int(_dt.datetime.now().timestamp())}.jpg")
                    img_req = urllib.request.Request(img_url)
                    img_req.add_header("User-Agent", "Mozilla/5.0")
                    with urllib.request.urlopen(img_req) as img_res, open(file_path, "wb") as out_file:
                        out_file.write(img_res.read())
                    downloaded += 1
            return True, f"Successfully downloaded {downloaded} images."
    except Exception as e:
        return False, f"Pexels API Error: {str(e)}"

# Load Settings
config = load_full_config()
available_fonts = get_available_fonts()

# ─────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────
st.title("🎯 Pinterest Toplu Görsel & İçerik Motoru")
st.caption("Platform Bağımsız Tarayıcı Tabanlı Kodsuz Otomasyon Paneli")

# R10 Demo Info Box
if DEMO_MODE:
    st.info(f"🧪 **R10 CANLI DEMO SÜRÜMÜ:** Bu mod test amaçlıdır. Her kategoriden **en fazla {DEMO_PIN_LIMIT} görsel** üretilir ve görsellere **'DEMO VERSION' filigranı** eklenir. Tam sürümde herhangi bir limit veya filigran bulunmamaktadır.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("⚙️ Genel Sistem & Niş Ayarları")
    
    site_url = st.text_input("Hedef Site URL Adresi:", config["settings"].get("site_url"))
    wp_upload = st.text_input("WordPress Görsel Yükleme Adresi (Uploads Base):", config["settings"].get("wp_upload_base"))
    board_name = st.text_input("Pinterest Pano Adı (Board Name):", config["settings"].get("board_name"))
    pexels_key = st.text_input("🔑 Pexels API Anahtarı:", config["settings"].get("pexels_api_key", ""), type="password")
    max_pins_per_cat = st.number_input("📈 Kategori Başına Üretilecek Pin Sayısı:", min_value=1, max_value=500, value=int(config["settings"].get("max_pins_per_cat", 50)))
    
    saved_font = config["settings"].get("selected_font", "Varsayılan Sistem")
    if saved_font not in available_fonts:
        saved_font = "Varsayılan Sistem"
    selected_font = st.selectbox("🔤 Tasarım Fontu Seçin (fonts/ Klasörünü Tarar):", available_fonts, index=available_fonts.index(saved_font))
    
    st.markdown("---")
    st.markdown("##### 🎨 Görsel CTA & Rozet Renk Ayarları")
    color_col1, color_col2 = st.columns(2)
    with color_col1:
        badge_color = st.color_picker("🏷️ Üst Rozet Rengi:", config["settings"].get("badge_color", "#F26C3F"))
    with color_col2:
        btn_color = st.color_picker("🔘 CTA Buton Rengi:", config["settings"].get("btn_color", "#FBA167"))

    st.markdown("---")
    sub_col1, sub_col2 = st.columns(2)
    with sub_col1:
        start_delay = st.number_input("Başlangıç Gecikmesi (Dakika):", value=int(config["settings"].get("start_delay_min", 5)))
        interval = st.number_input("Paylaşım Aralığı (Dakika):", value=int(config["settings"].get("interval_min", 10)))
    with sub_col2:
        alpha_top = st.slider("Panel Üst Şeffaflığı (0-255):", 0, 255, value=int(config["settings"].get("panel_alpha_top", 120)))
        alpha_bot = st.slider("Panel Alt Şeffaflığı (0-255):", 0, 255, value=int(config["settings"].get("panel_alpha_bot", 165)))

    col_save, col_reset = st.columns([2, 1])
    with col_save:
        if st.button("💾 Sistem Ayarlarını Kaydet", type="primary", use_container_width=True):
            config["settings"].update({
                "site_url": site_url, "wp_upload_base": wp_upload, "board_name": board_name,
                "start_delay_min": int(start_delay), "interval_min": int(interval),
                "ab_test_ratio": 0.0, "panel_alpha_top": int(alpha_top), "panel_alpha_bot": int(alpha_bot),
                "pexels_api_key": pexels_key, "max_pins_per_cat": int(max_pins_per_cat),
                "selected_font": selected_font,
                "badge_color": badge_color,
                "btn_color": btn_color
            })
            save_full_config(config)
            st.success("Tüm ayarlar başarıyla kaydedildi!")
            st.rerun()

    with col_reset:
        if st.button("🚨 Tüm Ayarları Sıfırla", type="secondary", use_container_width=True):
            if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
            if os.path.exists(USED_PINS_FILE): os.remove(USED_PINS_FILE)
            st.warning("Tüm yapılandırma ve geçmiş veriler sıfırlandı!")
            st.rerun()

    st.markdown("---")
    st.subheader("📂 Yeni Niş / Kategori Ekle")
    new_folder = st.text_input("Klasör / Niş Adı (Örn: yoga, cat-food, home-decor):")
    new_url = st.text_input("Hedef Sayfa / Yazı URL'i (Örn: yoga-mats-guide/):")
    new_kws = st.text_area("Anahtar Kelimeler (İngilizce - virgülle ayırarak yazın):")
    new_pex = st.text_input("Pexels Otomatik Arama Kelimesi:")
    
    if st.button("➕ Kategoriyi ve Klasörü Oluştur", use_container_width=True):
        if new_folder and new_url:
            folder_slug = slugify(new_folder)
            config["categories"][folder_slug] = {"pillar_url": new_url, "keywords": new_kws, "pexels_terms": new_pex}
            save_full_config(config)
            os.makedirs(os.path.join(BASE_BG_DIR, folder_slug), exist_ok=True)
            st.success(f"'{folder_slug}' kategorisi başarıyla eklendi!")
            st.rerun()

with col2:
    st.subheader("📋 Aktif Kategoriler ve Durum")
    all_physical_folders = sorted([d for d in os.listdir(BASE_BG_DIR) if os.path.isdir(os.path.join(BASE_BG_DIR, d))])
    used_pins_data = load_used_pins()
    
    for folder in all_physical_folders:
        folder_path = os.path.join(BASE_BG_DIR, folder)
        images_count = len([f for f in os.listdir(folder_path) if f.lower().endswith(("jpg", "jpeg", "png", "webp"))])
        
        if folder not in config["categories"]:
            config["categories"][folder] = {"pillar_url": f"{folder}/", "keywords": f"{folder} trends", "pexels_terms": folder}
            save_full_config(config)
            
        info = config["categories"][folder]
        past_count = len(used_pins_data.get(folder, []))
        
        with st.expander(f"📁 backgrounds/{folder} ({images_count} Görsel | {past_count} Üretilmiş Başlık)"):
            updated_url = st.text_input("Hedef Sayfa URL'i:", info.get("pillar_url", f"{folder}/"), key=f"url_{folder}")
            updated_kws = st.text_area("Anahtar Kelimeler:", info.get("keywords", ""), key=f"kws_{folder}")
            updated_pex = st.text_input("Pexels Arama Terimi:", info.get("pexels_terms", folder), key=f"pex_{folder}")
            
            if st.button(f"💾 Değişiklikleri Kaydet ({folder})", key=f"save_btn_{folder}"):
                config["categories"][folder] = {"pillar_url": updated_url, "keywords": updated_kws, "pexels_terms": updated_pex}
                save_full_config(config)
                st.success("Kategori bilgileri güncellendi!")
                st.rerun()
            
            st.markdown("---")
            how_many = st.number_input(f"İndirilecek Görsel Sayısı:", min_value=1, max_value=100, value=20, key=f"num_{folder}")
            if st.button(f"📥 Pexels'ten Otomatik İndir ({folder})", key=f"btn_{folder}"):
                success, msg = download_pexels_images(config["settings"].get("pexels_api_key", ""), updated_pex, folder_path, count=how_many)
                if success: st.success(msg); st.rerun()
                else: st.error(msg)

    st.markdown("---")
    st.subheader("🤖 Otomasyon Motoru Kontrolü")

    if st.button("🚀 BOTU BAŞLAT (TOPLU ÜRETİM YAP)", type="primary", use_container_width=True):
        st.write("### 🎬 Canlı İşlem Günlüğü & Üretilen Görseller")
        
        config = load_full_config()
        used_pins_data = load_used_pins()
        cfg = config.get("settings", {})
        
        # DEMO LIMIT CONTROL
        max_target = cfg.get("max_pins_per_cat", 50)
        if DEMO_MODE:
            max_target = min(max_target, DEMO_PIN_LIMIT)
            
        active_folders = sorted([d for d in os.listdir(BASE_BG_DIR) if os.path.isdir(os.path.join(BASE_BG_DIR, d))])
        
        output_dir = "outputs"
        if os.path.exists(output_dir): shutil.rmtree(output_dir)
        os.makedirs(output_dir)
        
        start_time = _dt.datetime.now() + _dt.timedelta(minutes=cfg.get("start_delay_min", 5)) - _dt.timedelta(hours=3)
        upload_folder = _dt.datetime.now().strftime("%Y/%m/")
        batch_id = _dt.datetime.now().strftime("%Y%m%d-%H%M")
        csv_rows = []
        global_pin_counter = 0
        
        for folder in active_folders:
            folder_path = os.path.join(BASE_BG_DIR, folder)
            cat_info = config["categories"].get(folder, {"pillar_url": f"{folder}/", "keywords": f"{folder} trends", "pexels_terms": folder})
            local_bgs = sorted([os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(("jpg", "jpeg", "png", "webp"))])
            
            if not local_bgs: continue
            kw_pool = [k.strip() for k in cat_info.get("keywords", "").split(",") if k.strip()]
            if not kw_pool: kw_pool = [folder.title()]
            
            for i in range(max_target):
                bg_path = local_bgs[i % len(local_bgs)]
                chosen_kws = random.sample(kw_pool, min(3, len(kw_pool)))
                main_kw = chosen_kws[0]
                chosen_title = generate_unique_title(main_kw, folder, used_pins_data)
                used_pins_data[folder].append(chosen_title)
                
                filename = f"{batch_id}-{folder}-{i}-{slugify(chosen_title)[:30]}.webp"
                out_path = os.path.join(output_dir, filename)
                image_url = f"{cfg.get('wp_upload_base')}{upload_folder}{filename}"
                ref = hashlib.md5(f"{chosen_title}{i}".encode()).hexdigest()[:8]
                dest_link = f"{cfg.get('site_url')}{cat_info.get('pillar_url')}?ref={ref}"
                
                pub_time = start_time + _dt.timedelta(minutes=global_pin_counter * cfg.get("interval_min", 10))
                pub_str = pub_time.strftime("%Y-%m-%dT%H:%M:%S")
                
                try:
                    create_pin_new(bg_path, out_path, chosen_title,
                                   cfg.get("panel_alpha_top", 120), cfg.get("panel_alpha_bot", 165), 
                                   COLOR_PALETTES[global_pin_counter % len(COLOR_PALETTES)], cfg.get("site_url", "yoursite.com"),
                                   cfg.get("selected_font", "Varsayılan Sistem"),
                                   cfg.get("badge_color", "#F26C3F"),
                                   cfg.get("btn_color", "#FBA167"))
                    
                    # LIVE SCREEN PREVIEW
                    st.text(f"✅ [{i+1}/{max_target}] -> {chosen_title}")
                    st.image(out_path, caption=f"Generated Pin: {chosen_title}", width=280)
                    
                    csv_rows.append([chosen_title, image_url, cfg.get("board_name"), "", f"Best {main_kw.lower()} tips and ideas.", dest_link, pub_str, ", ".join(chosen_kws)])
                    global_pin_counter += 1
                except Exception as e:
                    st.text(f"❌ Error [{i+1}]: {e}")
                    
        # DOWNLOAD BUTTONS AND CSV GENERATION
        if csv_rows:
            save_used_pins(used_pins_data)
            
            csv_path = os.path.join(output_dir, "pinterest_bulk_upload.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Title", "Media URL", "Pinterest board", "Thumbnail", "Description", "Link", "Publish date", "Keywords"])
                writer.writerows(csv_rows)
            
            st.success(f"🏆 Total {global_pin_counter} Pin images and CSV file successfully generated!")
            
            st.markdown("---")
            st.subheader("📥 Demo Çıktılarını İndirin")
            
            btn_col1, btn_col2 = st.columns(2)
            
            # 1. CSV Download Button
            with btn_col1:
                with open(csv_path, "rb") as csv_file:
                    st.download_button(
                        label="📄 Üretilen Pinterest CSV Dosyasını İndir",
                        data=csv_file,
                        file_name="pinterest_bulk_upload_demo.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            
            # 2. ZIP Download Button
            shutil.make_archive("demo_outputs", 'zip', output_dir)
            with btn_col2:
                with open("demo_outputs.zip", "rb") as zip_file:
                    st.download_button(
                        label="🖼️ Üretilen Görselleri İndir (.ZIP)",
                        data=zip_file,
                        file_name="demo_pin_gorselleri.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
